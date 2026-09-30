"""
app/pipeline/fields.py — Field extraction and validation from OCR text.

Extracts: name, strength, form, batch, mfg_date, expiry, manufacturer.
Each field returns { value, confidence }.
Validators: name fuzzy match, expiry logic, strength plausibility.
All date parsing wrapped in try/except — never raises.
"""

from __future__ import annotations
import re
import json
import logging
import calendar
from datetime import date
from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path

from app.config import (
    OCR_CONFIDENCE_MIN,
    NAME_FUZZY_OK,
    NAME_FUZZY_WARN,
    SHELF_LIFE_MAX_MONTHS,
    MEDICINES_JSON,
)

logger = logging.getLogger(__name__)

# ── Medicine database (lazy loaded) ───────────────────────────────────────
_medicines: Optional[list[dict]] = None


def _load_medicines() -> list[dict]:
    global _medicines
    if _medicines is None:
        try:
            with open(MEDICINES_JSON, "r", encoding="utf-8") as f:
                _medicines = json.load(f)
        except Exception as exc:
            logger.warning("fields: could not load medicines.json: %s", exc)
            _medicines = []
    return _medicines


# ── Field result dataclass ─────────────────────────────────────────────────

@dataclass
class FieldResult:
    value: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ExtractedFields:
    name: FieldResult = field(default_factory=FieldResult)
    strength: FieldResult = field(default_factory=FieldResult)
    form: FieldResult = field(default_factory=FieldResult)
    batch: FieldResult = field(default_factory=FieldResult)
    mfg_date: FieldResult = field(default_factory=FieldResult)
    expiry: FieldResult = field(default_factory=FieldResult)
    manufacturer: FieldResult = field(default_factory=FieldResult)

    # Validation flags (used by rules.py)
    name_flag: Optional[str] = None    # "ok" | "possible_misspelling" | "unknown_name"
    expiry_flag: Optional[str] = None  # "expired" | "expiry_before_mfg" | "shelf_life_exceeded" | "unparseable"
    matched_medicine: Optional[dict] = None


# ── Regex patterns ─────────────────────────────────────────────────────────

_BATCH_RE = re.compile(
    r"""(?:
        B\.?\s*No\.?         |   # B.No. / B No
        Batch\s*No\.?        |   # Batch No / Batch No.
        \bBatch\b            |   # Batch
        \bBN\b               |   # BN
        B\s+NO               |   # B NO
        Lot\s*No\.?          |   # Lot No
        MFG\.?\s*Batch       |   # MFG. Batch
        \bLot\b                  # Lot
    )[:\s.]*([A-Z0-9][\w\-/]{1,20})""",
    re.IGNORECASE | re.VERBOSE,
)

_STRENGTH_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|IU|µg|mEq)\b",
    re.IGNORECASE,
)
_FORM_RE = re.compile(
    r"\b(tablet|capsule|injection|syrup|suspension|cream|ointment|gel|drops|solution|powder|inhaler|patch)\b",
    re.IGNORECASE,
)
_MFG_RE = re.compile(
    r"(?:Mfd\.?\s*(?:By|Date)?|Mfg\.?\s*(?:Date)?|Manufactured\s+By)[:\s]*([A-Za-z0-9\s\.,&()\-]+?)(?=\n|Exp|Batch|$)",
    re.IGNORECASE | re.DOTALL,
)

# ── Month name → number ────────────────────────────────────────────────────
_MONTH_MAP = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
}

# Date patterns — ordered most-specific to least-specific
_EXPIRY_PATTERNS = [
    # EXP. DT / E.D. / EXP MM/YYYY (4-digit year)
    (re.compile(r"(?:EXP(?:IRY|IRES?)?\.?\s*(?:DT|DATE)?|E\.D\.)[:\s]*(\d{1,2})[/\-\.](\d{4})", re.IGNORECASE), "mm_yyyy"),
    # EXP MM/YYYY without prefix keywords
    (re.compile(r"(?:EXP|Expiry|Expires?|Use\s+before)[:\s]*(\d{1,2})[/\-\.](\d{4})", re.IGNORECASE), "mm_yyyy"),
    # EXP MM-YY (2-digit year)
    (re.compile(r"(?:EXP(?:IRY)?\.?\s*(?:DT)?|E\.D\.)[:\s]*(\d{1,2})[/\-](\d{2})(?!\d)", re.IGNORECASE), "mm_yy"),
    (re.compile(r"(?:EXP|Expiry|Expires?)[:\s]*(\d{1,2})[/\-](\d{2})(?!\d)", re.IGNORECASE), "mm_yy"),
    # EXP DD/MM/YYYY
    (re.compile(r"(?:EXP|Expiry)[:\s]*(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", re.IGNORECASE), "dd_mm_yyyy"),
    # MAY 2027 / MAY-2027
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\.](\d{4})\b", re.IGNORECASE), "mon_yyyy"),
    # EXP 05.2027
    (re.compile(r"(?:EXP|Expiry)[:\s]*(\d{1,2})\.(\d{4})", re.IGNORECASE), "mm_yyyy"),
]

_MFG_DATE_PATTERNS = [
    # MFG. DT / M.D. / Mfg / Manufacturing Date / Manuf. / Manufactured
    (re.compile(r"(?:MFG(?:\.?\s*D(?:T|ATE)?)?|M\.?D\.?|Manuf(?:\.|\b|acturing)?\s*(?:Date)?|Manufactured)[:\s\.]*(\d{1,2})[/\-\.](\d{4})", re.IGNORECASE), "mm_yyyy"),
    (re.compile(r"(?:MFD|Mfd\.?)[:\s\.]*(\d{1,2})[/\-\.](\d{4})", re.IGNORECASE), "mm_yyyy"),
    (re.compile(r"(?:MFG(?:\.?\s*D(?:T|ATE)?)?|M\.?D\.?|MFD|Mfd\.?|Manuf(?:\.|\b|acturing)?\s*(?:Date)?|Manufactured)[:\s\.]*(\d{1,2})[/\-](\d{2})(?!\d)", re.IGNORECASE), "mm_yy"),
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\.](\d{4})\b", re.IGNORECASE), "mon_yyyy"),
]


def _parse_date_mm_yyyy(text: str, patterns) -> Optional[str]:
    """Try all patterns; return MM/YYYY string or None. Never raises."""
    for pattern, fmt in patterns:
        try:
            m = pattern.search(text)
            if not m:
                continue
            if fmt == "mm_yyyy":
                mm, yyyy = int(m.group(1)), int(m.group(2))
                if 1 <= mm <= 12 and 1990 <= yyyy <= 2100:
                    return f"{mm:02d}/{yyyy}"
            elif fmt == "mm_yy":
                mm, yy = int(m.group(1)), int(m.group(2))
                yyyy = 2000 + yy if yy < 50 else 1900 + yy
                if 1 <= mm <= 12:
                    return f"{mm:02d}/{yyyy}"
            elif fmt == "dd_mm_yyyy":
                _, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= mm <= 12 and 1990 <= yyyy <= 2100:
                    return f"{mm:02d}/{yyyy}"
            elif fmt == "mon_yyyy":
                mon = _MONTH_MAP.get(m.group(1)[:3].lower())
                yyyy = int(m.group(2))
                if mon and 1990 <= yyyy <= 2100:
                    return f"{mon:02d}/{yyyy}"
        except Exception:
            continue
    return None


# ── Standalone parse helpers (also used by tests) ─────────────────────────

def _parse_batch(text: str) -> Optional[str]:
    """Extract batch number from OCR text. Returns raw string or None."""
    m = _BATCH_RE.search(text)
    return m.group(1).strip() if m else None


def _parse_expiry(text: str) -> Optional[str]:
    """Extract expiry date from OCR text. Returns MM/YYYY or raw match or None."""
    return _parse_date_mm_yyyy(text, _EXPIRY_PATTERNS)


def _parse_mfg_date(text: str) -> Optional[str]:
    """Extract manufacturing date from OCR text. Returns MM/YYYY or None."""
    return _parse_date_mm_yyyy(text, _MFG_DATE_PATTERNS)



def _expiry_to_date(expiry: str) -> Optional[date]:
    """Convert MM/YYYY to date (last day of month). Never raises."""
    try:
        parts = expiry.split("/")
        mm, yyyy = int(parts[0]), int(parts[1])
        last_day = calendar.monthrange(yyyy, mm)[1]
        return date(yyyy, mm, last_day)
    except Exception:
        return None


def _mfg_to_date(mfg: str) -> Optional[date]:
    """Convert MM/YYYY to first of month. Never raises."""
    try:
        parts = mfg.split("/")
        mm, yyyy = int(parts[0]), int(parts[1])
        return date(yyyy, mm, 1)
    except Exception:
        return None


# ── Name fuzzy match ───────────────────────────────────────────────────────

def _fuzzy_name_match(name: str) -> tuple[Optional[dict], str, float]:
    """
    Returns (matched_medicine, flag, score).
    flag: "ok" | "possible_misspelling" | "unknown_name"
    """
    medicines = _load_medicines()
    if not medicines or not name:
        return None, "unknown_name", 0.0

    try:
        from rapidfuzz import fuzz, process

        all_names: list[str] = []
        med_map: dict[str, dict] = {}
        for med in medicines:
            for n in [med.get("name", ""), med.get("generic", "")] + med.get("aliases", []):
                if n:
                    all_names.append(n)
                    med_map[n] = med

        if not all_names:
            return None, "unknown_name", 0.0

        result = process.extractOne(name, all_names, scorer=fuzz.token_set_ratio)
        if result is None:
            return None, "unknown_name", 0.0

        best_name, score, _ = result
        matched_med = med_map.get(best_name)

        if score >= NAME_FUZZY_OK:
            return matched_med, "ok", score / 100.0
        elif score >= NAME_FUZZY_WARN:
            return matched_med, "possible_misspelling", score / 100.0
        else:
            return None, "unknown_name", score / 100.0

    except ImportError:
        return None, "unknown_name", 0.0
    except Exception as exc:
        logger.debug("fields: fuzzy match error: %s", exc)
        return None, "unknown_name", 0.0


# ── Main extraction ────────────────────────────────────────────────────────

def extract_fields(text: str, avg_block_confidence: float = 0.7) -> ExtractedFields:
    """
    Extract structured fields from raw OCR text.
    avg_block_confidence is the mean EasyOCR confidence for all blocks.
    """
    result = ExtractedFields()

    # ── Batch ──────────────────────────────────────────────────────────────
    m = _BATCH_RE.search(text)
    if m:
        batch_val = m.group(1).strip().upper()
        result.batch = FieldResult(value=batch_val, confidence=min(avg_block_confidence + 0.1, 1.0))

    # ── Strength ──────────────────────────────────────────────────────────
    m = _STRENGTH_RE.search(text)
    if m:
        strength_val = f"{m.group(1)}{m.group(2).lower()}"
        result.strength = FieldResult(value=strength_val, confidence=avg_block_confidence)

    # ── Form ──────────────────────────────────────────────────────────────
    m = _FORM_RE.search(text)
    if m:
        result.form = FieldResult(value=m.group(1).capitalize(), confidence=avg_block_confidence)

    # ── Expiry ────────────────────────────────────────────────────────────
    expiry_val = _parse_date_mm_yyyy(text, _EXPIRY_PATTERNS)
    if expiry_val:
        result.expiry = FieldResult(value=expiry_val, confidence=min(avg_block_confidence + 0.05, 1.0))
    else:
        result.expiry_flag = "unparseable"

    # ── Mfg date ──────────────────────────────────────────────────────────
    mfg_val = _parse_date_mm_yyyy(text, _MFG_DATE_PATTERNS)
    if mfg_val:
        result.mfg_date = FieldResult(value=mfg_val, confidence=avg_block_confidence)

    # ── Manufacturer ──────────────────────────────────────────────────────
    m = _MFG_RE.search(text)
    if m:
        mfg_name = m.group(1).strip().rstrip(".,")
        if len(mfg_name) > 3:
            result.manufacturer = FieldResult(value=mfg_name, confidence=avg_block_confidence * 0.85)

    # ── Name — extract first substantial line or use strength context ──────
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 5]
    if lines:
        # Heuristic: longest line in the first 5 that contains a letter
        candidate = max(lines[:5], key=len, default="")
        if candidate:
            result.name = FieldResult(value=candidate[:80], confidence=avg_block_confidence * 0.8)

    # ── Name fuzzy validation ─────────────────────────────────────────────
    if result.name.value:
        matched, flag, name_conf = _fuzzy_name_match(result.name.value)
        result.name_flag = flag
        result.matched_medicine = matched
        # Blend OCR confidence with fuzzy confidence
        result.name.confidence = (result.name.confidence + name_conf) / 2

    # ── Expiry validation ─────────────────────────────────────────────────
    _validate_expiry(result)

    return result


def _validate_expiry(result: ExtractedFields) -> None:
    """Set expiry_flag based on logic. Never raises."""
    if not result.expiry.value:
        return

    today = date.today()
    exp_date = _expiry_to_date(result.expiry.value)
    if exp_date is None:
        result.expiry_flag = "unparseable"
        return

    if exp_date < today:
        result.expiry_flag = "expired"
        return

    # Expiry before manufacture date
    if result.mfg_date.value:
        mfg_date = _mfg_to_date(result.mfg_date.value)
        if mfg_date and exp_date < mfg_date:
            result.expiry_flag = "expiry_before_mfg"
            return
        # Shelf life
        if mfg_date:
            months = (exp_date.year - mfg_date.year) * 12 + (exp_date.month - mfg_date.month)
            if months > SHELF_LIFE_MAX_MONTHS:
                result.expiry_flag = "shelf_life_exceeded"
                return
