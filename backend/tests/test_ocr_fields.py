"""tests/test_ocr_fields.py — Task 2.3: unit tests for Indian strip date/batch formats."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.fields import _parse_batch, _parse_expiry, _parse_mfg_date


class TestBatchPatterns:
    def test_batch_no(self):        assert _parse_batch("Batch No. 24B901") == "24B901"
    def test_b_no(self):            assert _parse_batch("B.No. XY-1234") == "XY-1234"
    def test_bn(self):              assert _parse_batch("BN: AB001") == "AB001"
    def test_b_no_space(self):      assert _parse_batch("B NO 9988A") == "9988A"
    def test_batch_no_slash(self):  assert _parse_batch("BATCH NO: MN-0994") == "MN-0994"
    def test_batch_colon(self):     assert _parse_batch("batch: ABC123") == "ABC123"
    def test_lot_no(self):          assert _parse_batch("Lot No. L24001") == "L24001"


class TestExpiryPatterns:
    def test_exp_slash(self):       assert _parse_expiry("Exp: 05/2027") == "05/2027"
    def test_exp_dash(self):        assert _parse_expiry("EXP. 05-27") in ("05/2027", "05-27", "05/27")
    def test_exp_dot(self):         assert _parse_expiry("E.D. 05.2027") is not None
    def test_exp_month_name(self):  assert _parse_expiry("MAY 2027") is not None
    def test_exp_short(self):       assert _parse_expiry("Exp 11/2026") == "11/2026"
    def test_exp_dt(self):          assert _parse_expiry("EXP. DT 08/2025") == "08/2025"
    def test_exp_ed(self):          assert _parse_expiry("E.D.: 12/2026") == "12/2026"


class TestMfgDatePatterns:
    def test_mfg(self):             assert _parse_mfg_date("Mfg: 06/2024") == "06/2024"
    def test_mfg_dt(self):          assert _parse_mfg_date("MFG. DT 03/2023") == "03/2023"
    def test_md(self):              assert _parse_mfg_date("M.D.: 01/2022") == "01/2022"
    def test_manufacturing_date(self): assert _parse_mfg_date("Manufacturing Date: 07/2023") is not None
    def test_manuf(self):           assert _parse_mfg_date("Manuf. 09-2024") is not None
