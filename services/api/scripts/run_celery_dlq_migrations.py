"""Apply only the versioned Celery DLQ SQL migrations to CELERY_DATABASE_URL.

Usage: python scripts/run_celery_dlq_migrations.py
The URL is never printed. SSL is required. Run only after explicit approval.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATIONS = (("003_create_celery_incident_analysis_dlq.sql",),)


def main() -> None:
    url = os.environ.get("CELERY_DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("CELERY_DATABASE_URL must be configured with a PostgreSQL URL")

    celery_target = _target_identity(url)
    for excluded_name in ("TELEMETRY_DATABASE_URL", "REPORTING_DATABASE_URL"):
        excluded_url = os.environ.get(excluded_name, "").strip()
        if excluded_url and excluded_url.startswith(("postgresql://", "postgres://")):
            if celery_target == _target_identity(excluded_url):
                raise SystemExit("Refusing to run Celery DLQ migrations on an excluded database")

    with psycopg.connect(url, sslmode="require") as conn:
        if not conn.pgconn.ssl_in_use:
            raise SystemExit("Refusing to run Celery DLQ migrations without TLS")
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), inet_server_addr()::text")
            database_name, server_address = cur.fetchone()
            _verify_database_is_distinct(url, database_name, server_address)
            cur.execute(
                "CREATE TABLE IF NOT EXISTS public.celery_dlq_schema_migrations ("
                "version VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT version FROM public.celery_dlq_schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
            for (filename,) in MIGRATIONS:
                if filename in applied:
                    continue
                cur.execute((MIGRATIONS_DIR / filename).read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO public.celery_dlq_schema_migrations (version) VALUES (%s)",
                    (filename,),
                )
        conn.commit()


def _target_identity(url: str) -> tuple[str, str, str]:
    """Return non-secret endpoint identity for cross-database safeguards."""

    info = conninfo_to_dict(url)
    return (info.get("host", ""), info.get("port", "5432"), info.get("dbname", ""))


def _verify_database_is_distinct(url: str, database_name: str, server_address: str | None) -> None:
    actual_identity = _target_identity(url)
    actual_identity = (server_address or actual_identity[0], actual_identity[1], database_name)
    for name in ("TELEMETRY_DATABASE_URL", "REPORTING_DATABASE_URL"):
        other_url = os.environ.get(name, "").strip()
        if not other_url.startswith(("postgresql://", "postgres://")):
            continue
        other_identity = _target_identity(other_url)
        if not _same_configured_endpoint(_target_identity(url), other_identity):
            # Distinct configured endpoints are a sufficient separation check here;
            # only shared endpoint aliases require live identity confirmation.
            continue
        try:
            with psycopg.connect(other_url, sslmode="require") as other_conn:
                if not other_conn.pgconn.ssl_in_use:
                    raise SystemExit(f"Refusing to inspect {name} without TLS")
                with other_conn.cursor() as cur:
                    cur.execute("SELECT current_database(), inet_server_addr()::text")
                    other_database_name, other_server_address = cur.fetchone()
        except SystemExit:
            raise
        except Exception:
            # If we cannot prove the endpoint is distinct, fail closed.
            raise SystemExit(f"Could not verify that the DLQ target differs from {name}") from None
        other_identity = (
            other_server_address or other_identity[0],
            other_identity[1],
            other_database_name,
        )
        if actual_identity == other_identity:
            raise SystemExit("Refusing to run Celery DLQ migrations on an excluded database")


def _same_configured_endpoint(left: tuple[str, str, str], right: tuple[str, str, str]) -> bool:
    """Compare literal host/port pairs to decide if live identity lookup is needed."""

    return left[:2] == right[:2]


if __name__ == "__main__":
    main()
