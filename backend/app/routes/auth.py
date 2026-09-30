"""
app/routes/auth.py — Authentication endpoints.

POST /auth/login          — Username + password → JWT token
POST /auth/refresh        — Refresh an existing (non-expired) token
GET  /auth/me             — Return current user profile
POST /auth/change-password — Change own password
"""
from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.schemas import ChangePassword, LoginRequest, Token, UserOut
from app.auth.service import authenticate_user, change_password
from app.auth.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
)
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── POST /auth/login ──────────────────────────────────────────────────────

@router.post("/login", response_model=Token, summary="Obtain JWT access token")
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate with username + password.
    Returns a signed JWT valid for MEDSURE_JWT_EXPIRE minutes (default 8 hours).
    
    Roles:
      - **operator**: Can scan medicines and view scan history.
      - **admin**: Full access including user management and alert sync.
    """
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "username": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    logger.info("[auth] Login: user=%s role=%s", user.username, user.role)
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=user.role,
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────

@router.post("/refresh", response_model=Token, summary="Refresh JWT token")
def refresh_token(payload: dict = Depends(get_current_user)):
    """
    Issue a new token using an existing valid token.
    The old token continues to be valid until its original expiry.
    """
    new_token = create_access_token(
        data={
            "sub":      payload["sub"],
            "role":     payload.get("role", "operator"),
            "username": payload.get("username", ""),
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(
        access_token=new_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=payload.get("role", "operator"),
    )


# ── GET /auth/me ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut, summary="Get current user profile")
def me(
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.auth.models import User
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found or deactivated.")
    return user


# ── POST /auth/change-password ────────────────────────────────────────────

@router.post("/change-password", summary="Change own password")
def change_own_password(
    body: ChangePassword,
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = change_password(db, int(payload["sub"]), body.old_password, body.new_password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect.",
        )
    return {"message": "Password changed successfully."}
