"""Tests for task-scoped asynchronous Incident Analysis endpoints."""

from __future__ import annotations

import csv
import io
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class AsyncIncidentAnalysisApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    @patch("app.main.AsyncResult")
    def test_pending_and_completed_task_statuses(self, async_result) -> None:
        task = async_result.return_value
        task.state = "PENDING"
        response = self.client.get("/api/tasks/8fa7f66f-bad9-4585-ae8d-bb19e2b38666")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

        task.state = "SUCCESS"
        task.result = {
            "total_records": 1,
            "valid_records": 1,
            "invalid_records": 0,
            "by_category": {"ACCESS": 1},
            "by_status": {"OPEN": 1},
            "satisfaction_distribution": {},
            "average_satisfaction": None,
            "invalid_by_type": {},
        }
        response = self.client.get("/api/tasks/8fa7f66f-bad9-4585-ae8d-bb19e2b38666")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], task.result)

    @patch("app.main.AsyncResult")
    def test_task_failure_response_does_not_expose_exception(self, async_result) -> None:
        async_result.return_value.state = "FAILURE"
        async_result.return_value.result = RuntimeError("sensitive row data")
        response = self.client.get("/api/tasks/8fa7f66f-bad9-4585-ae8d-bb19e2b38666")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], "Analysis failed. Please upload the file again.")
        self.assertNotIn("sensitive row data", response.text)

    @patch("app.main.AsyncResult")
    def test_export_is_scoped_to_task_and_contains_aggregates_only(self, async_result) -> None:
        async_result.return_value.state = "SUCCESS"
        async_result.return_value.result = {
            "total_records": 1,
            "valid_records": 1,
            "invalid_records": 0,
            "by_category": {"ACCESS": 1},
            "by_status": {"OPEN": 1},
            "satisfaction_distribution": {},
            "average_satisfaction": None,
            "invalid_by_type": {},
        }
        response = self.client.get(
            "/api/incidents/tasks/8fa7f66f-bad9-4585-ae8d-bb19e2b38666/export"
        )
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertIn({"metric": "total_records", "dimension": "all", "value": "1"}, rows)
        for sensitive in ("customer_email", "ticket_id", "description", "@"):
            self.assertNotIn(sensitive, response.text)

    def test_invalid_task_id_is_not_found(self) -> None:
        response = self.client.get("/api/tasks/not-a-uuid")
        self.assertEqual(response.status_code, 404)

    def test_task_result_serializer_excludes_raw_values(self) -> None:
        from app.incidents.analysis import analyze_incidents as real_analyze
        from app.incidents.csv_reader import read_incidents_csv
        from app.incidents.task_results import serialize_analysis_result

        row = read_incidents_csv(io.StringIO(
            "ticket_id,date,client_company,category,description,agent_id,status,customer_email,satisfaction_score\n"
            "NXV-1,2024-01-01,Acme,ACCESS,private description,AGT-1,OPEN,person@example.com,\n"
        ))
        result = real_analyze(row)
        serialized = serialize_analysis_result(result)
        self.assertNotIn("person@example.com", repr(serialized))
        self.assertNotIn("private description", repr(serialized))


if __name__ == "__main__":
    unittest.main()
