"""
scripts/seed_db.py — Seed the database with medicines, alerts,
registry entries, clone scenario, and demo case metadata.

Run: python scripts/seed_db.py  (from the backend/ directory)
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent to path so we can import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import engine, SessionLocal, Base
from app.models import Alert, RegistrySim, ScanEvent
from app.config import DATA_DIR
from app.pipeline.authenticity import hash_field, normalise_batch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_db")


def seed_alerts(db):
    alerts_path = DATA_DIR / "alerts.json"
    if not alerts_path.exists():
        logger.warning("alerts.json not found — skipping alerts seed")
        return
    data = json.loads(alerts_path.read_text(encoding="utf-8"))
    count = 0
    for a in data:
        existing = db.query(Alert).filter(Alert.id == a["id"]).first()
        if existing:
            continue
        row = Alert(
            id=a["id"],
            brand=a["brand"],
            generic=a.get("generic"),
            batch_norm=a["batch_norm"],
            batch_raw=a.get("batch_raw"),
            mfg=a.get("mfg"),
            exp=a.get("exp"),
            manufacturer=a.get("manufacturer"),
            status=a.get("status", "recalled"),
            reason=a.get("reason"),
            source_month=a.get("source_month"),
            source_url=a.get("source_url"),
            snapshot_date=a.get("snapshot_date"),
            simulated=a.get("simulated", False),
        )
        db.add(row)
        count += 1
    db.commit()
    logger.info("Seeded %d alerts", count)


def seed_registry(db):
    """Seed demo codes into simulated registry."""
    entries = [
        # Genuine serial for Monocef clone scenario
        {"gtin": "08901234000034", "serial": "SERIAL_MN_001", "batch": "MN-0994", "status": "valid"},
        {"gtin": "08901234000034", "serial": "SERIAL_MN_002", "batch": "MN-0994", "status": "already_used"},
        # Genuine Cefix-O
        {"gtin": "08901234000058", "serial": "SERIAL_CFX_001", "batch": "CFX-88219", "status": "valid"},
        # Demo cases
        {"gtin": "08901234000010", "serial": "DEMO_GENUINE_001", "batch": "24B901", "status": "valid"},
        {"gtin": "08901234000010", "serial": "DEMO_CLONE_001", "batch": "CLONE-BATCH", "status": "already_used"},
        {"gtin": "08901234000041", "serial": "DEMO_DL_001", "batch": "DL-3341", "status": "blocked"},
    ]
    count = 0
    for e in entries:
        existing = db.query(RegistrySim).filter_by(
            gtin=e["gtin"], serial=e["serial"]
        ).first()
        if existing:
            continue
        row = RegistrySim(
            gtin=e["gtin"],
            serial=e["serial"],
            batch=e.get("batch"),
            status=e["status"],
            simulated=True,
        )
        db.add(row)
        count += 1
    db.commit()
    logger.info("Seeded %d registry entries", count)


def seed_clone_scenario(db):
    """
    Seed: same serial scanned in Chennai, then Delhi 40 min later by
    different device tokens. Labelled simulated.
    """
    serial = "SERIAL_MN_002"
    batch = "MN-0994"
    serial_hash = hash_field(serial)
    batch_hash = hash_field(normalise_batch(batch))

    base_ts = datetime(2026, 9, 30, 8, 30, 0, tzinfo=timezone.utc)

    events = [
        {
            "serial_hash": serial_hash,
            "batch_hash": batch_hash,
            "district": "Chennai",
            "lat_round": 13.08,
            "lng_round": 80.27,
            "ts": base_ts,
            "device_token": "device_chennai_001",
            "label": "low_risk",
            "quality_ok": True,
            "printed_batch": batch,
            "printed_expiry": "12/2025",
            "printed_name": "Monocef 1g Injection",
            "simulated": True,
        },
        {
            "serial_hash": serial_hash,
            "batch_hash": batch_hash,
            "district": "Delhi",
            "lat_round": 28.61,
            "lng_round": 77.20,
            "ts": base_ts + timedelta(minutes=40),
            "device_token": "device_delhi_002",
            "label": "high_suspicion",
            "quality_ok": True,
            "printed_batch": batch,
            "printed_expiry": "12/2025",
            "printed_name": "Monocef 1g Injection",
            "simulated": True,
        },
    ]

    count = 0
    for e in events:
        existing = db.query(ScanEvent).filter(
            ScanEvent.serial_hash == serial_hash,
            ScanEvent.device_token == e["device_token"],
        ).first()
        if existing:
            continue
        row = ScanEvent(**e)
        db.add(row)
        count += 1
    db.commit()
    logger.info("Seeded %d clone scenario events", count)


def create_demo_case_placeholders():
    """Create placeholder info files for each demo case."""
    from app.config import DEMO_CASES_DIR
    cases = {
        "genuine":          {"desc": "Genuine medicine pack — all checks pass"},
        "expiry_tampered":  {"desc": "Expiry date altered — high suspicion"},
        "logo_shifted":     {"desc": "Logo position shifted — needs verification"},
        "clone_code":       {"desc": "Cloned QR code — high suspicion"},
        "alert_match":      {"desc": "Batch matches CDSCO alert — high suspicion"},
        "blurry":           {"desc": "Blurry image — insufficient quality"},
    }
    for case_id, meta in cases.items():
        case_dir = DEMO_CASES_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        info_file = case_dir / "info.json"
        if not info_file.exists():
            import json
            info_file.write_text(json.dumps(meta, indent=2))
    logger.info("Demo case directories ready")


def main():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_alerts(db)
        seed_registry(db)
        seed_clone_scenario(db)
        create_demo_case_placeholders()
        logger.info("Database seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
