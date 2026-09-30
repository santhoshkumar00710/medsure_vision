"""
app/auth/schemas.py — Pydantic schemas for authentication endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Tokens ────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int           # seconds
    role: str


class TokenData(BaseModel):
    sub: Optional[str] = None    # user ID as string
    role: Optional[str] = None


# ── Login ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=6, max_length=128)


# ── User management ───────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username:  str            = Field(..., min_length=2, max_length=80)
    password:  str            = Field(..., min_length=6, max_length=128)
    email:     Optional[str]  = None
    full_name: Optional[str]  = None
    role:      str            = Field("operator", pattern="^(operator|admin)$")


class UserOut(BaseModel):
    id:         int
    username:   str
    email:      Optional[str]
    full_name:  Optional[str]
    role:       str
    is_active:  bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]

    model_config = {"from_attributes": True}


class ChangePassword(BaseModel):
    old_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6, max_length=128)
