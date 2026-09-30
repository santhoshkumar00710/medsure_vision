"""
tests/test_manual.py — POST /scan/manual contract tests.

Verifies that the manual endpoint:
- Never returns label "low_risk"
- Sets partial: true
- Runs alert matching when name + batch provided
- Returns correct structure
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Create tables before importing app
from app.db import engine, Base
Base.metadata.create_all(bind=engine)

from app.main import app

client = TestClient(app)


def _manual_post(payload: dict) -> dict:
    response = client.post("/scan/manual", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    return response.json()


class TestManualScan:
    def test_basic_manual_returns_200(self):
        data = _manual_post({
            "name": "Dolo 650",
            "batch": "DL-9001",
            "expiry": "11/2027",
            "device_token": "test_token_001",
        })
        assert "id" in data
        assert "label" in data
        assert "ts" in data

    def test_manual_never_low_risk(self):
        """Manual scan must never return low_risk."""
        data = _manual_post({
            "name": "Dolo 650",
            "batch": "DL-9001",
            "expiry": "11/2027",
            "device_token": "test_token_001",
        })
        assert data["label"] != "low_risk", "Manual scan must never return low_risk"

    def test_manual_partial_true(self):
        data = _manual_post({
            "name": "Augmentin 625",
            "batch": "AG-1001",
            "device_token": "test_token_002",
        })
        assert data["partial"] is True

    def test_manual_disclaimer_present(self):
        data = _manual_post({
            "name": "Pantocid 40",
            "batch": "PT-2001",
            "device_token": "test_token_003",
        })
        assert data.get("disclaimer") == "Screening only. This does not confirm authenticity."

    def test_manual_visual_not_ran(self):
        data = _manual_post({
            "name": "Metformin 500mg",
            "batch": "MF-3001",
            "device_token": "test_token_004",
        })
        visual = data.get("visual") or {}
        assert visual.get("ran") is False

    def test_manual_code_not_ran(self):
        data = _manual_post({
            "batch": "XX-0001",
            "expiry": "06/2027",
            "device_token": "test_token_005",
        })
        code = data.get("code") or {}
        assert code.get("ran") is False

    def test_manual_expired_batch_flagged(self):
        data = _manual_post({
            "name": "Dolo 650",
            "batch": "DL-OLD",
            "expiry": "01/2020",   # clearly expired
            "device_token": "test_token_006",
        })
        assert data["label"] in ("high_suspicion", "needs_verification")
        reason_ids = [r["id"] for r in data.get("reasons", [])]
        assert "EXPIRED" in reason_ids

    def test_manual_requires_device_token(self):
        response = client.post("/scan/manual", json={"name": "Dolo"})
        assert response.status_code == 422   # missing required field

    def test_simulated_flags_list(self):
        data = _manual_post({
            "name": "Dolo 650",
            "batch": "DL-9001",
            "device_token": "test_token_007",
        })
        assert "simulated_flags" in data
        assert isinstance(data["simulated_flags"], list)

    def test_manual_high_suspicion_has_next_steps(self):
        data = _manual_post({
            "name": "Monocef 1g Injection",
            "batch": "MN-0994",   # matches alert
            "expiry": "12/2025",
            "device_token": "test_token_008",
        })
        assert len(data.get("next_steps", [])) > 0
