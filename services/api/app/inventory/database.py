"""Lazy SQLModel engine and request-scoped session dependency.

Importing this module does not read environment variables or create a database
engine. The engine is created only when ``get_session`` is first iterated, so
unconfigured application startup remains independent of PostgreSQL.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine


DATABASE_URL_ENV = "DATABASE_URL"


def get_database_url() -> str:
    """Return a validated backend-only database URL without logging its value."""
    database_url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not database_url:
        raise RuntimeError(f"{DATABASE_URL_ENV} is not configured")
    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache the SQLModel engine on first use, without connecting."""
    return create_engine(get_database_url(), pool_pre_ping=True)


def clear_engine_cache() -> None:
    """Dispose the cached engine and clear it; useful for controlled shutdown/tests."""
    engine = get_engine.cache_info()
    if engine.currsize:
        get_engine().dispose()
    get_engine.cache_clear()


def get_session() -> Iterator[Session]:
    """Yield a session per request and always close it after response handling."""
    try:
        session = Session(get_engine())
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La persistencia de inventario no está configurada.",
        ) from exc

    try:
        yield session
    finally:
        session.close()
