"""
app/routes/scans.py — GET /scans, GET /scans/{id}, DELETE /scans
"""

from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Scan, ScanEvent
from app.schemas import ScanResult, ScanListItem, ScanListResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scans", response_model=ScanListResponse)
def list_scans(
    result: Optional[str] = Query(None, description="Filter by label"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Paginated scan history for the requesting device."""
    if not x_device_token:
        raise HTTPException(status_code=401, detail={"error": {"code": "INVALID_INPUT", "message": "X-Device-Token header required"}})

    q = db.query(Scan).filter(Scan.device_token == x_device_token)
    if result:
        q = q.filter(Scan.label == result)
    total = q.count()
    rows = q.order_by(Scan.ts.desc()).offset(offset).limit(limit).all()

    items = [
        ScanListItem(
            id=row.id,
            ts=row.ts.isoformat() if row.ts else "",
            label=row.label,
            name=row.name,
            batch=row.batch,
            expiry=row.expiry,
            manufacturer=row.manufacturer,
            top_reason=row.top_reason,
            partial=row.partial or False,
        )
        for row in rows
    ]
    return ScanListResponse(total=total, items=items)


@router.get("/scans/{scan_id}", response_model=ScanResult)
def get_scan(
    scan_id: str,
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Full ScanResult for one scan. Returns 404 if not found or wrong device."""
    row = db.query(Scan).filter(Scan.id == scan_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found"}})
    if x_device_token and row.device_token != x_device_token:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found"}})

    try:
        return ScanResult.model_validate(row.result_json)
    except Exception as exc:
        logger.error("scans: deserialise error for %s: %s", scan_id, exc)
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "Could not load scan result"}})


@router.delete("/scans", status_code=204)
def delete_scans(
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    db: Session = Depends(get_db),
):
    """Delete all scan rows for the requesting device."""
    if not x_device_token:
        raise HTTPException(status_code=401, detail={"error": {"code": "INVALID_INPUT", "message": "X-Device-Token header required"}})

    try:
        db.query(Scan).filter(Scan.device_token == x_device_token).delete()
        db.commit()
    except Exception as exc:
        logger.error("scans: delete error: %s", exc)
        db.rollback()
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "Delete failed"}})
    return None
