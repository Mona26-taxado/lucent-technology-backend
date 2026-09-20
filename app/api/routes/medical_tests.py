from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
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
from app.services.medical_pdf_service import generate_medical_pdf

router = APIRouter(prefix="/medical-tests", tags=["Medical Tests"])


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
