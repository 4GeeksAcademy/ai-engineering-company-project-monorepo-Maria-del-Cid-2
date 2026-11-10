"""Migration coverage for the additive demo idempotency columns."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine

from app.inventory.migrate_programmes import migrate_phase2_events, migrate_programmes


class InventoryIdempotencyMigrationTests(unittest.TestCase):
    def test_migration_adds_nullable_keys_and_is_rerunnable_without_changing_legacy_rows(self) -> None:
        with TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'inventory_migration_test.sqlite3'}")
            try:
                # Build a pre-idempotency schema, then emulate existing historical movements.
                SQLModel.metadata.create_all(engine)
                with engine.begin() as connection:
                    for table in ("asset_entries", "asset_exits"):
                        for index in inspect(connection).get_indexes(table):
                            if "seed_key" in (index.get("column_names") or []):
                                connection.execute(text(f"DROP INDEX IF EXISTS {index['name']}"))
                        connection.execute(text(f"ALTER TABLE {table} DROP COLUMN seed_key"))
                    for index in inspect(connection).get_indexes("inventory_kit_preparations"):
                        if "idempotency_key" in (index.get("column_names") or []):
                            connection.execute(text(f"DROP INDEX IF EXISTS {index['name']}"))
                    connection.execute(text(
                        "ALTER TABLE inventory_kit_preparations DROP COLUMN idempotency_key"
                    ))
                    connection.execute(text(
                        "INSERT INTO programmes (programme_id, name) VALUES ('legacy-programme', 'Legacy')"
                    ))
                    connection.execute(text(
                        "INSERT INTO assets (name, sku, category, office, currency) "
                        "VALUES ('Legacy item', 'LEGACY-1', 'training_materials', 'Valencia', 'EUR')"
                    ))
                    connection.execute(text(
                        "INSERT INTO asset_entries (asset_id, quantity, unit_cost, supplier, office, currency, "
                        "programme_id, user_uuid, created_at) VALUES "
                        "(1, 2, NULL, 'Legacy supplier', 'Valencia', 'EUR', 'legacy-programme', "
                        "'95ecdeab-722e-4b7d-a590-8fb0f387d93f', CURRENT_TIMESTAMP)"
                    ))

                migrate_programmes(engine)
                migrate_phase2_events(engine)
                migrate_programmes(engine)
                migrate_phase2_events(engine)

                with engine.connect() as connection:
                    entry = connection.execute(text(
                        "SELECT quantity, unit_cost, programme_id FROM asset_entries WHERE id = 1"
                    )).one()
                    self.assertEqual(tuple(entry), (2, None, "legacy-programme"))
                inspector = inspect(engine)
                for table in ("asset_entries", "asset_exits"):
                    columns = {column["name"]: column for column in inspector.get_columns(table)}
                    self.assertIn("seed_key", columns)
                    self.assertTrue(columns["seed_key"]["nullable"])
                preparation_columns = {
                    column["name"]: column
                    for column in inspector.get_columns("inventory_kit_preparations")
                }
                self.assertIn("idempotency_key", preparation_columns)
                self.assertTrue(preparation_columns["idempotency_key"]["nullable"])
                for table, expected_index in (
                    ("asset_entries", "uq_asset_entries_seed_key"),
                    ("asset_exits", "uq_asset_exits_seed_key"),
                    ("inventory_kit_preparations", "uq_inventory_kit_preparation_idempotency_key"),
                ):
                    self.assertIn(expected_index, {index["name"] for index in inspector.get_indexes(table)})
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
