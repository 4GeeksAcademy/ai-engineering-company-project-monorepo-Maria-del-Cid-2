"""Explicit additive migration of inventory programmes and office currencies."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, make_url

from .database import get_database_url, get_engine
from .models import Programme
from .seed import validate_seed_target


def migrate_programmes(engine: Engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = {"assets", "asset_entries", "asset_exits"}
        if not tables.issubset(inspector.get_table_names()):
            raise RuntimeError("Inventory tables must exist before migrating programmes.")

        for table in sorted(tables):
            invalid_offices = connection.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE office IS NULL OR office NOT IN ('Valencia', 'Miami')")
            ).scalar_one()
            if invalid_offices:
                raise RuntimeError(f"{table} contains noncanonical offices; migration cancelled.")
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "currency" in columns:
                invalid_currencies = connection.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE currency IS NOT NULL AND currency != CASE office WHEN 'Valencia' THEN 'EUR' ELSE 'USD' END")
                ).scalar_one()
                if invalid_currencies:
                    raise RuntimeError(f"{table} contains mismatched currencies; migration cancelled.")

        Programme.__table__.create(connection, checkfirst=True)
        for table in sorted(tables):
            columns = {column["name"] for column in inspect(connection).get_columns(table)}
            if "currency" not in columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN currency VARCHAR"))
            connection.execute(
                text(f"UPDATE {table} SET currency = CASE office WHEN 'Valencia' THEN 'EUR' ELSE 'USD' END WHERE currency IS NULL")
            )
            if table != "assets" and "programme_id" not in columns:
                connection.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN programme_id VARCHAR REFERENCES programmes (programme_id)")
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate an existing development/test inventory database.")
    parser.add_argument("--environment", choices=("development", "test"), required=True)
    args = parser.parse_args()
    database_url = get_database_url()
    validate_seed_target(args.environment, database_url)
    target = make_url(database_url)
    if target.get_backend_name() == "sqlite" and not Path(target.database or "").is_file():
        raise RuntimeError("Inventory database file does not exist; migration cancelled.")
    migrate_programmes(get_engine())
    print("Inventory programmes migration completed.")


if __name__ == "__main__":
    main()