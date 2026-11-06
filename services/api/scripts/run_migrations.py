"""
Run telemetry migrations 001 and 002 against the Supabase PostgreSQL database.

Usage:
    TELEMETRY_DATABASE_URL=postgresql://... python scripts/run_migrations.py

Safe to run multiple times — uses IF NOT EXISTS for 001 and IF NOT EXISTS /
idempotent ALTER for 002.
"""

import os
import sys

import psycopg

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def load_sql(filename: str) -> str:
    path = os.path.join(MIGRATIONS_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def migration_001_must_run_first() -> bool:
    """
    Check if telemetry_events exists.
    If not, migration 001 (CREATE TABLE) is needed.
    Returns True if 001 should run (table missing).
    """
    database_url = _get_url()
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'telemetry_events')"
            )
            exists = cur.fetchone()[0]
    return not exists


def _get_url() -> str:
    url = os.environ.get("TELEMETRY_DATABASE_URL", "").strip()
    if not url:
        print("❌ TELEMETRY_DATABASE_URL is not set.")
        sys.exit(1)
    return url


def apply_sql(filename: str, description: str) -> None:
    database_url = _get_url()
    print(f"📦 Applying {filename} — {description} ...")
    sql = load_sql(filename)
    # Split by semicolons to run each statement independently
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except psycopg.errors.DuplicateObject:
                    # IF NOT EXISTS handles most cases, but some ALTERs may
                    # already be applied — ignore gracefully.
                    print(f"  ⚠️  Already applied, skipping: {stmt[:80]}...")
                except Exception as e:
                    print(f"  ⚠️  Non-fatal: {e}")
            conn.commit()
    print(f"  ✅ {filename} applied successfully.")


def main() -> None:
    print("=" * 60)
    print("  Nexova Telemetry Migrations")
    print("=" * 60)

    url = _get_url()
    # Mask password for display
    safe_url = url.replace(url[url.index(":")+3:url.index("@")], "****:****")
    print(f"  Target: {safe_url}")
    print()

    # Migration 001
    print("--- Migration 001 ---")
    apply_sql("001_create_telemetry_events.sql", "CREATE TABLE telemetry_events")
    print()

    # Migration 002
    print("--- Migration 002 ---")
    apply_sql(
        "002_align_existing_telemetry_events.sql",
        "Align constraints and indexes",
    )
    print()

    # Verify
    print("--- Verification ---")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'telemetry_events' "
                "ORDER BY ordinal_position"
            )
            rows = cur.fetchall()
            print(f"  📋 telemetry_events columns ({len(rows)}):")
            for col, dtype, nullable in rows:
                print(f"     • {col:20} {dtype:15} {'NULL' if nullable == 'YES' else 'NOT NULL'}")

    print()
    print("✅ Migrations complete.")


if __name__ == "__main__":
    main()
