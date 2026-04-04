"""
Auth dependency — extracts and validates Bearer JWT via Supabase.

Usage:
    from app.middleware.auth import get_current_student_id

    @router.post("/some-endpoint")
    async def handler(student_id: str = Depends(get_current_student_id)):
        ...
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


def _get_supabase():
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_secret_key)


async def get_current_student_id(authorization: str = Header(None)) -> str:
    """
    FastAPI dependency — validates Bearer token, returns student UUID string.
    Raises 401 if missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        client = _get_supabase()
        response = await asyncio.to_thread(client.auth.get_user, token)
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if response.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return str(response.user.id)
