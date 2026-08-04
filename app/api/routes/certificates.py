from datetime import date
from typing import Optional
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.certificate import (
    CertificateCreate,
    CertificateUpdate,
    CertificateOut,
    CertificateListResponse,
    NextNumberResponse,
    BulkDeleteRequest,
)
from app.schemas.dashboard import MessageResponse
from app.services import certificate_service
from app.services.numbering_service import peek_next_number, get_or_create_settings
from app.services.file_service import save_upload, resolve_file_path, safe_pdf_filename
from app.services.pdf_service import generate_pdf, generate_missing_pdfs_batch

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get("/next-number", response_model=NextNumberResponse)
def get_next_number(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app_settings = get_or_create_settings(db)
    return NextNumberResponse(
        certificate_number=peek_next_number(db),
        automatic_numbering=app_settings.automatic_numbering,
    )


@router.get("/search", response_model=CertificateListResponse)
def search_certificates(
    candidate_name: Optional[str] = None,
    certificate_number: Optional[str] = None,
    address: Optional[str] = None,
    training_date: Optional[date] = None,
    driving_licence_number: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    print_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = certificate_service.list_certificates(
        db,
        page=page,
        page_size=page_size,
        candidate_name=candidate_name,
        certificate_number=certificate_number,
        address=address,
        training_date=training_date,
        driving_licence_number=driving_licence_number,
        date_from=date_from,
        date_to=date_to,
        print_status=print_status,
    )
    return CertificateListResponse(**result)


@router.get("/bulk-download")
async def bulk_download_certificates(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    training_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a ZIP of certificate PDFs filtered by training date.

    Existing PDFs are reused; missing ones are generated with one shared browser.
    """
    if not training_date and not date_from and not date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a training date, or a date from / date to range",
        )

    certs = certificate_service.list_certificates_by_date(
        db,
        date_from=date_from,
        date_to=date_to,
        training_date=training_date,
        limit=500,
    )
    if not certs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No certificates found for the selected date filter",
        )

    try:
        path_by_id = await generate_missing_pdfs_batch(db, certs)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk PDF generation failed: {e}",
        ) from e

    # PDFs are already compressed — STORE is much faster than DEFLATE
    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for cert in certs:
            path = path_by_id.get(cert.id)
            if not path or not path.exists():
                path = resolve_file_path(cert.pdf_path) if cert.pdf_path else None
            if not path or not path.exists():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"PDF missing for {cert.certificate_number}",
                )

            arcname = safe_pdf_filename(cert.certificate_number, cert.candidate_name)
            if arcname in used_names:
                stem = arcname[:-4] if arcname.lower().endswith(".pdf") else arcname
                arcname = f"{stem}-{cert.id}.pdf"
            used_names.add(arcname)
            zf.write(str(path), arcname)

    if training_date:
        stamp = training_date.isoformat()
    elif date_from and date_to:
        stamp = f"{date_from.isoformat()}_to_{date_to.isoformat()}"
    elif date_from:
        stamp = f"from_{date_from.isoformat()}"
    else:
        stamp = f"to_{date_to.isoformat()}"
    filename = f"certificates-{stamp}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/bulk-delete", response_model=MessageResponse)
def bulk_delete_certificates(
    data: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = certificate_service.bulk_delete_certificates(db, data.ids)
    return MessageResponse(message=f"Deleted {deleted} certificate(s)")


@router.get("", response_model=CertificateListResponse)
def list_certificates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    print_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = certificate_service.list_certificates(
        db, page=page, page_size=page_size, print_status=print_status
    )
    return CertificateListResponse(**result)

@router.post("", response_model=CertificateOut, status_code=status.HTTP_201_CREATED)
def create_certificate(
    data: CertificateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return certificate_service.create_certificate(db, data, current_user.id)


@router.get("/{cert_id}", response_model=CertificateOut)
def get_certificate(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return certificate_service.get_certificate(db, cert_id)


@router.put("/{cert_id}", response_model=CertificateOut)
def update_certificate(
    cert_id: int,
    data: CertificateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return certificate_service.update_certificate(db, cert_id, data)


@router.delete("/{cert_id}", response_model=MessageResponse)
def delete_certificate(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    certificate_service.delete_certificate(db, cert_id)
    return MessageResponse(message="Certificate deleted successfully")


@router.post("/{cert_id}/generate-pdf", response_model=CertificateOut)
async def generate_certificate_pdf(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cert = certificate_service.get_certificate(db, cert_id)
    try:
        await generate_pdf(db, cert)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}. Ensure Playwright browsers are installed (playwright install chromium).",
        )
    return certificate_service.get_certificate(db, cert_id)


@router.get("/{cert_id}/download")
def download_certificate_pdf(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cert = certificate_service.get_certificate(db, cert_id)
    if not cert.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF not generated yet. Generate PDF first.",
        )
    path = resolve_file_path(cert.pdf_path)
    if not path or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found on disk")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
    )


@router.post("/{cert_id}/mark-printed", response_model=CertificateOut)
def mark_certificate_printed(
    cert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return certificate_service.mark_printed(db, cert_id, current_user.id)


@router.post("/upload/logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    path = await save_upload(file, "logos")
    return {"path": path, "url": f"/api/files/{path}"}


@router.post("/upload/signature")
async def upload_signature(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    path = await save_upload(file, "signatures")
    return {"path": path, "url": f"/api/files/{path}"}
