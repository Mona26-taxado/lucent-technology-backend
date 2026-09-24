from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MedicalTestBase(BaseModel):
    exam_date: Optional[str] = None
    vehicle_number: Optional[str] = None
    company_name: Optional[str] = None
    training_location: Optional[str] = None

    patient_name: str = Field(min_length=1, max_length=300)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[str] = None
    mobile_number: Optional[str] = None

    height: Optional[str] = None
    weight: Optional[str] = None
    chest: Optional[str] = None
    blood_pressure: Optional[str] = None
    pulse: Optional[str] = None
    blood_sugar: Optional[str] = None

    lab_investigation: Optional[str] = None
    final_impression: Optional[str] = None
    certified_name: Optional[str] = None

    examiner_name: Optional[str] = None
    examiner_qualification: Optional[str] = None
    examiner_place: Optional[str] = None


class MedicalTestCreate(MedicalTestBase):
    pass


class MedicalTestUpdate(BaseModel):
    exam_date: Optional[str] = None
    vehicle_number: Optional[str] = None
    company_name: Optional[str] = None
    training_location: Optional[str] = None
    patient_name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[str] = None
    mobile_number: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    chest: Optional[str] = None
    blood_pressure: Optional[str] = None
    pulse: Optional[str] = None
    blood_sugar: Optional[str] = None
    lab_investigation: Optional[str] = None
    final_impression: Optional[str] = None
    certified_name: Optional[str] = None
    examiner_name: Optional[str] = None
    examiner_qualification: Optional[str] = None
    examiner_place: Optional[str] = None


class MedicalTestOut(MedicalTestBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MedicalTestListResponse(BaseModel):
    items: list[MedicalTestOut]
    total: int
    page: int
    page_size: int
    pages: int


class MedicalTestBulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class MedicalTestBulkDownloadRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class MedicalTestBulkDownloadJobRequest(BaseModel):
    """Create a background ZIP export job.

    - export_all=True → Download All Reports (ids ignored)
    - otherwise ids must be the selected report IDs
    """

    ids: list[int] | None = None
    export_all: bool = False


class MedicalTestBulkDownloadJobOut(BaseModel):
    job_id: str
    status: str
    processed: int
    total: int
    error: str | None = None
    download_url: str | None = None
