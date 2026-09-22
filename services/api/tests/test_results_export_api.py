"""Tests for the Unit 8 latest-result CSV endpoint."""

import csv
import io
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


ROOT = Path(__file__).parents[3]
DATASET = ROOT / "scripts" / "incidents-nexova.csv"


class LatestResultExportApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.csv_bytes = DATASET.read_bytes()

    def setUp(self) -> None:
        main_module._latest_result = None

    def post_csv(self, content: bytes):
        return self.client.post(
            "/api/incidents/analyze",
            files={"file": ("incidents.csv", content, "text/csv")},
        )

    def test_export_before_analysis_returns_not_found(self) -> None:
        response = self.client.get("/api/incidents/results/export")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No analysis result available")

    def test_post_then_get_returns_latest_aggregate_csv(self) -> None:
        post_response = self.post_csv(self.csv_bytes)
        self.assertEqual(post_response.status_code, 200)

        response = self.client.get("/api/incidents/results/export")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("metric,dimension,value", response.text)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertIn({"metric": "total_records", "dimension": "all", "value": "100"}, rows)
        self.assertIn({"metric": "valid_records", "dimension": "all", "value": "96"}, rows)
        self.assertIn({"metric": "invalid_records", "dimension": "all", "value": "4"}, rows)
        self.assertIn(
            {"metric": "average_satisfaction", "dimension": "closed_tickets", "value": "3.84"},
            rows,
        )

    def test_export_contains_all_aggregate_dimensions(self) -> None:
        self.post_csv(self.csv_bytes)
        response = self.client.get("/api/incidents/results/export")

        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        metrics = {row["metric"] for row in rows}
        self.assertTrue({
            "records_by_category",
            "records_by_status",
            "satisfaction_distribution",
            "invalid_by_type",
        }.issubset(metrics))

    def test_export_contains_no_sensitive_or_raw_fields(self) -> None:
        self.post_csv(self.csv_bytes)
        response = self.client.get("/api/incidents/results/export")

        self.assertNotIn("customer_email", response.text)
        self.assertNotIn("@", response.text)
        self.assertNotIn("ticket_id", response.text)
        self.assertNotIn("description", response.text)

    def test_second_post_replaces_latest_result(self) -> None:
        first = self.post_csv(self.csv_bytes)
        self.assertEqual(first.status_code, 200)
        replacement = (
            b"ticket_id,date,client_company,category,description,agent_id,status,"
            b"customer_email,satisfaction_score\n"
            b"NXV-000002,2024-01-18,Acme,ACCESS,Valid issue,AGT-08,OPEN,"
            b"person@example.com,\n"
        )
        second = self.post_csv(replacement)
        self.assertEqual(second.status_code, 200)

        response = self.client.get("/api/incidents/results/export")
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertIn({"metric": "total_records", "dimension": "all", "value": "1"}, rows)
        self.assertIn({"metric": "valid_records", "dimension": "all", "value": "1"}, rows)
        self.assertIn({"metric": "invalid_records", "dimension": "all", "value": "0"}, rows)
        self.assertNotIn("person@example.com", response.text)


if __name__ == "__main__":
    unittest.main()
