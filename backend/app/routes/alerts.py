"""
app/routes/alerts.py — GET /alerts
"""

from __future__ import annotations
import logging
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert
from app.schemas import AlertListResponse, AlertItem
from app.config import ALERT_STALE_DAYS

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(db: Session = Depends(get_db)):
    """Return all CDSCO alert entries with snapshot freshness indicator."""
    alerts = db.query(Alert).all()

    # Determine snapshot date
    snap_date: str | None = None
    if alerts:
        snap_date = max((a.snapshot_date or "1970-01-01") for a in alerts)

    stale = False
    if snap_date:
        try:
            sd = date.fromisoformat(snap_date)
            stale = (date.today() - sd).days > ALERT_STALE_DAYS
        except Exception:
            pass

    items = [
        AlertItem(
            id=a.id,
            brand=a.brand,
            generic=a.generic,
            batch_norm=a.batch_norm,
            mfg=a.mfg,
            exp=a.exp,
            status=a.status,
            reason=a.reason,
            source_month=a.source_month,
            source_url=a.source_url,
            simulated=a.simulated or False,
        )
        for a in alerts
    ]

    return AlertListResponse(
        snapshot_date=snap_date,
        snapshot_stale=stale,
        items=items,
    )
