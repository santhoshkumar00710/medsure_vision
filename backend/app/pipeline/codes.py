"""
app/pipeline/codes.py — Barcode / QR / DataMatrix decoder.

Decoder priority:
  1. pyzbar (QR, linear barcodes)
  2. pylibdmtx (DataMatrix)
  3. cv2.QRCodeDetector (fallback)

Payload type detection:
  - GS1 element string → parse with gs1.py
  - URL → parse query params, mark url_offline_note
  - Demo format: MEDSURE|gtin|batch|expiry|serial|name
  - Unknown → return raw
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np

from app.pipeline.gs1 import parse_gs1, GS1Payload

logger = logging.getLogger(__name__)


@dataclass
class DecodeResult:
    ran: bool = False
    code_type: Optional[str] = None      # gs1 | url | demo | unknown
    raw: Optional[str] = None
    gtin: Optional[str] = None
    batch: Optional[str] = None
    expiry: Optional[str] = None         # MM/YYYY
    serial: Optional[str] = None
    has_serial: bool = False
    gtin_valid: Optional[bool] = None
    payload_source: Optional[str] = None
    url_offline_note: Optional[str] = None
    gs1: Optional[GS1Payload] = None


def _try_pyzbar(img: np.ndarray) -> list[str]:
    """Try pyzbar; return list of raw decoded strings."""
    try:
        from pyzbar.pyzbar import decode
        decoded = decode(img)
        return [d.data.decode("utf-8", errors="replace") for d in decoded]
    except ImportError:
        logger.debug("codes: pyzbar not available")
        return []
    except Exception as exc:
        logger.debug("codes: pyzbar error: %s", exc)
        return []


def _try_pylibdmtx(img: np.ndarray) -> list[str]:
    """Try pylibdmtx for DataMatrix codes."""
    try:
        from pylibdmtx.pylibdmtx import decode
        decoded = decode(img)
        return [d.data.decode("utf-8", errors="replace") for d in decoded]
    except Exception as exc:
        logger.debug("codes: pylibdmtx not available or DLL missing: %s", exc)
        return []


def _try_cv2_qr(img: np.ndarray) -> list[str]:
    """Fallback: cv2 QRCodeDetector."""
    try:
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img)
        if data:
            return [data]
    except Exception as exc:
        logger.debug("codes: cv2 QR error: %s", exc)
    return []


def _looks_like_gs1(raw: str) -> bool:
    """Heuristic: starts with a known GS1 prefix or has AI markers."""
    gs1_prefixes = ("]d2", "]Q3", "]C1", "]e0", "]C0", "(01)", "01")
    if any(raw.startswith(p) for p in gs1_prefixes):
        return True
    # Starts with 14 consecutive digits = bare GTIN
    if re.match(r"^\d{14}", raw):
        return True
    return False


def _parse_url_payload(raw: str) -> DecodeResult:
    """Parse URL-type codes — extract query params where possible."""
    res = DecodeResult(
        ran=True,
        code_type="url",
        raw=raw,
        url_offline_note="This URL cannot be verified offline.",
    )
    try:
        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        # Try common query-param names
        res.gtin = (qs.get("gtin") or qs.get("01") or [None])[0]
        res.batch = (qs.get("batch") or qs.get("10") or qs.get("lot") or [None])[0]
        res.expiry = (qs.get("exp") or qs.get("17") or [None])[0]
        res.serial = (qs.get("serial") or qs.get("21") or [None])[0]
        res.has_serial = bool(res.serial)
    except Exception:
        pass
    return res


def _parse_demo_payload(raw: str) -> DecodeResult:
    """Parse MedSure demo format: MEDSURE|gtin|batch|expiry|serial|name"""
    parts = raw.split("|")
    res = DecodeResult(ran=True, code_type="demo", raw=raw, payload_source="demo")
    try:
        if len(parts) >= 5:
            res.gtin = parts[1] if len(parts) > 1 else None
            res.batch = parts[2] if len(parts) > 2 else None
            res.expiry = parts[3] if len(parts) > 3 else None
            res.serial = parts[4] if len(parts) > 4 else None
            res.has_serial = bool(res.serial)
            if res.gtin:
                from app.pipeline.gs1 import _luhn_check
                res.gtin_valid = _luhn_check(res.gtin)
    except Exception as exc:
        logger.debug("codes: demo parse error: %s", exc)
    return res


def _parse_gs1_payload(raw: str) -> DecodeResult:
    """Parse GS1 element string payload."""
    gs1 = parse_gs1(raw)
    return DecodeResult(
        ran=True,
        code_type="gs1",
        raw=raw,
        gtin=gs1.gtin,
        batch=gs1.batch,
        expiry=gs1.expiry,
        serial=gs1.serial,
        has_serial=bool(gs1.serial),
        gtin_valid=gs1.gtin_valid,
        payload_source="gs1",
        gs1=gs1,
    )


def _classify_and_parse(raw: str) -> DecodeResult:
    """Classify payload type and parse accordingly."""
    raw = raw.strip()
    if raw.upper().startswith("MEDSURE|"):
        return _parse_demo_payload(raw)
    if raw.startswith(("http://", "https://")):
        return _parse_url_payload(raw)
    if _looks_like_gs1(raw):
        return _parse_gs1_payload(raw)
    # Unknown
    return DecodeResult(ran=True, code_type="unknown", raw=raw)


def decode_codes(img_bytes: bytes) -> DecodeResult:
    """
    Attempt to decode any QR/barcode/DataMatrix from image bytes.
    Returns a DecodeResult. Never raises.
    """
    try:
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return DecodeResult(ran=False)
    except Exception as exc:
        logger.error("codes: image decode error: %s", exc)
        return DecodeResult(ran=False)

    raws: list[str] = []

    # 1. pyzbar
    raws.extend(_try_pyzbar(img))

    # 2. pylibdmtx (if no pyzbar result)
    if not raws:
        raws.extend(_try_pylibdmtx(img))

    # 3. cv2 fallback
    if not raws:
        raws.extend(_try_cv2_qr(img))

    if not raws:
        return DecodeResult(ran=True)  # ran but nothing found

    # Use the first successful decode
    best = raws[0]
    return _classify_and_parse(best)
