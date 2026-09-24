"""API tests for the Unit 7 FastAPI endpoint."""

import csv
import io
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).parents[3]
DATASET = ROOT / "scripts" / "incidents-nexova.csv"


class IncidentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.csv_bytes = DATASET.read_bytes()

    def post_csv(self, content: bytes, filename: str = "incidents.csv"):
        return self.client.post(
            "/api/incidents/analyze",
            files={"file": (filename, content, "text/csv")},
        )

    def test_valid_csv_returns_expected_aggregate_response(self) -> None:
        response = self.post_csv(self.csv_bytes)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_records"], 100)
        self.assertEqual(payload["valid_records"], 96)
        self.assertEqual(payload["invalid_records"], 4)
        self.assertEqual(payload["by_category"], {
            "TECHNICAL": 28,
            "BILLING": 18,
            "ACCESS": 21,
            "HR_QUERY": 17,
            "COMPLAINT": 12,
        })
        self.assertEqual(payload["by_status"], {
            "OPEN": 27,
            "CLOSED": 56,
            "DISCARDED": 13,
        })
        self.assertEqual(payload["satisfaction_distribution"], {
            "1": 2,
            "2": 5,
            "3": 10,
            "4": 22,
            "5": 17,
        })
        self.assertEqual(payload["average_satisfaction"], 3.84)

    def test_response_contains_only_aggregate_fields(self) -> None:
        response = self.post_csv(self.csv_bytes)
        response_text = response.text

        self.assertNotIn("customer_email", response_text)
        self.assertNotIn("@", response_text)
        self.assertNotIn("ticket_id", response_text)
        self.assertNotIn("description", response_text)

    def test_empty_file_returns_bad_request(self) -> None:
        response = self.post_csv(b"")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Uploaded CSV is empty")

    def test_missing_file_returns_unprocessable_entity(self) -> None:
        response = self.client.post("/api/incidents/analyze")

        self.assertEqual(response.status_code, 422)
        self.assertIn("file", response.text)

    def test_non_csv_filename_returns_bad_request(self) -> None:
        response = self.post_csv(self.csv_bytes, filename="incidents.txt")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Uploaded file must be a CSV")

    def test_malformed_csv_returns_bad_request(self) -> None:
        malformed = b"ticket_id,category\nNXV-1,ACCESS\n"
        response = self.post_csv(malformed)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid CSV file")


if __name__ == "__main__":
    unittest.main()
