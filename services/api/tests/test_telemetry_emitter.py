"""Unit tests for the backend TelemetryEmitter."""

from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch

from app.telemetry.emitter import (
    SCHEMA_VERSION,
    SOURCE,
    TelemetryEmitter,
    emit_event,
    get_emitter,
)
from app.telemetry.repository import TelemetryRecord, TelemetryStorageUnavailable


class FakeRepository:
    """Captures inserted records without connecting to a real database."""

    def __init__(self) -> None:
        self.records: list[TelemetryRecord] = []
        self.insert_count = 0

    def insert_many(self, records: list[TelemetryRecord]) -> int:
        self.records.extend(records)
        self.insert_count += 1
        return len(records)


class TelemetryEmitterTests(unittest.TestCase):
    """TelemetryEmitter builds valid TelemetryRecords and swallows errors."""

    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.emitter = TelemetryEmitter(repository=self.repository)

    def test_emit_api_request_completed_creates_record(self) -> None:
        self.emitter.emit(
            "api_request_completed",
            {"method": "GET", "path": "/api/products", "status_code": 200, "duration_ms": 42.5},
        )

        self.assertEqual(self.repository.insert_count, 1)
        self.assertEqual(len(self.repository.records), 1)
        record = self.repository.records[0]
        self.assertEqual(record.event_type, "api_request_completed")
        self.assertEqual(record.source, SOURCE)
        self.assertEqual(record.schema_version, SCHEMA_VERSION)
        self.assertIsNone(record.session_id)
        self.assertEqual(record.tags["method"], "GET")
        self.assertEqual(record.tags["path"], "/api/products")
        self.assertEqual(record.tags["status_code"], 200)
        self.assertEqual(record.tags["duration_ms"], 42.5)

    def test_emit_unhandled_api_error_creates_record(self) -> None:
        self.emitter.emit(
            "unhandled_api_error",
            {
                "method": "POST",
                "path": "/api/orders",
                "status_code": 500,
                "error_type": "ValueError",
                "error_message": "something went wrong",
            },
        )

        self.assertEqual(self.repository.insert_count, 1)
        record = self.repository.records[0]
        self.assertEqual(record.event_type, "unhandled_api_error")
        self.assertEqual(record.tags["method"], "POST")
        self.assertEqual(record.tags["status_code"], 500)
        self.assertEqual(record.tags["error_type"], "ValueError")

    def test_emit_filters_non_allowlisted_tags(self) -> None:
        self.emitter.emit(
            "api_request_completed",
            {
                "method": "GET",
                "path": "/api/test",
                "status_code": 200,
                "duration_ms": 10.0,
                "secret_internal_field": "must not be stored",
            },
        )

        record = self.repository.records[0]
        self.assertIn("method", record.tags)
        self.assertIn("path", record.tags)
        self.assertNotIn("secret_internal_field", record.tags)

    def test_emit_ignores_storage_unavailable(self) -> None:
        failing = MagicMock()
        failing.insert_many.side_effect = TelemetryStorageUnavailable("no db")
        emitter = TelemetryEmitter(repository=failing)

        # Should not raise — TelemetryStorageUnavailable is caught.
        emitter.emit(
            "api_request_completed",
            {"method": "GET", "path": "/test", "status_code": 200, "duration_ms": 1.0},
        )
        failing.insert_many.assert_called_once()

    def test_emit_ignores_arbitrary_exceptions(self) -> None:
        failing = MagicMock()
        failing.insert_many.side_effect = RuntimeError("unexpected crash")
        emitter = TelemetryEmitter(repository=failing)

        # Should not raise — all exceptions are caught.
        emitter.emit(
            "api_request_completed",
            {"method": "GET", "path": "/test", "status_code": 200, "duration_ms": 1.0},
        )
        failing.insert_many.assert_called_once()

    def test_emit_event_convenience_function(self) -> None:
        fake_repo = FakeRepository()
        with patch("app.telemetry.emitter.get_emitter") as mock_get:
            mock_emitter = TelemetryEmitter(repository=fake_repo)
            mock_get.return_value = mock_emitter

            emit_event(
                "api_request_completed",
                {"method": "GET", "path": "/test", "status_code": 200, "duration_ms": 5.0},
            )

            self.assertEqual(fake_repo.insert_count, 1)

    def test_get_emitter_returns_singleton(self) -> None:
        # Reset the module-level _emitter and verify get_emitter creates one.
        with patch("app.telemetry.emitter._emitter", None):
            e1 = get_emitter()
            e2 = get_emitter()
            self.assertIs(e1, e2)


if __name__ == "__main__":
    unittest.main()
