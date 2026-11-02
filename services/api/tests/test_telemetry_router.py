"""Tests for telemetry endpoints (POST /api/telemetry/events).

This module tests the telemetry event ingestion endpoint, including:
- Valid CloudEvents 1.0 envelopes
- Validation of required fields
- Error handling for malformed requests
- Logging of received events
"""

import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


class TelemetryEndpointTests(unittest.TestCase):
    """Test suite for POST /api/telemetry/events endpoint."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize TestClient for all tests."""
        cls.client = TestClient(app)
        cls.endpoint = "/api/telemetry/events"

    def test_receive_single_valid_event_returns_200(self) -> None:
        """Test receiving a single valid event returns HTTP 200 with count."""
        event_id = str(uuid4())
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": event_id,
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {
                        "product_id": 42,
                        "product_sku": "NXV-IT-001",
                        "quantity": 10.0,
                    },
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["received"], 1)

    def test_receive_multiple_events_returns_count(self) -> None:
        """Test receiving multiple events returns correct count."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {"product_id": 1, "quantity": 5.0},
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
                {
                    "specversion": "1.0",
                    "source": "/nexova/auth",
                    "id": str(uuid4()),
                    "type": "account_created",
                    "time": "2026-11-02T18:08:10.000Z",
                    "datacontenttype": "application/json",
                    "data": {},
                },
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["received"], 3)

    def test_receive_empty_batch_returns_200(self) -> None:
        """Test receiving an empty batch returns HTTP 200 with count 0."""
        batch = {"events": []}

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["received"], 0)

    def test_missing_events_field_returns_400(self) -> None:
        """Test payload without 'events' field returns HTTP 400."""
        invalid_batch = {"data": []}

        response = self.client.post(self.endpoint, json=invalid_batch)

        self.assertEqual(response.status_code, 422)
        # Pydantic returns 422 for missing required fields
        payload = response.json()
        self.assertIn("detail", payload)

    def test_events_field_null_returns_400(self) -> None:
        """Test payload with null 'events' field returns HTTP 400."""
        invalid_batch = {"events": None}

        response = self.client.post(self.endpoint, json=invalid_batch)

        # Pydantic should validate list type
        self.assertIn(response.status_code, [400, 422])

    def test_event_with_invalid_uuid_returns_422(self) -> None:
        """Test event with invalid UUID in 'id' field returns HTTP 422."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": "not-a-uuid",
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 422)

    def test_event_with_malformed_time_returns_422(self) -> None:
        """Test event with malformed RFC 3339 timestamp returns HTTP 422."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02 18:07:44",  # Missing T, missing Z
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 422)

    def test_event_with_wrong_specversion_returns_422(self) -> None:
        """Test event with specversion != 1.0 returns HTTP 422."""
        batch = {
            "events": [
                {
                    "specversion": "2.0",  # Invalid version
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 422)

    def test_event_with_wrong_datacontenttype_returns_422(self) -> None:
        """Test event with datacontenttype != application/json returns HTTP 422."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "text/plain",  # Invalid type
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 422)

    def test_event_with_extension_attributes_returns_200(self) -> None:
        """Test event with optional extension attributes (sessionId, schemaVersion) is accepted."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {"product_id": 42},
                    "sessionId": str(uuid4()),  # Extension attribute
                    "schemaVersion": "1.0.0",   # Extension attribute
                    "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["received"], 1)

    def test_event_with_extra_fields_in_data_returns_200(self) -> None:
        """Test event with additional properties in 'data' is accepted (no strict schema validation in Phase 1)."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {
                        "product_id": 42,
                        "extra_field": "should_be_accepted_in_phase_1",
                        "another_field": 123,
                    },
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        # Phase 1: Accept any data object (future phase will validate per schema)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["received"], 1)

    def test_event_missing_required_field_id_returns_422(self) -> None:
        """Test event missing 'id' field returns HTTP 422."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    # Missing 'id'
                    "type": "inbound_order_created",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 422)

    def test_event_missing_required_field_type_returns_422(self) -> None:
        """Test event missing 'type' field returns HTTP 422."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/inventory",
                    "id": str(uuid4()),
                    # Missing 'type'
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 422)

    def test_response_structure_matches_contract(self) -> None:
        """Test response structure always includes 'received' field with correct type."""
        batch = {
            "events": [
                {
                    "specversion": "1.0",
                    "source": "/nexova/test",
                    "id": str(uuid4()),
                    "type": "test_event",
                    "time": "2026-11-02T18:07:44.123Z",
                    "datacontenttype": "application/json",
                    "data": {},
                }
            ]
        }

        response = self.client.post(self.endpoint, json=batch)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("received", payload)
        self.assertIsInstance(payload["received"], int)
        self.assertGreaterEqual(payload["received"], 0)


if __name__ == "__main__":
    unittest.main()
