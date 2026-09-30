"""
tests/test_quality.py — Image quality assessment tests.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.quality import assess_quality


def _make_image(blur: bool = False, dark: bool = False, glare: bool = False, size=(640, 480)) -> bytes:
    """Create a synthetic test image."""
    w, h = size
    img = np.ones((h, w, 3), dtype=np.uint8) * 180  # mid-grey

    # Add text to simulate a medicine pack
    cv2.putText(img, "BATCH: TEST-001", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (30, 30, 30), 2)
    cv2.putText(img, "EXP: 11/2026", (50, 160), cv2.FONT_HERSHEY_SIMPLEX, 1, (30, 30, 30), 2)

    if dark:
        img = (img * 0.1).astype(np.uint8)

    if glare:
        # Add a bright patch
        img[100:300, 200:500] = 255

    if blur:
        img = cv2.GaussianBlur(img, (51, 51), 30)

    _, buf = cv2.imencode(".jpg", img)
    return bytes(buf)


class TestQualityAssessment:
    def test_good_image_passes(self):
        img = _make_image()
        report = assess_quality(img)
        assert report.ok is True
        assert report.blur > 0
        assert 0 <= report.brightness <= 1

    def test_blurry_image_fails(self):
        img = _make_image(blur=True)
        report = assess_quality(img)
        assert report.ok is False
        assert any("blurry" in t.lower() or "steady" in t.lower() for t in report.tips)

    def test_dark_image_fails(self):
        img = _make_image(dark=True)
        report = assess_quality(img)
        assert report.ok is False
        assert any("light" in t.lower() for t in report.tips)

    def test_glare_fails(self):
        img = _make_image(glare=True)
        report = assess_quality(img)
        assert report.ok is False

    def test_invalid_bytes(self):
        report = assess_quality(b"not an image")
        assert report.ok is False
        assert report.resolution_min == 0

    def test_metrics_are_floats(self):
        img = _make_image()
        report = assess_quality(img)
        assert isinstance(report.blur, float)
        assert isinstance(report.brightness, float)
        assert isinstance(report.glare, float)
        assert isinstance(report.contrast, float)
        assert isinstance(report.resolution_min, int)
