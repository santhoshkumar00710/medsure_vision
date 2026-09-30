"""
app/pipeline/fusion.py — Decision engine.

Combines hard rule hits + soft-score signals → label, confidence, checked/not_checked.
Implements the decision tree from the contract spec exactly.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from app.pipeline.rules import RuleHit
from app.pipeline.fields import ExtractedFields
from app.pipeline.codes import DecodeResult
from app.pipeline.visual import VisualReport
from app.pipeline.authenticity import AlertResult, CloneResult, RegistryResult
from app.config import OCR_CONFIDENCE_MIN


@dataclass
class FusionResult:
    label: str                          # low_risk | needs_verification | high_suspicion | insufficient_quality
    score: int
    score_breakdown: dict
    reasons: list[dict]
    checked: list[str]
    not_checked: list[str]
    confidence: str                     # low | moderate | high
    confidence_note: str
    next_steps: list[str]
    field_rows: list[dict]
    cross_check: list[dict]


def fuse(
    quality_ok: bool,
    hard_rules: list[RuleHit],
    fields: Optional[ExtractedFields],
    code: Optional[DecodeResult],
    visual: Optional[VisualReport],
    alert: Optional[AlertResult],
    clone: Optional[CloneResult],
    registry: Optional[RegistryResult],
    partial: bool = False,
) -> FusionResult:
    """
    Main decision function.
    partial=True means image / visual layers did not run (manual scan).
    """

    # ── Quality gate ──────────────────────────────────────────────────────
    if not quality_ok:
        return FusionResult(
            label="insufficient_quality",
            score=0,
            score_breakdown={},
            reasons=[],
            checked=[],
            not_checked=[
                "OCR text extraction (image quality insufficient)",
                "2D code verification (image quality insufficient)",
                "Visual similarity check (image quality insufficient)",
            ],
            confidence="low",
            confidence_note="Image quality check failed",
            next_steps=[
                "Hold the camera steady and ensure good lighting.",
                "Avoid glare — tilt the pack slightly away from the light source.",
                "Move closer to fill the frame with the medicine pack.",
                "Tap the shutter button again once the quality indicators are green.",
            ],
            field_rows=[],
            cross_check=[],
        )

    # ── Soft score ────────────────────────────────────────────────────────
    score_breakdown = {
        "visual_similarity": 0,
        "anomaly": 0,
        "ocr_confidence": 0,
        "unusual_scan_count": 0,
        "unclear_fields": 0,
    }

    # Visual similarity
    if visual and visual.ran and visual.identity_score is not None:
        if visual.identity_score < 0.5:
            score_breakdown["visual_similarity"] = 25
        elif visual.identity_score < 0.75:
            score_breakdown["visual_similarity"] = 15

    # Visual alignment
    if visual and visual.ran and visual.alignment_ok is False:
        score_breakdown["visual_alignment"] = 15
    
    # Anomaly score
    if visual and visual.ran and visual.anomaly_score is not None:
        if visual.anomaly_score > 0.6:
            score_breakdown["anomaly"] = 20

    # Low OCR confidence
    if fields:
        low_conf_fields = []
        for fname in ("name", "batch", "expiry", "manufacturer"):
            fv = getattr(fields, fname, None)
            if fv and fv.value and fv.confidence < OCR_CONFIDENCE_MIN:
                low_conf_fields.append(fname)
        if low_conf_fields:
            score_breakdown["ocr_confidence"] = 10

    # Unusual scan count (clone moderate)
    if clone and clone.signal == "moderate":
        score_breakdown["unusual_scan_count"] = 15

    # Unclear key fields
    if fields:
        unclear = sum(
            1 for fname in ("batch", "expiry")
            if getattr(fields, fname, None) and getattr(fields, fname).confidence < OCR_CONFIDENCE_MIN
        )
        if unclear > 0:
            score_breakdown["unclear_fields"] = 10

    score = sum(score_breakdown.values())

    # ── Layers that ran ───────────────────────────────────────────────────
    layers_ran: list[str] = []
    if fields:
        layers_ran.append("ocr")
    if code and code.ran:
        layers_ran.append("code")
    if visual and visual.ran:
        layers_ran.append("visual")

    # ── Decision tree ─────────────────────────────────────────────────────
    has_high_hard = any(h.severity == "high" for h in hard_rules)
    has_warn_hard = any(h.severity == "needs_verification" for h in hard_rules)
    all_three_layers = set(layers_ran) >= {"ocr", "code", "visual"}

    if partial:
        # Manual scan — never low_risk
        if has_high_hard or score >= 51:
            label = "high_suspicion"
        elif has_warn_hard or score >= 21 or len(layers_ran) < 2:
            label = "needs_verification"
        else:
            label = "needs_verification"   # always, since partial=True
    else:
        if has_high_hard or score >= 51:
            label = "high_suspicion"
        elif has_warn_hard or score >= 21 or not all_three_layers:
            label = "needs_verification"
        else:
            label = "low_risk"   # only when all 3 layers ran

    # ── Confidence ────────────────────────────────────────────────────────
    n_layers = len(layers_ran)
    if n_layers >= 3:
        confidence = "high"
        confidence_note = "3 of 3 layers ran and agreed"
    elif n_layers == 2:
        confidence = "moderate"
        confidence_note = "2 of 3 layers ran"
    else:
        confidence = "low"
        confidence_note = "Only 1 layer ran — result has low confidence"

    if partial:
        confidence = "low" if n_layers < 2 else "moderate"
        confidence_note = "Manual entry — image and visual layers did not run"

    # ── Checked / not_checked ─────────────────────────────────────────────
    checked: list[str] = []
    not_checked: list[str] = []

    if "ocr" in layers_ran:
        checked.append("OCR text consistency")
    else:
        not_checked.append("OCR text extraction did not run")

    if "code" in layers_ran:
        checked.append("2D matrix structure")
        if code and code.code_type == "url":
            not_checked.append("URL code cannot be verified offline")
    else:
        not_checked.append("2D code verification did not run")

    if "visual" in layers_ran:
        checked.append("Visual similarity against reference")
    else:
        if visual and visual.not_checked_reason:
            not_checked.append(visual.not_checked_reason)
        else:
            not_checked.append("Visual similarity check did not run")

    if alert is not None:
        checked.append("CDSCO drug alert list")
    else:
        not_checked.append("Drug alert list not checked")

    if registry is not None:
        if registry.status == "unavailable":
            not_checked.append("Serial not verified with manufacturer (registry unavailable)")
        elif registry.simulated:
            checked.append("Registry verification (simulated)")
            not_checked.append("Serial not verified with manufacturer (simulated registry)")
    else:
        not_checked.append("Serial not verified with manufacturer")

    if code and not code.has_serial:
        not_checked.append("Clone check needs a serial number — no AI 21 found in code")

    # ── Build reasons list ─────────────────────────────────────────────────
    reasons: list[dict] = []

    for rule in hard_rules:
        reasons.append({
            "id": rule.id,
            "text": rule.text,
            "severity": rule.severity,
            "contribution": rule.contribution,
        })

    # Add soft-score reasons
    if score_breakdown["visual_similarity"] > 0:
        reasons.append({
            "id": "LOW_VISUAL_SIMILARITY",
            "text": "The pack looks different from the reference image for this medicine.",
            "severity": "needs_verification",
            "contribution": score_breakdown["visual_similarity"],
        })
    if score_breakdown["anomaly"] > 0:
        reasons.append({
            "id": "VISUAL_ANOMALY",
            "text": "Unusual patterns detected in the pack image compared to the reference.",
            "severity": "needs_verification",
            "contribution": score_breakdown["anomaly"],
        })
    if score_breakdown["ocr_confidence"] > 0:
        reasons.append({
            "id": "LOW_OCR_CONFIDENCE",
            "text": "Some text on the pack could not be read clearly.",
            "severity": "needs_verification",
            "contribution": score_breakdown["ocr_confidence"],
        })
    if clone and clone.signal == "moderate":
        reasons.append({
            "id": "CLONE_MODERATE",
            "text": clone.verdict_text or "Unusual scan activity for this code. Verify with the manufacturer before use.",
            "severity": "needs_verification",
            "contribution": score_breakdown["unusual_scan_count"],
        })
    if score_breakdown["unclear_fields"] > 0:
        reasons.append({
            "id": "UNCLEAR_KEY_FIELDS",
            "text": "Key fields such as batch or expiry could not be read with enough certainty.",
            "severity": "needs_verification",
            "contribution": score_breakdown["unclear_fields"],
        })

    # ── next_steps ────────────────────────────────────────────────────────
    if label == "high_suspicion":
        next_steps = [
            "Do not dispense or ingest this pack under any circumstance.",
            "Quarantine the pack in the designated suspicious-batch bin.",
            "Inform your upstream distributor immediately.",
            "File a report with your state drug regulatory authority.",
        ]
    elif label == "needs_verification":
        next_steps = [
            "Check the batch number and expiry date by hand against the purchase invoice.",
            "Ask your supplier for the original manufacturer documentation for this batch.",
            "If in doubt, set the pack aside and do not dispense until verified.",
        ]
    elif label == "low_risk":
        next_steps = [
            "No inconsistencies found across all checks.",
            "Store as per label instructions.",
            "Report any concerns to your pharmacist supervisor.",
        ]
    else:  # insufficient_quality — handled above
        next_steps = []

    # ── Cross-check rows ──────────────────────────────────────────────────
    cross_check = _build_cross_check(fields, code)
    field_rows = [dict(cc) for cc in cross_check]

    return FusionResult(
        label=label,
        score=score,
        score_breakdown=score_breakdown,
        reasons=reasons,
        checked=checked,
        not_checked=not_checked,
        confidence=confidence,
        confidence_note=confidence_note,
        next_steps=next_steps,
        field_rows=field_rows,
        cross_check=cross_check,
    )


def _build_cross_check(
    fields: Optional[ExtractedFields],
    code: Optional[DecodeResult],
) -> list[dict]:
    """Build cross-check items between OCR fields and code payload."""
    items: list[dict] = []
    if not fields or not code or not code.ran:
        return items

    from app.pipeline.authenticity import normalise_batch

    # Batch
    if fields.batch.value or code.batch:
        printed = fields.batch.value
        code_val = code.batch
        if printed and code_val and fields.batch.confidence >= OCR_CONFIDENCE_MIN:
            status = "match" if normalise_batch(printed) == normalise_batch(code_val) else "mismatch"
        elif not printed or not code_val:
            status = "not_comparable"
        else:
            status = "not_comparable"
        items.append({
            "field": "batch",
            "printed": printed,
            "code": code_val,
            "code_value": code_val,
            "expected": None,
            "status": status,
            "bbox": None,
        })

    # Expiry
    if fields.expiry.value or code.expiry:
        printed = fields.expiry.value
        code_val = code.expiry
        if printed and code_val and fields.expiry.confidence >= OCR_CONFIDENCE_MIN:
            status = "match" if printed == code_val else "mismatch"
        else:
            status = "not_comparable"
        items.append({
            "field": "expiry",
            "printed": printed,
            "code": code_val,
            "code_value": code_val,
            "expected": None,
            "status": status,
            "bbox": None,
        })

    # Name (if in code payload — demo/GS1 does not typically have it)
    items.append({
        "field": "name",
        "printed": fields.name.value if fields.name.value else None,
        "code": None,
        "code_value": None,
        "expected": None,
        "status": "not_comparable",
        "bbox": None,
    })

    return items
