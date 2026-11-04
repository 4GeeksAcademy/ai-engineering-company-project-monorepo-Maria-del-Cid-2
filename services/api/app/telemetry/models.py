"""Pydantic models for telemetry events (CloudEvents 1.0 envelope).

This module defines the contract for telemetry events received by the
POST /api/telemetry/events endpoint. Each event follows CloudEvents 1.0
specification with optional extension attributes (sessionId, schemaVersion).
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class TelemetryEvent(BaseModel):
    """CloudEvents 1.0 envelope with optional extension attributes.
    
    Attributes:
        specversion: CloudEvents version (must be "1.0")
        source: Origin of the event (e.g., "/nexova/inventory", "/nexova/auth")
        id: Unique event identifier (UUID, also serves as idempotency key)
        type: Event type from the approved catalog
        time: RFC 3339 timestamp (ISO 8601)
        datacontenttype: MIME type of data payload (default "application/json")
        data: Event-specific payload (must be dict, validated per schema)
        traceparent: Optional W3C Trace Context header (max 55 chars)
        sessionId: Optional extension attribute for session tracking
        schemaVersion: Optional extension attribute for schema versioning
    """

    specversion: str = Field(
        default="1.0",
        description="CloudEvents specification version",
        pattern="^1\\.0$",
    )
    source: str = Field(
        ...,
        description="Event origin (URI reference)",
        min_length=1,
        max_length=255,
    )
    id: str = Field(
        ...,
        description="Unique event identifier (UUID format)",
        min_length=36,
        max_length=36,
    )
    type: str = Field(
        ...,
        description="Event type from approved catalog",
        min_length=1,
        max_length=100,
    )
    time: str = Field(
        ...,
        description="RFC 3339 timestamp when event occurred",
    )
    datacontenttype: str = Field(
        default="application/json",
        description="Media type of data payload",
        max_length=50,
    )
    data: dict[str, Any] = Field(
        ...,
        description="Event-specific payload (properties defined per schema)",
    )
    traceparent: Optional[str] = Field(
        default=None,
        description="W3C Trace Context parent span ID",
        max_length=55,
    )
    
    # CloudEvents extension attributes (optional)
    sessionId: Optional[str] = Field(
        default=None,
        description="Session identifier (extension attribute)",
        max_length=100,
    )
    schemaVersion: Optional[str] = Field(
        default=None,
        description="Schema version (extension attribute)",
        max_length=20,
    )

    @field_validator("id")
    @classmethod
    def validate_id_is_uuid(cls, v: str) -> str:
        """Ensure id is a valid UUID format."""
        try:
            # Validate UUID format (basic check for RFC 4122)
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError("id must be a valid UUID")
        return v

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Ensure time is in RFC 3339 / ISO 8601 format.
        
        Accepts formats like:
        - 2026-11-02T18:07:44.123Z
        - 2026-11-02T18:07:44Z
        - 2026-11-02T18:07:44+00:00
        """
        # Basic RFC 3339 validation: must contain T and Z or +/- offset
        if "T" not in v or (not v.endswith("Z") and "+" not in v and "-" not in v.split("T")[1]):
            raise ValueError(
                "time must be in RFC 3339 format (e.g., 2026-11-02T18:07:44Z)"
            )
        return v

    @field_validator("specversion")
    @classmethod
    def validate_specversion(cls, v: str) -> str:
        """Ensure specversion is exactly "1.0"."""
        if v != "1.0":
            raise ValueError('specversion must be "1.0"')
        return v

    @field_validator("datacontenttype")
    @classmethod
    def validate_datacontenttype(cls, v: str) -> str:
        """Ensure datacontenttype is application/json."""
        if v != "application/json":
            raise ValueError('datacontenttype must be "application/json"')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "specversion": "1.0",
                "source": "/nexova/inventory",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "type": "inbound_order_created",
                "time": "2026-11-02T18:07:44.123Z",
                "datacontenttype": "application/json",
                "data": {
                    "product_id": 42,
                    "product_sku": "NXV-IT-001",
                    "quantity": 10.0,
                },
                "traceparent": None,
                "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "schemaVersion": "1.0.0",
            }
        }
    )


class TelemetryBatch(BaseModel):
    """Batch of telemetry events.
    
    The payload sent by the frontend or backend client containing
    one or more events to be ingested.
    
    Attributes:
        events: Array of TelemetryEvent objects (required, at least empty list allowed)
    """

    events: list[TelemetryEvent] = Field(
        ...,
        description="Array of telemetry events",
    )

    @field_validator("events")
    @classmethod
    def validate_events_is_list(cls, v: list) -> list:
        """Ensure events is a list (never null or string)."""
        if not isinstance(v, list):
            raise ValueError("events must be a list")
        return v


class TelemetryResponse(BaseModel):
    """Response from POST /api/telemetry/events.
    
    Attributes:
        received: Total number of events received in the batch
        stored: Number of valid events inserted in telemetry_events
        rejected: Number of events rejected by TelemetryEvent validation
    """

    received: int = Field(
        ...,
        description="Number of events received",
        ge=0,
    )
    stored: int = Field(
        ...,
        description="Number of events stored successfully",
        ge=0,
    )
    rejected: int = Field(
        ...,
        description="Number of events rejected by validation",
        ge=0,
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "received": 3,
                "stored": 2,
                "rejected": 1,
            }
        }
    )
