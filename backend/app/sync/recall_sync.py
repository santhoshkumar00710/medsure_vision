"""
app/sync/recall_sync.py — Task 3: Regulatory Recall Auto-Sync

Pulls medicine recall / alert data from publicly accessible sources:
  1. CDSCO (India) — scrapes the Not-of-Standard-Quality (NSQ) drug list
     from the official CDSCO Drug Alerts endpoint.
  2. FDA (USA)  — OpenFDA drug enforcement recalls endpoint (JSON API).

Runs as:
  - A FastAPI background task (triggered via POST /admin/sync-alerts)
  - An APScheduler cron job (daily at 02:00 UTC) registered on app startup.

Design decisions:
  - All ingested rows get simulated=False and a snapshot_date.
  - Duplicate detection: SHA-256 of (brand_lower, batch_norm, source).
  - No external API keys needed — CDSCO HTML scrape + OpenFDA public API.
  - Errors are caught per-source so one failure doesn't block the other.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

OPENFDA_URL = (
    "https://api.fda.gov/drug/enforcement.json"
    "?search=status:Ongoing&limit=50&sort=report_date:desc"
)

CDSCO_ALERTS_URL = (
    "https://cdsco.gov.in/opencms/export/sites/CDSCO_WEB/drug-alert/"
    "drug-alerts.json"
)


# ── Normalise helpers ──────────────────────────────────────────────────────

def _normalise_batch(b: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", b.upper()) if b else ""


def _alert_id(brand: str, batch_norm: str, source: str) -> str:
    key = f"{brand.lower()}|{batch_norm}|{source}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ── Source: OpenFDA enforcement recalls ───────────────────────────────────

def _fetch_openfda() -> list[dict[str, Any]]:
    """Fetch recent drug enforcement recalls from OpenFDA (public, no API key)."""
    import urllib.request

    rows: list[dict] = []
    try:
        req = urllib.request.Request(OPENFDA_URL, headers={"User-Agent": "MedSure/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        logger.warning("[recall_sync] OpenFDA fetch failed: %s", exc)
        return []

    today_str = date.today().isoformat()
    for item in data.get("results", []):
        brand = (item.get("product_description") or item.get("brand_name") or "").strip()
        if not brand:
            continue
        batch_raw  = (item.get("lot_number") or "").strip()
        batch_norm = _normalise_batch(batch_raw)
        reason     = (item.get("reason_for_recall") or "").strip()
        status     = (item.get("status") or "recalled").lower()
        mfg        = (item.get("recalling_firm") or "").strip()

        rows.append({
            "id":            _alert_id(brand, batch_norm, "openfda"),
            "brand":         brand[:120],
            "generic":       "",
            "batch_raw":     batch_raw[:60],
            "batch_norm":    batch_norm[:60],
            "mfg":           "",
            "exp":           "",
            "manufacturer":  mfg[:120],
            "status":        status,
            "reason":        reason[:400],
            "source_month":  date.today().strftime("%b %Y"),
            "source_url":    OPENFDA_URL,
            "snapshot_date": today_str,
            "simulated":     False,
        })
    logger.info("[recall_sync] OpenFDA: fetched %d recalls", len(rows))
    return rows


# ── Source: CDSCO alerts ──────────────────────────────────────────────────

def _fetch_cdsco() -> list[dict[str, Any]]:
    """
    Try to fetch CDSCO drug-alerts JSON endpoint.
    CDSCO availability is inconsistent so errors are caught gracefully.
    """
    import urllib.request

    rows: list[dict] = []
    today_str = date.today().isoformat()

    try:
        req = urllib.request.Request(CDSCO_ALERTS_URL, headers={"User-Agent": "MedSure/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        entries = data if isinstance(data, list) else data.get("data", [])
        for item in entries:
            brand     = (item.get("productName") or item.get("brand") or "").strip()
            batch_raw = (item.get("batchNo") or item.get("batch") or "").strip()
            if not brand:
                continue
            batch_norm = _normalise_batch(batch_raw)
            rows.append({
                "id":            _alert_id(brand, batch_norm, "cdsco"),
                "brand":         brand[:120],
                "generic":       (item.get("genericName") or "")[:120],
                "batch_raw":     batch_raw[:60],
                "batch_norm":    batch_norm[:60],
                "mfg":           "",
                "exp":           "",
                "manufacturer":  (item.get("manufacturerName") or "")[:120],
                "status":        "recalled",
                "reason":        (item.get("reason") or "")[:400],
                "source_month":  date.today().strftime("%b %Y"),
                "source_url":    CDSCO_ALERTS_URL,
                "snapshot_date": today_str,
                "simulated":     False,
            })
        logger.info("[recall_sync] CDSCO: fetched %d alerts", len(rows))
    except Exception as exc:
        logger.warning("[recall_sync] CDSCO endpoint unavailable (%s) — skipping.", exc)

    return rows


# ── Merge into DB ─────────────────────────────────────────────────────────

def sync_alerts_to_db(db) -> dict[str, Any]:
    """
    Fetch alerts from all sources and upsert new rows into the DB Alert table.
    Returns a summary dict with counts per source.
    """
    from app.models import Alert

    all_new: list[dict] = []
    all_new.extend(_fetch_openfda())
    all_new.extend(_fetch_cdsco())

    if not all_new:
        return {
            "fetched": 0, "added": 0, "skipped": 0,
            "sources": [], "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    # Load existing IDs from DB (avoid full row fetch)
    existing_ids: set[str] = {row[0] for row in db.query(Alert.id).all()}
    added = 0
    skipped = 0

    for row in all_new:
        if row["id"] in existing_ids:
            skipped += 1
            continue
        alert = Alert(
            id=row["id"],
            brand=row["brand"],
            generic=row.get("generic", ""),
            batch_norm=row["batch_norm"],
            batch_raw=row.get("batch_raw", ""),
            mfg=row.get("mfg", ""),
            exp=row.get("exp", ""),
            manufacturer=row.get("manufacturer", ""),
            status=row.get("status", "recalled"),
            reason=row.get("reason", ""),
            source_month=row.get("source_month", ""),
            source_url=row.get("source_url", ""),
            snapshot_date=row.get("snapshot_date", date.today().isoformat()),
            simulated=False,
        )
        db.add(alert)
        existing_ids.add(row["id"])
        added += 1

    if added:
        db.commit()

    summary: dict[str, Any] = {
        "fetched":   len(all_new),
        "added":     added,
        "skipped":   skipped,
        "sources":   ["openfda", "cdsco"],
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[recall_sync] Sync complete: %s", summary)
    return summary


# ── APScheduler integration ───────────────────────────────────────────────

_scheduler = None


def start_scheduler():
    """
    Start an APScheduler BackgroundScheduler that auto-syncs alerts daily at 02:00 UTC.
    Call this from the FastAPI lifespan startup hook.
    """
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.info(
            "[recall_sync] APScheduler not installed — auto-sync disabled. "
            "Install with: pip install apscheduler"
        )
        return None

    from app.db import SessionLocal

    def _job():
        db = SessionLocal()
        try:
            result = sync_alerts_to_db(db)
            logger.info("[recall_sync] Scheduled sync done: %s", result)
        except Exception as exc:
            logger.error("[recall_sync] Scheduled sync failed: %s", exc)
        finally:
            db.close()

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_job, "cron", hour=2, minute=0, id="recall_sync_daily")
    _scheduler.start()
    logger.info("[recall_sync] APScheduler started — daily sync at 02:00 UTC")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[recall_sync] APScheduler stopped")
