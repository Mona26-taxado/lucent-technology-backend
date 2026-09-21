"""High-fidelity A4 PDF for Globe Hospital medical form (HTML/CSS, not scanned image)."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from app.core.config import BASE_DIR, get_settings
from app.models import MedicalTest

settings = get_settings()

LOGO_CANDIDATES = [
    BASE_DIR / "uploads" / "medical" / "globe-logo.png",
    BASE_DIR.parent / "frontend" / "public" / "medical" / "globe-logo.png",
]
LUCENT_CANDIDATES = [
    BASE_DIR / "uploads" / "medical" / "lucent-on-form.png",
    BASE_DIR.parent / "frontend" / "public" / "medical" / "lucent-on-form.png",
    BASE_DIR.parent / "frontend" / "public" / "lucent-logo.png",
]
TITLE_CANDIDATES = [
    BASE_DIR.parent / "frontend" / "public" / "medical" / "globe-title.png",
    BASE_DIR / "uploads" / "medical" / "globe-title.png",
]
CSS_CANDIDATES = [
    BASE_DIR.parent / "frontend" / "src" / "styles" / "globe-hospital-form.css",
    BASE_DIR / "app" / "static" / "globe-hospital-form.css",
]


def _data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _first_uri(candidates: list[Path]) -> str:
    for p in candidates:
        uri = _data_uri(p)
        if uri:
            return uri
    return ""


def _load_css() -> str:
    for p in CSS_CANDIDATES:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def _esc(v: str | None) -> str:
    if not v:
        return ""
    return (
        str(v)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


DOCTORS = [
    ("Dr. V.K. Shukla", ["M.B.B.S., M.D. (Medicine)", "(Managing Director & Consultant Physician)", "Timing: 10am to 12pm & 06pm pm to 08pm"]),
    ("Dr. Umesh Bhardwaj", ["Administrative Officer"]),
    ("Dr. Harsh Lamba", ["B.A.M.S., E & T.C, MBA in Hospital", "Administration (MANAGING DIRECTOR)"]),
    ("Dr. Saumya Bajpai Kaur", ["M.B.B.S., M.D. (Obst. & Gyna)", "K.G.M.U., Lko."]),
    ("Dr. Anand Agarwal", ["M.B.B.S., MMA (Gold Medalist)", "K.G.M.U., Lko."]),
    ("Dr. V.K. Rajbhar", ["M.B.B.S.", "Consultant Physician"]),
    ("Dr. Sparsh Bhalla", ["M.D. Medicine (KGMU)", "DM Cardiology (IPPS Kanpur)"]),
    ("Dr. Bhawan Nangarwal", ["M.B.B.S., Mch., (Neuro Surgeon)", "S.G.P.G.I., Lko."]),
    ("Dr. S.K. Tiwari", ["M.D. D.M. Gastro (K.G.M.U. Lko.)"]),
    ("Dr. Alok Maurya", ["M.B.B.S., MS, Mch. (Urology)"]),
    ("Dr. Gaurav Gupta", ["M.B.B.S., MS, (KGMU, Lko.)"]),
    ("Dr. Vinay Tripathi", ["MS. Ortho", "Bones & Joint Replacement Specialist"]),
    ("Dr. Ramakant Chaudhary", ["M.B.B.S., M.D. (Ped.)"]),
    ("Dr. Manoj Kumar Srivastava", ["MS..Oncologist (Cancer Specialist)"]),
    ("Dr. A.K. Srivastava", ["M.B.B.S., M.D. (Pulmonary Chest)", "& I.C.U. Critical Care- 8:00 to 9:00 p.m"]),
    ("Dr. S.P. Singh Maurya", ["M.B.B.S., PGPem (USA)", "ICU, Critical Care"]),
    ("Dr. Deeban George", ["MS (Gastroenterology Surgeon)", "KGMU, Lko."]),
    ("Dr. Jilani A. Q", ["MD, DNB, DM", "Neuro Psychiatry"]),
]

SERVICES = [
    ("जनरल एवं लैप्रोस्कोपिक सर्जरी", "कैंसर सर्जरी एवं कीमोथेरेपी", "पित्त एवं गुर्दे की पथरी की दूरबीन द्वारा ऑपरेशन"),
    ("नाक, कान गला सर्जरी", "पीडियाट्रिक सर्जरी", "स्त्री एवं प्रसूति रोग, नार्मल एवं सिजेरियन (ऑपरेशन)"),
    ("यूरो मूत्राशय सर्जरी", "आर्थोपेडिक सर्जरी", "न्यूरो सर्जरी"),
]


def _field(label: str, value: str, extra_class: str = "") -> str:
    cls = f"gh-field {extra_class}".strip()
    return (
        f'<div class="{cls}"><span class="gh-label">{label}</span>'
        f'<span class="gh-rule"><span class="gh-input">{value}</span></span></div>'
    )


def build_medical_form_html(row: MedicalTest) -> str:
    globe = _first_uri(LOGO_CANDIDATES)
    lucent = _first_uri(LUCENT_CANDIDATES)
    title = _first_uri(TITLE_CANDIDATES)
    css = _load_css()
    age = "" if row.age is None else str(row.age)

    doctors_html = "".join(
        '<div class="gh-doc">'
        f'<div class="gh-doc-name">{_esc(name)}</div>'
        + "".join(f'<div class="gh-doc-detail">{_esc(line)}</div>' for line in detail)
        + "</div>"
        for name, detail in DOCTORS
    )
    services_html = "".join(
        '<div class="gh-svc-row">'
        + "".join(
            f'<div class="gh-svc"><span class="gh-diamond">◆</span><span>{_esc(c)}</span></div>'
            for c in cols
        )
        + "</div>"
        for cols in SERVICES
    )

    lab_lines = (row.lab_investigation or "").split("\n")
    lab0 = _esc(lab_lines[0] if lab_lines else "")
    lab1 = _esc(" ".join(lab_lines[1:]) if len(lab_lines) > 1 else "")
    imp_lines = (row.final_impression or "").split("\n")
    imp0 = _esc(imp_lines[0] if imp_lines else "")

    title_html = (
        f'<img src="{title}" class="gh-title-img" alt="GLOBE HOSPITAL"/>'
        if title
        else '<div class="gh-trust" style="color:#003f82;font-size:28px">GLOBE HOSPITAL</div>'
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=794"/>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
{css}
/* PDF/QA capture shell — same 794×1123 document as live preview (screen CSS, not a separate print layout). */
html, body {{
  margin: 0 !important;
  padding: 0 !important;
  background: #fff;
  width: auto;
  min-width: 0;
  overflow: visible;
}}
#hospital-form-print {{
  margin: 0 !important;
  width: 794px;
  height: 1123px;
  min-width: 794px;
  max-width: 794px;
  min-height: 1123px;
  max-height: 1123px;
  box-sizing: border-box;
  overflow: hidden;
}}
.hospital-form-stage {{ padding: 0; background: #fff; width: 794px; }}
/* Print-safe values use the same .gh-input geometry as live <input class="gh-input"> */
span.gh-input {{
  display: block;
  min-height: 14px;
  white-space: pre-wrap;
}}
</style></head>
<body>
<div class="hospital-form" id="hospital-form-print">
  <header class="gh-header">
    <div class="gh-header-grid">
      <div class="gh-logo-col">
        {"<img src='" + globe + "' alt='' class='gh-logo'/>" if globe else ""}
        <div class="gh-reg">Reg. No.: RMEE2122200</div>
      </div>
      <div class="gh-header-mid">
        <div class="gh-phones">Hospital : 0522-2410951, 9451384215, 9794912989</div>
        {title_html}
        <div class="gh-trust">Run by (Ayushmaan Health &amp; Educational Trust)</div>
        <div class="gh-addr">Add.: Sector 10- C-Block, 4022, Jal Sansthan T.W.O. No.-10, Omkarshwar Temple, M.I.S. Chauraha Road,<br/>Meena Bakery, Rajajipuram, Lucknow</div>
        <div class="gh-slogan">(24 HOUR'S EMERGENCY, ALL TYPE OF MEDICAL &amp; AMBULANCE FACILITIES)</div>
      </div>
      <div class="gh-lucent-col">
        {"<img src='" + lucent + "' alt='' class='gh-lucent'/>" if lucent else ""}
      </div>
    </div>
    <div class="gh-hline"></div>
  </header>

  <div class="gh-body">
    <aside class="gh-docs">{doctors_html}</aside>
    <section class="gh-form">
      <div class="medical-top-row">
        <div class="vehicle-field">
          <span class="gh-label">VEHICLE NUMBER:</span>
          <span class="gh-rule"><span class="gh-input">{_esc(row.vehicle_number)}</span></span>
        </div>
        <div class="date-field">
          <span class="gh-label">Date</span>
          <span class="gh-rule gh-rule-dotted"><span class="gh-input">{_esc(row.exam_date)}</span></span>
        </div>
      </div>
      {_field("NAME OF COMPANY-", _esc(row.company_name))}
      {_field("PATIENT NAME:-", _esc(row.patient_name))}
      <div class="gh-pair">
        {_field("AGE-", _esc(age), "gh-age")}
        {_field("SEX-", _esc(row.gender), "gh-sex")}
      </div>
      <div class="gh-pair">
        {_field("HEIGHT-", _esc(row.height), "gh-hw")}
        {_field("WEIGHT-", _esc(row.weight), "gh-hw")}
      </div>
      {_field("CHEST (EXPIRATION/INSPIRATION)-", _esc(row.chest))}
      {_field("BLOOD PRESSURE -", _esc(row.blood_pressure))}
      {_field("PULSE-", _esc(row.pulse))}
      {_field("BLOOD SUGAR -", _esc(row.blood_sugar))}
      <div class="gh-block gh-block-lab">
        <div class="gh-field">
          <span class="gh-label">LAB INVESTIGATION REPORT</span>
          <span class="gh-rule"><span class="gh-input">{lab0}</span></span>
        </div>
        <div class="gh-blank-rule"><span class="gh-input">{lab1}</span></div>
      </div>
      <div class="gh-block gh-block-final">
        <div class="gh-field">
          <span class="gh-label">FINAL IMPRESSION :</span>
          <span class="gh-rule"><span class="gh-input">{imp0}</span></span>
        </div>
        <div class="gh-blank-rule"></div>
      </div>
      <div class="gh-cert">
        <p>CERTIFIED THAT I EXAMINED <span class="gh-inline-rule gh-rule-dotted"><span class="gh-input">{_esc(row.certified_name or row.patient_name)}</span></span></p>
        <p>PRESENTLY IN GOOD HEALTH AND FREE FROM ANY CARDIO-RESPIRATORY</p>
        <p>/COMMUNICABLE ALIMENT, HE/SHE IS FIT FOR ORGANISATION.</p>
      </div>
      <div class="gh-dots"></div>
      <div class="gh-sign">
        <div class="gh-field"><span class="gh-label">SIGNATURE OF MEDICAL EXAMINER</span><span class="gh-rule"></span></div>
        {_field("NAME &", _esc(row.examiner_name))}
        <div class="gh-field">
          <span class="gh-label">QUALIFICATION<span class="gh-leaders">....................</span></span>
          <span class="gh-rule"><span class="gh-input">{_esc(row.examiner_qualification)}</span></span>
        </div>
        <div class="gh-field">
          <span class="gh-label">PLACE<span class="gh-leaders">..............................</span></span>
          <span class="gh-rule"><span class="gh-input">{_esc(row.examiner_place)}</span></span>
        </div>
        <div class="gh-legal">(Not Valid For Medical Legal Use)</div>
      </div>
    </section>
  </div>

  <footer class="gh-footer">
    <div class="gh-foot-line"></div>
    <div class="gh-services">{services_html}</div>
    <div class="gh-pills">
      <span class="gh-pill gh-pill-icu">I.C.U.</span>
      <span class="gh-pill gh-pill-nicu">N.I.C.U.</span>
      <span class="gh-pill gh-pill-vent">VENTILATOR</span>
      <span class="gh-pill gh-pill-cancer">CANCER</span>
    </div>
    <div class="gh-em-line"></div>
    <div class="gh-emergency">
      <span class="gh-cross">✚</span>
      <div class="gh-em-mid">
        <div class="gh-em-title"><span class="gh-24">24X7</span> <span class="gh-em-hi">इमरजेन्सी एण्ड ट्रामा केयर</span></div>
        <div class="gh-em-phones">EMERGENCY CONTACT NO.: 9307467795, 9794912989</div>
      </div>
      <span class="gh-cross">✚</span>
    </div>
  </footer>
</div>
</body></html>"""


async def generate_medical_pdf(row: MedicalTest) -> Path:
    paths = await generate_medical_pdfs_batch([row])
    return paths[row.id]


def _png_bytes_to_a4_pdf(png_bytes: bytes, output: Path, *, css_px_width: int = 794) -> None:
    """Place the full form screenshot into one A4 page using CONTAIN (never crop).

    Screenshot may be DSF×794 × DSF×1123. That is still one CSS document.
    Fit the entire image inside A4; letterbox with white if needed.
    """
    import io

    from PIL import Image

    src = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    src_w, src_h = src.size

    # True A4 at 150 DPI (sharp enough for print, exact aspect)
    dpi = 150.0
    a4_w_mm, a4_h_mm = 210.0, 297.0
    a4_w_px = int(round(a4_w_mm / 25.4 * dpi))
    a4_h_px = int(round(a4_h_mm / 25.4 * dpi))

    scale = min(a4_w_px / src_w, a4_h_px / src_h)
    render_w = max(1, int(round(src_w * scale)))
    render_h = max(1, int(round(src_h * scale)))
    # Guard: never exceed A4 (rounding)
    render_w = min(render_w, a4_w_px)
    render_h = min(render_h, a4_h_px)

    fitted = src.resize((render_w, render_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (a4_w_px, a4_h_px), (255, 255, 255))
    x = (a4_w_px - render_w) // 2
    y = (a4_h_px - render_h) // 2
    canvas.paste(fitted, (x, y))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PDF", resolution=dpi)
    if os.environ.get("MEDICAL_PDF_DEBUG"):
        src.save(output.with_suffix(".capture.png"))


async def _wait_form_ready(page) -> dict:
    await page.evaluate("() => document.fonts.ready")
    await page.evaluate(
        """async () => {
          const imgs = Array.from(document.images || []);
          await Promise.all(imgs.map((img) => {
            if (img.complete && img.naturalWidth > 0) return null;
            return new Promise((resolve) => {
              img.addEventListener('load', resolve, { once: true });
              img.addEventListener('error', resolve, { once: true });
            });
          }));
        }"""
    )
    metrics = await page.evaluate(
        """() => {
          const el = document.querySelector('#hospital-form-print');
          if (!el) return null;
          const rect = el.getBoundingClientRect();
          const title = document.querySelector('.gh-title-img');
          return {
            width: rect.width,
            height: rect.height,
            scrollWidth: el.scrollWidth,
            scrollHeight: el.scrollHeight,
            titleNatural: title ? { w: title.naturalWidth, h: title.naturalHeight } : null,
            titleRendered: title ? { w: title.clientWidth, h: title.clientHeight } : null,
          };
        }"""
    )
    if not metrics:
        raise RuntimeError("Globe form #hospital-form-print not found before PDF capture")
    if abs(metrics["width"] - 794) > 1 or abs(metrics["height"] - 1123) > 2:
        raise RuntimeError(f"Globe form not at 794×1123 before PDF capture: {metrics}")
    if metrics["scrollWidth"] > 794 + 1 or metrics["scrollHeight"] > 1123 + 2:
        raise RuntimeError(
            "Globe form content overflows 794×1123 (would clip in screenshot): "
            f"scroll={metrics['scrollWidth']}×{metrics['scrollHeight']}"
        )
    return metrics


async def generate_medical_pdfs_batch(rows: list[MedicalTest]) -> dict[int, Path]:
    """Generate PDFs for many medical tests with one shared Chromium instance.

    Method: Playwright renders the SAME 794×1123 CSS document used by the live
    preview (shared globe-hospital-form.css), screenshots that node, then embeds
    the PNG into a true A4 PDF with CONTAIN placement (no crop).
    """
    from playwright.async_api import async_playwright

    if not rows:
        return {}

    default_browsers = Path.home() / "Library" / "Caches" / "ms-playwright"
    if default_browsers.exists() and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(default_browsers)

    out_dir = settings.generated_path.parent / "medical"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[int, Path] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            # Viewport larger than the form so browser chrome/margins cannot clip capture
            page = await browser.new_page(
                viewport={"width": 960, "height": 1280},
                device_scale_factor=2,
            )
            await page.emulate_media(media="screen")
            for row in rows:
                safe_name = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in (row.patient_name or "form")
                )
                output = out_dir / f"medical-{row.id}-{safe_name[:40]}.pdf"
                html = build_medical_form_html(row)
                await page.set_content(html, wait_until="networkidle")
                metrics = await _wait_form_ready(page)
                print(
                    f"[medical-pdf] id={row.id} box={metrics['width']}x{metrics['height']} "
                    f"scroll={metrics['scrollWidth']}x{metrics['scrollHeight']} "
                    f"title={metrics.get('titleNatural')}->{metrics.get('titleRendered')}"
                )
                png_bytes = await page.locator("#hospital-form-print").screenshot(
                    type="png",
                    animations="disabled",
                    caret="hide",
                )
                _png_bytes_to_a4_pdf(png_bytes, output, css_px_width=794)
                results[row.id] = output
        finally:
            await browser.close()
    return results
