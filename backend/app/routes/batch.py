"""
app/routes/batch.py — GET /batch/{hash}/status, POST /batch-report
"""

from __future__ import annotations
import uuid
import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ScanEvent, BatchReport, Scan
from app.schemas import (
    BatchStatusResponse, DistrictStatus,
    BatchReportRequest, BatchReportResponse,
)
from app.config import CLONE_DEVICE_THRESHOLD

logger = logging.getLogger(__name__)
router = APIRouter()

# Band thresholds (distinct device counts)
_BAND_NONE    = 0
_BAND_FEW     = 5    # < 5 distinct devices → none
_BAND_SEVERAL = 10
_BAND_MANY    = 25


def _count_to_band(distinct_devices: int) -> str:
    if distinct_devices < _BAND_FEW:
        return "none"
    elif distinct_devices < _BAND_SEVERAL:
        return "few"
    elif distinct_devices < _BAND_MANY:
        return "several"
    return "many"


@router.get("/batch/{batch_hash}/status", response_model=BatchStatusResponse)
def get_batch_status(batch_hash: str, db: Session = Depends(get_db)):
    """Community batch anomaly band. Never returns exact counts."""
    # Only quality-ok scans, one vote per device per batch per day
    events = (
        db.query(ScanEvent)
        .filter(ScanEvent.batch_hash == batch_hash)
        .filter(ScanEvent.quality_ok == True)
        .all()
    )

    if not events:
        return BatchStatusResponse(batch_hash=batch_hash, band="none")

    is_simulated = any(e.simulated for e in events)

    # Deduplicate: one vote per (device_token, date)
    seen: set[tuple] = set()
    deduped: list[ScanEvent] = []
    for ev in events:
        day = ev.ts.date() if ev.ts else date.today()
        key = (ev.device_token, day)
        if key not in seen:
            seen.add(key)
            deduped.append(ev)

    distinct_devices = len(set(ev.device_token for ev in deduped))
    band = _count_to_band(distinct_devices)

    # Per-district flagged share (only if band > none)
    districts: list[DistrictStatus] = []
    if band != "none":
        district_map: dict[str, list] = {}
        for ev in deduped:
            key = ev.district or "Unknown"
            if key not in district_map:
                district_map[key] = []
            district_map[key].append(ev.label in ("high_suspicion", "needs_verification"))

        for dist_name, flags in district_map.items():
            lat = next((ev.lat_round for ev in deduped if (ev.district or "Unknown") == dist_name and ev.lat_round), None)
            lng = next((ev.lng_round for ev in deduped if (ev.district or "Unknown") == dist_name and ev.lng_round), None)
            flagged_share = sum(flags) / len(flags) if flags else 0.0
            districts.append(DistrictStatus(
                district=dist_name,
                lat=lat,
                lng=lng,
                flagged_share=round(flagged_share, 3),
            ))

    return BatchStatusResponse(
        batch_hash=batch_hash,
        band=band,
        simulated=is_simulated,
        districts=districts,
    )


@router.post("/batch-report", response_model=BatchReportResponse, status_code=201)
def post_batch_report(
    req: BatchReportRequest,
    request: Request,
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """User community report. Rate-limited: 1 per device per batch per day."""
    device_token = x_device_token or "anonymous"
    today = date.today().isoformat()

    # Determine batch_hash from scan
    batch_hash: Optional[str] = None
    if req.scan_id:
        scan = db.query(Scan).filter(Scan.id == req.scan_id).first()
        if scan and scan.batch:
            from app.pipeline.authenticity import hash_field, normalise_batch
            batch_hash = hash_field(normalise_batch(scan.batch))

    # Rate limit: 1 per device per batch per day
    if batch_hash:
        existing = db.query(BatchReport).filter(
            BatchReport.device_token == device_token,
            BatchReport.batch_hash == batch_hash,
            BatchReport.day_key == today,
        ).first()
        if existing:
            raise HTTPException(
                status_code=429,
                detail={"error": {"code": "RATE_LIMITED", "message": "One report per batch per day"}}
            )

    report = BatchReport(
        id=str(uuid.uuid4()),
        scan_id=req.scan_id,
        batch_hash=batch_hash,
        device_token=device_token,
        note=req.note,
        day_key=today,
    )
    db.add(report)
    db.commit()

    return BatchReportResponse(id=report.id)
