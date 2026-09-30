"""
app/routes/serial.py — GET /serial/{hash}/trail
"""

from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ScanEvent
from app.schemas import SerialTrailResponse, TrailEvent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/serial/{serial_hash}/trail", response_model=SerialTrailResponse)
def get_serial_trail(serial_hash: str, db: Session = Depends(get_db)):
    """Scan trail for a serial hash."""
    events = (
        db.query(ScanEvent)
        .filter(ScanEvent.serial_hash == serial_hash)
        .order_by(ScanEvent.ts)
        .all()
    )

    if not events:
        return SerialTrailResponse(
            serial_hash=serial_hash,
            simulated=False,
            verdict_text=None,
            events=[],
        )

    is_simulated = any(e.simulated for e in events)

    trail_events = [
        TrailEvent(
            district=ev.district,
            lat=ev.lat_round,
            lng=ev.lng_round,
            ts=ev.ts.isoformat() if ev.ts else "",
            flagged=ev.label in ("high_suspicion", "needs_verification"),
        )
        for ev in events
    ]

    # Build verdict text
    flagged_events = [e for e in trail_events if e.flagged]
    verdict_text: Optional[str] = None
    if len(flagged_events) >= 2:
        locs = [e.district for e in flagged_events if e.district]
        if len(locs) >= 2:
            verdict_text = (
                f"Scanned in {locs[0]} and {locs[1]} within a short window. "
                "This is unusual. Verify with the manufacturer before use."
            )
        else:
            verdict_text = "Unusual scan activity detected for this code."

    return SerialTrailResponse(
        serial_hash=serial_hash,
        simulated=is_simulated,
        verdict_text=verdict_text,
        events=trail_events,
    )
