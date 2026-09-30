"""tests/test_medicines_db.py — Task 1.6 medicines.json integrity tests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MED_JSON   = ROOT / "data" / "medicines.json"
REF_DIR    = ROOT / "data" / "reference_images"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _luhn_check(gtin: str) -> bool:
    if len(gtin) != 14 or not gtin.isdigit():
        return False
    digits = [int(c) for c in gtin]
    total = sum(d * 3 if i % 2 == 0 else d for i, d in enumerate(reversed(digits[:-1])))
    return (10 - total % 10) % 10 == digits[-1]


def load_meds():
    return json.load(open(MED_JSON))


class TestMedicinesJson:
    def test_all_gtins_valid(self):
        """Every entry must have a GTIN-14 with correct check digit."""
        for m in load_meds():
            assert _luhn_check(m["gtin"]), (
                f"{m['id']} has invalid GTIN check digit: {m['gtin']}"
            )

    def test_ids_unique(self):
        meds = load_meds()
        ids = [m["id"] for m in meds]
        assert len(ids) == len(set(ids)), "Duplicate ids found in medicines.json"

    def test_required_fields(self):
        for m in load_meds():
            for field in ("id", "name", "generic", "aliases", "gtin"):
                assert field in m, f"{m.get('id','?')} missing field: {field}"

    def test_twenty_medicines(self):
        assert len(load_meds()) == 20, "Expected exactly 20 medicines"

    def test_gtins_are_fourteen_digits(self):
        for m in load_meds():
            assert len(m["gtin"]) == 14 and m["gtin"].isdigit(), (
                f"{m['id']} GTIN not 14 digits: {m['gtin']}"
            )

    def test_nonempty_reference_folders_map_to_id(self):
        """Every non-empty reference image folder must have a matching medicine id."""
        meds = load_meds()
        med_ids = {m["id"] for m in meds}
        if not REF_DIR.exists():
            return
        for folder in REF_DIR.iterdir():
            if not folder.is_dir():
                continue
            images = [f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS]
            if images:
                assert folder.name in med_ids, (
                    f"Reference folder '{folder.name}' has images but no matching id in medicines.json"
                )

    def test_all_ids_have_reference_folder(self):
        """Every medicine id should have a reference folder (even if empty)."""
        if not REF_DIR.exists():
            return
        folder_names = {f.name for f in REF_DIR.iterdir() if f.is_dir()}
        for m in load_meds():
            assert m["id"] in folder_names, (
                f"No reference folder for id '{m['id']}'"
            )

    def test_health_visual_coverage(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert "visual_layer_ready" in data
        assert "visual_medicines_covered" in data
        assert data["visual_medicines_covered"] >= 8
        assert data["visual_layer_ready"] is True
