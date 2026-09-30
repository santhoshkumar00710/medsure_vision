"""
app/auth/models.py — SQLAlchemy User model.

Roles:
  operator  — Can scan medicines, view their own history.
  admin     — All operator permissions + user management, sync triggers,
              alert overrides, and medicine reference library editing.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from app.db import Base


class User(Base):
    """Application user with role-based access."""
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String, unique=True, nullable=False, index=True)
    email      = Column(String, unique=True, nullable=True, index=True)
    full_name  = Column(String, nullable=True)
    hashed_pw  = Column(String, nullable=False)

    # role: "operator" | "admin"
    role       = Column(String, nullable=False, default="operator")
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
