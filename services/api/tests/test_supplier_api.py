"""Endpoint tests for Supplier Directory Step 3."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.suppliers.database import create_database
from app.suppliers.seed import seed_suppliers


PAYLOAD = {
    "name": "Test Supplier",
    "country": "Spain",
    "categories": ["ats_software"],
    "monthly_rate": 100.0,
    "currency": "EUR",
    "status": "active",
}


class SupplierApiTests(unittest.TestCase):
    FRONTEND_ORIGIN = "https://friendly-barnacle-qv5p44r9rxq2644j-3000.app.github.dev"

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "suppliers.json"
        os.environ["SUPPLIER_DIRECTORY_DB_PATH"] = str(self.database_path)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("SUPPLIER_DIRECTORY_DB_PATH", None)
        self.temporary_directory.cleanup()

    def create_supplier(self, payload: dict | None = None):
        return self.client.post("/api/suppliers", json=payload or PAYLOAD)

    def test_create_valid_supplier_generates_id_and_updated_at(self) -> None:
        response = self.create_supplier()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["id"], 1)
        self.assertEqual(body["name"], "Test Supplier")
        self.assertIsInstance(datetime.fromisoformat(body["updated_at"]), datetime)

    def test_create_rejects_invalid_supplier_data(self) -> None:
        for invalid in (
            {**PAYLOAD, "country": "France"},
            {**PAYLOAD, "country": "USA", "currency": "EUR"},
            {**PAYLOAD, "categories": ["unknown"]},
            {**PAYLOAD, "monthly_rate": 0},
            {**PAYLOAD, "status": "deleted"},
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.create_supplier(invalid).status_code, 422)

    def test_list_and_filters(self) -> None:
        self.create_supplier()
        self.create_supplier({**PAYLOAD, "name": "USA Supplier", "country": "USA", "currency": "USD", "categories": ["job_boards"]})
        self.assertEqual(self.client.get("/api/suppliers").status_code, 200)
        self.assertEqual(len(self.client.get("/api/suppliers").json()), 2)
        self.assertEqual(len(self.client.get("/api/suppliers?country=USA").json()), 1)
        self.assertEqual(len(self.client.get("/api/suppliers?category=ats_software").json()), 1)
        self.assertEqual(self.client.get("/api/suppliers?country=France").status_code, 422)

    def test_cors_allows_supplier_patch_and_delete(self) -> None:
        for method in ("PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.options(
                    "/api/suppliers/1/status" if method == "PATCH" else "/api/suppliers/1",
                    headers={
                        "Origin": self.FRONTEND_ORIGIN,
                        "Access-Control-Request-Method": method,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], self.FRONTEND_ORIGIN)
                self.assertIn(
                    method,
                    response.headers["access-control-allow-methods"].split(", "),
                )

    def test_get_by_id_and_missing_id(self) -> None:
        self.create_supplier()
        self.assertEqual(self.client.get("/api/suppliers/1").status_code, 200)
        self.assertEqual(self.client.get("/api/suppliers/999").status_code, 404)

    def test_update_rate_changes_updated_at_and_rejects_non_positive_rate(self) -> None:
        original = self.create_supplier().json()
        updated = self.client.patch("/api/suppliers/1/rate", json={"monthly_rate": 250}).json()
        self.assertEqual(updated["monthly_rate"], 250)
        self.assertNotEqual(updated["updated_at"], original["updated_at"])
        self.assertEqual(self.client.patch("/api/suppliers/1/rate", json={"monthly_rate": 0}).status_code, 422)
        self.assertEqual(self.client.patch("/api/suppliers/999/rate", json={"monthly_rate": 250}).status_code, 404)

    def test_update_status_validates_and_preserves_supplier(self) -> None:
        self.create_supplier()
        self.assertEqual(self.client.patch("/api/suppliers/1/status", json={"status": "suspended"}).status_code, 200)
        self.assertEqual(self.client.get("/api/suppliers/1").json()["status"], "suspended")
        self.assertEqual(self.client.patch("/api/suppliers/1/status", json={"status": "deleted"}).status_code, 422)
        self.assertEqual(self.client.patch("/api/suppliers/999/status", json={"status": "active"}).status_code, 404)

    def test_delete_removes_supplier_and_returns_not_found_afterwards(self) -> None:
        self.create_supplier()
        self.assertEqual(self.client.delete("/api/suppliers/1").status_code, 204)
        self.assertEqual(self.client.get("/api/suppliers/1").status_code, 404)
        self.assertEqual(self.client.delete("/api/suppliers/1").status_code, 404)

    def test_seeded_suppliers_can_be_listed(self) -> None:
        with create_database(self.database_path) as database:
            seed_suppliers(database)
        self.assertEqual(len(self.client.get("/api/suppliers").json()), 15)


if __name__ == "__main__":
    unittest.main()
