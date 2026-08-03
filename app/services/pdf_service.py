from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.page_size import get_paper_size, fit_certificate_mm, DEFAULT_PAPER_SIZE
from app.models import Certificate, CertificateTemplate
from app.services.file_service import resolve_file_path, safe_pdf_filename, parse_field_positions
from app.services.numbering_service import get_or_create_settings
from app.schemas.template import DEFAULT_FIELD_POSITIONS

settings = get_settings()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _file_to_data_uri(path: Optional[Path]) -> Optional[str]:
    if not path or not path.exists():
        return None
    import base64

    data = path.read_bytes()
    ext = path.suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    if ext == ".svg":
        mime = "image/svg+xml"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _format_date(d, date_format: str) -> str:
    """Always return a printable date string (never empty — empty skips PDF fields)."""
    fallback = "%d.%m.%Y"
    fmt = (date_format or "").strip() or fallback
    try:
        out = d.strftime(fmt)
    except Exception:
        out = d.strftime(fallback)
    return out or d.strftime(fallback)


def build_certificate_context(db: Session, certificate: Certificate) -> dict:
    app_settings = get_or_create_settings(db)
    paper = get_paper_size(getattr(app_settings, "paper_size", None) or DEFAULT_PAPER_SIZE)
    cert_w, cert_h = fit_certificate_mm(paper)

    template: Optional[CertificateTemplate] = None
    if certificate.template_id:
        template = db.query(CertificateTemplate).filter(CertificateTemplate.id == certificate.template_id).first()
    if not template:
        template = (
            db.query(CertificateTemplate)
            .filter(CertificateTemplate.is_default == True, CertificateTemplate.is_active == True)  # noqa: E712
            .first()
        )
    if not template:
        template = (
            db.query(CertificateTemplate)
            .filter(CertificateTemplate.is_active == True)  # noqa: E712
            .first()
        )

    field_positions = DEFAULT_FIELD_POSITIONS.copy()
    if template:
        stored = parse_field_positions(template.field_positions_json)
        for key, val in stored.items():
            if key in field_positions and isinstance(val, dict):
                field_positions[key] = {**field_positions[key], **val}
            else:
                field_positions[key] = val

    # Critical print fields — keep printable size/position (PDF used to drop these)
    for key in ("training_date", "certificate_number"):
        default = DEFAULT_FIELD_POSITIONS[key]
        pos = field_positions.get(key) if isinstance(field_positions.get(key), dict) else {}
        merged = {**default, **pos}
        if float(merged.get("y") or 0) < 0 or float(merged.get("font_size") or 0) <= 0:
            merged = default.copy()
        # Left-edge anchor near labels; avoid old center-at-78% clipping in Playwright
        if float(merged.get("x") or 0) >= 78:
            merged["x"] = default["x"]
            merged["y"] = default["y"]
            merged["width"] = default["width"]
        merged["text_align"] = "left"
        if float(merged.get("font_size") or 0) < 10:
            merged["font_size"] = default["font_size"]
        field_positions[key] = merged

    bg_uri = None
    if template:
        bg_path = resolve_file_path(template.background_image_path)
        bg_uri = _file_to_data_uri(bg_path)

    logo_path = resolve_file_path(certificate.logo_path) or resolve_file_path(app_settings.default_logo_path)
    sig_path = resolve_file_path(certificate.signature_path) or resolve_file_path(
        app_settings.default_signature_path
    )

    return {
        "certificate": certificate,
        "candidate_name": certificate.candidate_name,
        "address": certificate.address,
        "training_date": _format_date(certificate.training_date, app_settings.date_format),
        "certificate_number": certificate.certificate_number,
        "driving_licence_number": certificate.driving_licence_number or "",
        "company_name": certificate.company_name or "",
        "training_centre_name": certificate.training_centre_name or "",
        "authorized_person_name": certificate.authorized_person_name or "",
        "certificate_title": certificate.certificate_title or "",
        "certificate_description": certificate.certificate_description or "",
        "background_uri": bg_uri,
        "logo_uri": _file_to_data_uri(logo_path),
        "signature_uri": _file_to_data_uri(sig_path),
        "fields": field_positions,
        "organization_name": app_settings.organization_name,
        "page_width_mm": paper["width_mm"],
        "page_height_mm": paper["height_mm"],
        "cert_width_mm": cert_w,
        "cert_height_mm": cert_h,
        "paper_size": getattr(app_settings, "paper_size", None) or DEFAULT_PAPER_SIZE,
    }


def render_certificate_html(db: Session, certificate: Certificate) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("certificate.html")
    ctx = build_certificate_context(db, certificate)
    return template.render(**ctx)


async def generate_pdf(db: Session, certificate: Certificate) -> str:
    """Generate print PDF at configured paper size (A4 or 8.5x12)."""
    from playwright.async_api import async_playwright

    app_settings = get_or_create_settings(db)
    paper = get_paper_size(getattr(app_settings, "paper_size", None) or DEFAULT_PAPER_SIZE)

    html = render_certificate_html(db, certificate)
    settings.generated_path.mkdir(parents=True, exist_ok=True)

    filename = safe_pdf_filename(certificate.certificate_number, certificate.candidate_name)
    output_path = settings.generated_path / filename

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        # Wait for webfonts so PDF matches on-screen preview typography
        try:
            await page.evaluate("() => document.fonts.ready")
        except Exception:
            pass
        await page.wait_for_timeout(150)
        await page.pdf(
            path=str(output_path),
            width=f"{paper['width_mm']}mm",
            height=f"{paper['height_mm']}mm",
            landscape=False,
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            prefer_css_page_size=True,
        )
        await browser.close()

    relative = f"generated/certificates/{filename}"
    certificate.pdf_path = relative
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return relative
