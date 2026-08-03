from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, PrintHistory
from app.schemas.dashboard import PrintHistoryListResponse, PrintHistoryOut

router = APIRouter(prefix="/print-history", tags=["Print History"])


@router.get("", response_model=PrintHistoryListResponse)
def list_print_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PrintHistory).options(
        joinedload(PrintHistory.certificate),
        joinedload(PrintHistory.printer),
    )
    total = db.query(PrintHistory).count()
    pages = ceil(total / page_size) if page_size else 1
    rows = (
        query.order_by(PrintHistory.printed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        items.append(
            PrintHistoryOut(
                id=row.id,
                certificate_id=row.certificate_id,
                certificate_number=row.certificate.certificate_number if row.certificate else None,
                candidate_name=row.certificate.candidate_name if row.certificate else None,
                printed_by=row.printed_by,
                printed_by_name=row.printer.full_name if row.printer else None,
                printed_at=row.printed_at,
                print_count=row.certificate.print_count if row.certificate else None,
            )
        )

    return PrintHistoryListResponse(
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )
