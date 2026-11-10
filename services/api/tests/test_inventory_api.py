"""Isolated HTTP tests for inventory reads and writes."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from uuid import UUID, uuid4
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import create_engine as sqlalchemy_create_engine, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.inventory.database import get_session
from app.inventory.models import Asset, AssetEntry, AssetExit, Programme, TelemetryOutboxEvent
from app.inventory.router import _products_cache
from app.inventory.operations import (
    InsufficientStock,
    _asset_lookup_statement,
    create_outbound,
)
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
        _products_cache.invalidate("list")
        self.temporary_directory = TemporaryDirectory()
        db_path = Path(self.temporary_directory.name) / "inventory.sqlite3"
        self.engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add(Programme(programme_id="prog-test", name="Test programme"))
            session.commit()

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
            currency="EUR",
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
                    AssetEntry(asset_id=asset.id, quantity=10, unit_cost=4.0, supplier="Acme", office="Valencia", currency="EUR", user_uuid=_FAKE_USER.user_uuid),
                    AssetEntry(asset_id=asset.id, quantity=5, unit_cost=4.0, supplier="Acme", office="Valencia", currency="EUR", user_uuid=_FAKE_USER.user_uuid),
                    AssetExit(asset_id=asset.id, quantity=2, exit_type="allocation", assigned_to="Alex", office="Valencia", currency="EUR", user_uuid=_FAKE_USER.user_uuid),
                    AssetExit(asset_id=asset.id, quantity=1, exit_type="consumption", assigned_to=None, office="Valencia", currency="EUR", user_uuid=_FAKE_USER.user_uuid),
                ]
            )
            session.add(Asset(name="Mouse", sku="MOU-1", category="IT", office="Valencia", currency="EUR"))
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
                    AssetEntry(asset_id=asset.id, quantity=3, unit_cost=4.0, supplier="Acme", office="Valencia", currency="EUR", user_uuid=_FAKE_USER.user_uuid),
                    AssetExit(asset_id=asset.id, quantity=1, exit_type="allocation", assigned_to="Alex", office="Valencia", currency="EUR", user_uuid=_FAKE_USER.user_uuid),
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

    def test_phase2_configuration_and_regularization_require_admin(self) -> None:
        asset = self.add_asset()
        non_admin = User(
            id=9877,
            email="inventory-user@nexova.com",
            hashed_password="fake",
            is_active=True,
            role=UserRole.USER,
            created_at=datetime.now(timezone.utc),
            user_uuid=UUID("9a1aec0f-3165-4faf-a1d6-d1157a3e4bc2"),
        )
        app.dependency_overrides[get_current_user] = lambda: non_admin
        threshold = self.client.put("/api/inventory/thresholds", json={
            "asset_id": asset.id, "office": "Valencia", "threshold": 2,
        })
        kit = self.client.put("/api/inventory/kits", json={
            "kit_asset_id": asset.id, "office": "Valencia", "expected_cost": 10,
            "components": [{"component_asset_id": asset.id + 1, "quantity_per_kit": 1}],
        })
        regularization = self.client.post("/api/inventory/valuation/regularizations", json={
            "asset_id": asset.id, "office": "Valencia", "quantity": 1,
            "approved_unit_cost": 4, "reason": "test",
        })
        self.assertEqual(threshold.status_code, 403)
        self.assertEqual(kit.status_code, 403)
        self.assertEqual(regularization.status_code, 403)

    def test_all_inventory_endpoints_require_authentication(self) -> None:
        app.dependency_overrides.pop(get_current_user)
        for path in (
            "/api/inventory/products",
            "/api/inventory/products/1",
            "/api/inventory/orders",
        ):
            with self.subTest(method="GET", path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

        for path, payload in (
            ("/api/inventory/products", {"name": "Laptop", "sku": "LAP-1", "category": "IT", "office": "Valencia"}),
            ("/api/inventory/orders/inbound", {"asset_id": 1, "quantity": 1, "unit_cost": 12.5, "supplier": "Acme", "office": "Valencia"}),
            ("/api/inventory/orders/outbound", {"asset_id": 1, "quantity": 1, "exit_type": "consumption", "office": "Valencia"}),
        ):
            with self.subTest(method="POST", path=path):
                self.assertEqual(self.client.post(path, json=payload).status_code, 401)

    def test_create_product_and_reject_invalid_or_duplicate_data(self) -> None:
        payload = {"name": "Laptop", "sku": "LAP-NEW", "category": "IT", "office": "Valencia"}
        response = self.client.post("/api/inventory/products", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["current_stock"], 0)
        self.assertEqual(response.json()["sku"], "LAP-NEW")

        invalid = self.client.post(
            "/api/inventory/products",
            json={**payload, "sku": "LAP-2", "current_stock": 99},
        )
        self.assertEqual(invalid.status_code, 422)

        duplicate = self.client.post(
            "/api/inventory/products",
            json={**payload, "name": "Different name"},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(self.client.get("/api/inventory/products").json()), 1)

    def test_inbound_and_outbound_update_derived_stock(self) -> None:
        asset = self.add_asset()
        inbound = self.client.post(
            "/api/inventory/orders/inbound",
            json={
                "asset_id": asset.id,
                "quantity": 8,
                "unit_cost": 12.5,
                "supplier": "Acme",
                "office": "Valencia",
                "programme_id": "prog-test",
            },
        )
        self.assertEqual(inbound.status_code, 201, inbound.text)
        self.assertEqual(inbound.json()["user_uuid"], str(_FAKE_USER.user_uuid))
        self.assertEqual(inbound.json()["unit_cost"], 12.5)
        self.assertNotIn("user_uuid", {"asset_id", "quantity", "supplier", "office"})
        self.assertEqual(
            self.client.get(f"/api/inventory/products/{asset.id}").json()["current_stock"],
            8,
        )

        outbound = self.client.post(
            "/api/inventory/orders/outbound",
            json={
                "asset_id": asset.id,
                "quantity": 3,
                "exit_type": "allocation",
                "assigned_to": "Alex",
                "office": "Valencia",
                "programme_id": "prog-test",
            },
        )
        self.assertEqual(outbound.status_code, 201, outbound.text)
        self.assertEqual(outbound.json()["user_uuid"], str(_FAKE_USER.user_uuid))
        self.assertEqual(
            self.client.get(f"/api/inventory/products/{asset.id}").json()["current_stock"],
            5,
        )
        self.assertEqual(
            self.client.get("/api/inventory/orders").json()[0]["type"], "exit"
        )
        with Session(self.engine) as session:
            events = session.exec(select(TelemetryOutboxEvent).order_by(TelemetryOutboxEvent.event_type)).scalars().all()
            self.assertEqual([event.event_type for event in events], ["inbound_order_created", "outbound_order_created"])
            inbound_event = next(event for event in events if event.event_type == "inbound_order_created")
            self.assertEqual(inbound_event.tags["unit_cost"], 12.5)
            self.assertEqual(inbound_event.tags["programme_id"], "prog-test")
            self.assertEqual(inbound_event.movement_id, inbound.json()["id"])
            self.assertTrue(all(event.status == "pending" and event.attempt_count == 0 for event in events))

    def test_insufficient_stock_and_invalid_references_leave_no_movement(self) -> None:
        asset = self.add_asset()
        response = self.client.post(
            "/api/inventory/orders/outbound",
            json={
                "asset_id": asset.id,
                "quantity": 1,
                "exit_type": "consumption",
                "office": "Valencia",
                "programme_id": "prog-test",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/inventory/orders").json(), [])

        inbound = self.client.post(
            "/api/inventory/orders/inbound",
            json={
                "asset_id": 987654,
                "quantity": 1,
                "unit_cost": 3,
                "supplier": "Acme",
                "office": "Valencia",
                "programme_id": "prog-test",
            },
        )
        self.assertEqual(inbound.status_code, 404)
        self.assertEqual(self.client.get("/api/inventory/orders").json(), [])

    def test_outbound_contract_and_quantities_are_validated(self) -> None:
        asset = self.add_asset()
        for payload in (
            {"asset_id": asset.id, "quantity": 1, "exit_type": "transfer", "office": "Valencia"},
            {"asset_id": asset.id, "quantity": 1, "exit_type": "allocation", "office": "Valencia"},
            {"asset_id": asset.id, "quantity": 1, "exit_type": "consumption", "assigned_to": "Alex", "office": "Valencia"},
            {"asset_id": asset.id, "quantity": 0, "exit_type": "consumption", "office": "Valencia"},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/inventory/orders/outbound", json=payload)
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/inventory/orders").json(), [])

    def test_legacy_authenticated_user_without_uuid_is_blocked_without_mutation(self) -> None:
        legacy_user = _FAKE_USER.model_copy(update={"user_uuid": None})
        app.dependency_overrides[get_current_user] = lambda: legacy_user
        asset = self.add_asset()

        response = self.client.post(
            "/api/inventory/orders/inbound",
            json={"asset_id": asset.id, "quantity": 2, "unit_cost": 3, "supplier": "Acme", "office": "Valencia", "programme_id": "prog-test"},
        )
        self.assertEqual(response.status_code, 428)
        self.assertEqual(self.client.get("/api/inventory/orders").json(), [])

    def test_client_cannot_supply_movement_identity(self) -> None:
        asset = self.add_asset()
        response = self.client.post(
            "/api/inventory/orders/inbound",
            json={
                "asset_id": asset.id,
                "quantity": 1,
                "unit_cost": 3,
                "supplier": "Acme",
                "office": "Valencia",
                "user_uuid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            },
        )
        self.assertEqual(response.status_code, 422)
        with Session(self.engine) as session:
            self.assertEqual(session.exec(select(AssetEntry)).all(), [])

    def test_postgresql_outbound_lookup_uses_row_lock_but_sqlite_does_not_prove_it(self) -> None:
        postgres_statement = _asset_lookup_statement(1, lock_for_update=True)
        postgres_sql = str(postgres_statement.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE", postgres_sql)
        sqlite_sql = str(_asset_lookup_statement(1, lock_for_update=True).compile(self.engine))
        self.assertNotIn("FOR UPDATE", sqlite_sql)

    def test_database_constraints_reject_invalid_exit_and_allow_rollback(self) -> None:
        asset = self.add_asset()
        with Session(self.engine) as session:
            session.add(
                AssetExit(
                    asset_id=asset.id,
                    quantity=1,
                    exit_type="allocation",
                    assigned_to=None,
                    office="Valencia",
                    currency="EUR",
                    user_uuid=_FAKE_USER.user_uuid,
                )
            )
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

        self.assertEqual(self.client.get("/api/inventory/orders").json(), [])

    def test_failed_movement_insert_rolls_back_the_transaction(self) -> None:
        asset = self.add_asset()
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TRIGGER reject_inventory_entry BEFORE INSERT ON asset_entries "
                "BEGIN SELECT RAISE(ABORT, 'forced test failure'); END"
            )

        response = self.client.post(
            "/api/inventory/orders/inbound",
            json={"asset_id": asset.id, "quantity": 2, "unit_cost": 3, "supplier": "Acme", "office": "Valencia", "programme_id": "prog-test"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/api/inventory/orders").json(), [])
        self.assertEqual(
            self.client.get(f"/api/inventory/products/{asset.id}").json()["current_stock"],
            0,
        )


class InventoryPostgresConcurrencyTests(unittest.TestCase):
    """Optional true row-lock test against an explicitly isolated PostgreSQL DB.

    Set NEXOVA_INVENTORY_TEST_POSTGRES_URL to a disposable database whose name
    ends with ``_test``. The test creates and drops only a random private schema.
    It is deliberately skipped in ordinary SQLite runs.
    """

    database_url = os.environ.get("NEXOVA_INVENTORY_TEST_POSTGRES_URL", "").strip()
    database_name = make_url(database_url).database if database_url else ""
    enabled = bool(database_url) and bool(database_name) and database_name.endswith("_test")

    @unittest.skipUnless(enabled, "isolated PostgreSQL concurrency DB not configured")
    def test_two_concurrent_exits_cannot_both_consume_the_same_stock(self) -> None:
        url = make_url(self.database_url)
        if url.get_backend_name() != "postgresql":
            self.fail("NEXOVA_INVENTORY_TEST_POSTGRES_URL must use PostgreSQL")

        schema = f"inventory_test_{uuid4().hex}"
        admin_engine = sqlalchemy_create_engine(self.database_url, pool_pre_ping=True)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))

        isolated_url = make_url(self.database_url).set_query(
            {
                **make_url(self.database_url).query,
                "options": f"-csearch_path={schema}",
            }
        )
        engine = sqlalchemy_create_engine(isolated_url, pool_size=5, max_overflow=0)
        try:
            SQLModel.metadata.create_all(engine)
            with Session(engine) as session:
                asset = Asset(name="Test", sku="CONC-1", category="IT", office="Test", currency="USD")
                session.add(asset)
                session.flush()
                session.add(
                    AssetEntry(
                        asset_id=asset.id,
                        quantity=10,
                        supplier="Test supplier",
                        office="Test",
                        currency="USD",
                        user_uuid=_FAKE_USER.user_uuid,
                    )
                )
                session.commit()
                asset_id = asset.id

            barrier = Barrier(2)

            def attempt_exit() -> str:
                with Session(engine) as session:
                    barrier.wait(timeout=10)
                    try:
                        create_outbound(
                            session,
                            AssetExitCreate(
                                asset_id=asset_id,
                                quantity=7,
                                exit_type="consumption",
                                office="Test",
                            ),
                            user_uuid=_FAKE_USER.user_uuid,
                        )
                        return "committed"
                    except InsufficientStock:
                        return "insufficient"

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: attempt_exit(), range(2)))

            self.assertCountEqual(results, ["committed", "insufficient"])
            with Session(engine) as session:
                self.assertEqual(len(session.exec(select(AssetExit)).all()), 1)
        finally:
            engine.dispose()
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin_engine.dispose()


if __name__ == "__main__":
    unittest.main()
