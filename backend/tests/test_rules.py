"""
tests/test_rules.py — Rules engine and fusion decision tree tests.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.rules import evaluate_hard_rules, RuleHit
from app.pipeline.fusion import fuse
from app.pipeline.fields import ExtractedFields, FieldResult
from app.pipeline.codes import DecodeResult
from app.pipeline.authenticity import AlertResult, CloneResult, RegistryResult


def _make_fields(**kwargs) -> ExtractedFields:
    f = ExtractedFields()
    for k, v in kwargs.items():
        setattr(f, k, FieldResult(value=v, confidence=0.95))
    return f


def _make_code(**kwargs) -> DecodeResult:
    d = DecodeResult(ran=True, code_type="gs1")
    for k, v in kwargs.items():
        setattr(d, k, v)
    return d


class TestHardRules:
    def test_gtin_invalid_triggers(self):
        code = _make_code(gtin="08901234000015", gtin_valid=False)  # wrong check digit
        hits = evaluate_hard_rules(None, code, None, None, None)
        ids = [h.id for h in hits]
        assert "GTIN_INVALID" in ids

    def test_gtin_valid_no_hit(self):
        code = _make_code(gtin="08901234000014", gtin_valid=True)  # correct check digit
        hits = evaluate_hard_rules(None, code, None, None, None)
        ids = [h.id for h in hits]
        assert "GTIN_INVALID" not in ids

    def test_batch_mismatch(self):
        fields = _make_fields(batch="CFX-88219")
        code = _make_code(batch="CFX-88210", gtin_valid=True)
        hits = evaluate_hard_rules(fields, code, None, None, None)
        ids = [h.id for h in hits]
        assert "CODE_PRINT_MISMATCH" in ids
        assert any(h.severity == "high" for h in hits if h.id == "CODE_PRINT_MISMATCH")

    def test_same_batch_no_mismatch(self):
        fields = _make_fields(batch="MN-0994")
        code = _make_code(batch="MN0994", gtin_valid=True)  # same after normalisation
        hits = evaluate_hard_rules(fields, code, None, None, None)
        ids = [h.id for h in hits]
        assert "CODE_PRINT_MISMATCH" not in ids

    def test_expired_flag(self):
        fields = _make_fields(batch="X001")
        fields.expiry_flag = "expired"
        hits = evaluate_hard_rules(fields, None, None, None, None)
        ids = [h.id for h in hits]
        assert "EXPIRED" in ids
        assert any(h.severity == "high" for h in hits if h.id == "EXPIRED")

    def test_alert_exact_match(self):
        alert = AlertResult(match_level="exact", alert_id="CDSCO-2024-08-003")
        hits = evaluate_hard_rules(None, None, alert, None, None)
        ids = [h.id for h in hits]
        assert "ALERT_EXACT" in ids
        assert any(h.severity == "high" for h in hits if h.id == "ALERT_EXACT")

    def test_alert_partial_match(self):
        alert = AlertResult(match_level="partial", alert_id="CDSCO-2024-08-003")
        hits = evaluate_hard_rules(None, None, alert, None, None)
        ids = [h.id for h in hits]
        assert "ALERT_PARTIAL" in ids
        assert any(h.severity == "needs_verification" for h in hits if h.id == "ALERT_PARTIAL")

    def test_clone_strong(self):
        clone = CloneResult(signal="strong", verdict_text="Unusual activity.")
        hits = evaluate_hard_rules(None, None, None, clone, None)
        ids = [h.id for h in hits]
        assert "CLONE_STRONG" in ids

    def test_registry_blocked(self):
        registry = RegistryResult(status="blocked", simulated=True)
        hits = evaluate_hard_rules(None, None, None, None, registry)
        ids = [h.id for h in hits]
        assert "REGISTRY_USED_OR_BLOCKED" in ids


class TestFusionDecisionTree:
    def _visual_ok(self):
        from app.pipeline.visual import VisualReport
        v = VisualReport(ran=True, identity_score=0.92, alignment_ok=True)
        return v

    def _visual_off(self):
        from app.pipeline.visual import VisualReport
        return VisualReport(ran=False, not_checked_reason="No reference")

    def test_quality_fail_returns_insufficient(self):
        result = fuse(
            quality_ok=False,
            hard_rules=[],
            fields=None, code=None, visual=None,
            alert=None, clone=None, registry=None,
        )
        assert result.label == "insufficient_quality"

    def test_high_rule_gives_high_suspicion(self):
        rule = RuleHit(id="GTIN_INVALID", text="Bad GTIN", severity="high", contribution=0)
        result = fuse(
            quality_ok=True,
            hard_rules=[rule],
            fields=_make_fields(batch="B001"),
            code=_make_code(gtin_valid=False, gtin="08901234000015"),
            visual=self._visual_ok(),
            alert=AlertResult(),
            clone=CloneResult(),
            registry=RegistryResult(status="valid"),
        )
        assert result.label == "high_suspicion"

    def test_low_risk_requires_all_three_layers(self):
        """low_risk is only possible when OCR + code + visual all ran."""
        # Visual did not run
        result = fuse(
            quality_ok=True,
            hard_rules=[],
            fields=_make_fields(batch="B001"),
            code=_make_code(gtin="08901234000014", gtin_valid=True),
            visual=self._visual_off(),
            alert=AlertResult(),
            clone=CloneResult(),
            registry=RegistryResult(status="valid"),
        )
        assert result.label != "low_risk", "Must not be low_risk when visual did not run"

    def test_low_risk_all_layers(self):
        """All 3 layers ran, no rules hit -> low_risk."""
        result = fuse(
            quality_ok=True,
            hard_rules=[],
            fields=_make_fields(batch="B001"),
            code=_make_code(gtin="08901234000014", gtin_valid=True),
            visual=self._visual_ok(),
            alert=AlertResult(),
            clone=CloneResult(),
            registry=RegistryResult(status="valid"),
        )
        assert result.label == "low_risk"

    def test_partial_never_low_risk(self):
        """partial=True (manual scan) must never return low_risk."""
        result = fuse(
            quality_ok=True,
            hard_rules=[],
            fields=_make_fields(batch="B001"),
            code=DecodeResult(ran=False),
            visual=self._visual_off(),
            alert=AlertResult(),
            clone=CloneResult(),
            registry=RegistryResult(status="valid"),
            partial=True,
        )
        assert result.label != "low_risk"

    def test_needs_verification_rule(self):
        rule = RuleHit(id="NAME_POSSIBLE_MISSPELLING", text="Name differs", severity="needs_verification", contribution=0)
        result = fuse(
            quality_ok=True,
            hard_rules=[rule],
            fields=_make_fields(batch="B001"),
            code=_make_code(gtin="08901234000014", gtin_valid=True),
            visual=self._visual_ok(),
            alert=AlertResult(),
            clone=CloneResult(),
            registry=RegistryResult(status="valid"),
        )
        assert result.label == "needs_verification"

    def test_disclaimer_always_present(self):
        result = fuse(
            quality_ok=True,
            hard_rules=[],
            fields=_make_fields(batch="B001"),
            code=_make_code(gtin="08901234000014", gtin_valid=True),
            visual=self._visual_ok(),
            alert=AlertResult(),
            clone=CloneResult(),
            registry=RegistryResult(status="valid"),
        )
        assert result.label in ("low_risk", "needs_verification", "high_suspicion", "insufficient_quality")
