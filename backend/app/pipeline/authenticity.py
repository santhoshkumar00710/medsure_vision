"""
app/pipeline/authenticity.py — Authenticity layer.

1. Alert-list matcher (exact / partial / none)
2. Registry adapter (SimulatedRegistry)
3. Clone signal detector (scan_events table)
"""

from __future__ import annotations
import hashlib
import hmac
import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config import (
    HASH_SALT,
    CLONE_SPEED_KMH,
    CLONE_DEVICE_THRESHOLD,
    ALERT_STALE_DAYS,
)
from app.models import Alert, RegistrySim, ScanEvent

logger = logging.getLogger(__name__)


# ── Hashing ────────────────────────────────────────────────────────────────

def hash_field(value: str) -> str:
    """HMAC-SHA256 hash (hex) for serial / batch fields."""
    return hmac.new(
        HASH_SALT.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalise_batch(batch: str) -> str:
    """Uppercase, strip spaces/punctuation, strip common prefixes."""
    import re
    b = batch.upper().strip()
    b = re.sub(r"^(B\.?NO\.?|BATCH\s*NO\.?|LOT\s*NO\.?)\s*", "", b)
    b = re.sub(r"[\s\-./]", "", b)
    return b


# ── Alert matching ─────────────────────────────────────────────────────────

@dataclass
class AlertResult:
    match_level: str = "none"   # exact | partial | none
    alert_id: Optional[str] = None
    source_month: Optional[str] = None
    source_url: Optional[str] = None
    snapshot_date: Optional[str] = None
    snapshot_stale: bool = False


def match_alert(
    db: Session,
    name: Optional[str],
    batch: Optional[str],
    expiry: Optional[str],
) -> AlertResult:
    """
    Fuzzy-name + normalised-batch + optional expiry alert matching.
    Batch alone NEVER matches.
    """
    if not name or not batch:
        return AlertResult()

    try:
        from rapidfuzz import fuzz
    except ImportError:
        return AlertResult()

    norm_batch = normalise_batch(batch)
    alerts = db.query(Alert).all()

    # Snapshot date for freshness
    snap_date: Optional[str] = None
    if alerts:
        snap_date = max((a.snapshot_date or "1970-01-01") for a in alerts)

    stale = False
    if snap_date:
        try:
            sd = date.fromisoformat(snap_date)
            stale = (date.today() - sd).days > ALERT_STALE_DAYS
        except Exception:
            pass

    best_exact: Optional[Alert] = None
    best_partial: Optional[Alert] = None

    import re
    norm_name = re.sub(r"[^a-z0-9\s]", " ", name.lower())

    for alert in alerts:
        # Name fuzzy match with normalized punctuation
        alert_brand_norm = re.sub(r"[^a-z0-9\s]", " ", alert.brand.lower())
        name_score = max(
            fuzz.token_set_ratio(norm_name, alert_brand_norm),
            fuzz.partial_ratio(alert_brand_norm, norm_name),
        )
        if name_score < 85:
            continue

        # Batch match (normalised)
        alert_batch_norm = alert.batch_norm or ""
        if alert_batch_norm != norm_batch:
            continue

        # Exact: name + batch + expiry
        if expiry and alert.exp:
            if expiry == alert.exp:
                best_exact = alert
                break
        else:
            # Partial: name + batch only
            if best_partial is None:
                best_partial = alert

    if best_exact:
        return AlertResult(
            match_level="exact",
            alert_id=best_exact.id,
            source_month=best_exact.source_month,
            source_url=best_exact.source_url,
            snapshot_date=snap_date,
            snapshot_stale=stale,
        )
    if best_partial:
        return AlertResult(
            match_level="partial",
            alert_id=best_partial.id,
            source_month=best_partial.source_month,
            source_url=best_partial.source_url,
            snapshot_date=snap_date,
            snapshot_stale=stale,
        )
    return AlertResult(snapshot_date=snap_date, snapshot_stale=stale)


# ── Registry adapter ───────────────────────────────────────────────────────

@dataclass
class RegistryResult:
    status: str             # valid | unknown | already_used | blocked | unavailable
    simulated: bool = True


def registry_lookup(db: Session, gtin: Optional[str], serial: Optional[str]) -> RegistryResult:
    """Lookup serial in the simulated registry."""
    if not gtin or not serial:
        return RegistryResult(status="unknown", simulated=True)

    try:
        row = db.query(RegistrySim).filter_by(gtin=gtin, serial=serial).first()
        if row is None:
            return RegistryResult(status="unknown", simulated=True)
        return RegistryResult(status=row.status, simulated=True)
    except Exception as exc:
        logger.error("authenticity: registry error: %s", exc)
        return RegistryResult(status="unavailable", simulated=True)


# ── Haversine distance ─────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ── Clone signals ──────────────────────────────────────────────────────────

@dataclass
class CloneResult:
    signal: str = "none"              # none | moderate | strong
    verdict_text: Optional[str] = None


def detect_clone(
    db: Session,
    serial_hash: Optional[str],
    batch_hash: Optional[str],
    current_printed_batch: Optional[str],
    current_printed_expiry: Optional[str],
    current_printed_name: Optional[str],
    current_device_token: str,
    current_lat: Optional[float],
    current_lng: Optional[float],
    current_ts: datetime,
    registry_status: str,
) -> CloneResult:
    """
    Compute clone signals for a scan event.
    Only runs when serial_hash is available.
    """
    if not serial_hash:
        return CloneResult(signal="none")

    # ── Strong signal 1: registry already_used or blocked ────────────────
    if registry_status in ("already_used", "blocked"):
        return CloneResult(
            signal="strong",
            verdict_text="Unusual scan activity for this code. Verify with the manufacturer before use.",
        )

    # ── Fetch prior events for this serial ────────────────────────────────
    try:
        prior_events = (
            db.query(ScanEvent)
            .filter(ScanEvent.serial_hash == serial_hash)
            .filter(ScanEvent.device_token != current_device_token)
            .order_by(ScanEvent.ts)
            .all()
        )
    except Exception as exc:
        logger.error("authenticity: clone query error: %s", exc)
        return CloneResult(signal="none")

    if not prior_events:
        return CloneResult(signal="none")

    # ── Strong signal 2: same serial, different printed batch/expiry/name ─
    for ev in prior_events:
        if current_printed_batch and ev.printed_batch:
            if normalise_batch(current_printed_batch) != normalise_batch(ev.printed_batch):
                return CloneResult(
                    signal="strong",
                    verdict_text="Unusual scan activity for this code. Verify with the manufacturer before use.",
                )
        if current_printed_expiry and ev.printed_expiry:
            if current_printed_expiry != ev.printed_expiry:
                return CloneResult(
                    signal="strong",
                    verdict_text="Unusual scan activity for this code. Verify with the manufacturer before use.",
                )

    # ── Moderate signal 1: impossible travel ──────────────────────────────
    if current_lat is not None and current_lng is not None:
        for ev in prior_events:
            if ev.lat_round is None or ev.lng_round is None:
                continue
            dist_km = _haversine_km(current_lat, current_lng, ev.lat_round, ev.lng_round)
            time_diff_h = abs((current_ts - ev.ts).total_seconds()) / 3600.0
            if time_diff_h < 0.01:
                continue
            speed = dist_km / time_diff_h
            if speed > CLONE_SPEED_KMH:
                locs = f"Scanned in {ev.district or 'unknown location'} and another district"
                mins = int(abs((current_ts - ev.ts).total_seconds()) / 60)
                return CloneResult(
                    signal="moderate",
                    verdict_text=f"Unusual scan activity for this code. {locs} within {mins} minutes. Verify with the manufacturer before use.",
                )

    # ── Moderate signal 2: too many distinct devices ──────────────────────
    distinct_devices = len(set(e.device_token for e in prior_events)) + 1  # +1 for current
    if distinct_devices > CLONE_DEVICE_THRESHOLD:
        return CloneResult(
            signal="moderate",
            verdict_text="Unusual scan activity for this code. Verify with the manufacturer before use.",
        )

    return CloneResult(signal="none")


def record_scan_event(
    db: Session,
    serial_hash: Optional[str],
    batch_hash: Optional[str],
    district: Optional[str],
    lat_round: Optional[float],
    lng_round: Optional[float],
    ts: datetime,
    device_token: str,
    label: str,
    quality_ok: bool,
    printed_batch: Optional[str] = None,
    printed_expiry: Optional[str] = None,
    printed_name: Optional[str] = None,
    simulated: bool = False,
) -> None:
    """Persist a scan event for clone detection."""
    try:
        ev = ScanEvent(
            serial_hash=serial_hash,
            batch_hash=batch_hash,
            district=district,
            lat_round=lat_round,
            lng_round=lng_round,
            ts=ts,
            device_token=device_token,
            label=label,
            quality_ok=quality_ok,
            printed_batch=printed_batch,
            printed_expiry=printed_expiry,
            printed_name=printed_name,
            simulated=simulated,
        )
        db.add(ev)
        db.commit()
    except Exception as exc:
        logger.error("authenticity: record_scan_event error: %s", exc)
        db.rollback()
