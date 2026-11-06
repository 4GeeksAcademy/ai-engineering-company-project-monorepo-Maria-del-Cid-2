"""Append-only telemetry ingestion endpoint — ``/api/telemetry/events``."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import ValidationError

from app.telemetry.models import TelemetryEvent, TelemetryResponse
from app.telemetry.repository import (
    TelemetryRecord,
    TelemetryRepository,
    TelemetryStorageUnavailable,
)
from app.telemetry.tags import filter_tags
from app.telemetry.report import ReportData, build_report

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
logger = logging.getLogger(__name__)


def get_telemetry_repository() -> TelemetryRepository:
    """Build a lazy writer; it connects only when valid rows need insertion."""

    return TelemetryRepository()


@router.post("/events", response_model=TelemetryResponse, status_code=status.HTTP_200_OK)
def receive_events(payload: Any = Body(...)) -> TelemetryResponse:
    """Validate each raw event and persist valid rows in a single bulk insert."""

    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid payload: "events" must be an array',
        )

    raw_events = payload["events"]
    valid_records: list[TelemetryRecord] = []
    rejected = 0

    for raw_event in raw_events:
        try:
            event = TelemetryEvent.model_validate(raw_event)
        except ValidationError:
            rejected += 1
            continue

        valid_records.append(
            TelemetryRecord(
                event_id=event.id,
                event_type=event.type,
                timestamp=event.time,
                source=event.source,
                session_id=event.sessionId,
                schema_version=event.schemaVersion,
                tags=filter_tags(event.type, event.data),
            )
        )

    stored = 0
    if valid_records:
        try:
            stored = get_telemetry_repository().insert_many(valid_records)
        except TelemetryStorageUnavailable as exc:
            logger.error("telemetry.persistence_unavailable exception_type=%s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telemetry storage is temporarily unavailable",
            ) from exc

    logger.info(
        "telemetry.received count=%d stored=%d rejected=%d",
        len(raw_events),
        stored,
        rejected,
    )
    return TelemetryResponse(received=len(raw_events), stored=stored, rejected=rejected)


@router.get("/report", response_model=ReportData)
def get_report(
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
) -> ReportData:
    """Return the A1–A11 telemetry analytics report as JSON."""
    try:
        return build_report(start=start, end=end, limit=limit)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("telemetry.report_failed exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build telemetry report",
        ) from exc
