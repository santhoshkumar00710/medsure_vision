"""
app/pipeline/quality.py — Image quality assessment.

Computes blur, brightness, glare, contrast and resolution.
Returns ok flag + per-metric values + human-readable tips.
All thresholds come from config.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import logging

import cv2
import numpy as np

from app.config import (
    QUALITY_BLUR_MIN,
    QUALITY_BRIGHTNESS_MIN,
    QUALITY_BRIGHTNESS_MAX,
    QUALITY_GLARE_MAX,
    QUALITY_CONTRAST_MIN,
    QUALITY_RESOLUTION_MIN,
)

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    ok: bool
    blur: float
    brightness: float
    glare: float
    contrast: float
    resolution_min: int
    tips: list[str] = field(default_factory=list)


def assess_quality(img_bytes: bytes) -> QualityReport:
    """
    Assess image quality from raw bytes.
    Returns a QualityReport; if ok=False the scan should return insufficient_quality.
    """
    try:
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image bytes")
    except Exception as exc:
        logger.error("quality: decode error: %s", exc)
        return QualityReport(
            ok=False, blur=0.0, brightness=0.0, glare=1.0,
            contrast=0.0, resolution_min=0,
            tips=["Image could not be read. Please retake the photo."],
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = gray.shape[:2]

    # Blur: Laplacian variance (higher = sharper)
    blur_val = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Brightness: mean of V channel (0–1)
    brightness_val = float(hsv[:, :, 2].mean()) / 255.0

    # Glare: fraction of pixels with V >= 250
    glare_val = float(np.count_nonzero(hsv[:, :, 2] >= 250)) / (h * w)

    # Contrast: std-dev of grayscale
    contrast_val = float(gray.std())

    # Resolution
    res_min = min(h, w)

    tips: list[str] = []

    blur_ok       = blur_val       >= QUALITY_BLUR_MIN
    bright_ok     = QUALITY_BRIGHTNESS_MIN <= brightness_val <= QUALITY_BRIGHTNESS_MAX
    glare_ok      = glare_val      <= QUALITY_GLARE_MAX
    contrast_ok   = contrast_val   >= QUALITY_CONTRAST_MIN
    res_ok        = res_min        >= QUALITY_RESOLUTION_MIN

    if not blur_ok:
        tips.append("Hold steady — image appears blurry.")
    if not bright_ok:
        if brightness_val < QUALITY_BRIGHTNESS_MIN:
            tips.append("More light needed.")
        else:
            tips.append("Image is overexposed — reduce direct light.")
    if not glare_ok:
        tips.append("Reduce glare, tilt the pack.")
    if not contrast_ok:
        tips.append("Move closer for clearer print detail.")
    if not res_ok:
        tips.append("Move closer to the pack.")

    ok = blur_ok and bright_ok and glare_ok and contrast_ok and res_ok

    return QualityReport(
        ok=ok,
        blur=round(blur_val, 2),
        brightness=round(brightness_val, 3),
        glare=round(glare_val, 4),
        contrast=round(contrast_val, 2),
        resolution_min=res_min,
        tips=tips,
    )
