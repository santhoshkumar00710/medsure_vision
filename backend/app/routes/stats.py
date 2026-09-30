"""
app/routes/stats.py — GET /stats
"""

from __future__ import annotations
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Scan
from app.schemas import StatsResponse, TopBatch, TopIssue

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Scan).count()

    # By label
    label_rows = (
        db.query(Scan.label, func.count(Scan.id))
        .group_by(Scan.label)
        .all()
    )
    by_label = {
        "low_risk": 0,
        "needs_verification": 0,
        "high_suspicion": 0,
        "insufficient_quality": 0,
    }
    for label, cnt in label_rows:
        if label in by_label:
            by_label[label] = cnt

    # Top flagged batches
    batch_rows = (
        db.query(Scan.batch, Scan.label, func.count(Scan.id).label("cnt"))
        .filter(Scan.batch.isnot(None))
        .filter(Scan.label.in_(["high_suspicion", "needs_verification"]))
        .group_by(Scan.batch, Scan.label)
        .order_by(func.count(Scan.id).desc())
        .limit(5)
        .all()
    )
    top_batches = [TopBatch(batch=b, count=c, label=l) for b, l, c in batch_rows]

    # Top issues: count rule occurrences from reason JSON
    # This is a simplified scan — full implementation would parse result_json
    top_issues: list[TopIssue] = []

    return StatsResponse(
        total=total,
        by_label=by_label,
        top_batches=top_batches,
        top_issues=top_issues,
    )
