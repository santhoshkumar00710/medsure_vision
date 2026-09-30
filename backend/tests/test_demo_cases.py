"""tests/test_demo_cases.py — Task 3: each demo case returns the expected label."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

client = TestClient(app)

EXPECTED_LABELS = {
    "genuine":          {"low_risk", "needs_verification"},        # needs visual layer active for low_risk
    "expiry_tampered":  {"needs_verification", "high_suspicion"},
    "logo_shifted":     {"needs_verification", "high_suspicion"},
    "clone_code":       {"high_suspicion", "needs_verification"},
    "alert_match":      {"high_suspicion", "needs_verification"},
    "blurry":           {"insufficient_quality"},
}


@pytest.mark.parametrize("case_id,allowed_labels", EXPECTED_LABELS.items())
def test_demo_case_label(case_id, allowed_labels):
    """Each demo case must return one of the allowed labels."""
    resp = client.get(f"/demo/{case_id}")
    assert resp.status_code == 200, f"/demo/{case_id} returned {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    label = data.get("label")
    assert label in allowed_labels, (
        f"/demo/{case_id} returned label={label!r}, expected one of {allowed_labels}"
    )


def test_demo_unknown_case():
    """Unknown demo case IDs must return 404."""
    resp = client.get("/demo/nonexistent_case")
    assert resp.status_code == 404


def test_demo_response_has_disclaimer():
    resp = client.get("/demo/blurry")
    assert resp.status_code == 200
    data = resp.json()
    assert "disclaimer" in data
    assert "authenticity" not in data["disclaimer"].lower() or "does not confirm" in data["disclaimer"].lower()


def test_demo_simulated_flags():
    resp = client.get("/demo/blurry")
    data = resp.json()
    flags = data.get("simulated_flags", [])
    assert "demo_case" in flags
