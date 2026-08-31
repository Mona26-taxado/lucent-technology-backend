from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.page_size import (
    get_paper_size,
    fit_certificate_mm,
    DEFAULT_PAPER_SIZE,
    CERTIFICATE_BG_BLEED_SCALE,
)
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

    # Keep print fields identical to preview defaults (view === PDF)
    locked = ("training_date", "certificate_number", "address", "driving_licence_number")
    for key in locked:
        default = DEFAULT_FIELD_POSITIONS[key]
        field_positions[key] = default.copy()

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
        "bg_bleed_scale": CERTIFICATE_BG_BLEED_SCALE,
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
    ctx = build_certificate_context(db, certificate)
    ctx_date = ctx["training_date"]
    ctx_number = ctx["certificate_number"]
    date_pos = ctx["fields"]["training_date"]
    cert_pos = ctx["fields"]["certificate_number"]
    settings.generated_path.mkdir(parents=True, exist_ok=True)

    filename = safe_pdf_filename(certificate.certificate_number, certificate.candidate_name)
    output_path = settings.generated_path / filename

    # A4 @ 96dpi ≈ 794×1123; 8.5x12 @ 96dpi ≈ 816×1152
    viewport_w = int(round(paper["width_mm"] / 25.4 * 96))
    viewport_h = int(round(paper["height_mm"] / 25.4 * 96))

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": viewport_w, "height": viewport_h})
        await page.set_content(html, wait_until="load")
        try:
            await page.evaluate("() => document.fonts.ready")
        except Exception:
            pass
        # Failsafe: ensure text present; keep same anchors as preview/defaults
        await page.evaluate(
            """([dateText, certNo, datePos, certPos]) => {
              const dateEl = document.getElementById('print-training-date');
              const certEl = document.getElementById('print-certificate-number');
              if (dateEl) {
                if (!dateEl.textContent || !dateEl.textContent.trim()) dateEl.textContent = dateText;
                dateEl.style.left = datePos.x + '%';
                dateEl.style.top = datePos.y + '%';
                dateEl.style.maxWidth = (datePos.width || 22) + '%';
                dateEl.style.fontSize = (datePos.font_size || 10.5) + 'pt';
                dateEl.style.fontFamily = datePos.font_family || "'Open Sans', Arial, Helvetica, sans-serif";
                dateEl.style.fontWeight = String(datePos.font_weight || '700');
                dateEl.style.color = datePos.text_color || '#1A2B56';
                dateEl.style.textAlign = 'left';
                dateEl.style.visibility = 'visible';
                dateEl.style.opacity = '1';
                dateEl.style.display = 'block';
                dateEl.style.zIndex = '99';
              }
              if (certEl) {
                if (!certEl.textContent || !certEl.textContent.trim()) certEl.textContent = certNo;
                certEl.style.left = certPos.x + '%';
                certEl.style.top = certPos.y + '%';
                certEl.style.maxWidth = (certPos.width || 22) + '%';
                certEl.style.fontSize = (certPos.font_size || 12.7) + 'pt';
                certEl.style.fontFamily = certPos.font_family || "'Open Sans', Arial, Helvetica, sans-serif";
                certEl.style.fontWeight = String(certPos.font_weight || '700');
                certEl.style.color = certPos.text_color || '#1A2B56';
                certEl.style.textAlign = 'left';
                certEl.style.visibility = 'visible';
                certEl.style.opacity = '1';
                certEl.style.display = 'block';
                certEl.style.zIndex = '99';
              }
            }""",
            [ctx_date, ctx_number, date_pos, cert_pos],
        )
        await page.wait_for_timeout(200)
        await page.pdf(
            path=str(output_path),
            width=f"{paper['width_mm']}mm",
            height=f"{paper['height_mm']}mm",
            landscape=False,
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            prefer_css_page_size=True,
            page_ranges="1",
        )
        await browser.close()

    relative = f"generated/certificates/{filename}"
    certificate.pdf_path = relative
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return relative


async def _render_one_pdf_on_page(page, db: Session, certificate: Certificate, paper: dict) -> Path:
    """Render one certificate PDF using an already-open Playwright page (fast for bulk)."""
    html = render_certificate_html(db, certificate)
    ctx = build_certificate_context(db, certificate)
    ctx_date = ctx["training_date"]
    ctx_number = ctx["certificate_number"]
    date_pos = ctx["fields"]["training_date"]
    cert_pos = ctx["fields"]["certificate_number"]
    settings.generated_path.mkdir(parents=True, exist_ok=True)

    filename = safe_pdf_filename(certificate.certificate_number, certificate.candidate_name)
    output_path = settings.generated_path / filename

    await page.set_content(html, wait_until="domcontentloaded")
    try:
        await page.evaluate("() => document.fonts.ready")
    except Exception:
        pass
    await page.evaluate(
        """([dateText, certNo, datePos, certPos]) => {
          const dateEl = document.getElementById('print-training-date');
          const certEl = document.getElementById('print-certificate-number');
          if (dateEl) {
            if (!dateEl.textContent || !dateEl.textContent.trim()) dateEl.textContent = dateText;
            dateEl.style.left = datePos.x + '%';
            dateEl.style.top = datePos.y + '%';
            dateEl.style.maxWidth = (datePos.width || 22) + '%';
            dateEl.style.fontSize = (datePos.font_size || 10.5) + 'pt';
            dateEl.style.fontFamily = datePos.font_family || "'Open Sans', Arial, Helvetica, sans-serif";
            dateEl.style.fontWeight = String(datePos.font_weight || '700');
            dateEl.style.color = datePos.text_color || '#1A2B56';
            dateEl.style.textAlign = 'left';
            dateEl.style.visibility = 'visible';
            dateEl.style.opacity = '1';
            dateEl.style.display = 'block';
            dateEl.style.zIndex = '99';
          }
          if (certEl) {
            if (!certEl.textContent || !certEl.textContent.trim()) certEl.textContent = certNo;
            certEl.style.left = certPos.x + '%';
            certEl.style.top = certPos.y + '%';
            certEl.style.maxWidth = (certPos.width || 22) + '%';
            certEl.style.fontSize = (certPos.font_size || 12.7) + 'pt';
            certEl.style.fontFamily = certPos.font_family || "'Open Sans', Arial, Helvetica, sans-serif";
            certEl.style.fontWeight = String(certPos.font_weight || '700');
            certEl.style.color = certPos.text_color || '#1A2B56';
            certEl.style.textAlign = 'left';
            certEl.style.visibility = 'visible';
            certEl.style.opacity = '1';
            certEl.style.display = 'block';
            certEl.style.zIndex = '99';
          }
        }""",
        [ctx_date, ctx_number, date_pos, cert_pos],
    )
    await page.wait_for_timeout(80)
    await page.pdf(
        path=str(output_path),
        width=f"{paper['width_mm']}mm",
        height=f"{paper['height_mm']}mm",
        landscape=False,
        print_background=True,
        margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
        prefer_css_page_size=True,
        page_ranges="1",
    )

    relative = f"generated/certificates/{filename}"
    certificate.pdf_path = relative
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return output_path


async def generate_missing_pdfs_batch(db: Session, certificates: list[Certificate]) -> dict[int, Path]:
    """Generate only missing PDFs with one shared Chromium browser (much faster for bulk ZIP)."""
    from playwright.async_api import async_playwright

    app_settings = get_or_create_settings(db)
    paper = get_paper_size(getattr(app_settings, "paper_size", None) or DEFAULT_PAPER_SIZE)
    viewport_w = int(round(paper["width_mm"] / 25.4 * 96))
    viewport_h = int(round(paper["height_mm"] / 25.4 * 96))

    results: dict[int, Path] = {}
    missing: list[Certificate] = []

    for cert in certificates:
        path = resolve_file_path(cert.pdf_path) if cert.pdf_path else None
        if path and path.exists():
            results[cert.id] = path
        else:
            missing.append(cert)

    if not missing:
        return results

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = await browser.new_page(viewport={"width": viewport_w, "height": viewport_h})
        try:
            for cert in missing:
                path = await _render_one_pdf_on_page(page, db, cert, paper)
                results[cert.id] = path
        finally:
            await browser.close()

    return results
