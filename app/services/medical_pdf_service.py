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
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
{css}
html, body {{
  margin: 0; padding: 0; background: #fff;
  width: 794px; height: 1123px; overflow: hidden;
}}
.hospital-form-stage {{ padding: 0; background: #fff; }}
.gh-input {{ display: block; min-height: 14px; }}
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
        <div class="gh-phones">Hospital : 0522-2410951, 9451384215, 7800349822</div>
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
      <div class="gh-date-row">
        <div class="gh-field gh-date">
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


async def generate_medical_pdfs_batch(rows: list[MedicalTest]) -> dict[int, Path]:
    """Generate PDFs for many medical tests with one shared Chromium instance."""
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
            page = await browser.new_page(viewport={"width": 794, "height": 1123})
            for row in rows:
                safe_name = "".join(
                    c if c.isalnum() or c in "-_" else "_" for c in (row.patient_name or "form")
                )
                output = out_dir / f"medical-{row.id}-{safe_name[:40]}.pdf"
                html = build_medical_form_html(row)
                await page.set_content(html, wait_until="load")
                await page.pdf(
                    path=str(output),
                    width="210mm",
                    height="297mm",
                    landscape=False,
                    print_background=True,
                    margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
                    prefer_css_page_size=True,
                    page_ranges="1",
                )
                results[row.id] = output
        finally:
            await browser.close()
    return results
