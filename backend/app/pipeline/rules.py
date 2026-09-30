"""
app/pipeline/rules.py — Hard rules engine.

Each rule returns a RuleHit with { id, text, severity }.
No image-touching here — takes parsed pipeline outputs.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.config import OCR_CONFIDENCE_MIN
from app.pipeline.fields import ExtractedFields
from app.pipeline.codes import DecodeResult
from app.pipeline.authenticity import AlertResult, CloneResult, RegistryResult


@dataclass
class RuleHit:
    id: str
    text: str
    severity: str      # high | needs_verification | note
    contribution: int  # soft-score contribution (for display; hard rules don't add to score)


def evaluate_hard_rules(
    fields: Optional[ExtractedFields],
    code: Optional[DecodeResult],
    alert: Optional[AlertResult],
    clone: Optional[CloneResult],
    registry: Optional[RegistryResult],
) -> list[RuleHit]:
    """
    Evaluate all hard rules. Returns list of RuleHits.
    Hard rules → severity "high" or "needs_verification".
    """
    hits: list[RuleHit] = []

    # ── GTIN_INVALID ──────────────────────────────────────────────────────
    if code and code.ran and code.gtin and code.gtin_valid is False:
        hits.append(RuleHit(
            id="GTIN_INVALID",
            text="The product code contains an invalid GTIN check digit.",
            severity="high",
            contribution=0,
        ))

    # ── CODE_PRINT_MISMATCH ───────────────────────────────────────────────
    if code and code.ran and fields:
        # Batch mismatch
        if (
            code.batch
            and fields.batch.value
            and fields.batch.confidence >= OCR_CONFIDENCE_MIN
        ):
            from app.pipeline.authenticity import normalise_batch
            if normalise_batch(code.batch) != normalise_batch(fields.batch.value):
                hits.append(RuleHit(
                    id="CODE_PRINT_MISMATCH",
                    text=f"The batch number on the pack ({fields.batch.value}) does not match the code ({code.batch}).",
                    severity="high",
                    contribution=0,
                ))

        # Expiry mismatch
        if (
            code.expiry
            and fields.expiry.value
            and fields.expiry.confidence >= OCR_CONFIDENCE_MIN
            and not any(h.id == "CODE_PRINT_MISMATCH" for h in hits)  # avoid duplicate id
        ):
            if code.expiry != fields.expiry.value:
                hits.append(RuleHit(
                    id="CODE_PRINT_MISMATCH",
                    text=f"The expiry date on the pack ({fields.expiry.value}) does not match the code ({code.expiry}).",
                    severity="high",
                    contribution=0,
                ))

    # ── EXPIRED ───────────────────────────────────────────────────────────
    if fields and fields.expiry_flag == "expired":
        hits.append(RuleHit(
            id="EXPIRED",
            text="This pack has passed its expiry date. Do not use.",
            severity="high",
            contribution=0,
        ))
    elif fields and fields.expiry_flag == "expiry_before_mfg":
        hits.append(RuleHit(
            id="EXPIRED",
            text="The expiry date appears to be before the manufacture date — this is unusual.",
            severity="needs_verification",
            contribution=0,
        ))

    # ── NAME_POSSIBLE_MISSPELLING ─────────────────────────────────────────
    if fields and fields.name_flag == "possible_misspelling":
        hits.append(RuleHit(
            id="NAME_POSSIBLE_MISSPELLING",
            text="The medicine name may have a spelling difference from the registered name. Check carefully.",
            severity="needs_verification",
            contribution=0,
        ))

    # ── CODE_MISSING_FOR_LISTED_DRUG ─────────────────────────────────────
    if fields and fields.matched_medicine and code and code.ran and not code.gtin:
        hits.append(RuleHit(
            id="CODE_MISSING_FOR_LISTED_DRUG",
            text="This medicine is in the database but no machine-readable code was found on the pack.",
            severity="note",
            contribution=0,
        ))

    # ── ALERT_EXACT ───────────────────────────────────────────────────────
    if alert and alert.match_level == "exact":
        hits.append(RuleHit(
            id="ALERT_EXACT",
            text=(
                "This batch matches an official drug alert. "
                "A flagged batch does not mean every pack is affected, "
                "but this pack needs immediate verification."
            ),
            severity="high",
            contribution=0,
        ))

    # ── ALERT_PARTIAL ─────────────────────────────────────────────────────
    if alert and alert.match_level == "partial":
        hits.append(RuleHit(
            id="ALERT_PARTIAL",
            text=(
                "This batch partially matches an official drug alert. "
                "Possible match — please confirm with your supplier. "
                "A flagged batch does not mean every pack is affected."
            ),
            severity="needs_verification",
            contribution=0,
        ))

    # ── CLONE_STRONG ──────────────────────────────────────────────────────
    if clone and clone.signal == "strong":
        hits.append(RuleHit(
            id="CLONE_STRONG",
            text=clone.verdict_text or "Unusual scan activity for this code. Verify with the manufacturer before use.",
            severity="high",
            contribution=0,
        ))

    # ── REGISTRY_USED_OR_BLOCKED ──────────────────────────────────────────
    if registry and registry.status in ("already_used", "blocked"):
        hits.append(RuleHit(
            id="REGISTRY_USED_OR_BLOCKED",
            text="The serial number for this pack has already been scanned or is blocked in the registry.",
            severity="high",
            contribution=0,
        ))

    return hits
