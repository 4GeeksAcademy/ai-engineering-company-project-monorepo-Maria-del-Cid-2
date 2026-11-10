"""Read adapter for the reporting PostgreSQL schema."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

REPORTING_DATABASE_URL_ENV = "REPORTING_DATABASE_URL"
PIPELINE_NAME = "weekly_office_program_performance"


class ReportingStorageUnavailable(RuntimeError):
    """Raised when reporting storage is not configured or cannot be queried."""


def get_reporting_database_url() -> str:
    url = os.environ.get(REPORTING_DATABASE_URL_ENV, "").strip()
    if not url:
        raise ReportingStorageUnavailable(f"{REPORTING_DATABASE_URL_ENV} is not configured")
    if not url.startswith(("postgresql://", "postgres://")):
        raise ReportingStorageUnavailable(f"{REPORTING_DATABASE_URL_ENV} must use a PostgreSQL URL")
    return url


class ReportingRepository:
    """Read reporting results/history using the dedicated reporting URL."""

    def __init__(self, connect: Callable[..., Any] = psycopg.connect) -> None:
        self._connect = connect

    def latest_pipeline_run(self) -> dict[str, Any] | None:
        query = """
            SELECT id, pipeline_name, week_start, status, started_at, finished_at,
                   records_processed, records_inserted, records_updated,
                   records_rejected, error_message, trigger_type
            FROM reporting.pipeline_runs
            WHERE pipeline_name = %s
            ORDER BY started_at DESC, id DESC
            LIMIT 1
        """
        return self._fetch_one(query, (PIPELINE_NAME,))

    def weekly_performance(
        self,
        *,
        week_start: Any | None = None,
        office: str | None = None,
        programme_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if week_start is not None:
            conditions.append("week_start = %s")
            parameters.append(week_start)
        if office is not None:
            conditions.append("office = %s")
            parameters.append(office)
        if programme_id is not None:
            conditions.append("programme_id = %s")
            parameters.append(programme_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        query = f"""
            SELECT office, programme_id, week_start, total_material_cost,
                   kits_delivered_count, shortage_events_count,
                   cost_variance_events_count, currency, computed_at
            FROM reporting.weekly_office_program_performance
            {where}
            ORDER BY week_start DESC, office ASC, programme_id ASC
            LIMIT %s
        """
        return self._fetch_all(query, tuple(parameters))

    def _fetch_one(self, query: str, parameters: tuple[Any, ...]) -> dict[str, Any] | None:
        try:
            with self._connect(get_reporting_database_url(), row_factory=dict_row) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, parameters)
                    row = cursor.fetchone()
                connection.commit()
        except ReportingStorageUnavailable:
            raise
        except psycopg.Error as exc:
            raise ReportingStorageUnavailable("reporting query failed") from exc
        return dict(row) if row is not None else None

    def _fetch_all(self, query: str, parameters: tuple[Any, ...]) -> list[dict[str, Any]]:
        try:
            with self._connect(get_reporting_database_url(), row_factory=dict_row) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, parameters)
                    rows = cursor.fetchall()
                connection.commit()
        except ReportingStorageUnavailable:
            raise
        except psycopg.Error as exc:
            raise ReportingStorageUnavailable("reporting query failed") from exc
        return [dict(row) for row in rows]
