"""
app/routes/receiving.py — Receiving mode endpoints.
POST /receiving/sessions
POST /receiving/sessions/{id}/scan
GET  /receiving/sessions/{id}/summary
POST /receiving/sessions/{id}/accept
GET  /receiving/sessions/{id}/export
"""

from __future__ import annotations
import uuid
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReceivingSession, Scan, RegistrySim
from app.schemas import (
    ReceivingSessionRequest, ReceivingSessionResponse,
    ReceivingSummary, BatchConflict, ReceivingGroup,
    AcceptResponse, ScanResult,
)
from app.routes.scan import _run_full_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/receiving")


@router.post("/sessions", response_model=ReceivingSessionResponse, status_code=201)
def create_session(req: ReceivingSessionRequest, db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    session = ReceivingSession(
        id=session_id,
        supplier=req.supplier,
        invoice_no=req.invoice_no,   # stays local, never returned in API
    )
    db.add(session)
    db.commit()
    return ReceivingSessionResponse(id=session_id)


@router.post("/sessions/{session_id}/scan", response_model=ScanResult)
async def session_scan(
    session_id: str,
    image: UploadFile = File(...),
    image2: Optional[UploadFile] = File(None),
    device_token: str = Form(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    language: str = Form("en"),
    db: Session = Depends(get_db),
):
    """Run full pipeline and link result to session."""
    session = db.query(ReceivingSession).filter(ReceivingSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}})

    img_bytes = await image.read()
    img2_bytes = await image2.read() if image2 else None

    result = await _run_full_pipeline(
        img_bytes=img_bytes,
        img2_bytes=img2_bytes,
        device_token=device_token,
        lat=lat,
        lng=lng,
        language=language,
        db=db,
    )

    # Link scan to session
    try:
        db.query(Scan).filter(Scan.id == result.id).update({"session_id": session_id})
        db.commit()
        result.session_id = session_id
    except Exception as exc:
        logger.error("receiving: link scan error: %s", exc)

    return result


@router.get("/sessions/{session_id}/summary", response_model=ReceivingSummary)
def get_session_summary(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ReceivingSession).filter(ReceivingSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}})

    scans = db.query(Scan).filter(Scan.session_id == session_id).all()
    scanned = len(scans)
    flagged = sum(1 for s in scans if s.label in ("high_suspicion", "needs_verification"))
    accepted = sum(1 for s in scans if s.label == "low_risk")

    # Intra-lot consistency: group by batch
    batch_groups: dict[str, list[Scan]] = {}
    for s in scans:
        if s.batch:
            batch_groups.setdefault(s.batch, []).append(s)

    batch_conflicts: list[BatchConflict] = []
    for batch, group in batch_groups.items():
        expiries = set(s.expiry for s in group if s.expiry)
        manufacturers = set(s.manufacturer for s in group if s.manufacturer)
        if len(expiries) > 1:
            batch_conflicts.append(BatchConflict(
                batch=batch,
                conflict_type="expiry_mismatch",
                detail=f"Multiple expiry dates found in this lot: {', '.join(sorted(expiries))}",
            ))
        if len(manufacturers) > 1:
            batch_conflicts.append(BatchConflict(
                batch=batch,
                conflict_type="manufacturer_mismatch",
                detail=f"Multiple manufacturers found: {', '.join(sorted(manufacturers))}",
            ))

    # Groups
    groups: list[ReceivingGroup] = []
    for batch, group in batch_groups.items():
        label_priority = {"high_suspicion": 3, "needs_verification": 2, "insufficient_quality": 1, "low_risk": 0}
        worst = max(group, key=lambda s: label_priority.get(s.label, 0))
        name = next((s.name for s in group if s.name), None)
        groups.append(ReceivingGroup(
            name=name,
            batch=batch,
            count=len(group),
            worst_label=worst.label,
        ))

    return ReceivingSummary(
        id=session_id,
        supplier=session.supplier,
        scanned=scanned,
        flagged=flagged,
        accepted=accepted,
        batch_conflicts=batch_conflicts,
        groups=groups,
    )


@router.post("/sessions/{session_id}/accept", response_model=AcceptResponse)
def accept_session(session_id: str, db: Session = Depends(get_db)):
    """Mark non-flagged packs accepted; update registry for packs with serials."""
    session = db.query(ReceivingSession).filter(ReceivingSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}})

    scans = db.query(Scan).filter(
        Scan.session_id == session_id,
        Scan.label == "low_risk",
    ).all()

    accepted_count = len(scans)
    registry_updated = 0

    for scan in scans:
        result_data = scan.result_json or {}
        code_data = result_data.get("code", {})
        gtin = code_data.get("gtin")
        serial = code_data.get("serial")
        if gtin and serial:
            row = db.query(RegistrySim).filter_by(gtin=gtin, serial=serial).first()
            if row:
                row.status = "already_used"
                registry_updated += 1

    session.accepted = True
    try:
        db.commit()
    except Exception as exc:
        logger.error("receiving: accept error: %s", exc)
        db.rollback()

    return AcceptResponse(accepted=accepted_count, registry_updated=registry_updated)


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: str,
    format: str = Query("pdf", pattern="^(pdf|csv)$"),
    db: Session = Depends(get_db),
):
    """Export flagged pack list as PDF or CSV."""
    session = db.query(ReceivingSession).filter(ReceivingSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}})

    flagged_scans = db.query(Scan).filter(
        Scan.session_id == session_id,
        Scan.label.in_(["high_suspicion", "needs_verification"]),
    ).all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Batch", "Expiry", "Label", "Reason"])
        for s in flagged_scans:
            writer.writerow([s.id, s.name or "", s.batch or "", s.expiry or "", s.label, s.top_reason or ""])
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=session_{session_id}.csv"}
        )

    # PDF export
    try:
        from app.reports.pdf import generate_session_pdf
        pdf_bytes = generate_session_pdf(session, flagged_scans)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=session_{session_id}.pdf"}
        )
    except Exception as exc:
        logger.error("receiving: pdf export error: %s", exc)
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "PDF generation failed"}})
