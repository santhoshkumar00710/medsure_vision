"""
app/auth/service.py — Business logic for user management.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.schemas import UserCreate
from app.auth.security import hash_password, verify_password


def create_user(db: Session, data: UserCreate) -> User:
    """Create and persist a new user. Returns the saved User ORM object."""
    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        hashed_pw=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Return the User if credentials are valid, else None."""
    user: Optional[User] = db.query(User).filter(
        User.username == username,
        User.is_active == True,
    ).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_pw):
        return None
    # Record last login
    user.last_login = datetime.utcnow()
    db.commit()
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id).all()


def deactivate_user(db: Session, user_id: int) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    user.is_active = False
    db.commit()
    return True


def change_password(db: Session, user_id: int, old_pw: str, new_pw: str) -> bool:
    """Verify old password then update to new. Returns False if old_pw wrong."""
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user or not verify_password(old_pw, user.hashed_pw):
        return False
    user.hashed_pw = hash_password(new_pw)
    db.commit()
    return True


def ensure_default_admin(db: Session) -> None:
    """
    Create a default admin account if no users exist at all.
    Credentials: admin / medsure-admin-2024
    This account should be changed immediately in production.
    """
    if db.query(User).count() > 0:
        return
    import logging
    logging.getLogger(__name__).warning(
        "[auth] No users found — creating default admin (username=admin). "
        "CHANGE THE PASSWORD IMMEDIATELY in production!"
    )
    create_user(db, UserCreate(
        username="admin",
        password="medsure-admin-2024",
        full_name="Default Admin",
        role="admin",
    ))
