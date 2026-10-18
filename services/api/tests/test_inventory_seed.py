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
from tinydb import TinyDB
from tinydb.storages import JSONStorage

from app.inventory.models import Asset, AssetEntry, AssetExit
from app.inventory.seed import (
    ASSET_SEED,
    ENTRY_SEED,
    EXIT_SEED,
    SEED_USER_EMAIL_VARIABLE,
    SeedSafetyError,
    main,
    resolve_seed_user_uuid,
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

    def test_authorized_supabase_project_accepts_standard_postgres_database_only_for_dev(self) -> None:
        url = "postgresql://hidden:secret@db.yamhkvudzwcqsbqvfmox.supabase.co/postgres"
        validate_seed_target("development", url)
        with self.assertRaises(SeedSafetyError):
            validate_seed_target("test", url)

    def test_supabase_project_reference_must_match_authorized_development_project(self) -> None:
        wrong_project = "postgresql://hidden:secret@db.otherproject.supabase.co/postgres"
        wrong_database = "postgresql://hidden:secret@db.yamhkvudzwcqsbqvfmox.supabase.co/production"
        for url in (wrong_project, wrong_database):
            with self.subTest(target="[redacted]"), self.assertRaises(SeedSafetyError):
                validate_seed_target("development", url)

    def test_authorized_supabase_pooler_requires_authorized_ref_in_username(self) -> None:
        url = (
            "postgresql+psycopg://postgres.yamhkvudzwcqsbqvfmox:hidden@"
            "aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        )
        validate_seed_target("development", url)
        wrong_project = url.replace("postgres.yamhkvudzwcqsbqvfmox", "postgres.otherproject")
        with self.assertRaises(SeedSafetyError):
            validate_seed_target("development", wrong_project)

    def test_main_refuses_before_engine_creation_without_safe_environment(self) -> None:
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:secret@host/inventory_dev",
            SEED_USER_EMAIL_VARIABLE: "dev@example.test",
        }, clear=True), patch(
            "app.inventory.seed.get_engine", side_effect=AssertionError("engine must not be requested")
        ):
            self.assertEqual(main("production"), 1)

    def test_main_refuses_when_user_uuid_is_missing_or_invalid(self) -> None:
        safe_env = {
            "DATABASE_URL": "sqlite:///:memory:",
        }
        for user_email in (None, ""):
            environment = dict(safe_env)
            if user_email is not None:
                environment[SEED_USER_EMAIL_VARIABLE] = user_email
            with self.subTest(user_email=user_email), patch.dict(os.environ, environment, clear=True), patch(
                "app.inventory.seed.get_engine", side_effect=AssertionError("engine must not be requested")
            ):
                self.assertEqual(main("test"), 1)

    def test_main_resolves_user_uuid_from_local_account_before_engine_creation(self) -> None:
        environment = {
            "DATABASE_URL": "sqlite:///:memory:",
            SEED_USER_EMAIL_VARIABLE: "authorized@example.test",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "app.inventory.seed.resolve_seed_user_uuid", return_value=TEST_UUID
        ) as resolve_user, patch(
            "app.inventory.seed.get_engine", side_effect=AssertionError("engine must not be requested")
        ):
            self.assertEqual(main("test"), 1)
        resolve_user.assert_called_once_with("authorized@example.test")


class InventorySeedUserResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "auth.json"
        with TinyDB(self.database_path) as database:
            database.table("users").insert(
                {
                    "email": "Authorized@Example.test",
                    "is_active": True,
                    "user_uuid": str(TEST_UUID),
                    "id": 92,
                }
            )
            database.table("users").insert(
                {
                    "email": "inactive@example.test",
                    "is_active": False,
                    "user_uuid": str(TEST_UUID),
                    "id": 93,
                }
            )
            database.table("users").insert(
                {
                    "email": "legacy@example.test",
                    "is_active": True,
                    "id": 94,
                }
            )
            database.table("users").insert(
                {
                    "email": "malformed@example.test",
                    "is_active": True,
                    "user_uuid": "not-a-uuid",
                    "id": 95,
                }
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_resolves_persisted_uuid_for_case_insensitive_active_account(self) -> None:
        with patch.dict(os.environ, {"AUTH_DB_PATH": str(self.database_path)}):
            self.assertEqual(resolve_seed_user_uuid("  authorized@example.TEST "), TEST_UUID)

    def test_rejects_inactive_or_legacy_user_without_persisted_uuid(self) -> None:
        with patch.dict(os.environ, {"AUTH_DB_PATH": str(self.database_path)}):
            for email in (
                "inactive@example.test",
                "legacy@example.test",
                "malformed@example.test",
            ):
                with self.subTest(account=email), self.assertRaises(SeedSafetyError):
                    resolve_seed_user_uuid(email)

    def test_read_only_resolution_does_not_mutate_tinydb(self) -> None:
        before = self.database_path.read_bytes()
        with patch.dict(os.environ, {"AUTH_DB_PATH": str(self.database_path)}):
            self.assertEqual(resolve_seed_user_uuid("authorized@example.test"), TEST_UUID)
        self.assertEqual(self.database_path.read_bytes(), before)


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
                {
                    (
                        next(sku for sku, asset in assets.items() if asset.id == row.asset_id),
                        row.quantity,
                        row.supplier,
                        row.office,
                    )
                    for row in entries
                },
                {
                    ("NXV-IT-001", 10.0, "TechDistrib Valencia S.L.", "Valencia"),
                    ("NXV-IT-001", 5.0, "TechDistrib Valencia S.L.", "Valencia"),
                    ("NXV-PER-001", 8.0, "TechDistrib Valencia S.L.", "Valencia"),
                    ("NXV-PER-002", 12.0, "Office Depot Miami", "Miami"),
                },
            )

            self.assertEqual(
                {
                    (
                        next(sku for sku, asset in assets.items() if asset.id == row.asset_id),
                        row.quantity,
                        row.exit_type,
                        row.assigned_to,
                        row.office,
                    )
                    for row in exits
                },
                {
                    ("NXV-IT-001", 2.0, "allocation", "María García", "Valencia"),
                    ("NXV-IT-001", 1.0, "consumption", None, "Valencia"),
                    ("NXV-PER-001", 1.0, "allocation", "Carlos López", "Valencia"),
                },
            )

            expected_stock = {
                "NXV-IT-001": 12.0,
                "NXV-IT-002": 0.0,
                "NXV-PER-001": 7.0,
                "NXV-PER-002": 12.0,
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
