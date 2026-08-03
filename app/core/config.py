from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "Certificate Printing Management System"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-to-a-long-random-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'certificate_system.db'}"

    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://lucenttech.in,https://www.lucenttech.in"
    )

    UPLOAD_DIR: str = "uploads"
    GENERATED_DIR: str = "generated/certificates"
    MAX_UPLOAD_SIZE_MB: int = 10

    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_ADMIN_FULL_NAME: str = "System Administrator"

    ALLOWED_IMAGE_EXTENSIONS: set = {".png", ".jpg", ".jpeg"}
    ALLOWED_IMAGE_MIMES: set = {"image/png", "image/jpeg", "image/jpg"}

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def generated_path(self) -> Path:
        path = Path(self.GENERATED_DIR)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
