"""Integration tests for backend telemetry instrumentation.

Covers:
- ``api_request_completed`` emitted by ``TimingMiddleware``
- ``unhandled_api_error`` emitted by the global exception handler
- Loop protection (telemetry endpoint does NOT emit ``api_request_completed``)
"""

from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.telemetry.repository import TelemetryRecord


def _build_emitter_test_app() -> FastAPI:
    """Build a minimal FastAPI app with TimingMiddleware for testing.

    This avoids auth dependencies present on all real routers.
    """
    from app.middleware import TimingMiddleware

    app = FastAPI()
    app.add_middleware(TimingMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _build_crash_test_app() -> FastAPI:
    """Build a minimal app with TimingMiddleware and a crashing endpoint."""
    from app.middleware import TimingMiddleware

    app = FastAPI()
    app.add_middleware(TimingMiddleware)

    @app.get("/crash")
    async def crash_endpoint() -> None:
        raise ValueError("simulated crash for telemetry test")

    @app.exception_handler(Exception)
    async def handler(request, exc) -> JSONResponse:
        from app.telemetry.emitter import emit_event

        try:
            emit_event(
                "unhandled_api_error",
                {
                    "method": request.method or "?",
                    "path": str(request.url.path),
                    "status_code": 500,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:200] if str(exc) else None,
                },
            )
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content={"message": "No se pudo completar la operación. Inténtalo de nuevo."},
        )

    return app


class FakeRepository:
    """Captures emitted records for assertion."""

    def __init__(self) -> None:
        self.records: list[TelemetryRecord] = []

    def insert_many(self, records: list[TelemetryRecord]) -> int:
        self.records.extend(records)
        return len(records)


class TelemetryInstrumentationTests(unittest.TestCase):
    """Verify that backend events are emitted on real HTTP requests."""

    def setUp(self) -> None:
        self.repository = FakeRepository()
        # Patch the TelemetryRepository *inside* the emitter module so that
        # the emitter singleton uses our fake when it is created.
        self.repo_patcher = patch(
            "app.telemetry.emitter.TelemetryRepository",
            return_value=self.repository,
        )
        self.mock_repo_cls = self.repo_patcher.start()
        # Reset the module-level emitter singleton so it is re-created with
        # the patched TelemetryRepository on the next call to get_emitter().
        self.emitter_patcher = patch(
            "app.telemetry.emitter._emitter",
            None,
        )
        self.emitter_patcher.start()

    def tearDown(self) -> None:
        self.emitter_patcher.stop()
        self.repo_patcher.stop()

    def test_api_request_completed_is_emitted_on_success(self) -> None:
        """A normal request emits exactly one api_request_completed event."""
        client = TestClient(_build_emitter_test_app())
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        completed = [r for r in self.repository.records if r.event_type == "api_request_completed"]
        self.assertEqual(
            len(completed),
            1,
            f"Expected 1 api_request_completed, got {len(completed)}; "
            f"all records: {[r.event_type for r in self.repository.records]}",
        )
        record = completed[0]
        self.assertEqual(record.source, "/nexova/api")
        self.assertEqual(record.tags["method"], "GET")
        self.assertEqual(record.tags["path"], "/health")
        self.assertEqual(record.tags["status_code"], 200)
        self.assertIn("duration_ms", record.tags)
        self.assertIsInstance(record.tags["duration_ms"], (int, float))

    def test_telemetry_endpoint_does_not_emit_api_request_completed(self) -> None:
        """Loop protection: the live telemetry endpoint itself must NOT emit."""
        from app.main import app as live_app

        client = TestClient(live_app)
        valid_event = {
            "specversion": "1.0",
            "source": "/nexova/test",
            "id": str(uuid4()),
            "type": "inbound_order_created",
            "time": "2026-11-06T12:00:00Z",
            "datacontenttype": "application/json",
            "data": {"product_id": 1, "product_sku": "TEST", "quantity": 1},
            "sessionId": "test-session",
            "schemaVersion": "1.0.0",
        }
        response = client.post("/api/telemetry/events", json={"events": [valid_event]})

        self.assertEqual(response.status_code, 200)
        completed = [
            r for r in self.repository.records if r.event_type == "api_request_completed"
        ]
        self.assertEqual(
            len(completed),
            0,
            f"Telemetry endpoint should not emit api_request_completed, got {len(completed)}",
        )

    def test_api_request_completed_on_404(self) -> None:
        """Even 404 responses emit api_request_completed."""
        client = TestClient(_build_emitter_test_app())
        response = client.get("/nonexistent-route")

        self.assertEqual(response.status_code, 404)
        completed = [
            r for r in self.repository.records if r.event_type == "api_request_completed"
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].tags["status_code"], 404)

    def test_unhandled_api_error_is_emitted_on_500(self) -> None:
        """An endpoint that crashes triggers the global Exception handler
        and emits unhandled_api_error."""
        client = TestClient(_build_crash_test_app(), raise_server_exceptions=False)
        response = client.get("/crash")

        self.assertEqual(response.status_code, 500)
        unhandled = [
            r for r in self.repository.records if r.event_type == "unhandled_api_error"
        ]
        self.assertEqual(
            len(unhandled),
            1,
            f"Expected 1 unhandled_api_error, got {len(unhandled)}; "
            f"all records: {[r.event_type for r in self.repository.records]}",
        )
        record = unhandled[0]
        self.assertEqual(record.tags["method"], "GET")
        self.assertEqual(record.tags["path"], "/crash")
        self.assertEqual(record.tags["status_code"], 500)
        self.assertEqual(record.tags["error_type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
