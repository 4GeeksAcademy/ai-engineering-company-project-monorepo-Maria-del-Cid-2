"""Isolated SQLModel and HTTP contract tests for inventory models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import Uuid as SQLAlchemyUuid
from sqlmodel import SQLModel, Session, create_engine

from app.inventory.models import Asset, AssetEntry, AssetExit
from app.inventory.schemas import (
    AssetCreate,
    AssetEntryCreate,
    AssetEntryResponse,
    AssetExitCreate,
    AssetExitResponse,
    AssetResponse,
    AssetWithStockResponse,
)


TEST_UUID = UUID("95ecdeab-722e-4b7d-a590-8fb0f387d93f")


class InventorySchemaTests(unittest.TestCase):
    def test_asset_create_requires_fields_and_response_has_id(self) -> None:
        payload = AssetCreate(name="Laptop", sku="LAP-1", category="IT", office="Valencia")
        self.assertEqual(payload.sku, "LAP-1")
        with self.assertRaises(ValidationError):
            AssetCreate(name="Laptop", sku="LAP-1", office="Valencia")

        response = AssetResponse(id=1, **payload.model_dump())
        self.assertEqual(response.id, 1)

    def test_current_stock_exists_only_on_calculated_response_schema(self) -> None:
        fields = {"id": 1, "name": "Laptop", "sku": "LAP-1", "category": "IT", "office": "Valencia"}
        response = AssetWithStockResponse(**fields, current_stock=3)
        self.assertEqual(response.current_stock, 3)
        self.assertNotIn("current_stock", Asset.model_fields)
        self.assertNotIn("current_stock", AssetResponse.model_fields)
        with self.assertRaises(ValidationError):
            AssetCreate(**fields, current_stock=3)

    def test_entry_schema_requires_fields_uuid_is_response_only(self) -> None:
        payload = AssetEntryCreate(asset_id=1, quantity=2, supplier="Acme", office="Valencia")
        with self.assertRaises(ValidationError):
            AssetEntryCreate(asset_id=1, quantity=0, supplier="Acme", office="Valencia")
        with self.assertRaises(ValidationError):
            AssetEntryCreate(asset_id=1, quantity=1, supplier="Acme", office="Valencia", user_uuid=str(TEST_UUID))

        response = AssetEntryResponse(
            id=1,
            created_at=datetime.now(timezone.utc),
            user_uuid=TEST_UUID,
            **payload.model_dump(),
        )
        self.assertEqual(response.user_uuid, TEST_UUID)
        with self.assertRaises(ValidationError):
            AssetEntryResponse(
                id=1,
                created_at=datetime.now(timezone.utc),
                user_uuid="not-a-uuid",
                **payload.model_dump(),
            )

    def test_exit_type_and_assigned_to_rules(self) -> None:
        allocation = AssetExitCreate(
            asset_id=1,
            quantity=1,
            exit_type="allocation",
            assigned_to="Alex",
            office="Valencia",
        )
        consumption = AssetExitCreate(
            asset_id=1,
            quantity=1,
            exit_type="consumption",
            assigned_to=None,
            office="Valencia",
        )
        self.assertEqual(allocation.exit_type, "allocation")
        self.assertIsNone(consumption.assigned_to)

        invalid = (
            {"exit_type": "other", "assigned_to": "Alex"},
            {"exit_type": "allocation", "assigned_to": None},
            {"exit_type": "consumption", "assigned_to": "Alex"},
        )
        for variant in invalid:
            with self.subTest(variant=variant), self.assertRaises(ValidationError):
                AssetExitCreate(
                    asset_id=1,
                    quantity=1,
                    office="Valencia",
                    **variant,
                )

        with self.assertRaises(ValidationError):
            AssetExitCreate(
                asset_id=1,
                quantity=-1,
                exit_type="consumption",
                office="Valencia",
            )

        response = AssetExitResponse(
            id=1,
            created_at=datetime.now(timezone.utc),
            user_uuid=TEST_UUID,
            **consumption.model_dump(),
        )
        self.assertEqual(response.user_uuid, TEST_UUID)


class InventoryOrmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        db_path = Path(self.temporary_directory.name) / "inventory.sqlite3"
        self.engine = create_engine(f"sqlite:///{db_path}")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_tables_have_expected_relations_and_no_persisted_stock(self) -> None:
        self.assertNotIn("current_stock", Asset.__table__.columns)
        self.assertIn("asset_id", AssetEntry.__table__.columns)
        self.assertIn("asset_id", AssetExit.__table__.columns)
        self.assertEqual(len(AssetEntry.__table__.c.asset_id.foreign_keys), 1)
        self.assertEqual(len(AssetExit.__table__.c.asset_id.foreign_keys), 1)

        asset = Asset(name="Laptop", sku="LAP-1", category="IT", office="Valencia")
        entry = AssetEntry(
            quantity=3,
            supplier="Acme",
            office="Valencia",
            user_uuid=TEST_UUID,
        )
        exit_movement = AssetExit(
            quantity=1,
            exit_type="allocation",
            assigned_to="Alex",
            office="Valencia",
            user_uuid=TEST_UUID,
        )
        asset.entries.append(entry)
        asset.exits.append(exit_movement)

        with Session(self.engine) as session:
            session.add(asset)
            session.commit()
            session.refresh(asset)
            self.assertEqual(entry.asset_id, asset.id)
            self.assertEqual(exit_movement.asset_id, asset.id)
            self.assertEqual(entry.asset.sku, "LAP-1")
            self.assertEqual(exit_movement.asset.sku, "LAP-1")
            self.assertIsInstance(entry.created_at, datetime)
            self.assertEqual(entry.created_at.tzinfo, timezone.utc)
            self.assertIsInstance(exit_movement.created_at, datetime)
            self.assertEqual(exit_movement.created_at.tzinfo, timezone.utc)

    def test_movement_uuid_uses_uuid_type_and_is_required_in_storage(self) -> None:
        for model in (AssetEntry, AssetExit):
            with self.subTest(model=model.__name__):
                column = model.__table__.c.user_uuid
                self.assertIsInstance(column.type, SQLAlchemyUuid)
                self.assertFalse(column.nullable)

        self.assertIs(AssetEntry.model_fields["user_uuid"].annotation, UUID)
        self.assertIs(AssetExit.model_fields["user_uuid"].annotation, UUID)
        valid_payload = {
            "asset_id": 1,
            "quantity": 1,
            "supplier": "Acme",
            "office": "Valencia",
            "user_uuid": str(TEST_UUID),
        }
        entry = AssetEntry.model_validate(valid_payload)
        self.assertEqual(entry.user_uuid, TEST_UUID)
        with self.assertRaises(ValidationError):
            AssetEntry.model_validate({**valid_payload, "user_uuid": "bad-uuid"})
        self.assertIsInstance(uuid4(), UUID)

    def test_database_constraints_enforce_unique_sku_positive_amount_and_exit_rules(self) -> None:
        with Session(self.engine) as session:
            session.add(Asset(name="One", sku="DUP", category="IT", office="Valencia"))
            session.add(Asset(name="Two", sku="DUP", category="IT", office="Valencia"))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            asset = Asset(name="One", sku="ONE", category="IT", office="Valencia")
            session.add(asset)
            session.commit()
            session.refresh(asset)

            session.add(
                AssetEntry(
                    asset_id=asset.id,
                    quantity=-1,
                    supplier="Acme",
                    office="Valencia",
                    user_uuid=TEST_UUID,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                AssetExit(
                    asset_id=asset.id,
                    quantity=1,
                    exit_type="consumption",
                    assigned_to="Alex",
                    office="Valencia",
                    user_uuid=TEST_UUID,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                AssetEntry(
                    asset_id=999,
                    quantity=1,
                    supplier="Acme",
                    office="Valencia",
                    user_uuid=TEST_UUID,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()