"""
app/config.py — Central configuration for MedSure Vision backend.
All thresholds live here so they can be tuned without touching pipeline code.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = BASE_DIR / "data"
MEDIA_DIR = BASE_DIR / "media"
DEMO_CASES_DIR = DATA_DIR / "demo_cases"
REFERENCE_IMAGES_DIR = DATA_DIR / "reference_images"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"
MEDICINES_JSON = DATA_DIR / "medicines.json"
ALERTS_JSON = DATA_DIR / "alerts.json"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# ── Database ───────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'medsure.db'}"
)

# ── Privacy / hashing ──────────────────────────────────────────────────────
# HMAC-SHA256 salt for serial and batch hashes.
# Override with MEDSURE_HASH_SALT env var in production.
HASH_SALT: str = os.environ.get("MEDSURE_HASH_SALT", "medsure-dev-salt-change-in-prod")

# ── Quality thresholds ─────────────────────────────────────────────────────
QUALITY_BLUR_MIN: float = float(os.environ.get("QUALITY_BLUR_MIN", "80.0"))
QUALITY_BRIGHTNESS_MIN: float = float(os.environ.get("QUALITY_BRIGHTNESS_MIN", "0.20"))
QUALITY_BRIGHTNESS_MAX: float = float(os.environ.get("QUALITY_BRIGHTNESS_MAX", "0.95"))
QUALITY_GLARE_MAX: float = float(os.environ.get("QUALITY_GLARE_MAX", "0.15"))
QUALITY_CONTRAST_MIN: float = float(os.environ.get("QUALITY_CONTRAST_MIN", "15.0"))
QUALITY_RESOLUTION_MIN: int = int(os.environ.get("QUALITY_RESOLUTION_MIN", "180"))

# ── OCR confidence ─────────────────────────────────────────────────────────
# Fields below this threshold are "unclear" — never count as confirmed mismatch.
OCR_CONFIDENCE_MIN: float = float(os.environ.get("OCR_CONFIDENCE_MIN", "0.55"))

# ── Fuzzy name match ───────────────────────────────────────────────────────
NAME_FUZZY_OK: int = int(os.environ.get("NAME_FUZZY_OK", "95"))
NAME_FUZZY_WARN: int = int(os.environ.get("NAME_FUZZY_WARN", "80"))

# ── Expiry / shelf-life ────────────────────────────────────────────────────
# Max shelf life in months before a flag is raised.
SHELF_LIFE_MAX_MONTHS: int = int(os.environ.get("SHELF_LIFE_MAX_MONTHS", "60"))

# ── Clone / scan-event signals ─────────────────────────────────────────────
# Speed above this (km/h) between distinct device tokens = impossible travel.
CLONE_SPEED_KMH: float = float(os.environ.get("CLONE_SPEED_KMH", "900.0"))
# Distinct device count above this for a batch = moderate clone signal.
CLONE_DEVICE_THRESHOLD: int = int(os.environ.get("CLONE_DEVICE_THRESHOLD", "5"))

# ── Soft-score bands ───────────────────────────────────────────────────────
SCORE_LOW_MAX: int = 20
SCORE_NEEDS_MAX: int = 50
# score >= 51 → high_suspicion

# ── Alert staleness ────────────────────────────────────────────────────────
ALERT_STALE_DAYS: int = int(os.environ.get("ALERT_STALE_DAYS", "45"))

# ── Rate limits ────────────────────────────────────────────────────────────
RATE_SCAN_PER_HOUR: int = int(os.environ.get("RATE_SCAN_PER_HOUR", "60"))
RATE_REPORT_PER_DAY: int = int(os.environ.get("RATE_REPORT_PER_DAY", "1"))

# ── Feature flags ──────────────────────────────────────────────────────────
VISUAL_ENABLED: bool = os.environ.get("VISUAL_ENABLED", "true").lower() == "true"
PATCHCORE_ENABLED: bool = os.environ.get("PATCHCORE_ENABLED", "false").lower() == "true"
SSIM_ENABLED: bool = os.environ.get("SSIM_ENABLED", "false").lower() == "true"

# ── CORS ───────────────────────────────────────────────────────────────────
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:5500",
    "http://localhost:8080",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:8080",
    "null",               # file:// origin when opened directly in browser
]

# ── App meta ───────────────────────────────────────────────────────────────
APP_VERSION: str = "1.0.0"
