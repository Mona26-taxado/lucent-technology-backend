from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import ApplicationSettings, Certificate


def get_or_create_settings(db: Session) -> ApplicationSettings:
    settings = db.query(ApplicationSettings).first()
    if not settings:
        settings = ApplicationSettings(
            organization_name="Lucent Technology",
            certificate_prefix="LT",
            automatic_numbering=True,
            current_year=datetime.now().year,
            current_serial_number=4000,
            number_padding=7,
            date_format="%d.%m.%Y",
            pdf_storage_directory="generated/certificates",
            paper_size="9.5x13",
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    # Ensure paper_size column/value exists for older DBs
    if not getattr(settings, "paper_size", None):
        try:
            settings.paper_size = "9.5x13"
            db.add(settings)
            db.commit()
            db.refresh(settings)
        except Exception:
            pass
    return settings


def format_certificate_number(prefix: str, serial: int, padding: int) -> str:
    """Format: LT/0004000"""
    return f"{prefix}/{str(serial).zfill(padding)}"


def peek_next_number(db: Session) -> str:
    """Return the next number without incrementing."""
    app_settings = get_or_create_settings(db)
    return format_certificate_number(
        app_settings.certificate_prefix,
        app_settings.current_serial_number,
        app_settings.number_padding,
    )


def allocate_next_number(db: Session) -> str:
    """Allocate and increment the next certificate number."""
    app_settings = get_or_create_settings(db)

    number = format_certificate_number(
        app_settings.certificate_prefix,
        app_settings.current_serial_number,
        app_settings.number_padding,
    )

    # Ensure uniqueness — skip any numbers already used
    while db.query(Certificate).filter(Certificate.certificate_number == number).first():
        app_settings.current_serial_number += 1
        number = format_certificate_number(
            app_settings.certificate_prefix,
            app_settings.current_serial_number,
            app_settings.number_padding,
        )

    app_settings.current_serial_number += 1
    db.add(app_settings)
    db.flush()
    return number


def validate_manual_number(db: Session, certificate_number: str, exclude_id: int | None = None) -> None:
    app_settings = get_or_create_settings(db)
    if app_settings.automatic_numbering:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual certificate numbering is disabled. Enable it in Settings to enter a custom number.",
        )
    query = db.query(Certificate).filter(Certificate.certificate_number == certificate_number)
    if exclude_id:
        query = query.filter(Certificate.id != exclude_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Certificate number '{certificate_number}' already exists",
        )
