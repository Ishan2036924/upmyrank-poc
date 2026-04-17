"""
Auth endpoints — Supabase email/password auth.

POST /auth/signup  — register new student
POST /auth/login   — sign in, get JWT
GET  /auth/me      — validate token, return student profile
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Supabase client helper ────────────────────────────────────────────────────

def _get_supabase():
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_secret_key)


# ── Request models ────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    exam_type: str = "JEE"   # JEE or NEET
    target_year: int = 2026


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(body: SignupRequest, request: Request):
    """
    Create a new Supabase auth user then insert a matching row in `students`.
    Returns JWT access token on success.
    """
    pool = request.app.state.db_pool

    if body.exam_type not in ("JEE", "NEET"):
        raise HTTPException(status_code=400, detail="exam_type must be JEE or NEET")

    try:
        client = _get_supabase()
        response = await asyncio.to_thread(
            client.auth.sign_up,
            {"email": body.email, "password": body.password},
        )
    except Exception as exc:
        logger.error("Supabase signup failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if response.user is None:
        raise HTTPException(
            status_code=400,
            detail="Signup failed — check email/password requirements",
        )

    student_id = uuid.UUID(str(response.user.id))

    # Insert student row (idempotent — Supabase may call this twice on retry)
    try:
        await pool.execute(
            """
            INSERT INTO students (id, name, email, exam_type, target_year)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
            """,
            student_id,
            body.name,
            body.email,
            body.exam_type,
            body.target_year,
        )
        # Seed student_memory row (non-fatal if migration not yet applied)
        try:
            await pool.execute(
                "INSERT INTO student_memory (student_id) VALUES ($1) ON CONFLICT DO NOTHING",
                student_id,
            )
        except Exception:
            pass
    except Exception as exc:
        logger.error("DB insert for student %s failed: %s", student_id, exc)
        raise HTTPException(status_code=500, detail="Student record creation failed") from exc

    token         = response.session.access_token  if response.session else None
    refresh_token = response.session.refresh_token if response.session else None
    return {
        "token": token,
        "refresh_token": refresh_token,
        "student_id": str(student_id),
        "name": body.name,
        "exam_type": body.exam_type,
    }


@router.post("/login")
async def login(body: LoginRequest):
    """Sign in with email + password, return JWT."""
    try:
        client = _get_supabase()
        response = await asyncio.to_thread(
            client.auth.sign_in_with_password,
            {"email": body.email, "password": body.password},
        )
    except Exception as exc:
        logger.warning("Supabase login failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc

    if response.user is None or response.session is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "student_id": str(response.user.id),
    }


@router.get("/me")
async def me(request: Request, authorization: str = Header(None)):
    """Validate Bearer token and return student profile."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    pool = request.app.state.db_pool

    try:
        client = _get_supabase()
        response = await asyncio.to_thread(client.auth.get_user, token)
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if response.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    student_id = uuid.UUID(str(response.user.id))

    row = await pool.fetchrow(
        "SELECT id, name, exam_type, target_year FROM students WHERE id = $1",
        student_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Student profile not found")

    return {
        "student_id": str(row["id"]),
        "name": row["name"],
        "exam_type": row["exam_type"],
        "target_year": row["target_year"],
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    """Exchange a Supabase refresh token for a new access token."""
    try:
        client = _get_supabase()
        response = await asyncio.to_thread(
            client.auth.refresh_session,
            body.refresh_token,
        )
    except Exception as exc:
        logger.warning("Token refresh failed: %s", exc)
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.") from exc

    if response.session is None:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    return {
        "token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
    }
