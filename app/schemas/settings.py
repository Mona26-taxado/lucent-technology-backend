from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SettingsUpdate(BaseModel):
    organization_name: Optional[str] = None
    certificate_prefix: Optional[str] = None
    automatic_numbering: Optional[bool] = None
    current_year: Optional[int] = None
    current_serial_number: Optional[int] = None
    number_padding: Optional[int] = Field(default=None, ge=1, le=10)
    default_logo_path: Optional[str] = None
    default_signature_path: Optional[str] = None
    default_template_id: Optional[int] = None
    date_format: Optional[str] = None
    default_address: Optional[str] = None
    pdf_storage_directory: Optional[str] = None
    paper_size: Optional[str] = None


class SettingsOut(BaseModel):
    id: int
    organization_name: str
    certificate_prefix: str
    automatic_numbering: bool
    current_year: int
    current_serial_number: int
    number_padding: int
    default_logo_path: Optional[str] = None
    default_signature_path: Optional[str] = None
    default_template_id: Optional[int] = None
    date_format: str
    default_address: Optional[str] = None
    pdf_storage_directory: str
    paper_size: str = "a4"
    updated_at: datetime

    class Config:
        from_attributes = True
