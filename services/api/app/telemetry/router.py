"""Telemetry HTTP endpoints — /api/telemetry.

This router receives telemetry events from the frontend and backend clients.
Events are validated against CloudEvents 1.0 specification and optional
extension attributes (sessionId, schemaVersion).

Currently, this is a stub that logs events and returns HTTP 200.
In a future phase, events will be persisted to PostgreSQL or a message queue.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.telemetry.models import TelemetryBatch, TelemetryEvent, TelemetryResponse

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


@router.post("/events", response_model=TelemetryResponse, status_code=status.HTTP_200_OK)
def receive_events(batch: TelemetryBatch) -> TelemetryResponse:
    """Receive a batch of telemetry events.

    Accepts a JSON payload with the following structure:

    ```json
    {
      "events": [
        {
          "specversion": "1.0",
          "source": "/nexova/inventory",
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "type": "inbound_order_created",
          "time": "2026-11-02T18:07:44.123Z",
          "datacontenttype": "application/json",
          "data": { ... },
          "sessionId": "optional",
          "schemaVersion": "optional"
        },
        ...
      ]
    }
    ```

    **Validation:**
    - Each event must be a valid CloudEvents 1.0 envelope.
    - `id` must be a UUID.
    - `time` must be RFC 3339 formatted.
    - `data` is validated per schema (allowlist of properties).

    **Response:**
    - HTTP 200: All events received and queued. Response includes count.
    - HTTP 400: Payload structure is invalid (e.g., missing "events" field).
    - HTTP 422: Event validation failed (e.g., invalid UUID, malformed time).

    **Current behavior (Phase 1):**
    - This is a stub endpoint. Events are logged but NOT persisted.
    - Logging includes:
      - Total count of events received.
      - List of event types.
    - Future phases will add persistence (PostgreSQL, message queue, etc.)

    **Idempotency:**
    - Event ID (`id` field) uniquely identifies each event.
    - In a future phase, duplicate event IDs will be detected and skipped.
    - Clients should generate UUIDs, not rely on the backend for deduplication.

    **Privacy:**
    - Events must not include Authorization headers, API keys, or sensitive data.
    - PII is excluded (names, emails, IP addresses).
    - User identification is via UUID (seudonimization).

    **Extension attributes:**
    - `sessionId`: Optional session identifier for grouping events.
    - `schemaVersion`: Optional schema version for evolution tracking.
    """
    # Validate that events array is not null
    if batch.events is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid payload: "events" field must not be null',
        )

    # Accept empty batch (no error)
    event_count = len(batch.events)

    # Log total count
    logger.info("telemetry.received count=%d", event_count)

    # Log event types (with counts for repeated types)
    if event_count > 0:
        from collections import Counter

        event_types = [event.type for event in batch.events]
        type_counts = Counter(event_types)
        type_str = " ".join(
            [f"{type_}(x{count})" if count > 1 else type_ 
             for type_, count in sorted(type_counts.items())]
        )
        logger.info("telemetry.event_types %s", type_str)

    # Return success response
    return TelemetryResponse(received=event_count)
