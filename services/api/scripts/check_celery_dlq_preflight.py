"""Sanitized read-only preflight for the dedicated Celery DLQ database."""

from __future__ import annotations

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


def target_identity(url: str) -> tuple[str, str, str]:
    info = conninfo_to_dict(url)
    return info.get("host", ""), info.get("port", "5432"), info.get("dbname", "")


def main() -> None:
    url = os.environ.get("CELERY_DATABASE_URL", "").strip()
    print(f"url_configured={bool(url)}")
    if not url:
        raise SystemExit(1)

    params = conninfo_to_dict(url)
    print(f"sslmode_explicitly_required={params.get('sslmode') == 'require'}")
    print(f"sslmode_configured={bool(params.get('sslmode'))}")
    distinct = all(
        not (other := os.environ.get(name, "").strip())
        or target_identity(url) != target_identity(other)
        for name in ("TELEMETRY_DATABASE_URL", "REPORTING_DATABASE_URL")
    )
    print(f"target_distinct_from_telemetry_reporting={distinct}")
    with psycopg.connect(url, sslmode="require") as conn:
        print(f"client_tls_active={bool(conn.pgconn.ssl_in_use)}")
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            print(f"read_only_select_one={cur.fetchone()[0] == 1}")
            cur.execute(
                "SELECT to_regclass('public.celery_incident_analysis_dlq') IS NOT NULL"
            )
            print(f"dlq_table_exists={cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
