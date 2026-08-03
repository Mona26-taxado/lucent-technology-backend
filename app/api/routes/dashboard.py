from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, PrintHistory, Certificate
from app.schemas.dashboard import DashboardSummary, PrintHistoryListResponse, PrintHistoryOut
from app.schemas.certificate import CertificateOut
from app.services.certificate_service import get_dashboard_summary, get_recent_certificates

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return DashboardSummary(**get_dashboard_summary(db))


@router.get("/recent-certificates", response_model=list[CertificateOut])
def recent_certificates(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_recent_certificates(db, limit)
