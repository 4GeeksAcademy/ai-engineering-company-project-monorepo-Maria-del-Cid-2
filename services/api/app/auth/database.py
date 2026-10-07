"""TinyDB initialisation for Users and Profiles persistence.

Mantiene una base de datos TinyDB independiente de la de suppliers
para evitar acoplar la persistencia de autenticación con la de negocio.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from tinydb import TinyDB

DEFAULT_DATABASE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3] / "data" / "auth.json"
)


def get_database_path() -> Path:
    """Return the configured TinyDB path, defaulting to ``data/auth.json``."""

    configured_path = os.getenv("AUTH_DB_PATH")
    return Path(configured_path) if configured_path else DEFAULT_DATABASE_PATH


def create_database(path: str | Path | None = None) -> TinyDB:
    """Create (or open) a TinyDB instance for auth data.

    The optional path lets tests use a temporary file without affecting the
    real database. Production code can configure the path via the
    ``AUTH_DB_PATH`` environment variable.
    """

    database_path = Path(path) if path is not None else get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(database_path)


def get_database() -> TinyDB:
    """Return the application auth database instance."""

    return create_database()


def get_users_table(database: TinyDB | None = None) -> TinyDB.table_class:
    """Return the ``users`` table from the auth database."""

    db = database if database is not None else get_database()
    return db.table("users")


def get_profiles_table(database: TinyDB | None = None) -> TinyDB.table_class:
    """Return the ``profiles`` table from the auth database."""

    db = database if database is not None else get_database()
    return db.table("profiles")


def get_password_reset_tokens_table(database: TinyDB | None = None) -> TinyDB.table_class:
    """Return the password reset token table from the auth database."""

    db = database if database is not None else get_database()
    return db.table("password_reset_tokens")