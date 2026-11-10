"""HTTP integration tests for partial telemetry ingestion."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.telemetry.repository import TelemetryStorageUnavailable


def valid_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "specversion": "1.0",
        "source": "/nexova/inventory",
        "id": str(uuid4()),
        "type": "inbound_order_created",
        "time": "2026-11-02T18:07:44.123Z",
        "datacontenttype": "application/json",
        "data": {
            "product_id": 42,
            "product_sku": "NXV-IT-001",
            "quantity": 10.0,
            "unapproved_property": "must not be stored",
        },
        "sessionId": "session-123",
        "schemaVersion": "1.0.0",
    }
    event.update(overrides)
    return event


class FakeTelemetryRepository:
    def __init__(self, stored_count: int | None = None) -> None:
        self.calls: list[list[object]] = []
        self.stored_count = stored_count

    def insert_many(self, records: list[object]) -> int:
        self.calls.append(records)
        return self.stored_count if self.stored_count is not None else len(records)


class TelemetryEndpointTests(unittest.TestCase):
    """The HTTP handler validates events individually before one bulk write."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.endpoint = "/api/telemetry/events"

    def setUp(self) -> None:
        self.repository = FakeTelemetryRepository()
        self.repository_patch = patch(
            "app.telemetry.router.get_telemetry_repository",
            return_value=self.repository,
        )
        self.repository_patch.start()

    def tearDown(self) -> None:
        self.repository_patch.stop()

    def test_valid_event_is_stored_and_allowlisted(self) -> None:
        response = self.client.post(self.endpoint, json={"events": [valid_event()]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 1, "stored": 1, "rejected": 0})
        self.assertEqual(len(self.repository.calls), 1)
        record = self.repository.calls[0][0]
        self.assertEqual(record.event_type, "inbound_order_created")
        self.assertEqual(record.tags["product_id"], 42)
        self.assertNotIn("unapproved_property", record.tags)

    def test_mixed_batch_accepts_valid_events_and_rejects_invalid_ones(self) -> None:
        invalid = valid_event(id="not-a-uuid")
        response = self.client.post(
            self.endpoint,
            json={"events": [valid_event(), invalid, valid_event()]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 3, "stored": 2, "rejected": 1})
        self.assertEqual(len(self.repository.calls), 1)
        self.assertEqual(len(self.repository.calls[0]), 2)

    def test_all_invalid_events_do_not_call_storage(self) -> None:
        response = self.client.post(
            self.endpoint,
            json={"events": [valid_event(id="invalid"), {"type": "missing-envelope"}]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 2, "stored": 0, "rejected": 2})
        self.assertEqual(self.repository.calls, [])

    def test_empty_batch_does_not_call_storage(self) -> None:
        response = self.client.post(self.endpoint, json={"events": []})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 0, "stored": 0, "rejected": 0})
        self.assertEqual(self.repository.calls, [])

    def test_missing_or_non_array_events_returns_400(self) -> None:
        for payload in ({}, {"events": None}, {"events": "not-an-array"}, []):
            with self.subTest(payload=payload):
                response = self.client.post(self.endpoint, json=payload)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.repository.calls, [])

    def test_duplicate_is_not_reported_as_a_validation_rejection(self) -> None:
        self.repository.stored_count = 0
        response = self.client.post(self.endpoint, json={"events": [valid_event()]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 1, "stored": 0, "rejected": 0})

    def test_storage_failure_returns_503_without_exposing_details(self) -> None:
        failing_repository = FakeTelemetryRepository()
        failing_repository.insert_many = lambda records: (_ for _ in ()).throw(
            TelemetryStorageUnavailable("private database url")
        )
        with patch(
            "app.telemetry.router.get_telemetry_repository",
            return_value=failing_repository,
        ):
            response = self.client.post(self.endpoint, json={"events": [valid_event()]})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Telemetry storage is temporarily unavailable")

    def test_telemetry_report_endpoint_remains_available(self) -> None:
        expected = {
            "period": {"start": "2026-11-02", "end": "2026-11-09", "days": 7},
            "metrics": {"total_events": 3},
        }
        with patch("app.telemetry.router.build_report_json", return_value=expected) as build:
            response = self.client.get(
                "/api/telemetry/report?start_date=2026-11-02&end_date=2026-11-09&limit=20"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        build.assert_called_once_with(
            start="2026-11-02", end="2026-11-09", limit=20,
        )


if __name__ == "__main__":
    unittest.main()
