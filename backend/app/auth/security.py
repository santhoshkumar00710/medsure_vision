"""
app/auth/security.py — Password hashing, JWT encoding/decoding.

Uses:
  - bcrypt (via passlib) for password hashing.
  - python-jose for JWT (HS256).
  
Secret key and token lifetime are read from environment variables:
  MEDSURE_JWT_SECRET  — REQUIRED in production (falls back to insecure dev key).
  MEDSURE_JWT_EXPIRE  — Token lifetime in minutes (default: 480 = 8 hours).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────

SECRET_KEY: str = os.environ.get(
    "MEDSURE_JWT_SECRET",
    "medsure-dev-jwt-secret-CHANGE-IN-PROD-USE-32-CHARS-MIN",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("MEDSURE_JWT_EXPIRE", "480")   # 8 hours default
)

if SECRET_KEY.startswith("medsure-dev"):
    logger.warning(
        "[auth] Using default dev JWT secret. Set MEDSURE_JWT_SECRET env var in production!"
    )


# ── Password hashing ───────────────────────────────────────────────────────

try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _PASSLIB_OK = True
except ImportError:
    _PASSLIB_OK = False
    logger.error(
        "[auth] passlib not installed — password hashing unavailable. "
        "Run: pip install passlib[bcrypt]"
    )


def hash_password(plain: str) -> str:
    if not _PASSLIB_OK:
        raise RuntimeError("passlib[bcrypt] required for password hashing.")
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not _PASSLIB_OK:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────

try:
    from jose import JWTError, jwt as _jose_jwt
    _JOSE_OK = True
except ImportError:
    _JOSE_OK = False
    logger.error(
        "[auth] python-jose not installed — JWT disabled. "
        "Run: pip install python-jose[cryptography]"
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if not _JOSE_OK:
        raise RuntimeError("python-jose required for JWT.")
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    payload["iat"] = datetime.now(timezone.utc)
    return _jose_jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises jose.JWTError on failure."""
    if not _JOSE_OK:
        raise RuntimeError("python-jose required for JWT.")
    return _jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
