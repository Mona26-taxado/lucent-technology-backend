from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings, BASE_DIR
from app.core.database import engine, Base, SessionLocal
from app.core.security import get_password_hash
from app.models import User, ApplicationSettings, CertificateTemplate
from app.services.file_service import ensure_directories, dump_field_positions
from app.schemas.template import DEFAULT_FIELD_POSITIONS
from app.api.routes import auth, certificates, templates, dashboard, print_history, settings, files, backup

app_settings = get_settings()


def ensure_schema_patches() -> None:
    """Add columns that create_all won't add on existing SQLite tables."""
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(application_settings)")).fetchall()
        }
        if "paper_size" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE application_settings "
                    "ADD COLUMN paper_size VARCHAR(20) NOT NULL DEFAULT 'a4'"
                )
            )


def seed_database() -> None:
    ensure_directories()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == app_settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=app_settings.DEFAULT_ADMIN_USERNAME,
                password_hash=get_password_hash(app_settings.DEFAULT_ADMIN_PASSWORD),
                full_name=app_settings.DEFAULT_ADMIN_FULL_NAME,
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()

        settings_row = db.query(ApplicationSettings).first()
        if not settings_row:
            settings_row = ApplicationSettings(
                organization_name="Lucent Technology",
                certificate_prefix="LT",
                automatic_numbering=True,
                current_year=datetime.now().year,
                current_serial_number=4000,
                number_padding=7,
                date_format="%d.%m.%Y",
                pdf_storage_directory="generated/certificates",
                paper_size="a4",
            )
            db.add(settings_row)
            db.commit()
            db.refresh(settings_row)

        template = db.query(CertificateTemplate).first()
        if not template:
            bg = BASE_DIR / "uploads" / "templates" / "certificate_bg_from_pdf.png"
            if not bg.exists():
                bg = BASE_DIR / "uploads" / "templates" / "default_certificate_bg.png"
            if bg.exists():
                relative = f"uploads/templates/{bg.name}"
                template = CertificateTemplate(
                    template_name="Lucent Defensive Driving Certificate",
                    background_image_path=relative,
                    field_positions_json=dump_field_positions(DEFAULT_FIELD_POSITIONS),
                    is_default=True,
                    is_active=True,
                )
                db.add(template)
                db.commit()
                db.refresh(template)
        else:
            # Keep default template aligned with Certificate.pdf artwork when present
            lucent_bg = "uploads/templates/certificate_bg_from_pdf.png"
            if (BASE_DIR / lucent_bg).exists():
                if template.background_image_path != lucent_bg or template.template_name.startswith("Default"):
                    template.background_image_path = lucent_bg
                    template.template_name = "Lucent Defensive Driving Certificate"
                    template.field_positions_json = dump_field_positions(DEFAULT_FIELD_POSITIONS)
                    template.is_default = True
                    template.is_active = True
                    db.add(template)
                    db.commit()
                    db.refresh(template)

        if settings_row and template and not settings_row.default_template_id:
            settings_row.default_template_id = template.id
            db.add(settings_row)
            db.commit()
    finally:
        db.close()


def create_app() -> FastAPI:
    application = FastAPI(
        title=app_settings.APP_NAME,
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router, prefix="/api")
    application.include_router(certificates.router, prefix="/api")
    application.include_router(templates.router, prefix="/api")
    application.include_router(dashboard.router, prefix="/api")
    application.include_router(print_history.router, prefix="/api")
    application.include_router(settings.router, prefix="/api")
    application.include_router(files.router, prefix="/api")
    application.include_router(backup.router, prefix="/api")

    @application.get("/api/health")
    def health():
        return {"status": "ok", "app": app_settings.APP_NAME}

    @application.on_event("startup")
    def on_startup():
        Base.metadata.create_all(bind=engine)
        ensure_schema_patches()
        seed_database()

    return application


app = create_app()
