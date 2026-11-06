"""Backend telemetry emitter for server-side events.

Emits ``api_request_completed`` and ``unhandled_api_error`` events directly
from the backend process using ``TelemetryRepository``. Failures are logged
but never raised, so telemetry cannot break the request flow.

Usage::

    from app.telemetry.emitter import emit_event

    emit_event("api_request_completed", {"method": "GET", "path": "/api/products", ...})
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.telemetry.repository import (
    TelemetryRecord,
    TelemetryRepository,
    TelemetryStorageUnavailable,
)
from app.telemetry.tags import filter_tags

logger = logging.getLogger(__name__)

SOURCE = "/nexova/api"
SCHEMA_VERSION = "1.0.0"

_emitter: TelemetryEmitter | None = None


def _rfc3339_now() -> str:
    """Return the current UTC time as an RFC 3339 / ISO 8601 string."""
    now = datetime.now(timezone.utc)
    # e.g. 2026-11-06T12:34:56.123456Z
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond:06d}Z"


class TelemetryEmitter:
    """Builds and persists backend telemetry events.

    Uses ``TelemetryRepository`` for persistence. Every public method
    catches all exceptions so that telemetry never disrupts the caller.
    """

    def __init__(self, repository: TelemetryRepository | None = None) -> None:
        self._repository = repository or TelemetryRepository()

    def _build_record(self, event_type: str, tags: dict[str, Any]) -> TelemetryRecord:
        """Construct a TelemetryRecord with allowlist-filtered tags."""
        return TelemetryRecord(
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp=_rfc3339_now(),
            source=SOURCE,
            session_id=None,
            schema_version=SCHEMA_VERSION,
            tags=filter_tags(event_type, tags),
        )

    def emit(self, event_type: str, tags: dict[str, Any]) -> None:
        """Persist one telemetry event.

        All exceptions are caught and logged so that a failure to store
        telemetry never propagates to the caller.
        """
        try:
            record = self._build_record(event_type, tags)
            self._repository.insert_many([record])
            logger.debug(
                "telemetry.emitted event_type=%s",
                event_type,
            )
        except TelemetryStorageUnavailable:
            logger.warning(
                "telemetry.emitter.skipped event_type=%s reason=storage_unavailable",
                event_type,
            )
        except Exception:
            logger.exception(
                "telemetry.emitter.failed event_type=%s",
                event_type,
            )


def get_emitter() -> TelemetryEmitter:
    """Return the module-level singleton emitter."""
    global _emitter
    if _emitter is None:
        _emitter = TelemetryEmitter()
    return _emitter


def emit_event(event_type: str, tags: dict[str, Any]) -> None:
    """Convenience helper — emit one event via the module-level emitter."""
    get_emitter().emit(event_type, tags)
