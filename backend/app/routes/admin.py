"""
app/routes/admin.py — Admin-only routes (Task 3 + Task 4).

Routes:
  POST /admin/sync-alerts   — Manually trigger regulatory recall sync (admin only)
  GET  /admin/sync-status   — Get last sync summary (admin only)
  GET  /admin/users         — List users (admin only)
  POST /admin/users         — Create a new user (admin only)
  DELETE /admin/users/{id}  — Deactivate a user (admin only)

All routes require a valid JWT with role == "admin".
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.dependencies import require_role
from app.auth.models import User
from app.auth.schemas import UserCreate, UserOut
from app.auth.service import create_user, list_users, deactivate_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Last sync summary cache (in-memory, reset on restart)
_last_sync_summary: dict[str, Any] = {}


# ── POST /admin/sync-alerts ───────────────────────────────────────────────

@router.post("/sync-alerts", summary="Trigger regulatory recall sync")
def trigger_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    """
    Manually trigger a background sync of regulatory recalls from
    CDSCO (India) and OpenFDA (USA). Returns immediately; sync runs in background.
    """
    global _last_sync_summary

    def _do_sync():
        global _last_sync_summary
        from app.db import SessionLocal
        sync_db = SessionLocal()
        try:
            from app.sync.recall_sync import sync_alerts_to_db
            result = sync_alerts_to_db(sync_db)
            _last_sync_summary = result
            logger.info("Manual recall sync complete: %s", result)
        except Exception as exc:
            logger.error("Manual recall sync failed: %s", exc)
            _last_sync_summary = {"error": str(exc)}
        finally:
            sync_db.close()

    background_tasks.add_task(_do_sync)
    return {"message": "Recall sync started in background", "status": "running"}


# ── GET /admin/sync-status ────────────────────────────────────────────────

@router.get("/sync-status", summary="Last sync summary")
def sync_status(
    _: dict = Depends(require_role("admin")),
):
    """Return the result of the last regulatory recall sync."""
    if not _last_sync_summary:
        return {"message": "No sync has run yet in this session.", "summary": None}
    return {"summary": _last_sync_summary}


# ── GET /admin/users ──────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut], summary="List all users")
def get_users(
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    return list_users(db)


# ── POST /admin/users ─────────────────────────────────────────────────────

@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Create a new user")
def create_new_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin")),
):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists.",
        )
    return create_user(db, body)


# ── DELETE /admin/users/{user_id} ─────────────────────────────────────────

@router.delete("/users/{user_id}", summary="Deactivate a user")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: dict = Depends(require_role("admin")),
):
    if current.get("sub") == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    ok = deactivate_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"User {user_id} deactivated."}
