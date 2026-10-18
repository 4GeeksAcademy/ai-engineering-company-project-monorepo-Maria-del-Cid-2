"""Isolated tests for the guarded inventory development seed."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine

from app.inventory.models import Asset, AssetEntry, AssetExit
from app.inventory.seed import (
    ASSET_SEED,
    ENTRY_SEED,
    EXIT_SEED,
    SEED_ENVIRONMENT_VARIABLE,
    SEED_USER_UUID_VARIABLE,
    SeedSafetyError,
    main,
    seed_inventory,
    validate_seed_target,
)


TEST_UUID = UUID("95ecdeab-722e-4b7d-a590-8fb0f387d93f")


class InventorySeedSafetyTests(unittest.TestCase):
    def test_database_target_requires_explicit_matching_environment(self) -> None:
        cases = (
            ("", "sqlite:////tmp/inventory_dev.sqlite3"),
            ("production", "postgresql://user:pass@host/inventory_dev"),
            ("development", "postgresql://user:pass@host/inventory"),
            ("development", "sqlite:////tmp/inventory_test.sqlite3"),
            ("test", "sqlite:////tmp/inventory.sqlite3"),
            ("development", "mysql://user:pass@host/inventory_dev"),
        )
        for environment, database_url in cases:
            with self.subTest(environment=environment, target="[redacted]"), self.assertRaises(SeedSafetyError):
                validate_seed_target(environment, database_url)

    def test_valid_development_and_test_targets_are_accepted(self) -> None:
        validate_seed_target("development", "postgresql://hidden:secret@host/nexova_inventory_dev")
        validate_seed_target("test", "postgresql://hidden:secret@host/nexova_inventory_test")
        validate_seed_target("development", "sqlite:////tmp/nexova_inventory_dev.sqlite3")
        validate_seed_target("test", "sqlite:///:memory:")

    def test_main_refuses_before_engine_creation_without_safe_environment(self) -> None:
        environment = {
            SEED_ENVIRONMENT_VARIABLE: "production",
            "DATABASE_URL": "postgresql://user:secret@host/inventory_dev",
            SEED_USER_UUID_VARIABLE: str(TEST_UUID),
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "app.inventory.seed.get_engine", side_effect=AssertionError("engine must not be requested")
        ):
            self.assertEqual(main(), 1)

    def test_main_refuses_when_user_uuid_is_missing_or_invalid(self) -> None:
        safe_env = {
            SEED_ENVIRONMENT_VARIABLE: "test",
            "DATABASE_URL": "sqlite:///:memory:",
        }
        for user_uuid in (None, "not-a-uuid"):
            environment = dict(safe_env)
            if user_uuid is not None:
                environment[SEED_USER_UUID_VARIABLE] = user_uuid
            with self.subTest(user_uuid=user_uuid), patch.dict(os.environ, environment, clear=True), patch(
                "app.inventory.seed.get_engine", side_effect=AssertionError("engine must not be requested")
            ):
                self.assertEqual(main(), 1)


class InventorySeedDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        db_path = Path(self.temporary_directory.name) / "inventory_seed_test.sqlite3"
        self.engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_seed_has_requested_assets_movements_and_derived_stock(self) -> None:
        with Session(self.engine) as session:
            counts = seed_inventory(session, TEST_UUID)
            self.assertEqual(counts, {"assets": 6, "entries": 4, "exits": 3})

            assets = {
                asset.sku: asset
                for asset in session.scalars(select(Asset)).all()
            }
            self.assertEqual(set(assets), {asset["sku"] for asset in ASSET_SEED})
            for expected in ASSET_SEED:
                actual = assets[expected["sku"]]
                self.assertEqual(
                    {key: getattr(actual, key) for key in expected},
                    expected,
                )

            entries = session.scalars(select(AssetEntry)).all()
            exits = session.scalars(select(AssetExit)).all()
            self.assertEqual(len(entries), 4)
            self.assertEqual(len(exits), 3)
            self.assertTrue(all(entry.user_uuid == TEST_UUID for entry in entries))
            self.assertTrue(all(exit_row.user_uuid == TEST_UUID for exit_row in exits))
            self.assertGreaterEqual(len(entries), 4)
            self.assertGreaterEqual(len(exits), 3)

            self.assertEqual(
                [(row.quantity, row.supplier, row.office) for row in entries if row.asset_id == assets["NXV-IT-001"].id],
                [(10.0, "TechDistrib Valencia S.L.", "Valencia"), (5.0, "TechDistrib Valencia S.L.", "Valencia")],
            )
            self.assertEqual(
                {row.office for row in entries if row.asset_id == assets["NXV-IT-002"].id},
                {"Miami"},
            )
            self.assertIn("Valencia", {row.office for row in entries})
            self.assertIn("Miami", {row.office for row in entries})
            self.assertEqual(
                {row.supplier for row in entries if row.office == "Miami"},
                {"Office Depot Miami"},
            )

            allocation_rows = [row for row in exits if row.exit_type == "allocation"]
            consumption_rows = [row for row in exits if row.exit_type == "consumption"]
            self.assertEqual(len(allocation_rows), 2)
            self.assertTrue(all(row.assigned_to for row in allocation_rows))
            self.assertEqual(len(consumption_rows), 1)
            self.assertTrue(all(row.assigned_to is None for row in consumption_rows))

            expected_stock = {
                "NXV-IT-001": 10.0,
                "NXV-IT-002": 10.0,
                "NXV-PER-001": 7.0,
                "NXV-PER-002": 0.0,
                "NXV-OFF-001": 0.0,
                "NXV-TRN-001": 0.0,
            }
            for sku, asset in assets.items():
                total_in = session.exec(
                    select(func.coalesce(func.sum(AssetEntry.quantity), 0.0)).where(
                        AssetEntry.asset_id == asset.id
                    )
                ).one()
                total_out = session.exec(
                    select(func.coalesce(func.sum(AssetExit.quantity), 0.0)).where(
                        AssetExit.asset_id == asset.id
                    )
                ).one()
                stock = float(total_in[0]) - float(total_out[0])
                self.assertEqual(stock, expected_stock[sku])
                self.assertGreaterEqual(stock, 0)

    def test_repeated_seed_is_idempotent_and_leaves_existing_rows_unchanged(self) -> None:
        with Session(self.engine) as session:
            first = seed_inventory(session, TEST_UUID)
            initial_assets = [
                (row.id, row.name, row.sku, row.category, row.office)
                for row in session.scalars(select(Asset).order_by(Asset.id)).all()
            ]
            initial_entries = [
                (row.id, row.asset_id, row.quantity, row.supplier, row.office, row.user_uuid, row.created_at)
                for row in session.scalars(select(AssetEntry).order_by(AssetEntry.id)).all()
            ]
            initial_exits = [
                (row.id, row.asset_id, row.quantity, row.exit_type, row.assigned_to, row.office, row.user_uuid, row.created_at)
                for row in session.scalars(select(AssetExit).order_by(AssetExit.id)).all()
            ]
            session.commit()
            second = seed_inventory(session, TEST_UUID)
            self.assertEqual(first, {"assets": 6, "entries": 4, "exits": 3})
            self.assertEqual(second, {"assets": 0, "entries": 0, "exits": 0})
            self.assertEqual(
                initial_assets,
                [(row.id, row.name, row.sku, row.category, row.office) for row in session.scalars(select(Asset).order_by(Asset.id)).all()],
            )
            self.assertEqual(
                initial_entries,
                [(row.id, row.asset_id, row.quantity, row.supplier, row.office, row.user_uuid, row.created_at) for row in session.scalars(select(AssetEntry).order_by(AssetEntry.id)).all()],
            )
            self.assertEqual(
                initial_exits,
                [(row.id, row.asset_id, row.quantity, row.exit_type, row.assigned_to, row.office, row.user_uuid, row.created_at) for row in session.scalars(select(AssetExit).order_by(AssetExit.id)).all()],
            )

    def test_conflicting_asset_aborts_whole_seed_without_mutation(self) -> None:
        with Session(self.engine) as session:
            existing = Asset(
                name="Renamed by a human",
                sku="NXV-IT-001",
                category="hardware",
                office="Valencia",
            )
            session.add(existing)
            session.commit()
            existing_id = existing.id

            with self.assertRaises(SeedSafetyError):
                seed_inventory(session, TEST_UUID)

            self.assertEqual(session.exec(select(func.count()).select_from(Asset)).one()[0], 1)
            self.assertEqual(session.exec(select(func.count()).select_from(AssetEntry)).one()[0], 0)
            self.assertEqual(session.exec(select(func.count()).select_from(AssetExit)).one()[0], 0)
            unchanged = session.get(Asset, existing_id)
            self.assertEqual(unchanged.name, "Renamed by a human")

    def test_negative_existing_stock_aborts_without_adding_seed_movements(self) -> None:
        with Session(self.engine) as session:
            asset = Asset(name='Portátil 14" Business', sku="NXV-IT-001", category="hardware", office="Valencia")
            session.add(asset)
            session.flush()
            session.add(
                AssetExit(
                    asset_id=asset.id,
                    quantity=1,
                    exit_type="consumption",
                    assigned_to=None,
                    office="Valencia",
                    user_uuid=TEST_UUID,
                )
            )
            session.commit()

            with self.assertRaises(SeedSafetyError):
                seed_inventory(session, TEST_UUID)

            self.assertEqual(session.exec(select(func.count()).select_from(Asset)).one()[0], 1)
            self.assertEqual(session.exec(select(func.count()).select_from(AssetEntry)).one()[0], 0)
            self.assertEqual(session.exec(select(func.count()).select_from(AssetExit)).one()[0], 1)

    def test_existing_exact_movements_are_reused_but_different_uuid_is_not(self) -> None:
        with Session(self.engine) as session:
            original = seed_inventory(session, TEST_UUID)
            different_user_uuid = UUID("73990c82-4e37-4708-b45f-ef7f0ae4d267")
            second_user = seed_inventory(session, different_user_uuid)
            self.assertEqual(original, {"assets": 6, "entries": 4, "exits": 3})
            self.assertEqual(second_user, {"assets": 0, "entries": 4, "exits": 3})
            self.assertEqual(session.exec(select(func.count()).select_from(AssetEntry)).one()[0], 8)
            self.assertEqual(session.exec(select(func.count()).select_from(AssetExit)).one()[0], 6)


if __name__ == "__main__":
    unittest.main()
