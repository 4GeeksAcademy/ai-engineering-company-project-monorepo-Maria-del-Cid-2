"""Tests for the inventory products cache (TTLCache integration).

These tests verify that GET /api/inventory/products:
1. Caches results on the first call.
2. Reuses the cached result on subsequent calls without re-querying.
3. Re-queries after TTL expiration.
4. Invalidates the cache on POST /products.
5. Invalidates the cache on POST /orders/inbound and POST /orders/outbound.
6. Invalidation is scoped to the ``list`` key only.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
from uuid import UUID

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.inventory.database import get_session
from app.inventory.models import Asset, AssetEntry
from app.inventory.router import _products_cache, CACHE_TTL_PRODUCTS
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


def _seed_asset(session: Session, name: str, sku: str, stock: float) -> Asset:
    """Create an asset and add entry movements so derived stock equals *stock*."""
    asset = Asset(name=name, sku=sku, category="IT", office="Valencia")
    session.add(asset)
    session.commit()
    if stock > 0:
        session.add(AssetEntry(
            asset_id=asset.id, quantity=stock, supplier="Seed",
            office="Valencia", user_uuid=_FAKE_USER.user_uuid,
        ))
        session.commit()
    return asset


class InventoryCacheTests(unittest.TestCase):
    """Verifies that the products cache behaves correctly."""

    def setUp(self) -> None:
        self._tmpdir = TemporaryDirectory()
        self._db_path = os.path.join(self._tmpdir.name, "test.db")
        self.engine = create_engine(
            f"sqlite:///{self._db_path}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(self.engine)

        def override_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        _products_cache.clear()

        with Session(self.engine) as session:
            asset = _seed_asset(session, "Monitor", "MON-1", 25.0)
            self.asset_id = asset.id
            # Extra stock so outbound tests don't need per-test setup
            session.add(AssetEntry(
                asset_id=self.asset_id, quantity=50, supplier="ExtraStock",
                office="Valencia", user_uuid=_FAKE_USER.user_uuid,
            ))
            session.commit()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()
        _products_cache.clear()
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_first_call_caches_result(self) -> None:
        """After the first GET, the cache contains the result."""
        self.assertIsNone(_products_cache.get("list"))

        response = self.client.get("/api/inventory/products")
        self.assertEqual(response.status_code, 200)

        cached = _products_cache.get("list")
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0].sku, "MON-1")

    def test_second_call_uses_cache(self) -> None:
        """A second GET within TTL does not need to re-query (cache hit)."""
        # Populate cache
        self.client.get("/api/inventory/products")

        # Replace the global cache with a spy that records interactions
        from app.inventory import router

        original_cache = router._products_cache
        spy_calls: list[str] = []
        spy_return: list[object | None] = [None]

        class SpyCache:
            @property
            def size(self):
                return original_cache.size

            def clear(self):
                original_cache.clear()

            def delete(self, key):
                original_cache.delete(key)

            def get(self, key):
                spy_calls.append(key)
                result = original_cache.get(key)
                spy_return[0] = result
                return result

            def set(self, key, value, ttl=None):
                original_cache.set(key, value, ttl)

            def invalidate(self, prefix):
                return original_cache.invalidate(prefix)

        router._products_cache = SpyCache()  # type: ignore[assignment]
        try:
            response = self.client.get("/api/inventory/products")
        finally:
            router._products_cache = original_cache

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(spy_calls), 1)
        self.assertIsNotNone(spy_return[0])

    def test_expiration_triggers_new_query(self) -> None:
        """After the TTL elapses, the next GET re-queries the database."""
        fixed_now = 1_000_000.0

        with mock.patch("app.cache.ttl_cache.time.monotonic", return_value=fixed_now):
            self.client.get("/api/inventory/products")
            self.assertIsNotNone(_products_cache.get("list"))

        with mock.patch(
            "app.cache.ttl_cache.time.monotonic",
            return_value=fixed_now + CACHE_TTL_PRODUCTS + 0.001,
        ):
            self.assertIsNone(_products_cache.get("list"))
            response = self.client.get("/api/inventory/products")
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(_products_cache.get("list"))

    def test_post_product_invalidates_cache(self) -> None:
        """Creating a product clears the cached list."""
        self.client.get("/api/inventory/products")
        self.assertIsNotNone(_products_cache.get("list"))

        response = self.client.post(
            "/api/inventory/products",
            json={
                "name": "Keyboard", "sku": "KEY-1",
                "category": "IT", "office": "Valencia",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(_products_cache.get("list"))

        response = self.client.get("/api/inventory/products")
        self.assertEqual(response.status_code, 200)
        products = response.json()
        skus = {p["sku"] for p in products}
        self.assertIn("MON-1", skus)
        self.assertIn("KEY-1", skus)

    def test_inbound_invalidates_cache(self) -> None:
        """Registering an inbound clears the cached list."""
        self.client.get("/api/inventory/products")
        self.assertIsNotNone(_products_cache.get("list"))

        response = self.client.post(
            "/api/inventory/orders/inbound",
            json={
                "asset_id": self.asset_id, "quantity": 10,
                "supplier": "Acme", "office": "Valencia",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(_products_cache.get("list"))

        response = self.client.get("/api/inventory/products")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(_products_cache.get("list"))

    def test_outbound_invalidates_cache(self) -> None:
        """Registering an outbound clears the cached list."""
        self.client.get("/api/inventory/products")
        self.assertIsNotNone(_products_cache.get("list"))

        response = self.client.post(
            "/api/inventory/orders/outbound",
            json={
                "asset_id": self.asset_id, "quantity": 5,
                "exit_type": "allocation", "assigned_to": "Alice",
                "office": "Valencia",            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(_products_cache.get("list"))

        response = self.client.get("/api/inventory/products")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(_products_cache.get("list"))

    def test_invalidate_does_not_affect_other_cache_keys(self) -> None:
        """Invalidation removes only the 'list' key, not unrelated entries."""
        self.client.get("/api/inventory/products")
        self.assertIsNotNone(_products_cache.get("list"))

        _products_cache.set("other:data", {"hello": "world"})
        self.assertEqual(_products_cache.size, 2)

        self.client.post(
            "/api/inventory/products",
            json={
                "name": "Mouse", "sku": "MOU-2",
                "category": "IT", "office": "Valencia",
            },        )

        self.assertIsNone(_products_cache.get("list"))
        self.assertEqual(_products_cache.get("other:data"), {"hello": "world"})