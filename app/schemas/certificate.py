from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime, date


class CertificateCreate(BaseModel):
    certificate_number: Optional[str] = None
    candidate_name: str = Field(min_length=1, max_length=300)
    address: str = Field(min_length=1, max_length=500)
    training_date: date
    driving_licence_number: Optional[str] = None
    certificate_type: Optional[str] = None
    block_type: Optional[str] = None
    company_name: Optional[str] = None
    training_centre_name: Optional[str] = None
    authorized_person_name: Optional[str] = None
    certificate_title: Optional[str] = None
    certificate_description: Optional[str] = None
    template_id: Optional[int] = None
    logo_path: Optional[str] = None
    signature_path: Optional[str] = None


class CertificateUpdate(BaseModel):
    certificate_number: Optional[str] = None
    candidate_name: Optional[str] = None
    address: Optional[str] = None
    training_date: Optional[date] = None
    driving_licence_number: Optional[str] = None
    certificate_type: Optional[str] = None
    block_type: Optional[str] = None
    company_name: Optional[str] = None
    training_centre_name: Optional[str] = None
    authorized_person_name: Optional[str] = None
    certificate_title: Optional[str] = None
    certificate_description: Optional[str] = None
    template_id: Optional[int] = None
    logo_path: Optional[str] = None
    signature_path: Optional[str] = None


class CertificateOut(BaseModel):
    id: int
    certificate_number: str
    candidate_name: str
    address: str
    training_date: date
    driving_licence_number: Optional[str] = None
    certificate_type: Optional[str] = None
    block_type: Optional[str] = None
    company_name: Optional[str] = None
    training_centre_name: Optional[str] = None
    authorized_person_name: Optional[str] = None
    certificate_title: Optional[str] = None
    certificate_description: Optional[str] = None
    logo_path: Optional[str] = None
    signature_path: Optional[str] = None
    pdf_path: Optional[str] = None
    template_id: Optional[int] = None
    print_status: str
    print_count: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CertificateListResponse(BaseModel):
    items: list[CertificateOut]
    total: int
    page: int
    page_size: int
    pages: int


class NextNumberResponse(BaseModel):
    certificate_number: str
    automatic_numbering: bool


class CertificateSearchParams(BaseModel):
    candidate_name: Optional[str] = None
    certificate_number: Optional[str] = None
    address: Optional[str] = None
    training_date: Optional[date] = None
    driving_licence_number: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    print_status: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
