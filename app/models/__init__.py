from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String,
    Boolean,
    Integer,
    DateTime,
    Date,
    Text,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    certificates = relationship("Certificate", back_populates="creator")
    print_histories = relationship("PrintHistory", back_populates="printer")


class CertificateTemplate(Base):
    __tablename__ = "certificate_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    background_image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    field_positions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    certificates = relationship("Certificate", back_populates="template")


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    certificate_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    candidate_name: Mapped[str] = mapped_column(String(300), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    training_date: Mapped[date] = mapped_column(Date, nullable=False)
    driving_licence_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    certificate_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    block_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    training_centre_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    authorized_person_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    certificate_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    certificate_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    signature_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("certificate_templates.id"), nullable=True)
    print_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    print_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template = relationship("CertificateTemplate", back_populates="certificates")
    creator = relationship("User", back_populates="certificates")
    print_histories = relationship(
        "PrintHistory", back_populates="certificate", cascade="all, delete-orphan"
    )


class PrintHistory(Base):
    __tablename__ = "print_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("certificates.id"), nullable=False)
    printed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    printed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    certificate = relationship("Certificate", back_populates="print_histories")
    printer = relationship("User", back_populates="print_histories")


class MedicalTest(Base):
    """Globe Hospital medical examination form records."""

    __tablename__ = "medical_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vehicle_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    training_location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    patient_name: Mapped[str] = mapped_column(String(300), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mobile_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    height: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    weight: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    chest: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    blood_pressure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pulse: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    blood_sugar: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    lab_investigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_impression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    certified_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    examiner_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    examiner_qualification: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    examiner_place: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Legacy fields (kept for older rows / optional use)
    sugar: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pulse_rate: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    heart_beat: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    body_temperature: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ecg_findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ecg_result: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    xray_findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    xray_result: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    examined: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    overall_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_right: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vision_left: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    retina_test: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lens_condition: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    eye_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApplicationSettings(Base):
    __tablename__ = "application_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_name: Mapped[str] = mapped_column(
        String(300), default="Lucent Technology", nullable=False
    )
    certificate_prefix: Mapped[str] = mapped_column(String(50), default="LT", nullable=False)
    automatic_numbering: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_year: Mapped[int] = mapped_column(Integer, default=2026, nullable=False)
    current_serial_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    number_padding: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    default_logo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_signature_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("certificate_templates.id"), nullable=True
    )
    date_format: Mapped[str] = mapped_column(String(50), default="%d.%m.%Y", nullable=False)
    default_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_storage_directory: Mapped[str] = mapped_column(
        String(500), default="generated/certificates", nullable=False
    )
    paper_size: Mapped[str] = mapped_column(String(20), default="9.5x13", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


__all__ = [
    "User",
    "Certificate",
    "CertificateTemplate",
    "PrintHistory",
    "MedicalTest",
    "ApplicationSettings",
]
