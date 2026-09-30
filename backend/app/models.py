"""
app/models.py — SQLAlchemy ORM table definitions.
"""

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, JSON
)
from sqlalchemy.orm import relationship

from app.db import Base


class Scan(Base):
    """Stores each scan result."""
    __tablename__ = "scans"

    id = Column(String, primary_key=True)
    device_token = Column(String, nullable=False, index=True)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    label = Column(String, nullable=False)         # low_risk | needs_verification | high_suspicion | insufficient_quality
    partial = Column(Boolean, default=False)
    name = Column(String, nullable=True)
    batch = Column(String, nullable=True)
    expiry = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    top_reason = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=False)      # full ScanResult blob
    session_id = Column(String, ForeignKey("receiving_sessions.id"), nullable=True)
    simulated = Column(Boolean, default=False)

    session = relationship("ReceivingSession", back_populates="scans")


class ScanEvent(Base):
    """Community clone-detection events (anonymised)."""
    __tablename__ = "scan_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_hash = Column(String, nullable=True, index=True)
    batch_hash = Column(String, nullable=True, index=True)
    district = Column(String, nullable=True)
    lat_round = Column(Float, nullable=True)
    lng_round = Column(Float, nullable=True)
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    device_token = Column(String, nullable=False)
    label = Column(String, nullable=True)
    quality_ok = Column(Boolean, default=True)
    simulated = Column(Boolean, default=False)

    # Denormalised for cross-check comparisons
    printed_batch = Column(String, nullable=True)
    printed_expiry = Column(String, nullable=True)
    printed_name = Column(String, nullable=True)


class Alert(Base):
    """CDSCO-sourced alert entries."""
    __tablename__ = "alerts"

    id = Column(String, primary_key=True)
    brand = Column(String, nullable=False)
    generic = Column(String, nullable=True)
    batch_norm = Column(String, nullable=False, index=True)   # normalised batch
    batch_raw = Column(String, nullable=True)
    mfg = Column(String, nullable=True)
    exp = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    status = Column(String, nullable=False, default="recalled")
    reason = Column(Text, nullable=True)
    source_month = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    snapshot_date = Column(String, nullable=True)   # ISO date string
    simulated = Column(Boolean, default=False)


class RegistrySim(Base):
    """Simulated manufacturer registry (demo only)."""
    __tablename__ = "registry_sim"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gtin = Column(String, nullable=False, index=True)
    serial = Column(String, nullable=False, index=True)
    batch = Column(String, nullable=True)
    status = Column(String, nullable=False, default="valid")  # valid | already_used | blocked
    simulated = Column(Boolean, default=True)


class ReceivingSession(Base):
    """Receiving mode bulk-scan sessions."""
    __tablename__ = "receiving_sessions"

    id = Column(String, primary_key=True)
    supplier = Column(String, nullable=True)
    invoice_no = Column(String, nullable=True)    # stays local, never returned in API
    created_at = Column(DateTime, default=datetime.utcnow)
    accepted = Column(Boolean, default=False)

    scans = relationship("Scan", back_populates="session")


class BatchReport(Base):
    """User community reports for suspicious batches."""
    __tablename__ = "batch_reports"

    id = Column(String, primary_key=True)
    scan_id = Column(String, ForeignKey("scans.id"), nullable=True)
    batch_hash = Column(String, nullable=True)
    device_token = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    ts = Column(DateTime, default=datetime.utcnow)
    day_key = Column(String, nullable=True)    # YYYY-MM-DD for rate limiting
