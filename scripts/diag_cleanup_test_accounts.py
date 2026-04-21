#!/usr/bin/env python3
"""
Test-account cleanup — DELETE all dev/synthetic/audit/preview accounts from
prod DB (and the linked Supabase auth.users), keeping only real human users.

USAGE:
    # Always dry-run first to see exactly what will be deleted:
    python scripts/diag_cleanup_test_accounts.py

    # When happy with the dry-run preview, execute:
    python scripts/diag_cleanup_test_accounts.py --execute

Safety:
  - Default mode is DRY-RUN (prints what would happen, deletes nothing).
  - Explicit allowlist of REAL users — anyone matching the allowlist is
    NEVER touched, regardless of any other heuristic.
  - One transaction per student → if anything fails mid-cleanup, only that
    student's deletes roll back, the rest persist (limits blast radius).
  - Logs every action to /tmp/diag/cleanup_log.txt with timestamps.
  - Cascading deletes are EXPLICIT (concept_mastery → session_events →
    doubt_blocks → doubt_sessions → study_sessions → student_memory →
    students → auth.users) — no reliance on FK CASCADE because some FKs
    use SET NULL which would orphan rows.

What gets KEPT:
  - srivastava.ish@northeastern.edu (Ishan, all variants)
  - ajaey.incredible@gmail.com (Ajaey, all variants)
  - Any students.email matching the ALLOWLIST_EMAILS set
  - Test Student (00e92458) — has 84 mastery rows, valuable historical data

What gets DELETED:
  - All synthbeta+*@upmyrank.test (synthetic_beta.py output)
  - All audit.*@upmyrank.test (Phase 8 security tests)
  - All uidemo+preview@upmyrank.test (preview tests)
  - All *@t.local + *@test.local (older dev sprints)
  - Any *@upmyrank.test that ISN'T in the allowlist
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from typing import Any

import asyncpg
import httpx

# ── CONFIG ─────────────────────────────────────────────────────────────────

DATABASE_URL = None
SUPABASE_URL = None
SUPABASE_SECRET_KEY = None
with open("/Users/ishansrivastava/Desktop/upmyrank/.env") as f:
    for line in f:
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            DATABASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("SUPABASE_URL="):
            SUPABASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("SUPABASE_SECRET_KEY="):
            SUPABASE_SECRET_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")

assert DATABASE_URL, "DATABASE_URL missing from .env"
assert SUPABASE_URL, "SUPABASE_URL missing from .env"
assert SUPABASE_SECRET_KEY, "SUPABASE_SECRET_KEY missing from .env"

# ── ALLOWLIST — these students are ALWAYS preserved ────────────────────────
ALLOWLIST_EMAILS = {
    "srivastava.ish@northeastern.edu",  # Ishan (you), primary
    "ajaey.incredible@gmail.com",        # Ajaey, real
}

# Specific student IDs to preserve regardless of email pattern.
# 00e92458 = "Test Student" with 84 mastery rows — historical data we don't
# want to lose (it's the only proof we have that the genome update path
# CAN work when sessions actually end).
ALLOWLIST_STUDENT_IDS = {
    "00e92458-",  # Test Student — UUID prefix; we'll match on str(uuid).startswith
}

# Names with no email (NULL email) that we want to preserve — these are
# accounts created via direct DB insert during early dev that may be real.
ALLOWLIST_NAMES_WHEN_NO_EMAIL = {
    "Sri", "IS", "Ishan", "Ajaey Sharma",
}


def is_allowlisted(student: dict) -> bool:
    """True if this student should be PRESERVED."""
    email = (student.get("email") or "").lower().strip()
    name = (student.get("name") or "").strip()
    sid = str(student.get("id", ""))

    if email and email in ALLOWLIST_EMAILS:
        return True
    if any(sid.startswith(prefix) for prefix in ALLOWLIST_STUDENT_IDS):
        return True
    if not email and name in ALLOWLIST_NAMES_WHEN_NO_EMAIL:
        return True
    return False


def is_test_account(student: dict) -> bool:
    """Heuristic: does this look like a test/dev/synthetic account?"""
    email = (student.get("email") or "").lower().strip()
    name = (student.get("name") or "").lower().strip()

    if not email:
        # No email + name not in allowlist → conservative: don't delete
        return False

    test_email_patterns = (
        "synthbeta+",
        "audit.",
        "uidemo+",
        "@t.local",
        "@test.local",
        "@upmyrank.test",
    )
    if any(p in email for p in test_email_patterns):
        return True

    # Name heuristics — only when also non-real-looking
    test_name_patterns = (
        "synth ", "audit", "preview", "comp tester", "convq tester",
        "topic test", "verify tester", "gatetest", "batch", "probe",
        "e2e test", "test eval", "test student", "test user",
    )
    if any(p in name for p in test_name_patterns):
        return True

    return False


# ── DB helpers ─────────────────────────────────────────────────────────────

async def list_students(pool) -> list[dict]:
    rows = await pool.fetch("""
        SELECT s.id, s.name, s.email, s.created_at, s.onboarding_completed,
               COALESCE((SELECT COUNT(*) FROM study_sessions ss WHERE ss.student_id = s.id), 0) AS sessions,
               COALESCE((SELECT COUNT(*) FROM doubt_blocks db WHERE db.student_id = s.id), 0) AS doubts,
               COALESCE((SELECT COUNT(*) FROM concept_mastery cm WHERE cm.student_id = s.id), 0) AS mastery_rows
        FROM students s
        ORDER BY s.created_at DESC
    """)
    return [dict(r) for r in rows]


async def count_dependent_rows(pool, student_id) -> dict:
    """Count rows that will be deleted when this student is removed."""
    out = {}
    out["concept_mastery"] = await pool.fetchval("SELECT COUNT(*) FROM concept_mastery WHERE student_id = $1", student_id)
    out["session_events"]  = await pool.fetchval("SELECT COUNT(*) FROM session_events WHERE student_id = $1", student_id)
    out["doubt_blocks"]    = await pool.fetchval("SELECT COUNT(*) FROM doubt_blocks WHERE student_id = $1", student_id)
    out["doubt_sessions"]  = await pool.fetchval("SELECT COUNT(*) FROM doubt_sessions WHERE student_id = $1", student_id)
    out["study_sessions"]  = await pool.fetchval("SELECT COUNT(*) FROM study_sessions WHERE student_id = $1", student_id)
    try:
        out["student_memory"] = await pool.fetchval("SELECT COUNT(*) FROM student_memory WHERE student_id = $1", student_id)
    except Exception:
        out["student_memory"] = 0
    try:
        out["session_metrics"] = await pool.fetchval("SELECT COUNT(*) FROM session_metrics WHERE student_id = $1", student_id)
    except Exception:
        out["session_metrics"] = 0
    try:
        out["response_feedback"] = await pool.fetchval("SELECT COUNT(*) FROM response_feedback WHERE student_id = $1", student_id)
    except Exception:
        out["response_feedback"] = 0
    return out


async def delete_student_cascade(pool, student_id) -> dict:
    """Explicit chain of deletes — one transaction per student.

    v0.20.5 fix: previous version had per-table try/except INSIDE the
    transaction, which poisoned the transaction on first error and
    blocked every subsequent statement. Now: all-or-nothing per student.
    Per-table errors are detected by introspecting the schema first
    (skip tables that don't exist).
    """
    # Some tables may not exist in all migration histories — query schema once.
    existing_tables = {
        r["table_name"] for r in await pool.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
    }
    candidate_tables = (
        "response_feedback", "session_metrics", "concept_mastery",
        "conversation_turn_quality", "judge_evaluations",
        "session_events", "doubt_blocks", "doubt_sessions",
        "study_sessions", "student_memory",
    )
    counts: dict = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for table in candidate_tables:
                if table not in existing_tables:
                    continue
                # Detect column name (some tables use student_id, others may differ)
                cols = await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = $1 AND table_schema = 'public'",
                    table,
                )
                col_names = {r["column_name"] for r in cols}
                if "student_id" not in col_names:
                    continue
                n = await conn.execute(
                    f"DELETE FROM {table} WHERE student_id = $1", student_id,
                )
                counts[table] = n
            n = await conn.execute("DELETE FROM students WHERE id = $1", student_id)
            counts["students"] = n
    return counts


async def delete_supabase_auth_user(http: httpx.AsyncClient, student_id: str) -> str:
    """Best-effort: delete the matching auth.users row in Supabase.

    Tight timeout (5s) — first cleanup run (12:31) hung indefinitely on
    one of the Supabase auth calls, blocking the whole script.
    """
    try:
        r = await asyncio.wait_for(
            http.delete(
                f"{SUPABASE_URL}/auth/v1/admin/users/{student_id}",
                headers={
                    "apikey": SUPABASE_SECRET_KEY,
                    "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
                },
            ),
            timeout=5.0,
        )
        if r.status_code in (200, 204):
            return "deleted"
        if r.status_code == 404:
            return "not_found_in_auth"
        return f"http_{r.status_code}: {r.text[:120]}"
    except asyncio.TimeoutError:
        return "supabase_timeout (DB row deleted, auth row still exists)"
    except Exception as exc:
        return f"error: {str(exc)[:120]}"


# ── Main ───────────────────────────────────────────────────────────────────

async def main(execute: bool):
    log_lines: list[str] = []

    def log(msg: str):
        ts = dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        log_lines.append(line)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)

    log(f"Mode: {'EXECUTE' if execute else 'DRY-RUN'}")
    log(f"Allowlist emails: {sorted(ALLOWLIST_EMAILS)}")
    log(f"Allowlist student-id prefixes: {sorted(ALLOWLIST_STUDENT_IDS)}")
    log(f"Allowlist names-when-no-email: {sorted(ALLOWLIST_NAMES_WHEN_NO_EMAIL)}")

    students = await list_students(pool)
    log(f"\nTotal students in DB: {len(students)}")

    keep, delete, skip = [], [], []
    for s in students:
        if is_allowlisted(s):
            keep.append(s)
        elif is_test_account(s):
            delete.append(s)
        else:
            skip.append(s)  # ambiguous — preserve to be safe

    log(f"  KEEP (allowlisted):       {len(keep)}")
    log(f"  DELETE (test heuristic):  {len(delete)}")
    log(f"  SKIP (ambiguous, kept):   {len(skip)}")

    log("\n=== KEEP list ===")
    for s in keep:
        log(f"  {str(s['id'])[:8]} {(s['name'] or '?'):20s} {(s['email'] or '?'):42s} sess={s['sessions']:>3} doubts={s['doubts']:>3} mastery={s['mastery_rows']:>3}")

    log("\n=== SKIP (ambiguous, kept) ===")
    for s in skip:
        log(f"  {str(s['id'])[:8]} {(s['name'] or '?'):20s} {(s['email'] or '?'):42s} sess={s['sessions']:>3} doubts={s['doubts']:>3}")

    log(f"\n=== DELETE list ({len(delete)} accounts) ===")
    total_deps: dict[str, int] = {}
    for s in delete:
        deps = await count_dependent_rows(pool, s["id"])
        for k, v in deps.items():
            total_deps[k] = total_deps.get(k, 0) + (v if isinstance(v, int) else 0)
        dep_str = " ".join(f"{k}={v}" for k, v in deps.items() if v)
        log(f"  {str(s['id'])[:8]} {(s['name'] or '?'):20s} {(s['email'] or '?'):42s}  | {dep_str}")

    log(f"\n=== Total dependent rows that will be removed ===")
    for k, v in sorted(total_deps.items()):
        log(f"  {k}: {v}")

    if not execute:
        log("\n--- DRY-RUN COMPLETE — nothing was changed. Re-run with --execute to actually delete. ---")
        await pool.close()
        # Save log
        os.makedirs("/tmp/diag", exist_ok=True)
        with open("/tmp/diag/cleanup_log.txt", "w") as f:
            f.write("\n".join(log_lines))
        return

    # ── EXECUTE ─────────────────────────────────────────────────────────────
    log(f"\n!!!  EXECUTING — deleting {len(delete)} accounts and their data  !!!")
    log("Sleeping 5s — Ctrl-C now if you don't want this.")
    await asyncio.sleep(5)

    async with httpx.AsyncClient(timeout=30.0) as http:
        for i, s in enumerate(delete, 1):
            sid = s["id"]
            try:
                db_counts = await delete_student_cascade(pool, sid)
                auth_status = await delete_supabase_auth_user(http, str(sid))
                log(f"  [{i}/{len(delete)}] {str(sid)[:8]} {(s['email'] or '?'):42s} db={db_counts['students']} auth={auth_status}")
            except Exception as exc:
                log(f"  [{i}/{len(delete)}] {str(sid)[:8]} FAILED: {str(exc)[:150]}")

    # Verify after
    after = await list_students(pool)
    log(f"\n=== AFTER ===")
    log(f"Total students remaining: {len(after)}")
    for s in after:
        log(f"  {str(s['id'])[:8]} {(s['name'] or '?'):20s} {(s['email'] or '?'):42s}")

    await pool.close()
    os.makedirs("/tmp/diag", exist_ok=True)
    with open("/tmp/diag/cleanup_log.txt", "w") as f:
        f.write("\n".join(log_lines))
    log("\nFull log → /tmp/diag/cleanup_log.txt")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true",
                   help="Actually delete. Default is dry-run (safe).")
    args = p.parse_args()
    asyncio.run(main(execute=args.execute))
