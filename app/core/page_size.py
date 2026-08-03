# Design artwork aspect (Certificate.pdf) — used for on-screen preview proportions
CERTIFICATE_ASPECT_W = 686
CERTIFICATE_ASPECT_H = 938

# Print / PDF paper sizes (client requirement)
PAPER_SIZES = {
    "a4": {
        "label": "A4 (210 × 297 mm)",
        "width_mm": 210.0,
        "height_mm": 297.0,
        "width_in": 8.27,
        "height_in": 11.69,
    },
    "8.5x12": {
        "label": "8.5 × 12 in",
        "width_mm": 215.9,
        "height_mm": 304.8,
        "width_in": 8.5,
        "height_in": 12.0,
    },
}

DEFAULT_PAPER_SIZE = "a4"


def get_paper_size(key: str | None) -> dict:
    if key and key in PAPER_SIZES:
        return PAPER_SIZES[key]
    return PAPER_SIZES[DEFAULT_PAPER_SIZE]


def fit_certificate_mm(paper: dict) -> tuple[float, float]:
    """Fit design-aspect certificate inside the paper without stretching."""
    aspect = CERTIFICATE_ASPECT_W / CERTIFICATE_ASPECT_H
    page_w = float(paper["width_mm"])
    page_h = float(paper["height_mm"])
    width = page_w
    height = width / aspect
    if height > page_h:
        height = page_h
        width = height * aspect
    return round(width, 3), round(height, 3)
