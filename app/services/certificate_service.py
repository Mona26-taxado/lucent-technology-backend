from datetime import datetime, date
from math import ceil
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException, status

from app.models import Certificate, PrintHistory, User, CertificateTemplate
from app.schemas.certificate import CertificateCreate, CertificateUpdate
from app.services.numbering_service import (
    get_or_create_settings,
    allocate_next_number,
    validate_manual_number,
    peek_next_number,
)


def create_certificate(db: Session, data: CertificateCreate, user_id: int) -> Certificate:
    app_settings = get_or_create_settings(db)

    if data.certificate_number:
        validate_manual_number(db, data.certificate_number)
        cert_number = data.certificate_number
    elif app_settings.automatic_numbering:
        cert_number = allocate_next_number(db)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate number is required when automatic numbering is disabled",
        )

    existing = db.query(Certificate).filter(Certificate.certificate_number == cert_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate number '{cert_number}' already exists",
        )

    template_id = data.template_id or app_settings.default_template_id
    logo_path = data.logo_path or app_settings.default_logo_path
    signature_path = data.signature_path or app_settings.default_signature_path
    address = data.address or app_settings.default_address or ""

    cert = Certificate(
        certificate_number=cert_number,
        candidate_name=data.candidate_name.strip(),
        address=address.strip(),
        training_date=data.training_date,
        driving_licence_number=data.driving_licence_number,
        certificate_type=data.certificate_type,
        block_type=data.block_type,
        company_name=data.company_name,
        training_centre_name=data.training_centre_name,
        authorized_person_name=data.authorized_person_name,
        certificate_title=data.certificate_title,
        certificate_description=data.certificate_description,
        logo_path=logo_path,
        signature_path=signature_path,
        template_id=template_id,
        print_status="pending",
        print_count=0,
        created_by=user_id,
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


def update_certificate(db: Session, cert_id: int, data: CertificateUpdate) -> Certificate:
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")

    update_data = data.model_dump(exclude_unset=True)

    if "certificate_number" in update_data and update_data["certificate_number"]:
        new_num = update_data["certificate_number"]
        if new_num != cert.certificate_number:
            app_settings = get_or_create_settings(db)
            if app_settings.automatic_numbering:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change certificate number while automatic numbering is enabled",
                )
            existing = (
                db.query(Certificate)
                .filter(Certificate.certificate_number == new_num, Certificate.id != cert_id)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Certificate number '{new_num}' already exists",
                )

    for key, value in update_data.items():
        setattr(cert, key, value)

    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


def get_certificate(db: Session, cert_id: int) -> Certificate:
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return cert


def delete_certificate(db: Session, cert_id: int) -> None:
    cert = get_certificate(db, cert_id)
    db.delete(cert)
    db.commit()


def list_certificates(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    candidate_name: Optional[str] = None,
    certificate_number: Optional[str] = None,
    address: Optional[str] = None,
    training_date: Optional[date] = None,
    driving_licence_number: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    print_status: Optional[str] = None,
) -> dict:
    query = db.query(Certificate)

    if candidate_name:
        query = query.filter(Certificate.candidate_name.ilike(f"%{candidate_name}%"))
    if certificate_number:
        query = query.filter(Certificate.certificate_number.ilike(f"%{certificate_number}%"))
    if address:
        query = query.filter(Certificate.address.ilike(f"%{address}%"))
    if training_date:
        query = query.filter(Certificate.training_date == training_date)
    if driving_licence_number:
        query = query.filter(Certificate.driving_licence_number.ilike(f"%{driving_licence_number}%"))
    if date_from:
        query = query.filter(Certificate.training_date >= date_from)
    if date_to:
        query = query.filter(Certificate.training_date <= date_to)
    if print_status:
        if print_status == "printed":
            query = query.filter(Certificate.print_status == "printed")
        elif print_status == "pending":
            query = query.filter(Certificate.print_status == "pending")

    total = query.count()
    pages = ceil(total / page_size) if page_size else 1
    items = (
        query.order_by(Certificate.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


def mark_printed(db: Session, cert_id: int, user_id: int) -> Certificate:
    cert = get_certificate(db, cert_id)
    cert.print_status = "printed"
    cert.print_count = (cert.print_count or 0) + 1
    history = PrintHistory(certificate_id=cert.id, printed_by=user_id)
    db.add(history)
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


def get_dashboard_summary(db: Session) -> dict:
    today = date.today()
    total = db.query(func.count(Certificate.id)).scalar() or 0
    today_count = (
        db.query(func.count(Certificate.id))
        .filter(func.date(Certificate.created_at) == today)
        .scalar()
        or 0
    )
    printed = (
        db.query(func.count(Certificate.id)).filter(Certificate.print_status == "printed").scalar() or 0
    )
    pending = (
        db.query(func.count(Certificate.id)).filter(Certificate.print_status == "pending").scalar() or 0
    )
    return {
        "total_certificates": total,
        "certificates_today": today_count,
        "total_printed": printed,
        "pending_print": pending,
    }


def get_recent_certificates(db: Session, limit: int = 3) -> list[Certificate]:
    return db.query(Certificate).order_by(Certificate.created_at.desc()).limit(limit).all()
