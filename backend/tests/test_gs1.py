"""
tests/test_gs1.py — GS1 parser unit tests.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.gs1 import parse_gs1, _luhn_check, _gs1_date_to_mmyyyy


class TestGTINCheckDigit:
    def test_valid_gtin(self):
        # 08901234000014 has correct check digit 4
        assert _luhn_check("08901234000014") is True

    def test_invalid_gtin(self):
        # Deliberately wrong check digit
        assert _luhn_check("08901234000015") is False

    def test_short_gtin(self):
        assert _luhn_check("123") is False


class TestGS1DateParsing:
    def test_normal_date(self):
        assert _gs1_date_to_mmyyyy("261130") == "11/2026"

    def test_day_zero(self):
        # Day 00 → last day of month
        result = _gs1_date_to_mmyyyy("261100")
        assert result == "11/2026"

    def test_invalid_month(self):
        assert _gs1_date_to_mmyyyy("261300") is None

    def test_invalid_day(self):
        assert _gs1_date_to_mmyyyy("261132") is None  # day 32

    def test_pivot_year_old(self):
        # yy=50 → 1950
        result = _gs1_date_to_mmyyyy("500630")
        assert result == "06/1950"


class TestGS1Parser:
    def test_gs1_with_prefix_d2(self):
        # ]d2 prefix — 08901234000014 has valid check digit
        raw = "]d201089012340000141726113010BATCH001"
        result = parse_gs1(raw)
        assert result.gtin == "08901234000014"
        assert result.gtin_valid is True
        assert result.expiry == "11/2026"
        assert result.batch == "BATCH001"

    def test_bracketed_format(self):
        raw = "(01)08901234000014(10)BATCH123(17)261130(21)SERIAL001"
        result = parse_gs1(raw)
        assert result.gtin == "08901234000014"
        assert result.batch == "BATCH123"
        assert result.expiry == "11/2026"
        assert result.serial == "SERIAL001"

    def test_gs_separator(self):
        raw = "01089012340000141726113010BATCH456\x1d21SER999"
        result = parse_gs1(raw)
        assert result.gtin == "08901234000014"
        assert result.serial == "SER999"

    def test_bad_gtin_detected(self):
        raw = "(01)08901234000015(10)BATCH"  # wrong check digit
        result = parse_gs1(raw)
        assert result.gtin_valid is False

    def test_empty_payload(self):
        result = parse_gs1("")
        assert result.gtin is None
        assert len(result.parse_errors) > 0

    def test_q3_prefix(self):
        raw = "]Q301089012340000141726113010LOT001"
        result = parse_gs1(raw)
        assert result.gtin == "08901234000014"

    def test_no_serial(self):
        raw = "(01)08901234000014(10)BATCH123(17)261130"
        result = parse_gs1(raw)
        assert result.serial is None

    def test_bad_expiry_month_graceful(self):
        # Month 13 is invalid — should not raise, return parse error
        raw = "(01)08901234000014(17)261300"
        result = parse_gs1(raw)
        assert result.expiry is None
        assert any("17" in e for e in result.parse_errors)


class TestDemoFormat:
    def test_demo_format_parse(self):
        from app.pipeline.codes import _parse_demo_payload
        raw = "MEDSURE|08901234000014|BATCH001|11/2026|SERIAL001|Dolo 650"
        result = _parse_demo_payload(raw)
        assert result.code_type == "demo"
        assert result.gtin == "08901234000014"
        assert result.batch == "BATCH001"
        assert result.expiry == "11/2026"
        assert result.serial == "SERIAL001"
        assert result.has_serial is True
