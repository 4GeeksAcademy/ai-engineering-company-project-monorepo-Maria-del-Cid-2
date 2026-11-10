"""Prefect deployment adapter for manual reporting runs."""

from __future__ import annotations

import os
from datetime import date
from uuid import UUID

DEPLOYMENT_ENV = "REPORTING_PREFECT_DEPLOYMENT"
DEFAULT_DEPLOYMENT = "weekly_office_program_performance/weekly-office-program-performance"


class ReportingOrchestrationUnavailable(RuntimeError):
    """Raised when a Prefect deployment cannot be requested."""


def trigger_weekly_office_program_performance_flow(week_start: date) -> UUID:
    """Request a Prefect deployment run; never executes ETL in the API process."""
    deployment = os.environ.get(DEPLOYMENT_ENV, DEFAULT_DEPLOYMENT).strip()
    if not deployment:
        raise ReportingOrchestrationUnavailable("Reporting Prefect deployment is not configured")
    try:
        from prefect.deployments import run_deployment

        flow_run = run_deployment(
            deployment,
            parameters={"week_start": week_start, "trigger_type": "manual"},
            timeout=0,
        )
    except Exception as exc:
        raise ReportingOrchestrationUnavailable("Unable to request reporting flow") from exc
    run_id = getattr(flow_run, "id", None)
    if run_id is None:
        raise ReportingOrchestrationUnavailable("Prefect did not return a flow run ID")
    return UUID(str(run_id))
