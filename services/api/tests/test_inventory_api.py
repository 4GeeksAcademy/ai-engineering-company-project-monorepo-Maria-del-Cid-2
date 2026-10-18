"""Isolated HTTP tests for read-only inventory endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.inventory.database import get_session
from app.inventory.models import Asset, AssetEntry, AssetExit
from app.main import app


_FAKE_USER = User(
    id=9876,
    email="inventory-test@nexova.com",
    hashed_password="fake",
    is_active=True,
    role=UserRole.ADMIN,
    created_at=datetime.now(timezone.utc),
    user_uuid=UUID("95ecdeab-722e-4b7d-a590-8fb0f387d93f"),
)


class InventoryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        db_path = Path(self.temporary_directory.name) / "inventory.sqlite3"
        self.engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self.engine)

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_session, None)
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def add_asset(self, **kwargs: Any) -> Asset:
        asset = Asset(
            name=str(kwargs.pop("name", "Laptop")),
            sku=str(kwargs.pop("sku", "LAP-1")),
            category="IT",
            office="Valencia",
        )
        with Session(self.engine) as session:
            session.add(asset)
            session.commit()
            session.refresh(asset)
            return asset

    def test_products_calculate_stock_without_multiplying_movements(self) -> None:
        asset = self.add_asset()
        with Session(self.engine) as session:
            session.add_all(
                [
                    AssetEntry(asset_id=asset.id, quantity=10, supplier="Acme", office="Valencia", user_uuid=_FAKE_USER.user_uuid),
                    AssetEntry(asset_id=asset.id, quantity=5, supplier="Acme", office="Valencia", user_uuid=_FAKE_USER.user_uuid),
                    AssetExit(asset_id=asset.id, quantity=2, exit_type="allocation", assigned_to="Alex", office="Valencia", user_uuid=_FAKE_USER.user_uuid),
                    AssetExit(asset_id=asset.id, quantity=1, exit_type="consumption", assigned_to=None, office="Valencia", user_uuid=_FAKE_USER.user_uuid),
                ]
            )
            session.add(Asset(name="Mouse", sku="MOU-1", category="IT", office="Valencia"))
            session.commit()

        response = self.client.get("/api/inventory/products")
        self.assertEqual(response.status_code, 200)
        products = {row["sku"]: row for row in response.json()}
        self.assertEqual(products["LAP-1"]["current_stock"], 12)
        self.assertEqual(products["MOU-1"]["current_stock"], 0)

    def test_product_detail_and_missing_product(self) -> None:
        asset = self.add_asset()
        self.assertEqual(self.client.get(f"/api/inventory/products/{asset.id}").json()["current_stock"], 0)
        self.assertEqual(self.client.get("/api/inventory/products/999").status_code, 404)

    def test_orders_are_discriminated_entry_and_exit_variants(self) -> None:
        asset = self.add_asset()
        with Session(self.engine) as session:
            session.add_all(
                [
                    AssetEntry(asset_id=asset.id, quantity=3, supplier="Acme", office="Valencia", user_uuid=_FAKE_USER.user_uuid),
                    AssetExit(asset_id=asset.id, quantity=1, exit_type="allocation", assigned_to="Alex", office="Valencia", user_uuid=_FAKE_USER.user_uuid),
                ]
            )
            session.commit()

        response = self.client.get("/api/inventory/orders")
        self.assertEqual(response.status_code, 200)
        orders = response.json()
        self.assertEqual({order["type"] for order in orders}, {"entry", "exit"})
        entry = next(order for order in orders if order["type"] == "entry")
        exit_order = next(order for order in orders if order["type"] == "exit")
        self.assertEqual(entry["supplier"], "Acme")
        self.assertNotIn("exit_type", entry)
        self.assertEqual(exit_order["exit_type"], "allocation")
        self.assertNotIn("supplier", exit_order)
        self.assertEqual(entry["asset_id"], asset.id)
        self.assertEqual(exit_order["assigned_to"], "Alex")

    def test_all_inventory_endpoints_require_authentication(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        for path in (
            "/api/inventory/products",
            "/api/inventory/products/1",
            "/api/inventory/orders",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)


if __name__ == "__main__":
    unittest.main()
