#!/usr/bin/env python3
"""
pedagogy_drift_report.py — Weekly pedagogy quality report.

Queries the last 7 days of session_events where scaffolding_score IS NOT NULL,
groups by topic, calculates avg score per topic, and flags topics below 1.5 as
pedagogy drift.

Run:
    cd /Users/ishansrivastava/Desktop/upmyrank
    python scripts/pedagogy_drift_report.py
    python scripts/pedagogy_drift_report.py --days 14   # custom window

Output:
    A formatted table printed to stdout. Exit code 1 if any topic is flagged.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _load_database_url() -> str:
    """Read DATABASE_URL from the .env file in the project root."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f".env not found at {env_path}")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line[len("DATABASE_URL="):]
    raise ValueError("DATABASE_URL not found in .env")


async def run_report(days: int) -> int:
    """
    Run the drift report.

    Returns:
        0 — no drift detected
        1 — one or more topics flagged
    """
    import asyncpg

    db_url = _load_database_url()
    # asyncpg requires postgresql:// scheme
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            f"""
            SELECT
                ds.topic,
                AVG(se.scaffolding_score)::FLOAT  AS avg_score,
                COUNT(*)                          AS session_count
            FROM session_events se
            JOIN doubt_sessions ds ON ds.id = se.session_id
            WHERE se.scaffolding_score IS NOT NULL
              AND se.created_at >= NOW() - INTERVAL '{days} days'
              AND ds.topic IS NOT NULL
            GROUP BY ds.topic
            ORDER BY avg_score ASC
            """
        )
    finally:
        await conn.close()

    if not rows:
        print(f"No scored sessions found in the last {days} days.")
        return 0

    drift_threshold = 1.5
    any_flagged = False

    # ── Print report ──────────────────────────────────────────────────────────
    col_topic   = 35
    col_score   = 12
    col_count   = 10
    col_status  = 24

    header = (
        f"{'TOPIC':<{col_topic}} "
        f"{'AVG SCORE':>{col_score}} "
        f"{'SESSIONS':>{col_count}} "
        f"{'STATUS':<{col_status}}"
    )
    divider = "-" * len(header)

    print(f"\nPedagogy Drift Report — last {days} days")
    print(f"Drift threshold: avg_score < {drift_threshold}")
    print(divider)
    print(header)
    print(divider)

    for row in rows:
        topic       = (row["topic"] or "Unknown")[:col_topic]
        avg_score   = float(row["avg_score"])
        count       = int(row["session_count"])
        is_flagged  = avg_score < drift_threshold
        status      = "⚠️  PEDAGOGY DRIFT DETECTED" if is_flagged else "✓  OK"
        if is_flagged:
            any_flagged = True

        print(
            f"{topic:<{col_topic}} "
            f"{avg_score:>{col_score}.3f} "
            f"{count:>{col_count}} "
            f"{status:<{col_status}}"
        )

    print(divider)
    print(f"\nTotal topics evaluated: {len(rows)}")
    flagged_count = sum(1 for r in rows if float(r["avg_score"]) < drift_threshold)
    if flagged_count:
        print(f"⚠️  {flagged_count} topic(s) below threshold — review Socratic prompt quality.")
    else:
        print("✓  All topics within acceptable range.")
    print()

    return 1 if any_flagged else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Pedagogy drift report")
    parser.add_argument(
        "--days", type=int, default=7,
        help="Number of days to look back (default: 7)",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(run_report(args.days))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
