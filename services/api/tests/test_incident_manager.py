"""Tests for the persistent Centralized Incident Manager."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.incidents import manager_router
from app.incidents.manager_database import create_database
from app.incidents.manager_repository import IncidentRepository
from app.main import app


class IncidentManagerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database = create_database(Path(self.temp_dir.name) / "incidents.json")

        def override_repository():
            yield IncidentRepository(database)

        app.dependency_overrides[manager_router.get_repository] = override_repository
        app.dependency_overrides[manager_router.get_current_user] = lambda: None
        self.client = TestClient(app)
        self.database = database

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.database.close()
        self.temp_dir.cleanup()

    def test_manager_requires_authentication(self) -> None:
        app.dependency_overrides.pop(manager_router.get_current_user)

        response = self.client.get("/api/incidents/summary")

        self.assertEqual(response.status_code, 401)

    def payload(self, **changes: object) -> dict[str, object]:
        value: dict[str, object] = {
            "title": "Access issue in the candidate portal",
            "description": "Candidates cannot sign in to the portal.",
            "category": "technical_failure",
            "status": "open",
            "origin": "branch",
            "branch": "remote",
        }
        value.update(changes)
        return value

    def test_empty_summary_contains_zero_dimensions(self) -> None:
        response = self.client.get("/api/incidents/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["by_status"]["open"], 0)
        self.assertEqual(payload["by_category"]["sla_breach"], 0)
        self.assertEqual(payload["by_branch"]["remote"], 0)

    def test_create_list_filters_and_detail(self) -> None:
        created = self.client.post("/api/incidents", json=self.payload()).json()
        self.client.post(
            "/api/incidents",
            json=self.payload(
                title="Client complaint",
                category="client_complaint",
                origin="customer",
                branch="central",
            ),
        )

        self.assertEqual(created["id"], 1)
        self.assertNotIn("ticket_id", created)
        self.assertNotIn("customer_email", created)
        filtered = self.client.get("/api/incidents", params={"branch": "remote"})
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(len(filtered.json()), 1)
        self.assertEqual(self.client.get("/api/incidents/1").status_code, 200)
        self.assertEqual(self.client.get("/api/incidents/999").status_code, 404)

    def test_status_transitions_are_restricted(self) -> None:
        self.client.post("/api/incidents", json=self.payload())

        moved = self.client.patch("/api/incidents/1/status", json={"status": "in_progress"})
        self.assertEqual(moved.status_code, 200)
        resolved = self.client.patch("/api/incidents/1/status", json={"status": "resolved"})
        self.assertEqual(resolved.status_code, 200)
        final_attempt = self.client.patch("/api/incidents/1/status", json={"status": "open"})
        self.assertEqual(final_attempt.status_code, 400)
        self.assertEqual(final_attempt.json()["field"], "status")

    def test_incident_validation_returns_safe_400(self) -> None:
        response = self.client.post("/api/incidents", json={"title": ""})

        self.assertEqual(response.status_code, 400)
        self.assertIn("field", response.json())
        self.assertIn("message", response.json())
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
