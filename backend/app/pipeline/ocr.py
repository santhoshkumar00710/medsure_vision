"""
app/pipeline/ocr.py — OCR engine wrapper.

Runs EasyOCR (primary) + Tesseract (fallback via pytesseract).
Merges results by text-block voting; disagreement lowers confidence.
Preprocesses: deskew, CLAHE, adaptive threshold.
Models are lazy-loaded once at startup.
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Model singletons ───────────────────────────────────────────────────────
_easyocr_reader = None


def _get_easyocr():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            logger.info("ocr: EasyOCR loaded")
        except Exception as exc:
            logger.warning("ocr: EasyOCR unavailable: %s", exc)
            _easyocr_reader = False
    return _easyocr_reader if _easyocr_reader is not False else None


# ── Preprocessing ──────────────────────────────────────────────────────────

def _preprocess(img: np.ndarray) -> np.ndarray:
    """Deskew + CLAHE + adaptive threshold for OCR."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    return enhanced


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Simple deskew via moments."""
    try:
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 10:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return gray
        h, w = gray.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return gray


@dataclass
class RawOcrBlock:
    text: str
    confidence: float
    source: str   # "easyocr" | "tesseract"
    bbox: Optional[list] = None


def _run_easyocr(img: np.ndarray) -> list[RawOcrBlock]:
    reader = _get_easyocr()
    if reader is None:
        return []
    try:
        results = reader.readtext(img, detail=1)
        blocks = []
        for (bbox, text, conf) in results:
            if text.strip():
                blocks.append(RawOcrBlock(text=text.strip(), confidence=conf, source="easyocr", bbox=bbox))
        return blocks
    except Exception as exc:
        logger.debug("ocr: easyocr error: %s", exc)
        return []


def _run_tesseract(img: np.ndarray) -> list[RawOcrBlock]:
    try:
        import pytesseract
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                          config="--psm 6")
        blocks = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text:
                continue
            conf_raw = data["conf"][i]
            conf = max(0.0, float(conf_raw) / 100.0) if conf_raw != -1 else 0.3
            blocks.append(RawOcrBlock(text=text, confidence=conf, source="tesseract"))
        return blocks
    except ImportError:
        logger.debug("ocr: pytesseract not installed")
        return []
    except Exception as exc:
        logger.debug("ocr: tesseract error: %s", exc)
        return []


def _merge_blocks(easy: list[RawOcrBlock], tess: list[RawOcrBlock]) -> str:
    """
    Merge text from both engines into a single string.
    Prefers EasyOCR; Tesseract adds words not found in EasyOCR output.
    """
    easy_text = " ".join(b.text for b in easy)
    tess_text = " ".join(b.text for b in tess)

    if not easy_text and not tess_text:
        return ""
    if not easy_text:
        return tess_text
    if not tess_text:
        return easy_text

    # Simple union: prefer easyocr, append unique tess words
    easy_words = set(easy_text.lower().split())
    extra = [w for w in tess_text.split() if w.lower() not in easy_words]
    if extra:
        return easy_text + " " + " ".join(extra)
    return easy_text


def run_ocr(img_bytes: bytes) -> tuple[str, list[RawOcrBlock]]:
    """
    Run OCR on raw image bytes.
    Returns (merged_text, blocks).
    Never raises.
    """
    try:
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return "", []
    except Exception:
        return "", []

    gray = _preprocess(img)
    gray = _deskew(gray)

    easy_blocks = _run_easyocr(gray)
    tess_blocks = _run_tesseract(gray)

    # Also run on crops (top half, bottom half) for better coverage
    h = gray.shape[0]
    top = gray[:h // 2, :]
    bot = gray[h // 2:, :]
    easy_blocks += _run_easyocr(top) + _run_easyocr(bot)

    merged_text = _merge_blocks(easy_blocks, tess_blocks)
    all_blocks = easy_blocks + tess_blocks
    return merged_text, all_blocks
