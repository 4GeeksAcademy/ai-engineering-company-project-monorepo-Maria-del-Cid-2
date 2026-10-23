"""API tests for the Unit 7 FastAPI endpoint."""

import csv
import io
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).parents[3]
DATASET = ROOT / "scripts" / "incidents-nexova.csv"


async def _raise_unexpected_error():
    raise RuntimeError("internal detail must not reach the client")


app.add_api_route("/__test/unexpected-error", _raise_unexpected_error, methods=["GET"])


class IncidentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.safe_error_client = TestClient(app, raise_server_exceptions=False)
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

    def test_analyze_response_has_exactly_aggregate_keys(self) -> None:
        """The payload is locked to exactly the eight aggregate fields.

        Guards against future serialization drift (extra fields leaking or
        aggregate fields being renamed/removed), which would break the
        frontend ``IncidentAnalysisResult`` contract.
        """
        response = self.post_csv(self.csv_bytes)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload.keys()),
            {
                "total_records",
                "valid_records",
                "invalid_records",
                "by_category",
                "by_status",
                "satisfaction_distribution",
                "average_satisfaction",
                "invalid_by_type",
            },
        )

    def test_openapi_declares_incident_analysis_response_schema(self) -> None:
        """``POST /api/incidents/analyze`` documents a response_model contract.

        Verifies Fase 2: the endpoint now declares ``IncidentAnalysisResponse``
        in OpenAPI, exposing exactly the aggregate fields and no raw CSV input
        fields (customer_email, ticket_id, description).
        """
        schema = app.openapi()
        post_path = schema["paths"]["/api/incidents/analyze"]["post"]
        response_schema = post_path["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(response_schema["$ref"], "#/components/schemas/IncidentAnalysisResponse")

        component = schema["components"]["schemas"]["IncidentAnalysisResponse"]
        self.assertEqual(
            set(component["properties"].keys()),
            {
                "total_records",
                "valid_records",
                "invalid_records",
                "by_category",
                "by_status",
                "satisfaction_distribution",
                "average_satisfaction",
                "invalid_by_type",
            },
        )
        self.assertNotIn("customer_email", component["properties"])
        self.assertNotIn("ticket_id", component["properties"])
        self.assertNotIn("description", component["properties"])

    def test_empty_file_returns_bad_request(self) -> None:
        response = self.post_csv(b"")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Uploaded CSV is empty")

    def test_missing_file_returns_unprocessable_entity(self) -> None:
        response = self.client.post("/api/incidents/analyze")

        self.assertEqual(response.status_code, 422)
        self.assertIn("file", response.text)
        self.assertNotIn('"input"', response.text)
        self.assertNotIn('"ctx"', response.text)

    def test_validation_error_does_not_expose_password_or_token(self) -> None:
        response = self.safe_error_client.post(
            "/api/auth/reset-password",
            json={
                "token": "reset-token-secret",
                "new_password": "new-password-secret",
                "confirm_password": "different-password-secret",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("reset-token-secret", response.text)
        self.assertNotIn("new-password-secret", response.text)
        self.assertNotIn("different-password-secret", response.text)
        self.assertNotIn('"input"', response.text)
        self.assertNotIn('"ctx"', response.text)

    def test_unexpected_error_returns_generic_500_and_safe_log(self) -> None:
        with self.assertLogs("app.main", level="ERROR") as logs:
            response = self.safe_error_client.get(
                "/__test/unexpected-error",
                headers={"X-Request-ID": "audit-correlation-123"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"message": "No se pudo completar la operación. Inténtalo de nuevo."},
        )
        self.assertNotIn("internal detail must not reach the client", response.text)
        log_output = "\n".join(logs.output)
        self.assertIn("path=/__test/unexpected-error", log_output)
        self.assertIn("exception_type=RuntimeError", log_output)
        self.assertIn("correlation_id=audit-correlation-123", log_output)
        self.assertNotIn("internal detail must not reach the client", log_output)

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
