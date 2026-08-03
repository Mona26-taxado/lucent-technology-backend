from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# Positions calibrated for Lucent Technology Certificate.pdf background.
# Coordinates are percentages of page width/height (origin top-left).
# Static artwork (title, seals, labels) stays on the background image.
DEFAULT_FIELD_POSITIONS = {
    "candidate_name": {
        "x": 50,
        "y": 45.5,
        "width": 75,
        "font_size": 38.86,
        "font_family": "'Great Vibes', cursive",
        "font_weight": "600",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
    "driving_licence_number": {
        "x": 50,
        "y": 55.5,
        "width": 50,
        "font_size": 19.86,
        "font_family": "'Open Sans', sans-serif",
        "font_weight": "600",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
    "address": {
        "x": 54,
        "y": 66,
        "width": 62,
        "font_size": 16.53,
        "font_family": "'Open Sans', sans-serif",
        "font_weight": "600",
        "text_color": "#1A2B56",
        "text_align": "center",
        "text_decoration": "underline",
    },
    "training_date": {
        # Under background label "Training Date :" (no room to the right — border)
        "x": 70,
        "y": 83.8,
        "width": 24,
        "font_size": 13,
        "font_family": "'Open Sans', Arial, Helvetica, sans-serif",
        "font_weight": "700",
        "text_color": "#1A2B56",
        "text_align": "left",
    },
    "certificate_number": {
        # Under background label "Certificate No."
        "x": 70,
        "y": 88.0,
        "width": 24,
        "font_size": 13,
        "font_family": "'Open Sans', Arial, Helvetica, sans-serif",
        "font_weight": "700",
        "text_color": "#1A2B56",
        "text_align": "left",
    },
    "signature": {
        "x": 28,
        "y": 83,
        "width": 18,
        "height": 6,
    },
    # Logo is already printed on Certificate.pdf — keep off-canvas unless needed
    "logo": {
        "x": 80,
        "y": 13,
        "width": 16,
        "height": 10,
    },
    # Optional overlays (only shown when values are provided)
    "company_name": {
        "x": 50,
        "y": -20,
        "width": 60,
        "font_size": 14,
        "font_family": "'Open Sans', sans-serif",
        "font_weight": "700",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
    "training_centre_name": {
        "x": 50,
        "y": -20,
        "width": 60,
        "font_size": 12,
        "font_family": "'Open Sans', sans-serif",
        "font_weight": "400",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
    "authorized_person_name": {
        "x": 28,
        "y": 88,
        "width": 22,
        "font_size": 10,
        "font_family": "'Open Sans', sans-serif",
        "font_weight": "600",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
    "certificate_title": {
        "x": 50,
        "y": -20,
        "width": 70,
        "font_size": 20,
        "font_family": "'Playfair Display', serif",
        "font_weight": "700",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
    "certificate_description": {
        "x": 50,
        "y": -20,
        "width": 70,
        "font_size": 12,
        "font_family": "'Open Sans', sans-serif",
        "font_weight": "400",
        "text_color": "#1A2B56",
        "text_align": "center",
    },
}


class FieldPosition(BaseModel):
    x: float = 50
    y: float = 50
    width: float = 40
    height: Optional[float] = None
    font_size: Optional[float] = 14
    font_family: Optional[str] = "'Open Sans', sans-serif"
    font_weight: Optional[str] = "400"
    text_color: Optional[str] = "#1A2B56"
    text_align: Optional[str] = "center"


class TemplateCreate(BaseModel):
    template_name: str = Field(min_length=1, max_length=200)
    field_positions_json: Optional[dict[str, Any]] = None
    is_default: bool = False
    is_active: bool = True


class TemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    field_positions_json: Optional[dict[str, Any]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class TemplateOut(BaseModel):
    id: int
    template_name: str
    background_image_path: str
    field_positions_json: dict[str, Any]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
