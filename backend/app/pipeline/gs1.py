"""
app/pipeline/gs1.py — GS1 element-string parser.

Handles:
- Symbology prefixes: ]d2, ]Q3, ]C1
- GS separator (0x1d) and bracketed (01)...(10)... format
- AIs: 01 (GTIN-14), 10 (batch), 11 (mfg date), 17 (expiry), 21 (serial)
- GTIN check-digit validation (Luhn mod-10)
- GS1 date to MM/YYYY: day 00 → last day of month
- All date parsing wrapped in try/except — never raises
"""

from __future__ import annotations
import re
import calendar
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# GS (group separator) character
GS = "\x1d"

# Symbology prefixes to strip
SYMBOLOGY_PREFIXES = ("]d2", "]Q3", "]C1", "]e0", "]C0")

# AI definitions: ai -> (min_len, max_len, fixed)
_AI_SPECS: dict[str, tuple[int, int]] = {
    "01": (14, 14),   # GTIN-14
    "10": (1, 20),    # Batch/lot
    "11": (6, 6),     # Mfg date YYMMDD
    "17": (6, 6),     # Expiry date YYMMDD
    "21": (1, 20),    # Serial
}

FIXED_LENGTH_AIS = {"01", "11", "17"}


@dataclass
class GS1Payload:
    gtin: Optional[str] = None
    batch: Optional[str] = None
    mfg_date: Optional[str] = None      # MM/YYYY
    expiry: Optional[str] = None        # MM/YYYY
    serial: Optional[str] = None
    gtin_valid: bool = False
    parse_errors: list[str] = field(default_factory=list)


def _strip_prefix(raw: str) -> str:
    for prefix in SYMBOLOGY_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix):]
    return raw


def _gs1_date_to_mmyyyy(yymmdd: str) -> Optional[str]:
    """Convert GS1 YYMMDD to MM/YYYY. Day 00 = last day of month. Never raises."""
    try:
        yy = int(yymmdd[0:2])
        mm = int(yymmdd[2:4])
        dd = int(yymmdd[4:6])
        if not (1 <= mm <= 12):
            return None
        # Pivot year: 00-49 = 2000-2049, 50-99 = 1950-1999
        yyyy = 2000 + yy if yy < 50 else 1900 + yy
        if dd == 0:
            dd = calendar.monthrange(yyyy, mm)[1]
        if not (1 <= dd <= 31):
            return None
        return f"{mm:02d}/{yyyy}"
    except Exception:
        return None


def _luhn_check(gtin: str) -> bool:
    """Validate GTIN check digit using GS1 Luhn (mod-10). Must be 14 digits."""
    try:
        if len(gtin) != 14 or not gtin.isdigit():
            return False
        digits = [int(c) for c in gtin]
        check = digits[-1]
        total = 0
        for i, d in enumerate(reversed(digits[:-1])):
            total += d * 3 if i % 2 == 0 else d
        expected = (10 - (total % 10)) % 10
        return expected == check
    except Exception:
        return False


def _parse_bracketed(raw: str) -> GS1Payload:
    """Parse (01)...(10)... bracketed GS1 format."""
    pattern = re.compile(r'\((\d{2,4})\)([^(]*)')
    result = GS1Payload()
    for m in pattern.finditer(raw):
        ai, value = m.group(1), m.group(2).strip()
        _apply_ai(result, ai, value)
    return result


def _parse_gs_delimited(raw: str) -> GS1Payload:
    """Parse GS-delimited or continuous GS1 element string."""
    result = GS1Payload()
    pos = 0
    n = len(raw)

    while pos < n:
        # Try to read AI
        for ai_len in (4, 3, 2):
            if pos + ai_len > n:
                continue
            candidate_ai = raw[pos: pos + ai_len]
            if candidate_ai in _AI_SPECS:
                ai = candidate_ai
                pos += ai_len
                min_l, max_l = _AI_SPECS[ai]
                if ai in FIXED_LENGTH_AIS:
                    value = raw[pos: pos + max_l]
                    pos += max_l
                else:
                    # Variable length: read until GS or end
                    end = raw.find(GS, pos)
                    if end == -1:
                        end = n
                    value = raw[pos:end]
                    if len(value) > max_l:
                        value = value[:max_l]
                    pos = end
                    if pos < n and raw[pos] == GS:
                        pos += 1   # skip GS
                _apply_ai(result, ai, value)
                break
        else:
            # Unknown AI — skip character
            pos += 1

    return result


def _apply_ai(result: GS1Payload, ai: str, value: str) -> None:
    """Apply a parsed AI+value to the GS1Payload, handling errors gracefully."""
    value = value.strip()
    if ai == "01":
        if len(value) == 14 and value.isdigit():
            result.gtin = value
            result.gtin_valid = _luhn_check(value)
        else:
            result.parse_errors.append(f"AI 01: invalid GTIN '{value}'")
            result.gtin = value
            result.gtin_valid = False
    elif ai == "10":
        result.batch = value if value else None
    elif ai == "11":
        d = _gs1_date_to_mmyyyy(value)
        result.mfg_date = d
        if d is None:
            result.parse_errors.append(f"AI 11: unparseable mfg date '{value}'")
    elif ai == "17":
        d = _gs1_date_to_mmyyyy(value)
        result.expiry = d
        if d is None:
            result.parse_errors.append(f"AI 17: unparseable expiry '{value}'")
    elif ai == "21":
        result.serial = value if value else None


def parse_gs1(raw: str) -> GS1Payload:
    """
    Main entry point. Strips prefix, detects format, parses.
    Never raises — parse errors are recorded in payload.parse_errors.
    """
    raw = raw.strip()
    raw = _strip_prefix(raw)

    if not raw:
        p = GS1Payload()
        p.parse_errors.append("Empty payload after prefix strip")
        return p

    # Bracketed format
    if "(" in raw and ")" in raw:
        return _parse_bracketed(raw)

    # GS-delimited or continuous
    return _parse_gs_delimited(raw)
