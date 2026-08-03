from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings, BASE_DIR
from app.core.database import engine, Base, SessionLocal
from app.core.security import get_password_hash
from app.models import User, ApplicationSettings, CertificateTemplate
from app.services.file_service import ensure_directories, dump_field_positions, parse_field_positions
from app.schemas.template import DEFAULT_FIELD_POSITIONS
from app.api.routes import auth, certificates, templates, dashboard, print_history, settings, files, backup

app_settings = get_settings()


def resolve_existing_template_bg(relative_path: str | None):
    if not relative_path:
        return None
    clean = relative_path.replace("..", "").lstrip("/\\")
    full = BASE_DIR / clean
    return full if full.exists() and full.is_file() else None


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
        lucent_bg_rel = "uploads/templates/certificate_bg_from_pdf.png"
        lucent_bg_abs = BASE_DIR / lucent_bg_rel
        default_bg_abs = BASE_DIR / "uploads" / "templates" / "default_certificate_bg.png"

        if not template:
            bg = lucent_bg_abs if lucent_bg_abs.exists() else default_bg_abs
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
            # Repair missing background file on disk (common after deploy without uploads/)
            stored = resolve_existing_template_bg(template.background_image_path)
            if not stored:
                if lucent_bg_abs.exists():
                    template.background_image_path = lucent_bg_rel
                    template.template_name = "Lucent Defensive Driving Certificate"
                    template.field_positions_json = dump_field_positions(DEFAULT_FIELD_POSITIONS)
                    template.is_default = True
                    template.is_active = True
                    db.add(template)
                    db.commit()
                    db.refresh(template)
                elif default_bg_abs.exists():
                    template.background_image_path = f"uploads/templates/{default_bg_abs.name}"
                    db.add(template)
                    db.commit()
                    db.refresh(template)
            elif lucent_bg_abs.exists() and (
                template.background_image_path != lucent_bg_rel
                or template.template_name.startswith("Default")
            ):
                # Prefer Lucent artwork when present
                if template.template_name.startswith("Default") or not stored:
                    template.background_image_path = lucent_bg_rel
                    template.template_name = "Lucent Defensive Driving Certificate"
                    template.field_positions_json = dump_field_positions(DEFAULT_FIELD_POSITIONS)
                    template.is_default = True
                    template.is_active = True
                    db.add(template)
                    db.commit()
                    db.refresh(template)

        # Keep critical print fields aligned with code defaults (date/cert no often
        # vanish in PDF when older template JSON used center-anchor + cqw near the edge).
        if template:
            stored_positions = parse_field_positions(template.field_positions_json)
            changed = False
            for key in ("training_date", "certificate_number", "driving_licence_number"):
                desired = DEFAULT_FIELD_POSITIONS[key]
                current = stored_positions.get(key) if isinstance(stored_positions.get(key), dict) else {}
                if key == "driving_licence_number":
                    needs_refresh = (
                        not current
                        or current.get("font_family") != desired["font_family"]
                        or str(current.get("font_weight")) not in ("700", "bold")
                    )
                    if needs_refresh:
                        stored_positions[key] = {
                            **(current or {}),
                            **desired,
                            **{k: current[k] for k in ("x", "y", "width") if isinstance(current, dict) and k in current},
                        }
                        changed = True
                    continue
                needs_refresh = (
                    not current
                    or float(current.get("y") or 0) < 0
                    or abs(float(current.get("x") or 0) - float(desired["x"])) > 0.05
                    or abs(float(current.get("y") or 0) - float(desired["y"])) > 0.05
                    or current.get("text_align") != "left"
                    or float(current.get("font_size") or 0) < 12
                )
                if needs_refresh:
                    stored_positions[key] = {
                        **desired,
                        **{
                            k: v
                            for k, v in current.items()
                            if k in ("font_family", "font_weight", "text_color") and v
                        },
                        "x": desired["x"],
                        "y": desired["y"],
                        "width": desired["width"],
                        "font_size": desired["font_size"],
                        "text_align": "left",
                    }
                    changed = True
            if changed:
                template.field_positions_json = dump_field_positions(stored_positions)
                db.add(template)
                db.commit()

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
