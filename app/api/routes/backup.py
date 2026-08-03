import io
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.config import BASE_DIR
from app.models import User

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.get("/download")
def download_backup(current_user: User = Depends(get_current_user)):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Database file(s)
        for db_path in BASE_DIR.glob("*.db"):
            zf.write(db_path, arcname=f"database/{db_path.name}")

        # Uploads and generated PDFs
        for folder_name in ("uploads", "generated"):
            folder = BASE_DIR / folder_name
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if path.is_file() and path.name != ".gitkeep":
                    zf.write(path, arcname=str(path.relative_to(BASE_DIR)))

    buffer.seek(0)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"certificate-backup-{stamp}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
