"""Tests for telemetry models (Pydantic validation).

This module tests the TelemetryEvent, TelemetryBatch, and TelemetryResponse
models to ensure CloudEvents 1.0 compliance and proper validation.
"""

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.telemetry.models import TelemetryBatch, TelemetryEvent, TelemetryResponse


class TelemetryEventValidationTests(unittest.TestCase):
    """Test suite for TelemetryEvent model validation."""

    def test_valid_event_parses_successfully(self) -> None:
        """Test a valid CloudEvents 1.0 envelope parses without errors."""
        event_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "application/json",
            "data": {"product_id": 42, "quantity": 10.0},
        }

        event = TelemetryEvent(**event_data)

        self.assertEqual(event.specversion, "1.0")
        self.assertEqual(event.source, "/nexova/inventory")
        self.assertEqual(event.type, "inbound_order_created")
        self.assertIsNotNone(event.id)

    def test_event_with_extension_attributes_parses_successfully(self) -> None:
        """Test event with optional extension attributes."""
        event_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "application/json",
            "data": {},
            "sessionId": str(uuid4()),
            "schemaVersion": "1.0.0",
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
        }

        event = TelemetryEvent(**event_data)

        self.assertIsNotNone(event.sessionId)
        self.assertEqual(event.schemaVersion, "1.0.0")
        self.assertIsNotNone(event.traceparent)

    def test_missing_required_field_raises_validation_error(self) -> None:
        """Test missing required fields raise ValidationError."""
        incomplete_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            # Missing 'id'
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "application/json",
            "data": {},
        }

        with self.assertRaises(ValidationError):
            TelemetryEvent(**incomplete_data)

    def test_invalid_specversion_raises_validation_error(self) -> None:
        """Test specversion != 1.0 raises ValidationError."""
        event_data = {
            "specversion": "2.0",
            "source": "/nexova/inventory",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "application/json",
            "data": {},
        }

        with self.assertRaises(ValidationError):
            TelemetryEvent(**event_data)

    def test_invalid_uuid_in_id_raises_validation_error(self) -> None:
        """Test invalid UUID in 'id' field raises ValidationError."""
        event_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            "id": "not-a-uuid",
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "application/json",
            "data": {},
        }

        with self.assertRaises(ValidationError):
            TelemetryEvent(**event_data)

    def test_malformed_time_raises_validation_error(self) -> None:
        """Test malformed RFC 3339 timestamp raises ValidationError."""
        event_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-02 18:07:44",  # Missing T and Z
            "datacontenttype": "application/json",
            "data": {},
        }

        with self.assertRaises(ValidationError):
            TelemetryEvent(**event_data)

    def test_valid_rfc3339_formats_accepted(self) -> None:
        """Test various valid RFC 3339 formats are accepted."""
        valid_times = [
            "2026-11-02T18:07:44.123Z",
            "2026-11-02T18:07:44Z",
            "2026-11-02T18:07:44+00:00",
            "2026-11-02T18:07:44-05:00",
        ]

        for time_str in valid_times:
            event_data = {
                "specversion": "1.0",
                "source": "/nexova/test",
                "id": str(uuid4()),
                "type": "test_event",
                "time": time_str,
                "datacontenttype": "application/json",
                "data": {},
            }

            event = TelemetryEvent(**event_data)
            self.assertEqual(event.time, time_str)

    def test_wrong_datacontenttype_raises_validation_error(self) -> None:
        """Test datacontenttype != application/json raises ValidationError."""
        event_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "text/plain",
            "data": {},
        }

        with self.assertRaises(ValidationError):
            TelemetryEvent(**event_data)

    def test_data_accepts_any_dict(self) -> None:
        """Test 'data' field accepts any dictionary structure."""
        event_data = {
            "specversion": "1.0",
            "source": "/nexova/inventory",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-02T18:07:44.123Z",
            "datacontenttype": "application/json",
            "data": {
                "simple": "value",
                "nested": {"key": "value"},
                "array": [1, 2, 3],
                "number": 42,
                "bool": True,
                "null": None,
            },
        }

        event = TelemetryEvent(**event_data)

        self.assertIsInstance(event.data, dict)
        self.assertEqual(event.data["simple"], "value")


class TelemetryBatchValidationTests(unittest.TestCase):
    """Test suite for TelemetryBatch model validation."""

    def test_valid_batch_with_single_event_parses(self) -> None:
        """Test valid batch with one event parses successfully."""
        batch_data = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        batch = TelemetryBatch(**batch_data)

        self.assertEqual(len(batch.events), 1)
        self.assertIsInstance(batch.events[0], TelemetryEvent)

    def test_valid_batch_with_multiple_events_parses(self) -> None:
        """Test valid batch with multiple events parses successfully."""
        batch_data = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                },
                {
                    "specversion": "1.0",
                    "source": "/nexova/auth",
                    "id": str(uuid4()),
                    "type": "login_succeeded",
                    "time": "2026-11-02T18:08:00.000Z",
                    "datacontenttype": "application/json",
                    "data": {},
                },
            ]
        }

        batch = TelemetryBatch(**batch_data)

        self.assertEqual(len(batch.events), 2)

    def test_empty_batch_parses_successfully(self) -> None:
        """Test empty batch is valid."""
        batch_data = {"events": []}

        batch = TelemetryBatch(**batch_data)

        self.assertEqual(len(batch.events), 0)

    def test_batch_with_invalid_event_raises_error(self) -> None:
        """Test batch containing invalid event raises ValidationError."""
        batch_data = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": "not-a-uuid",  # Invalid
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        with self.assertRaises(ValidationError):
            TelemetryBatch(**batch_data)

    def test_batch_without_events_field_raises_error(self) -> None:
        """Test batch missing 'events' field raises ValidationError."""
        invalid_batch = {}

        with self.assertRaises(ValidationError):
            TelemetryBatch(**invalid_batch)


class TelemetryResponseValidationTests(unittest.TestCase):
    """Test suite for TelemetryResponse model validation."""

    def test_valid_response_parses_successfully(self) -> None:
        """Test valid response counters parse successfully."""
        response_data = {"received": 3, "stored": 2, "rejected": 1}

        response = TelemetryResponse(**response_data)

        self.assertEqual(response.received, 3)
        self.assertEqual(response.stored, 2)
        self.assertEqual(response.rejected, 1)

    def test_response_with_zero_received_is_valid(self) -> None:
        """Test response with zero counters is valid."""
        response_data = {"received": 0, "stored": 0, "rejected": 0}

        response = TelemetryResponse(**response_data)

        self.assertEqual(response.received, 0)

    def test_response_missing_received_field_raises_error(self) -> None:
        """Test response missing 'received' field raises ValidationError."""
        invalid_response = {}

        with self.assertRaises(ValidationError):
            TelemetryResponse(**invalid_response)

    def test_response_with_negative_received_raises_error(self) -> None:
        """Test response with negative received count raises ValidationError."""
        invalid_response = {"received": -1, "stored": 0, "rejected": 0}

        with self.assertRaises(ValidationError):
            TelemetryResponse(**invalid_response)


if __name__ == "__main__":
    unittest.main()
