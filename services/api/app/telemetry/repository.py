"""PostgreSQL persistence adapter for telemetry events.

Telemetry deliberately uses its own ``TELEMETRY_DATABASE_URL`` setting instead
of the inventory ``DATABASE_URL``. That prevents a local SQLite inventory
configuration from being used accidentally for Supabase telemetry writes.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


TELEMETRY_DATABASE_URL_ENV = "TELEMETRY_DATABASE_URL"


class TelemetryStorageUnavailable(RuntimeError):
    """Raised when telemetry persistence has no valid PostgreSQL destination."""


@dataclass(frozen=True)
class TelemetryRecord:
    """One already-validated row ready for ``telemetry_events``."""

    event_id: str
    event_type: str
    timestamp: str
    source: str
    session_id: str | None
    schema_version: str | None
    tags: dict[str, Any]


def get_telemetry_database_url() -> str:
    """Return the private telemetry PostgreSQL URL without logging it."""

    database_url = os.environ.get(TELEMETRY_DATABASE_URL_ENV, "").strip()
    if not database_url:
        raise TelemetryStorageUnavailable(
            f"{TELEMETRY_DATABASE_URL_ENV} is not configured"
        )
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise TelemetryStorageUnavailable(
            f"{TELEMETRY_DATABASE_URL_ENV} must use a PostgreSQL URL"
        )
    return database_url


class TelemetryRepository:
    """Append-only bulk writer for the Supabase telemetry table."""

    def __init__(self, connect: Callable[[str], Any] = psycopg.connect) -> None:
        self._connect = connect

    def insert_many(self, records: Sequence[TelemetryRecord]) -> int:
        """Persist records with one INSERT statement and return inserted count.

        ``event_id`` is unique. A retry containing an event that already exists
        is idempotently ignored instead of turning the complete batch into an
        error. No UPDATE or DELETE query is issued by this adapter.
        """

        if not records:
            return 0

        placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s)"] * len(records))
        query = (
            "INSERT INTO public.telemetry_events "
            "(event_id, event_type, timestamp, source, session_id, schema_version, tags) "
            f"VALUES {placeholders} "
            "ON CONFLICT (event_id) DO NOTHING "
            "RETURNING event_id"
        )
        parameters: list[Any] = []
        for record in records:
            parameters.extend(
                (
                    record.event_id,
                    record.event_type,
                    record.timestamp,
                    record.source,
                    record.session_id,
                    record.schema_version,
                    Jsonb(record.tags),
                )
            )

        try:
            with self._connect(get_telemetry_database_url()) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, parameters)
                    inserted_count = len(cursor.fetchall())
                connection.commit()
        except TelemetryStorageUnavailable:
            raise
        except psycopg.Error as exc:
            raise TelemetryStorageUnavailable("telemetry persistence failed") from exc

        return inserted_count
