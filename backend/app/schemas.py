"""
app/schemas.py — Pydantic schemas matching the API contract exactly.
Field names here must match /docs/api-contract.md. Do not rename.
"""

from __future__ import annotations
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, field_validator


# ── Shared enums (as Literals for strict validation) ───────────────────────

LabelType = str          # low_risk | needs_verification | high_suspicion | insufficient_quality
SeverityType = str       # high | needs_verification | note
ConfidenceType = str     # low | moderate | high
CodeType = str           # gs1 | url | demo | unknown
CrossCheckStatus = str   # match | mismatch | not_comparable


# ── Sub-objects ────────────────────────────────────────────────────────────

class QualityResult(BaseModel):
    ok: bool
    blur: float
    brightness: float
    glare: float
    contrast: float
    resolution_min: int
    tips: list[str]


class OcrField(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class OcrResult(BaseModel):
    ran: bool
    name: Optional[OcrField] = None
    strength: Optional[OcrField] = None
    form: Optional[OcrField] = None
    batch: Optional[OcrField] = None
    mfg_date: Optional[OcrField] = None
    expiry: Optional[OcrField] = None
    manufacturer: Optional[OcrField] = None


class CodeResult(BaseModel):
    ran: bool
    type: Optional[CodeType] = None
    raw: Optional[str] = None
    gtin: Optional[str] = None
    batch: Optional[str] = None
    expiry: Optional[str] = None
    serial: Optional[str] = None
    has_serial: bool = False
    gtin_valid: Optional[bool] = None
    payload_source: Optional[str] = None
    url_offline_note: Optional[str] = None


class CrossCheckItem(BaseModel):
    field: str
    printed: Optional[str] = None
    code: Optional[str] = None
    status: CrossCheckStatus
    bbox: Optional[list[float]] = None


class AnomalyRegion(BaseModel):
    label: str
    bbox: list[float]
    score: float


class VisualResult(BaseModel):
    ran: bool
    identity_score: Optional[float] = None
    alignment_ok: Optional[bool] = None
    heatmap_url: Optional[str] = None
    anomaly_score: Optional[float] = None
    anomaly_regions: Optional[list[AnomalyRegion]] = None


class RegistryStatus(BaseModel):
    status: str       # valid | unknown | already_used | blocked | unavailable
    simulated: bool


class AlertMatch(BaseModel):
    match_level: str   # exact | partial | none
    alert_id: Optional[str] = None
    source_month: Optional[str] = None
    source_url: Optional[str] = None
    snapshot_date: Optional[str] = None
    snapshot_stale: Optional[bool] = None


class CloneResult(BaseModel):
    signal: Optional[str] = None   # none | moderate | strong
    verdict_text: Optional[str] = None


class AuthenticityResult(BaseModel):
    ran: bool
    registry: Optional[RegistryStatus] = None
    alert: Optional[AlertMatch] = None
    clone: Optional[CloneResult] = None


class Reason(BaseModel):
    id: str
    text: str
    severity: SeverityType
    contribution: int


class ScoreBreakdown(BaseModel):
    visual_similarity: int = 0
    anomaly: int = 0
    ocr_confidence: int = 0
    unusual_scan_count: int = 0
    unclear_fields: int = 0


class FieldRow(BaseModel):
    field: str
    printed: Optional[str] = None
    code_value: Optional[str] = None
    expected: Optional[str] = None
    status: CrossCheckStatus
    bbox: Optional[list[float]] = None


class ScanResult(BaseModel):
    id: str
    ts: str
    label: LabelType
    partial: bool = False

    quality: Optional[QualityResult] = None
    ocr: Optional[OcrResult] = None
    code: Optional[CodeResult] = None
    cross_check: Optional[list[CrossCheckItem]] = None
    visual: Optional[VisualResult] = None
    authenticity: Optional[AuthenticityResult] = None

    reasons: list[Reason] = []
    score: int = 0
    score_breakdown: Optional[ScoreBreakdown] = None

    checked: list[str] = []
    not_checked: list[str] = []
    confidence: ConfidenceType = "low"
    confidence_note: str = ""

    field_rows: list[FieldRow] = []
    next_steps: list[str] = []
    simulated_flags: list[str] = []
    disclaimer: str = "Screening only. This does not confirm authenticity."

    session_id: Optional[str] = None


# ── Scan list item (summary) ───────────────────────────────────────────────

class ScanListItem(BaseModel):
    id: str
    ts: str
    label: LabelType
    name: Optional[str] = None
    batch: Optional[str] = None
    expiry: Optional[str] = None
    manufacturer: Optional[str] = None
    top_reason: Optional[str] = None
    partial: bool = False


class ScanListResponse(BaseModel):
    total: int
    items: list[ScanListItem]


# ── Manual scan request ────────────────────────────────────────────────────

class ManualScanRequest(BaseModel):
    name: Optional[str] = None
    batch: Optional[str] = None
    expiry: Optional[str] = None
    mfg_date: Optional[str] = None
    manufacturer: Optional[str] = None
    strength: Optional[str] = None
    form: Optional[str] = None
    device_token: str
    language: str = "en"


# ── Serial trail ───────────────────────────────────────────────────────────

class TrailEvent(BaseModel):
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    ts: str
    flagged: bool = False


class SerialTrailResponse(BaseModel):
    serial_hash: str
    simulated: bool
    verdict_text: Optional[str] = None
    events: list[TrailEvent]


# ── Batch status ───────────────────────────────────────────────────────────

class DistrictStatus(BaseModel):
    district: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    flagged_share: float = 0.0


class BatchStatusResponse(BaseModel):
    batch_hash: str
    band: str   # none | few | several | many
    simulated: bool = False
    districts: list[DistrictStatus] = []


# ── Batch report ───────────────────────────────────────────────────────────

class BatchReportRequest(BaseModel):
    scan_id: Optional[str] = None
    note: Optional[str] = None


class BatchReportResponse(BaseModel):
    id: str


# ── Alerts ─────────────────────────────────────────────────────────────────

class AlertItem(BaseModel):
    id: str
    brand: str
    generic: Optional[str] = None
    batch_norm: str
    mfg: Optional[str] = None
    exp: Optional[str] = None
    status: str
    reason: Optional[str] = None
    source_month: Optional[str] = None
    source_url: Optional[str] = None
    simulated: bool = False


class AlertListResponse(BaseModel):
    snapshot_date: Optional[str] = None
    snapshot_stale: bool = False
    items: list[AlertItem]


# ── Stats ──────────────────────────────────────────────────────────────────

class TopBatch(BaseModel):
    batch: str
    count: int
    label: str


class TopIssue(BaseModel):
    rule_id: str
    count: int


class StatsResponse(BaseModel):
    total: int
    by_label: dict[str, int]
    top_batches: list[TopBatch]
    top_issues: list[TopIssue]


# ── Health ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    components: dict[str, bool]
    db: str
    version: str


# ── Receiving ──────────────────────────────────────────────────────────────

class ReceivingSessionRequest(BaseModel):
    supplier: Optional[str] = None
    invoice_no: Optional[str] = None


class ReceivingSessionResponse(BaseModel):
    id: str


class BatchConflict(BaseModel):
    batch: str
    conflict_type: str
    detail: str


class ReceivingGroup(BaseModel):
    name: Optional[str] = None
    batch: Optional[str] = None
    count: int
    worst_label: str


class ReceivingSummary(BaseModel):
    id: str
    supplier: Optional[str] = None
    scanned: int
    flagged: int
    accepted: int
    batch_conflicts: list[BatchConflict] = []
    groups: list[ReceivingGroup] = []


class AcceptResponse(BaseModel):
    accepted: int
    registry_updated: int


# ── Error envelope ─────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
