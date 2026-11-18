"""API tests for the Unit 7 FastAPI endpoint."""

import csv
import io
import os
import tempfile
import unittest
from unittest.mock import patch
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
        cls.upload_dir = tempfile.TemporaryDirectory()
        os.environ["INCIDENT_ANALYSIS_UPLOAD_DIR"] = cls.upload_dir.name

    @classmethod
    def tearDownClass(cls) -> None:
        cls.upload_dir.cleanup()
        os.environ.pop("INCIDENT_ANALYSIS_UPLOAD_DIR", None)

    def post_csv(self, content: bytes, filename: str = "incidents.csv"):
        return self.client.post(
            "/api/incidents/analyze",
            files={"file": (filename, content, "text/csv")},
        )

    @patch("app.main.analyze_incidents_task.apply_async")
    def test_valid_csv_is_accepted_and_only_opaque_reference_is_queued(self, enqueue) -> None:
        enqueue.return_value.id = "8fa7f66f-bad9-4585-ae8d-bb19e2b38666"
        response = self.post_csv(self.csv_bytes)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"task_id": enqueue.return_value.id})
        queued_args = enqueue.call_args.kwargs.get("args") or enqueue.call_args.args[0]
        self.assertEqual(len(queued_args), 1)
        self.assertRegex(queued_args[0], r"^[0-9a-f]{32}$")

    @patch("app.main.analyze_incidents_task.apply_async")
    def test_upload_content_is_not_in_task_message_or_acknowledgement(self, enqueue) -> None:
        enqueue.return_value.id = "8fa7f66f-bad9-4585-ae8d-bb19e2b38666"
        response = self.post_csv(self.csv_bytes)
        self.assertEqual(response.status_code, 202)
        self.assertNotIn("customer_email", response.text)
        self.assertNotIn("@", response.text)
        self.assertNotIn("ticket_id", response.text)
        self.assertNotIn("description", response.text)
        self.assertNotIn("@", repr(enqueue.call_args))

    def test_openapi_declares_incident_analysis_response_schema(self) -> None:
        """``POST /api/incidents/analyze`` documents a response_model contract.

        Verifies Fase 2: the endpoint now declares ``IncidentAnalysisResponse``
        in OpenAPI, exposing exactly the aggregate fields and no raw CSV input
        fields (customer_email, ticket_id, description).
        """
        schema = app.openapi()
        post_path = schema["paths"]["/api/incidents/analyze"]["post"]
        response_schema = post_path["responses"]["202"]["content"][
            "application/json"
        ]["schema"]
        self.assertEqual(response_schema["$ref"], "#/components/schemas/IncidentAnalysisTaskAccepted")

        component = schema["components"]["schemas"]["IncidentAnalysisTaskAccepted"]
        self.assertEqual(
            set(component["properties"].keys()),
            {"task_id"},
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

    def test_oversized_csv_returns_payload_too_large(self) -> None:
        with patch("app.main.MAX_INCIDENT_UPLOAD_BYTES", 8):
            response = self.post_csv(self.csv_bytes)
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
