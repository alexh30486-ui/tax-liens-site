"""
Postgres connection pool lifecycle.

Kept separate from main.py and routers so both can depend on it without
circular imports, and so it's testable in isolation.
"""

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(database_url: str) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """FastAPI dependency. Raises clearly if called before startup finished,
    instead of a confusing AttributeError on None."""
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized — app.main's lifespan handler "
            "should have called init_pool() at startup."
        )
    return _pool
