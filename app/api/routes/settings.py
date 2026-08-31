from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.page_size import (
    PAPER_SIZES,
    DEFAULT_PAPER_SIZE,
    CERTIFICATE_NATIVE_WIDTH_MM,
    CERTIFICATE_NATIVE_HEIGHT_MM,
)
from app.api.deps import get_current_user
from app.models import User
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.schemas.dashboard import MessageResponse
from app.services.numbering_service import get_or_create_settings
from app.services.file_service import save_upload
from app.core.security import verify_password, get_password_hash
from app.schemas.auth import ChangePasswordRequest

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/paper-sizes")
def list_paper_sizes(
    current_user: User = Depends(get_current_user),
):
    """Exact PDF print dimensions (backend source of truth)."""
    return {
        "default": DEFAULT_PAPER_SIZE,
        "certificate_native_mm": {
            "width": CERTIFICATE_NATIVE_WIDTH_MM,
            "height": CERTIFICATE_NATIVE_HEIGHT_MM,
        },
        "sizes": {key: paper for key, paper in PAPER_SIZES.items()},
    }


@router.get("", response_model=SettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_or_create_settings(db)


@router.put("", response_model=SettingsOut)
def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app_settings = get_or_create_settings(db)
    update_data = data.model_dump(exclude_unset=True)
    if "paper_size" in update_data:
        key = update_data["paper_size"]
        if key not in PAPER_SIZES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid paper_size. Use one of: {', '.join(PAPER_SIZES)}",
            )
    for key, value in update_data.items():
        setattr(app_settings, key, value)
    if not getattr(app_settings, "paper_size", None):
        app_settings.paper_size = DEFAULT_PAPER_SIZE
    db.add(app_settings)
    db.commit()
    db.refresh(app_settings)
    return app_settings


@router.post("/upload/default-logo")
async def upload_default_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = await save_upload(file, "logos")
    app_settings = get_or_create_settings(db)
    app_settings.default_logo_path = path
    db.add(app_settings)
    db.commit()
    return {"path": path, "url": f"/api/files/{path}"}


@router.post("/upload/default-signature")
async def upload_default_signature(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = await save_upload(file, "signatures")
    app_settings = get_or_create_settings(db)
    app_settings.default_signature_path = path
    db.add(app_settings)
    db.commit()
    return {"path": path, "url": f"/api/files/{path}"}


@router.post("/change-password", response_model=MessageResponse)
def change_admin_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.password_hash = get_password_hash(data.new_password)
    db.add(current_user)
    db.commit()
    return MessageResponse(message="Password changed successfully")
