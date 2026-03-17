import logging
from typing import Optional

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_db() -> None:
    global _pool

    dsn = settings.database_url
    kwargs: dict = dict(min_size=2, max_size=10)

    # Supabase uses PgBouncer in Transaction mode (port 5432):
    #   • statement_cache_size=0  — prepared statements unsupported by pgbouncer
    #   • ssl='require'           — Supabase mandates TLS
    # Strip ?sslmode= if present; asyncpg uses the explicit ssl kwarg instead.
    if "supabase.com" in dsn:
        kwargs["statement_cache_size"] = 0
        kwargs["ssl"] = "require"
        # asyncpg doesn't parse ?sslmode from the DSN; remove it to avoid warnings
        dsn = dsn.split("?")[0]

    _pool = await asyncpg.create_pool(dsn=dsn, **kwargs)
    logger.info("Database pool initialized (min=2, max=10)")


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return _pool
