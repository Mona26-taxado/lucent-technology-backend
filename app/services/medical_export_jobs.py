"""Background ZIP export jobs for medical test bulk download (no Redis/Celery).

Jobs are filesystem-backed under generated/medical_exports/{job_id}/ so status and
ZIP survive briefly, and downloads require authenticated API access (no public URLs).
"""

from __future__ import annotations

import asyncio
import io
import json
import secrets
import shutil
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.core.config import BASE_DIR, get_settings
from app.core.database import SessionLocal
from app.models import MedicalTest
from app.services.medical_pdf_service import generate_medical_pdfs_batch

settings = get_settings()

EXPORT_ROOT = BASE_DIR / "generated" / "medical_exports"
JOB_TTL_SECONDS = 60 * 60  # 1 hour
MAX_IDS = 500

_lock = threading.Lock()
_jobs: dict[str, "ExportJob"] = {}


def _safe_token(value: str | None, *, fallback: str, max_len: int = 40) -> str:
    raw = "".join(c if c.isalnum() or c in "-_" else "_" for c in (value or ""))
    cleaned = "_".join(part for part in raw.split("_") if part).strip("_")
    return (cleaned[:max_len] or fallback)


def selected_zip_entry_name(row: MedicalTest, serial: int) -> str:
    patient = _safe_token(row.patient_name, fallback="patient", max_len=30).upper()
    vehicle = _safe_token(row.vehicle_number, fallback="", max_len=24).upper()
    seq = f"{serial:03d}"
    if vehicle:
        return f"{seq}-{patient}-{vehicle}.pdf"
    return f"{seq}-{patient}-medical-test.pdf"


@dataclass
class ExportJob:
    job_id: str
    user_id: int
    ids: list[int]
    export_all: bool = False
    status: str = "queued"  # queued|processing|completed|failed
    processed: int = 0
    total: int = 0
    error: str | None = None
    zip_name: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    @property
    def dir(self) -> Path:
        return EXPORT_ROOT / self.job_id

    @property
    def zip_path(self) -> Path:
        return self.dir / (self.zip_name or "export.zip")

    @property
    def meta_path(self) -> Path:
        return self.dir / "status.json"

    def to_public(self) -> dict:
        payload = {
            "job_id": self.job_id,
            "status": self.status,
            "processed": self.processed,
            "total": self.total,
            "error": self.error,
        }
        if self.status == "completed":
            payload["download_url"] = f"/api/medical-tests/bulk-download/jobs/{self.job_id}/file"
        return payload

    def persist(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(
            json.dumps(
                {
                    "job_id": self.job_id,
                    "user_id": self.user_id,
                    "ids": self.ids,
                    "export_all": self.export_all,
                    "status": self.status,
                    "processed": self.processed,
                    "total": self.total,
                    "error": self.error,
                    "zip_name": self.zip_name,
                    "created_at": self.created_at,
                    "completed_at": self.completed_at,
                }
            ),
            encoding="utf-8",
        )


def _load_job_from_disk(job_id: str) -> ExportJob | None:
    meta = EXPORT_ROOT / job_id / "status.json"
    if not meta.exists():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return ExportJob(
        job_id=data["job_id"],
        user_id=int(data["user_id"]),
        ids=list(data.get("ids") or []),
        export_all=bool(data.get("export_all")),
        status=data.get("status") or "failed",
        processed=int(data.get("processed") or 0),
        total=int(data.get("total") or 0),
        error=data.get("error"),
        zip_name=data.get("zip_name") or "",
        created_at=float(data.get("created_at") or time.time()),
        completed_at=data.get("completed_at"),
    )


def get_job(job_id: str) -> ExportJob | None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            return job
    job = _load_job_from_disk(job_id)
    if job:
        with _lock:
            _jobs[job_id] = job
    return job


def cleanup_expired_jobs() -> None:
    now = time.time()
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    expired_ids: list[str] = []
    with _lock:
        for job_id, job in list(_jobs.items()):
            if now - job.created_at > JOB_TTL_SECONDS:
                expired_ids.append(job_id)
                _jobs.pop(job_id, None)
    for path in EXPORT_ROOT.iterdir() if EXPORT_ROOT.exists() else []:
        if not path.is_dir():
            continue
        job_id = path.name
        meta = path / "status.json"
        created = path.stat().st_mtime
        if meta.exists():
            try:
                created = float(json.loads(meta.read_text(encoding="utf-8")).get("created_at") or created)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        if now - created > JOB_TTL_SECONDS or job_id in expired_ids:
            shutil.rmtree(path, ignore_errors=True)


def create_export_job(
    *,
    user_id: int,
    ids: list[int] | None = None,
    export_all: bool = False,
) -> ExportJob:
    """Create a job. export_all=True means all medical tests (Download All)."""
    cleanup_expired_jobs()
    job_id = secrets.token_urlsafe(18)
    stamp = date.today().isoformat()
    job = ExportJob(
        job_id=job_id,
        user_id=user_id,
        ids=[],
        export_all=export_all,
        status="queued",
        zip_name=f"medical-test-reports-{stamp}.zip",
    )

    db = SessionLocal()
    try:
        if export_all:
            job.total = min(db.query(MedicalTest).count(), MAX_IDS)
            job.ids = []
        else:
            unique: list[int] = []
            seen: set[int] = set()
            for raw in ids or []:
                n = int(raw)
                if n > 0 and n not in seen:
                    seen.add(n)
                    unique.append(n)
            job.ids = unique[:MAX_IDS]
            if not job.ids:
                job.total = 0
            else:
                found = {
                    r.id
                    for r in db.query(MedicalTest.id).filter(MedicalTest.id.in_(job.ids)).all()
                }
                job.ids = [i for i in job.ids if i in found]
                job.total = len(job.ids)
    finally:
        db.close()

    if job.total <= 0:
        job.status = "failed"
        job.error = "No medical test reports found for this export"
        job.persist()
        with _lock:
            _jobs[job.job_id] = job
        return job

    job.persist()
    with _lock:
        _jobs[job.job_id] = job

    # Always run off the request event loop so Nginx/HTTP can return immediately
    # and TestClient/uvicorn never starve the Playwright coroutine.
    threading.Thread(
        target=lambda: asyncio.run(_run_job(job.job_id)),
        daemon=True,
        name=f"medical-export-{job.job_id[:10]}",
    ).start()
    return job


async def _run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    job.status = "processing"
    job.processed = 0
    job.persist()

    pdf_paths: dict[int, Path] = {}
    try:
        db = SessionLocal()
        try:
            if job.export_all:
                rows = (
                    db.query(MedicalTest)
                    .order_by(MedicalTest.created_at.desc())
                    .limit(MAX_IDS)
                    .all()
                )
            else:
                by_id = {
                    row.id: row
                    for row in db.query(MedicalTest).filter(MedicalTest.id.in_(job.ids)).all()
                }
                rows = [by_id[i] for i in job.ids if i in by_id]
            job.total = len(rows)
            job.persist()
            if not rows:
                raise RuntimeError("No medical test reports found for this export")

            def on_progress(done: int, total: int) -> None:
                j = get_job(job_id)
                if not j:
                    return
                j.processed = done
                j.total = total
                j.persist()

            for row in rows:
                db.expunge(row)
        finally:
            db.close()

        pdf_dir = job.dir / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_paths = await generate_medical_pdfs_batch(
            rows,
            out_dir=pdf_dir,
            on_progress=on_progress,
        )

        buffer = io.BytesIO()
        used: set[str] = set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
            for index, row in enumerate(rows, start=1):
                path = pdf_paths.get(row.id)
                if not path or not path.exists():
                    raise RuntimeError(f"PDF missing for medical test #{row.id}")
                name = selected_zip_entry_name(row, index)
                if name in used:
                    stem = name[:-4] if name.lower().endswith(".pdf") else name
                    name = f"{stem}-dup.pdf"
                used.add(name)
                zf.write(str(path), name)

        job.zip_path.write_bytes(buffer.getvalue())
        job.status = "completed"
        job.processed = job.total
        job.completed_at = time.time()
        job.persist()
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = time.time()
        job.persist()
    finally:
        # Always remove per-report PDFs; keep ZIP only while job is completed/unexpired
        pdf_dir = job.dir / "pdfs"
        if pdf_dir.exists():
            shutil.rmtree(pdf_dir, ignore_errors=True)
        if job.status == "failed":
            # Keep status.json for a bit so clients can read the error, drop large artifacts
            for child in list(job.dir.iterdir()) if job.dir.exists() else []:
                if child.name == "status.json":
                    continue
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)


def mark_job_downloaded(job_id: str) -> None:
    """Eager cleanup after successful authenticated download."""
    job = get_job(job_id)
    if not job:
        return
    shutil.rmtree(job.dir, ignore_errors=True)
    with _lock:
        _jobs.pop(job_id, None)


def mark_job_downloaded_soon(job_id: str, delay_seconds: float = 15.0) -> None:
    """Allow FileResponse to finish streaming before deleting the ZIP."""
    time.sleep(delay_seconds)
    mark_job_downloaded(job_id)
