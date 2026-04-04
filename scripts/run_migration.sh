#!/usr/bin/env bash
# run_migration.sh — run any SQL migration file against the Supabase DB
#
# Usage:
#   ./scripts/run_migration.sh scripts/migrate_v4_memory.sql
#   ./scripts/run_migration.sh scripts/migrate_v5_persona.sql
#
# Reads DATABASE_URL from .env in the project root.
# Requires: Python 3.11 + asyncpg (already in Poetry venv)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
PYTHON="$PROJECT_ROOT/.venv/bin/python"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <path-to-sql-file>" >&2
  exit 1
fi

SQL_FILE="$1"

if [[ ! -f "$SQL_FILE" ]]; then
  echo "Error: SQL file not found: $SQL_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: .env file not found at $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f "$PYTHON" ]]; then
  echo "Error: Poetry venv not found at $PYTHON — run 'poetry install' first" >&2
  exit 1
fi

echo "Running migration: $SQL_FILE"

"$PYTHON" - "$SQL_FILE" "$ENV_FILE" <<'PYEOF'
import asyncio
import sys
import os

async def main(sql_file: str, env_file: str):
    # Load DATABASE_URL from .env
    db_url = None
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                db_url = line[len("DATABASE_URL="):]
                break

    if not db_url:
        print("Error: DATABASE_URL not found in .env", file=sys.stderr)
        sys.exit(1)

    with open(sql_file) as f:
        sql = f.read()

    import asyncpg

    # asyncpg requires postgresql:// scheme (not postgres://)
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(sql)
        print("Migration applied successfully.")
    finally:
        await conn.close()

asyncio.run(main(sys.argv[1], sys.argv[2]))
PYEOF

echo "Done."
