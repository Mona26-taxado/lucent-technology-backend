# Design artwork aspect (Certificate.pdf) — used for on-screen preview proportions
CERTIFICATE_ASPECT_W = 686
CERTIFICATE_ASPECT_H = 938

# Native artwork size from Certificate.pdf (686×938 pt @ 72 dpi)
CERTIFICATE_NATIVE_WIDTH_MM = round(CERTIFICATE_ASPECT_W * 25.4 / 72, 2)
CERTIFICATE_NATIVE_HEIGHT_MM = round(CERTIFICATE_ASPECT_H * 25.4 / 72, 2)


def _in_to_mm(inches: float) -> float:
    """Convert inches to mm (ISO print standard, 1 in = 25.4 mm)."""
    return round(inches * 25.4, 1)


# Print / PDF paper sizes — mm values derived from inches (not hand-typed)
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
        "width_mm": _in_to_mm(8.5),
        "height_mm": _in_to_mm(12.0),
        "width_in": 8.5,
        "height_in": 12.0,
    },
    "9.5x13": {
        "label": "9.5 × 13 in",
        "width_mm": _in_to_mm(9.5),
        "height_mm": _in_to_mm(13.0),
        "width_in": 9.5,
        "height_in": 13.0,
    },
}

# Certificate stock — matches artwork within ~0.3% (best for print)
DEFAULT_PAPER_SIZE = "9.5x13"

# Scale background past page edges to crop white margin in template artwork (corners).
CERTIFICATE_BG_BLEED_SCALE = 1.08


def get_paper_size(key: str | None) -> dict:
    if key and key in PAPER_SIZES:
        return PAPER_SIZES[key]
    return PAPER_SIZES[DEFAULT_PAPER_SIZE]


def fit_certificate_mm(paper: dict) -> tuple[float, float]:
    """Fill the full paper — no letterbox margins."""
    return round(float(paper["width_mm"]), 3), round(float(paper["height_mm"]), 3)


def paper_size_matches_frontend(key: str, width_mm: float, height_mm: float) -> bool:
    """Guard against frontend/backend size drift."""
    paper = PAPER_SIZES.get(key)
    if not paper:
        return False
    return paper["width_mm"] == width_mm and paper["height_mm"] == height_mm
