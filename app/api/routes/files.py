from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.models import User
from app.core.config import BASE_DIR

router = APIRouter(prefix="/files", tags=["Files"])

ALLOWED_ROOTS = [
    BASE_DIR / "uploads",
    BASE_DIR / "generated",
]


@router.get("/{file_path:path}")
def serve_file(file_path: str, current_user: User = Depends(get_current_user)):
    clean = file_path.replace("..", "").lstrip("/\\")
    full = (BASE_DIR / clean).resolve()

    allowed = False
    for root in ALLOWED_ROOTS:
        try:
            full.relative_to(root.resolve())
            allowed = True
            break
        except ValueError:
            continue

    if not allowed or not full.exists() or not full.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    media = "application/octet-stream"
    suffix = full.suffix.lower()
    if suffix == ".png":
        media = "image/png"
    elif suffix in (".jpg", ".jpeg"):
        media = "image/jpeg"
    elif suffix == ".svg":
        media = "image/svg+xml"
    elif suffix == ".pdf":
        media = "application/pdf"

    return FileResponse(path=str(full), media_type=media)
