"""Tests for the incidents summary cache (TTLCache integration).

These tests verify that GET /api/incidents/summary:
1. Caches results on the first call.
2. Reuses the cached result on subsequent calls without re-querying.
3. Re-queries after TTL expiration (10 s).
4. Invalidates the cache on POST /api/incidents (create incident).
5. Invalidates the cache on PATCH /api/incidents/{id}/status (status update).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from fastapi.testclient import TestClient

from app.incidents import manager_router
from app.incidents.manager_router import (
    _summary_cache,
    CACHE_TTL_SUMMARY,
)
from app.incidents.manager_database import create_database
from app.incidents.manager_repository import IncidentRepository
from app.main import app


def _payload(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Test incident",
        "description": "Description for test",
        "category": "technical_failure",
        "status": "open",
        "origin": "branch",
        "branch": "remote",
    }
    base.update(changes)
    return base


class IncidentSummaryCacheTests(unittest.TestCase):
    """Verifies that the incidents summary cache behaves correctly."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "incidents.json"
        database = create_database(db_path)

        def override_repository():
            yield IncidentRepository(database)

        app.dependency_overrides.clear()
        app.dependency_overrides[manager_router.get_repository] = override_repository
        app.dependency_overrides[manager_router.get_current_user] = lambda: None
        self.client = TestClient(app)
        self.database = database
        _summary_cache.clear()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.database.close()
        self.temp_dir.cleanup()
        _summary_cache.clear()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _replace_cache_with_spy(self):
        """Replace the global cache with a spy to track interactions.

        Returns (spy) where spy.get_calls tracks all get() invocations
        and spy.last_get_returned tracks the result of the last get().
        """
        from app.incidents import manager_router as router

        original_cache = router._summary_cache
        _calls: list[str] = []
        _returned: list[object | None] = [None]

        class SpyCache:
            @property
            def size(self):
                return original_cache.size

            def clear(self):
                original_cache.clear()

            def delete(self, key):
                original_cache.delete(key)

            def get(self, key):
                _calls.append(key)
                result = original_cache.get(key)
                _returned[0] = result
                return result

            def set(self, key, value, ttl=None):
                original_cache.set(key, value, ttl)

            def invalidate(self, prefix):
                return original_cache.invalidate(prefix)

        router._summary_cache = SpyCache()  # type: ignore[assignment]
        spy = lambda: None
        spy.calls = _calls
        spy.returned = _returned
        spy.restore = lambda: setattr(router, "_summary_cache", original_cache)
        return spy

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_first_call_caches_result(self) -> None:
        """After the first GET, the cache contains the result."""
        # Seed one incident
        self.client.post("/api/incidents", json=_payload())

        self.assertIsNone(_summary_cache.get("summary"))

        response = self.client.get("/api/incidents/summary")
        self.assertEqual(response.status_code, 200)

        cached = _summary_cache.get("summary")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.total, 1)

    def test_second_call_uses_cache(self) -> None:
        """A second GET within TTL uses the cached result."""
        self.client.post("/api/incidents", json=_payload())
        self.client.get("/api/incidents/summary")

        spy = self._replace_cache_with_spy()
        try:
            response = self.client.get("/api/incidents/summary")
        finally:
            spy.restore()

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(spy.calls), 1)
        self.assertIsNotNone(spy.returned[0])

    def test_expiration_triggers_new_query(self) -> None:
        """After the TTL elapses, the next GET re-queries the database."""
        self.client.post("/api/incidents", json=_payload())
        fixed_now = 1_000_000.0

        with mock.patch("app.cache.ttl_cache.time.monotonic", return_value=fixed_now):
            self.client.get("/api/incidents/summary")
            self.assertIsNotNone(_summary_cache.get("summary"))

        with mock.patch(
            "app.cache.ttl_cache.time.monotonic",
            return_value=fixed_now + CACHE_TTL_SUMMARY + 0.001,
        ):
            self.assertIsNone(_summary_cache.get("summary"))
            response = self.client.get("/api/incidents/summary")
            self.assertEqual(response.status_code, 200)
            self.assertIsNotNone(_summary_cache.get("summary"))

    def test_create_incident_invalidates_cache(self) -> None:
        """Creating an incident clears the summary cache."""
        self.client.post("/api/incidents", json=_payload())
        self.client.get("/api/incidents/summary")
        self.assertIsNotNone(_summary_cache.get("summary"))

        self.client.post(
            "/api/incidents",
            json=_payload(title="Second incident", category="client_complaint"),
        )
        self.assertIsNone(_summary_cache.get("summary"))

        # Next GET re-populates
        response = self.client.get("/api/incidents/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

    def test_status_update_invalidates_cache(self) -> None:
        """Changing an incident's status clears the summary cache."""
        self.client.post("/api/incidents", json=_payload())
        self.client.get("/api/incidents/summary")
        self.assertIsNotNone(_summary_cache.get("summary"))

        self.client.patch("/api/incidents/1/status", json={"status": "in_progress"})
        self.assertIsNone(_summary_cache.get("summary"))

        # Next GET reflects the status change
        response = self.client.get("/api/incidents/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["by_status"]["open"], 0)
        self.assertEqual(data["by_status"]["in_progress"], 1)

    def test_cache_after_post_then_get_returns_updated_count(self) -> None:
        """Regression: creating then immediately getting summary returns correct count."""
        self.client.post("/api/incidents", json=_payload())

        response = self.client.get("/api/incidents/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_invalidate_does_not_affect_other_cache_instances(self) -> None:
        """Invalidation of summary cache does not affect the products cache."""
        from app.inventory.router import _products_cache

        self.client.post("/api/incidents", json=_payload())
        self.client.get("/api/incidents/summary")
        _products_cache.set("list", ["dummy"])

        # Invalidate summary
        self.client.post("/api/incidents", json=_payload(title="Another incident"))
        self.assertIsNone(_summary_cache.get("summary"))
        self.assertIsNotNone(_products_cache.get("list"))