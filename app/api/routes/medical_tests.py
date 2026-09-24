from math import ceil
import io
import zipfile
from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User, MedicalTest
from app.schemas.dashboard import MessageResponse
from app.schemas.medical_test import (
    MedicalTestCreate,
    MedicalTestUpdate,
    MedicalTestOut,
    MedicalTestListResponse,
    MedicalTestBulkDeleteRequest,
    MedicalTestBulkDownloadRequest,
)
from app.services.medical_pdf_service import generate_medical_pdf, generate_medical_pdfs_batch

router = APIRouter(prefix="/medical-tests", tags=["Medical Tests"])


def _safe_token(value: str | None, *, fallback: str, max_len: int = 40) -> str:
    raw = "".join(c if c.isalnum() or c in "-_" else "_" for c in (value or ""))
    cleaned = "_".join(part for part in raw.split("_") if part).strip("_")
    return (cleaned[:max_len] or fallback)


def _safe_zip_name(row: MedicalTest) -> str:
    """Legacy name used by Download All Reports ZIP."""
    patient = _safe_token(row.patient_name, fallback="patient")
    date_part = (row.exam_date or "nodate").replace("/", "-")
    return f"medical-{row.id}-{date_part}-{patient}.pdf"


def _selected_zip_name(row: MedicalTest, serial: int) -> str:
    """ZIP entry for Download Selected: 001-PATIENT-VEHICLE.pdf"""
    patient = _safe_token(row.patient_name, fallback="patient", max_len=30).upper()
    vehicle = _safe_token(row.vehicle_number, fallback="", max_len=24).upper()
    seq = f"{serial:03d}"
    if vehicle:
        return f"{seq}-{patient}-{vehicle}.pdf"
    return f"{seq}-{patient}-medical-test.pdf"


@router.get("", response_model=MedicalTestListResponse)
def list_medical_tests(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MedicalTest)
    if q and q.strip():
        like = f"%{q.strip()}%"
        compact = f"%{''.join(q.strip().split())}%"
        query = query.filter(
            or_(
                MedicalTest.patient_name.ilike(like),
                MedicalTest.mobile_number.ilike(like),
                MedicalTest.company_name.ilike(like),
                MedicalTest.training_location.ilike(like),
                MedicalTest.vehicle_number.ilike(like),
                func.replace(MedicalTest.vehicle_number, " ", "").ilike(compact),
            )
        )
    total = query.count()
    pages = ceil(total / page_size) if page_size else 1
    items = (
        query.order_by(MedicalTest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return MedicalTestListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def _zip_medical_rows(
    rows: list[MedicalTest],
    path_by_id: dict[int, Path],
    *,
    name_fn: Callable[[MedicalTest, int], str],
) -> bytes:
    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for index, row in enumerate(rows, start=1):
            path = path_by_id.get(row.id)
            if not path or not path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"PDF missing for medical test #{row.id}",
                )
            arcname = name_fn(row, index)
            if arcname in used_names:
                stem = arcname[:-4] if arcname.lower().endswith(".pdf") else arcname
                arcname = f"{stem}-dup.pdf"
            used_names.add(arcname)
            zf.write(str(path), arcname)
    return buffer.getvalue()


@router.get("/bulk-download")
async def bulk_download_medical_tests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a ZIP of all medical test report PDFs (Download All Reports)."""
    rows = db.query(MedicalTest).order_by(MedicalTest.created_at.desc()).limit(500).all()
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No medical test reports found",
        )

    try:
        path_by_id = await generate_medical_pdfs_batch(rows)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk PDF generation failed: {exc}",
        ) from exc

    zip_bytes = _zip_medical_rows(
        rows,
        path_by_id,
        name_fn=lambda row, _i: _safe_zip_name(row),
    )
    stamp = date.today().isoformat()
    filename = f"medical-reports-{stamp}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/bulk-download")
async def bulk_download_selected_medical_tests(
    data: MedicalTestBulkDownloadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a ZIP of PDFs for the selected medical test IDs only."""
    ids: list[int] = []
    seen: set[int] = set()
    for raw in data.ids:
        n = int(raw)
        if n > 0 and n not in seen:
            seen.add(n)
            ids.append(n)
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid medical test IDs provided",
        )
    if len(ids) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many reports selected (max 200)",
        )

    found = db.query(MedicalTest).filter(MedicalTest.id.in_(ids)).all()
    by_id = {row.id: row for row in found}
    # Preserve request order for stable ZIP serials; skip missing/deleted IDs safely
    rows = [by_id[i] for i in ids if i in by_id]
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching medical test reports found for the selected IDs",
        )

    path_by_id: dict[int, Path] = {}
    try:
        path_by_id = await generate_medical_pdfs_batch(rows)
        zip_bytes = _zip_medical_rows(rows, path_by_id, name_fn=_selected_zip_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk PDF generation failed: {exc}",
        ) from exc
    finally:
        # ZIP is in-memory; remove PDFs generated for this selected batch
        for path in path_by_id.values():
            try:
                if path.exists() and path.is_file():
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    stamp = date.today().isoformat()
    filename = f"medical-test-reports-{stamp}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/bulk-delete", response_model=MessageResponse)
def bulk_delete_medical_tests(
    data: MedicalTestBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete the given medical test IDs. Unknown IDs are skipped."""
    ids = sorted({int(i) for i in data.ids if int(i) > 0})
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid medical test IDs provided",
        )

    rows = db.query(MedicalTest).filter(MedicalTest.id.in_(ids)).all()
    deleted = 0
    try:
        for row in rows:
            db.delete(row)
            deleted += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk delete failed: {exc}",
        ) from exc

    return MessageResponse(
        message=f"{deleted} medical test report{'s' if deleted != 1 else ''} deleted successfully."
    )


@router.get("/{test_id}/pdf")
async def download_medical_pdf(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(MedicalTest).filter(MedicalTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical test not found")
    try:
        path = await generate_medical_pdf(row)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {exc}",
        ) from exc
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
    )


@router.get("/{test_id}", response_model=MedicalTestOut)
def get_medical_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(MedicalTest).filter(MedicalTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical test not found")
    return row


@router.post("", response_model=MedicalTestOut, status_code=status.HTTP_201_CREATED)
def create_medical_test(
    data: MedicalTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = data.model_dump()
    if payload.get("vehicle_number") is not None:
        vn = str(payload["vehicle_number"]).strip()
        payload["vehicle_number"] = vn or None
    row = MedicalTest(**payload, created_by=current_user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{test_id}", response_model=MedicalTestOut)
def update_medical_test(
    test_id: int,
    data: MedicalTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(MedicalTest).filter(MedicalTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical test not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "vehicle_number" and value is not None:
            value = str(value).strip() or None
        setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{test_id}", response_model=MessageResponse)
def delete_medical_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(MedicalTest).filter(MedicalTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical test not found")
    db.delete(row)
    db.commit()
    return MessageResponse(message="Medical test deleted")
