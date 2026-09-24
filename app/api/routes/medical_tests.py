from math import ceil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
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
    MedicalTestBulkDownloadJobRequest,
    MedicalTestBulkDownloadJobOut,
)
from app.services.medical_export_jobs import (
    create_export_job,
    get_job,
    mark_job_downloaded_soon,
)
from app.services.medical_pdf_service import generate_medical_pdf

router = APIRouter(prefix="/medical-tests", tags=["Medical Tests"])


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


@router.post(
    "/bulk-download/jobs",
    response_model=MedicalTestBulkDownloadJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_bulk_download_job(
    data: MedicalTestBulkDownloadJobRequest,
    current_user: User = Depends(get_current_user),
):
    """Start a background ZIP export. Poll GET .../jobs/{id} then download the file."""
    if data.export_all:
        job = create_export_job(user_id=current_user.id, export_all=True)
    else:
        ids = [int(i) for i in (data.ids or []) if int(i) > 0]
        if not ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid medical test IDs provided",
            )
        if len(ids) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many reports selected (max 500)",
            )
        job = create_export_job(user_id=current_user.id, ids=ids, export_all=False)

    if job.status == "failed" and job.total <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=job.error or "No medical test reports found for this export",
        )
    return MedicalTestBulkDownloadJobOut(**job.to_public())


@router.get("/bulk-download/jobs/{job_id}", response_model=MedicalTestBulkDownloadJobOut)
def get_bulk_download_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    job = get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    return MedicalTestBulkDownloadJobOut(**job.to_public())


@router.get("/bulk-download/jobs/{job_id}/file")
def download_bulk_download_job_file(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    job = get_job(job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Export job is not ready (status={job.status})",
        )
    if not job.zip_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file expired or missing",
        )
    # Remove ZIP shortly after the response finishes streaming
    background_tasks.add_task(mark_job_downloaded_soon, job_id)
    return FileResponse(
        path=str(job.zip_path),
        media_type="application/zip",
        filename=job.zip_name or "medical-test-reports.zip",
    )


@router.post("/bulk-delete", response_model=MessageResponse)
def bulk_delete_medical_tests(
    data: MedicalTestBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete the given medical test IDs from the database."""
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
    """Permanently delete this medical test row from the database."""
    row = db.query(MedicalTest).filter(MedicalTest.id == test_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical test not found")
    db.delete(row)
    db.commit()
    return MessageResponse(message="Medical test deleted")
