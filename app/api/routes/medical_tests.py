from math import ceil
import io
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
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
)
from app.services.medical_pdf_service import generate_medical_pdf, generate_medical_pdfs_batch

router = APIRouter(prefix="/medical-tests", tags=["Medical Tests"])


def _safe_zip_name(row: MedicalTest) -> str:
    patient = "".join(c if c.isalnum() or c in "-_ " else "_" for c in (row.patient_name or "patient"))
    patient = "_".join(patient.split())[:40] or "patient"
    date_part = (row.exam_date or "nodate").replace("/", "-")
    return f"medical-{row.id}-{date_part}-{patient}.pdf"


@router.get("", response_model=MedicalTestListResponse)
def list_medical_tests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MedicalTest)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            (MedicalTest.patient_name.ilike(like))
            | (MedicalTest.mobile_number.ilike(like))
            | (MedicalTest.company_name.ilike(like))
            | (MedicalTest.training_location.ilike(like))
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


@router.get("/bulk-download")
async def bulk_download_medical_tests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a ZIP of all medical test report PDFs."""
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

    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for row in rows:
            path = path_by_id.get(row.id)
            if not path or not path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"PDF missing for medical test #{row.id}",
                )
            arcname = _safe_zip_name(row)
            if arcname in used_names:
                stem = arcname[:-4] if arcname.lower().endswith(".pdf") else arcname
                arcname = f"{stem}-dup.pdf"
            used_names.add(arcname)
            zf.write(str(path), arcname)

    stamp = date.today().isoformat()
    filename = f"medical-reports-{stamp}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    row = MedicalTest(**data.model_dump(), created_by=current_user.id)
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
