"""
app/main.py — FastAPI application entry point.

CORS for localhost:5173.
Static /media directory for heatmap images.
Global exception handler (never exposes stack traces).
"""

from __future__ import annotations
import logging
import io
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, APP_VERSION, MEDIA_DIR, FRONTEND_DIR
from app.db import engine, Base, SessionLocal

# Create all tables
Base.metadata.create_all(bind=engine)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Startup checks ────────────────────────────────────────────────────────

def _check_components() -> dict[str, bool]:
    """Report optional component availability at startup."""
    checks: dict[str, bool] = {}

    try:
        import easyocr
        checks["easyocr"] = True
    except ImportError:
        checks["easyocr"] = False

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        checks["tesseract"] = True
    except Exception:
        checks["tesseract"] = False

    try:
        from pylibdmtx.pylibdmtx import decode
        checks["pylibdmtx"] = True
    except Exception:
        checks["pylibdmtx"] = False

    try:
        import torchvision
        checks["mobilenet"] = True
    except ImportError:
        checks["mobilenet"] = False

    from app.config import PATCHCORE_ENABLED
    checks["patchcore"] = PATCHCORE_ENABLED and checks.get("mobilenet", False)

    return checks


_component_status: dict[str, bool] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _component_status
    _component_status = _check_components()
    logger.info("MedSure Vision backend starting — components: %s", _component_status)

    # Bootstrap default admin user if no users exist
    try:
        from app.db import SessionLocal as _SL
        from app.auth.service import ensure_default_admin
        _db = _SL()
        ensure_default_admin(_db)
        _db.close()
    except Exception as _e:
        logger.warning("[auth] Default admin bootstrap failed: %s", _e)

    # Start APScheduler for daily regulatory recall sync
    try:
        from app.sync.recall_sync import start_scheduler
        start_scheduler()
    except Exception as _e:
        logger.warning("[sync] Scheduler start failed: %s", _e)

    # Lazy-warm EasyOCR in background (don't block startup)
    try:
        from app.pipeline.ocr import _get_easyocr
        _get_easyocr()
    except Exception:
        pass

    yield

    # Shutdown scheduler
    try:
        from app.sync.recall_sync import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    logger.info("MedSure Vision backend shutting down")


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="MedSure Vision API",
    version=APP_VERSION,
    description="AI-assisted first-line screening tool for medicine packs.",
    lifespan=lifespan,
)

# CORS — allow Authorization header so JWT works from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
)

# Static media (heatmap PNGs)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


# ── Frontend static files (same-origin for PWA service worker) ───────────

from fastapi.responses import RedirectResponse, FileResponse

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect bare root to index.html so the PWA installs correctly."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))

if FRONTEND_DIR.exists():
    # Mount after API routes registration so /scan etc. take priority.
    # We do a late mount at the end of the file — see bottom of main.py.
    _frontend_dir_ready = True
else:
    _frontend_dir_ready = False
    logger.warning("Frontend directory not found at %s — serving API only.", FRONTEND_DIR)



# ── Global exception handler ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s — %s %s", exc, request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
    )


# ── Routes ────────────────────────────────────────────────────────────────

from app.routes import scan, scans, serial, batch, alerts, stats, receiving
from app.routes import auth as auth_routes
from app.routes import admin as admin_routes
from fastapi import Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db import get_db

# Ensure User table exists (auth models are in app.auth.models)
from app.auth.models import User as _UserModel  # noqa: F401

app.include_router(scan.router)
app.include_router(scans.router)
app.include_router(serial.router)
app.include_router(batch.router)
app.include_router(alerts.router)
app.include_router(stats.router)
app.include_router(receiving.router)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)



# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = "ok"
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        db_ok = "error"

    # Visual embedding coverage
    from app.config import EMBEDDINGS_PATH, MEDICINES_JSON
    import json as _json
    visual_covered = 0
    total_medicines = 0
    try:
        total_medicines = len(_json.load(open(MEDICINES_JSON)))
        if EMBEDDINGS_PATH.exists():
            import numpy as np
            emb = np.load(str(EMBEDDINGS_PATH), allow_pickle=False)
            visual_covered = len(emb.files)
    except Exception:
        pass

    global _component_status
    if not _component_status:
        _component_status = _check_components()
    components = dict(_component_status)
    visual_ready = (visual_covered > 0) and bool(components.get("mobilenet", False))
    components["visual_layer_ready"] = visual_ready
    components["visual_medicines_covered"] = visual_covered
    components["total_medicines"] = total_medicines

    return {
        "status": "ok",
        "visual_layer_ready": visual_ready,
        "visual_medicines_covered": visual_covered,
        "components": components,
        "db": db_ok,
        "version": APP_VERSION,
    }



# ── PDF report endpoint ───────────────────────────────────────────────────

@app.get("/scans/{scan_id}/report.pdf")
def scan_pdf(
    scan_id: str,
    db: Session = Depends(get_db),
):
    from app.models import Scan
    from app.reports.pdf import generate_scan_pdf

    row = db.query(Scan).filter(Scan.id == scan_id).first()
    if row is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Scan not found"}},
        )

    pdf_bytes = generate_scan_pdf(row.result_json or {})
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}.pdf"},
    )


# ── Frontend static mount (MUST be last — catch-all) ─────────────────────
# All unmatched paths fall through to the frontend SPA.
# API routes registered above take priority because they were added first.
if _frontend_dir_ready:
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    logger.info("Frontend served from %s at http://localhost:8000/", FRONTEND_DIR)
