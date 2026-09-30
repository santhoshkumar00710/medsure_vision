"""
app/auth/dependencies.py — FastAPI dependency injectors for JWT auth.

Usage in routes:
  from app.auth.dependencies import get_current_user, require_role

  @router.get("/protected")
  def my_route(user = Depends(get_current_user)):
      ...

  @router.post("/admin-only")
  def admin_route(_ = Depends(require_role("admin"))):
      ...
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Optional Bearer token scheme — auto_error=False so unauthenticated requests
# get a clean 401 rather than FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """
    Extract and verify the JWT from the Authorization: Bearer <token> header.
    Returns the decoded token payload dict on success.
    Raises HTTP 401 on missing/invalid/expired token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        from app.auth.security import decode_token
        payload = decode_token(token)
    except Exception as exc:
        logger.debug("[auth] JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim.",
        )

    return payload


def require_role(*roles: str):
    """
    Dependency factory: require the current user to have one of the given roles.

    Example:
        Depends(require_role("admin"))
        Depends(require_role("admin", "operator"))
    """
    def _check(payload: dict = Depends(get_current_user)) -> dict:
        user_role = payload.get("role", "")
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not authorised for this action. "
                       f"Required: {list(roles)}",
            )
        return payload
    return _check


# Convenience aliases
require_admin    = require_role("admin")
require_operator = require_role("admin", "operator")
