"""
tests/test_privacy.py — Privacy and data handling tests.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.authenticity import hash_field, normalise_batch


class TestHashing:
    def test_hash_is_hex(self):
        h = hash_field("SERIAL001")
        assert all(c in "0123456789abcdef" for c in h)
        assert len(h) == 64   # SHA-256 hex

    def test_same_input_same_hash(self):
        assert hash_field("BATCH001") == hash_field("BATCH001")

    def test_different_inputs_different_hashes(self):
        assert hash_field("SERIAL001") != hash_field("SERIAL002")

    def test_hash_not_reversible(self):
        # Cannot trivially recover original from hash
        h = hash_field("TOP_SECRET_SERIAL")
        assert "TOP_SECRET_SERIAL" not in h


class TestBatchNormalisation:
    def test_strips_b_no_prefix(self):
        assert normalise_batch("B.No. MN-0994") == "MN0994"

    def test_strips_batch_no_prefix(self):
        assert normalise_batch("Batch No. CFX88219") == "CFX88219"

    def test_uppercase(self):
        assert normalise_batch("mn-0994") == "MN0994"

    def test_removes_spaces(self):
        assert normalise_batch("MN 0994") == "MN0994"

    def test_removes_hyphens(self):
        assert normalise_batch("CFX-88219") == "CFX88219"

    def test_empty_string(self):
        # Should not raise
        result = normalise_batch("")
        assert isinstance(result, str)

    def test_normalised_batches_match(self):
        a = normalise_batch("B.No.MN-0994")
        b = normalise_batch("MN0994")
        assert a == b


class TestDeleteScans:
    def test_delete_removes_only_own_scans(self):
        from fastapi.testclient import TestClient
        from app.db import engine, Base, SessionLocal
        from app.models import Scan
        import uuid, json
        from datetime import datetime, timezone

        Base.metadata.create_all(bind=engine)
        from app.main import app
        client = TestClient(app)

        db = SessionLocal()
        # Insert two scans with different device tokens
        device_a = "device_privacy_a"
        device_b = "device_privacy_b"
        minimal_result = {
            "id": "", "ts": "", "label": "low_risk", "partial": False,
            "checked": [], "not_checked": [], "reasons": [],
            "score": 0, "confidence": "high", "confidence_note": "",
            "next_steps": [], "simulated_flags": [],
            "disclaimer": "Screening only. This does not confirm authenticity.",
        }

        id_a = str(uuid.uuid4())
        id_b = str(uuid.uuid4())
        for did, scan_id in [(device_a, id_a), (device_b, id_b)]:
            r = dict(minimal_result)
            r["id"] = scan_id
            scan = Scan(
                id=scan_id, device_token=did,
                ts=datetime.now(timezone.utc),
                label="low_risk", partial=False,
                result_json=r,
            )
            db.add(scan)
        db.commit()
        db.close()

        # Delete device_a's scans
        response = client.delete("/scans", headers={"X-Device-Token": device_a})
        assert response.status_code == 204

        # device_a gone, device_b still present
        db2 = SessionLocal()
        assert db2.query(Scan).filter(Scan.device_token == device_a).count() == 0
        assert db2.query(Scan).filter(Scan.device_token == device_b).count() >= 1
        db2.close()
