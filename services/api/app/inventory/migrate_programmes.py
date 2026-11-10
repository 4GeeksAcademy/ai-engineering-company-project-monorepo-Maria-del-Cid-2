"""Explicit additive migration of inventory costs, programmes, and telemetry outbox."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, make_url

from .database import get_database_url, get_engine
from .models import (
    AssetEntry,
    AssetExit,
    InventoryRegularization,
    InventoryValuation,
    InventoryValuationLedger,
    KitComponent,
    KitConfiguration,
    KitPreparation,
    Programme,
    StockThreshold,
    TelemetryOutboxEvent,
)
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
        if "unit_cost" not in {
            column["name"] for column in inspect(connection).get_columns("asset_entries")
        }:
            connection.execute(text("ALTER TABLE asset_entries ADD COLUMN unit_cost FLOAT"))
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
        TelemetryOutboxEvent.__table__.create(connection, checkfirst=True)
        outbox_columns = {
            column["name"] for column in inspect(connection).get_columns("telemetry_outbox")
        }
        if "locked_until" not in outbox_columns:
            connection.execute(text("ALTER TABLE telemetry_outbox ADD COLUMN locked_until TIMESTAMP NULL"))
        if "lease_token" not in outbox_columns:
            connection.execute(text("ALTER TABLE telemetry_outbox ADD COLUMN lease_token VARCHAR NULL"))
        claim_index = next(
            index for index in TelemetryOutboxEvent.__table__.indexes
            if index.name == "ix_telemetry_outbox_claim"
        )
        claim_index.create(connection, checkfirst=True)


def migrate_phase2_events(engine: Engine) -> None:
    """Create additive valuation/configuration tables without inventing costs.

    Existing net stock is initialized as unvalued, because legacy exits have no
    cost allocation and historical receipts may have no unit cost. Re-running
    the migration never overwrites valuation state established after migration.
    """

    with engine.begin() as connection:
        inspector = inspect(connection)
        required = {"assets", "asset_entries", "asset_exits", "programmes", "telemetry_outbox"}
        if not required.issubset(inspector.get_table_names()):
            raise RuntimeError("Run the programmes/outbox migration before the Phase 2 events migration.")

        bad_office = connection.execute(text(
            "SELECT COUNT(*) FROM assets WHERE office NOT IN ('Valencia', 'Miami')"
        )).scalar_one()
        if bad_office:
            raise RuntimeError("Assets contain noncanonical offices; valuation initialization cancelled.")
        negative_stock = connection.execute(text(
            "SELECT COUNT(*) FROM assets a "
            "LEFT JOIN (SELECT asset_id, SUM(quantity) q FROM asset_entries GROUP BY asset_id) e ON e.asset_id=a.id "
            "LEFT JOIN (SELECT asset_id, SUM(quantity) q FROM asset_exits GROUP BY asset_id) x ON x.asset_id=a.id "
            "WHERE COALESCE(e.q, 0) < COALESCE(x.q, 0)"
        )).scalar_one()
        if negative_stock:
            raise RuntimeError("Negative historical stock exists; resolve it before initializing valuation.")
        for model in (
            StockThreshold,
            InventoryValuation,
            InventoryValuationLedger,
            KitConfiguration,
            KitComponent,
            KitPreparation,
            InventoryRegularization,
        ):
            model.__table__.create(connection, checkfirst=True)
        for table in ("asset_entries", "asset_exits"):
            columns = {column["name"] for column in inspect(connection).get_columns(table)}
            if "seed_key" not in columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN seed_key VARCHAR NULL"))
        entry_seed_index = next(index for index in AssetEntry.__table__.indexes if index.name == "uq_asset_entries_seed_key")
        exit_seed_index = next(index for index in AssetExit.__table__.indexes if index.name == "uq_asset_exits_seed_key")
        entry_seed_index.create(connection, checkfirst=True)
        exit_seed_index.create(connection, checkfirst=True)
        preparation_columns = {
            column["name"] for column in inspect(connection).get_columns("inventory_kit_preparations")
        }
        if "idempotency_key" not in preparation_columns:
            connection.execute(text(
                "ALTER TABLE inventory_kit_preparations ADD COLUMN idempotency_key VARCHAR NULL"
            ))
        preparation_index = next(
            index for index in KitPreparation.__table__.indexes
            if index.name == "uq_inventory_kit_preparation_idempotency_key"
        )
        preparation_index.create(connection, checkfirst=True)
        connection.execute(text(
            "INSERT INTO inventory_valuations (asset_id, valued_quantity, unvalued_quantity, average_cost) "
            "SELECT a.id, 0, COALESCE(e.q, 0) - COALESCE(x.q, 0), 0 FROM assets a "
            "LEFT JOIN (SELECT asset_id, SUM(quantity) q FROM asset_entries GROUP BY asset_id) e ON e.asset_id=a.id "
            "LEFT JOIN (SELECT asset_id, SUM(quantity) q FROM asset_exits GROUP BY asset_id) x ON x.asset_id=a.id "
            "WHERE NOT EXISTS (SELECT 1 FROM inventory_valuations v WHERE v.asset_id=a.id)"
        ))


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