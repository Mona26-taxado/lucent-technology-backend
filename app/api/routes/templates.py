import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, CertificateTemplate, Certificate
from app.schemas.template import TemplateOut, TemplateUpdate, DEFAULT_FIELD_POSITIONS
from app.schemas.dashboard import MessageResponse
from app.services.file_service import save_upload, parse_field_positions, dump_field_positions

router = APIRouter(prefix="/templates", tags=["Templates"])


def _template_out(template: CertificateTemplate) -> TemplateOut:
    return TemplateOut(
        id=template.id,
        template_name=template.template_name,
        background_image_path=template.background_image_path,
        field_positions_json=parse_field_positions(template.field_positions_json),
        is_default=template.is_default,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("", response_model=list[TemplateOut])
def list_templates(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CertificateTemplate)
    if active_only:
        query = query.filter(CertificateTemplate.is_active == True)  # noqa: E712
    templates = query.order_by(CertificateTemplate.created_at.desc()).all()
    return [_template_out(t) for t in templates]


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_name: str = Form(...),
    is_default: bool = Form(False),
    is_active: bool = Form(True),
    field_positions_json: Optional[str] = Form(None),
    background: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bg_path = await save_upload(background, "templates")

    if field_positions_json:
        try:
            positions = json.loads(field_positions_json)
        except json.JSONDecodeError:
            positions = DEFAULT_FIELD_POSITIONS.copy()
    else:
        positions = DEFAULT_FIELD_POSITIONS.copy()

    if is_default:
        db.query(CertificateTemplate).update({CertificateTemplate.is_default: False})

    template = CertificateTemplate(
        template_name=template_name.strip(),
        background_image_path=bg_path,
        field_positions_json=dump_field_positions(positions),
        is_default=is_default,
        is_active=is_active,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_out(template)


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(CertificateTemplate).filter(CertificateTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _template_out(template)


@router.put("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    template_name: Optional[str] = Form(None),
    is_default: Optional[bool] = Form(None),
    is_active: Optional[bool] = Form(None),
    field_positions_json: Optional[str] = Form(None),
    background: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(CertificateTemplate).filter(CertificateTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template_name is not None:
        template.template_name = template_name.strip()
    if is_active is not None:
        template.is_active = is_active
    if field_positions_json is not None:
        try:
            positions = json.loads(field_positions_json)
            template.field_positions_json = dump_field_positions(positions)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid field_positions_json")
    if background and background.filename:
        template.background_image_path = await save_upload(background, "templates")
    if is_default is True:
        db.query(CertificateTemplate).filter(CertificateTemplate.id != template_id).update(
            {CertificateTemplate.is_default: False}
        )
        template.is_default = True
    elif is_default is False:
        template.is_default = False

    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_out(template)


@router.delete("/{template_id}", response_model=MessageResponse)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(CertificateTemplate).filter(CertificateTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    in_use = db.query(Certificate).filter(Certificate.template_id == template_id).count()
    if in_use > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete template: used by {in_use} certificate(s). Deactivate it instead.",
        )

    db.delete(template)
    db.commit()
    return MessageResponse(message="Template deleted successfully")


@router.post("/{template_id}/set-default", response_model=TemplateOut)
def set_default_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(CertificateTemplate).filter(CertificateTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    db.query(CertificateTemplate).update({CertificateTemplate.is_default: False})
    template.is_default = True
    template.is_active = True
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_out(template)
