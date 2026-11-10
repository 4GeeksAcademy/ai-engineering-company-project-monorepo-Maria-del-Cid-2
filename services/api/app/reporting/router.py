"""Authenticated endpoints for weekly business-reporting runs and results."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.reporting.repository import ReportingRepository, ReportingStorageUnavailable
from app.reporting.schemas import (
    PipelineRunAccepted,
    PipelineRunRequest,
    PipelineRunResponse,
    WeeklyPerformanceResponse,
)
from app.reporting.trigger import (
    ReportingOrchestrationUnavailable,
    trigger_weekly_office_program_performance_flow,
)

router = APIRouter(
    prefix="/api/reporting",
    tags=["reporting"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)


def get_reporting_repository() -> ReportingRepository:
    return ReportingRepository()


def _most_recent_closed_week(today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday() + 7)


@router.get("/pipeline-runs/latest", response_model=PipelineRunResponse)
def get_latest_pipeline_run(
    repository: ReportingRepository = Depends(get_reporting_repository),
) -> PipelineRunResponse:
    try:
        run = repository.latest_pipeline_run()
    except ReportingStorageUnavailable as exc:
        logger.error("reporting.storage_unavailable exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reporting storage is temporarily unavailable",
        ) from exc
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pipeline runs found")
    return PipelineRunResponse.model_validate(run)


@router.post(
    "/pipeline-runs",
    response_model=PipelineRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_pipeline_run(
    payload: PipelineRunRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> PipelineRunAccepted:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator permission required.")
    requested_week = payload.week_start if payload is not None else None
    week_start = requested_week or _most_recent_closed_week()
    try:
        run_id = trigger_weekly_office_program_performance_flow(week_start)
    except ReportingOrchestrationUnavailable as exc:
        logger.error("reporting.orchestration_unavailable exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reporting pipeline is temporarily unavailable",
        ) from exc
    return PipelineRunAccepted(
        run_id=run_id,
        pipeline_name="weekly_office_program_performance",
        week_start=week_start,
    )


@router.get("/weekly-office-program-performance", response_model=list[WeeklyPerformanceResponse])
def get_weekly_office_program_performance(
    week_start: date | None = None,
    office: Literal["Valencia", "Miami"] | None = None,
    programme_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=1000),
    repository: ReportingRepository = Depends(get_reporting_repository),
) -> list[WeeklyPerformanceResponse]:
    if week_start is not None and week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday (ISO week start)")
    try:
        rows = repository.weekly_performance(
            week_start=week_start,
            office=office,
            programme_id=programme_id,
            limit=limit,
        )
    except ReportingStorageUnavailable as exc:
        logger.error("reporting.storage_unavailable exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reporting storage is temporarily unavailable",
        ) from exc
    return [WeeklyPerformanceResponse.model_validate(row) for row in rows]
