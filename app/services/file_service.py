import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile, HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def ensure_directories() -> None:
    for sub in ("logos", "templates", "signatures"):
        (settings.upload_path / sub).mkdir(parents=True, exist_ok=True)
    settings.generated_path.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    return name


def validate_image_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}",
        )

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in settings.ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type: {content_type}. Allowed: PNG, JPG, JPEG",
        )


async def save_upload(file: UploadFile, subdirectory: str) -> str:
    """Save uploaded file and return relative path from backend root."""
    ensure_directories()
    validate_image_upload(file)

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    if len(content) < 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File appears empty or corrupt")

    # Basic magic-byte check
    is_png = content[:8] == b"\x89PNG\r\n\x1a\n"
    is_jpeg = content[:2] == b"\xff\xd8"
    if not (is_png or is_jpeg):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File content is not a valid image")

    ext = Path(sanitize_filename(file.filename)).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_dir = settings.upload_path / subdirectory
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / unique_name
    dest_path.write_bytes(content)

    return f"uploads/{subdirectory}/{unique_name}"


def resolve_file_path(relative_path: Optional[str]) -> Optional[Path]:
    if not relative_path:
        return None
    # Prevent directory traversal
    clean = relative_path.replace("..", "").lstrip("/\\")
    from app.core.config import BASE_DIR

    full = BASE_DIR / clean
    if full.exists():
        return full
    return None


def parse_field_positions(raw: str) -> dict:
    try:
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def dump_field_positions(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def safe_pdf_filename(certificate_number: str, candidate_name: str) -> str:
    num = certificate_number.replace("/", "-").replace("\\", "-")
    name = "".join(c if c.isalnum() or c in ("-", "_", " ") else "" for c in candidate_name)
    name = "-".join(name.split())
    return f"{num}-{name}.pdf"
