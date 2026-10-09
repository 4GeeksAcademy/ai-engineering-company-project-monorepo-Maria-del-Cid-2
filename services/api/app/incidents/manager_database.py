"""TinyDB setup for the persistent Incident Manager."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from tinydb import TinyDB

DEFAULT_DATABASE_PATH: Final[Path] = Path(__file__).resolve().parents[3] / "data" / "incidents.json"


def get_database_path() -> Path:
    configured_path = os.getenv("INCIDENTS_DB_PATH")
    return Path(configured_path) if configured_path else DEFAULT_DATABASE_PATH


def create_database(path: str | Path | None = None) -> TinyDB:
    database_path = Path(path) if path is not None else get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return TinyDB(database_path)


def get_database() -> TinyDB:
    return create_database()
