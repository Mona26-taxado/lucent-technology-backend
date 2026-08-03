from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PrintHistoryOut(BaseModel):
    id: int
    certificate_id: int
    certificate_number: Optional[str] = None
    candidate_name: Optional[str] = None
    printed_by: Optional[int] = None
    printed_by_name: Optional[str] = None
    printed_at: datetime
    print_count: Optional[int] = None

    class Config:
        from_attributes = True


class PrintHistoryListResponse(BaseModel):
    items: list[PrintHistoryOut]
    total: int
    page: int
    page_size: int
    pages: int


class DashboardSummary(BaseModel):
    total_certificates: int
    certificates_today: int
    total_printed: int
    pending_print: int


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
