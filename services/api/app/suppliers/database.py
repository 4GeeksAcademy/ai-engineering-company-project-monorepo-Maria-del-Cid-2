"""TinyDB initialisation for Supplier Directory persistence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from tinydb import TinyDB

DEFAULT_DATABASE_PATH: Final[Path] = Path(__file__).resolve().parents[3] / "data" / "suppliers.json"


def get_database_path() -> Path:
    """Return the configured TinyDB path, defaulting to the service data folder."""

    configured_path = os.getenv("SUPPLIER_DIRECTORY_DB_PATH")
    return Path(configured_path) if configured_path else DEFAULT_DATABASE_PATH


def create_database(path: str | Path | None = None) -> TinyDB:
    """Create a TinyDB instance and its parent directory when needed.

    The optional path is primarily useful for isolated tests. Route and seed
    integrations can use the default path or configure it through the
    ``SUPPLIER_DIRECTORY_DB_PATH`` environment variable.
    """

    database_path = Path(path) if path is not None else get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(database_path)


def get_database() -> TinyDB:
    """Return the application database instance."""

    return create_database()
