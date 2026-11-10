"""HTTP contract tests for weekly business reporting endpoints."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.main import app
from app.reporting.router import get_reporting_repository
from app.reporting.repository import ReportingStorageUnavailable
from app.reporting.trigger import ReportingOrchestrationUnavailable


RUN = {
    "id": uuid4(),
    "pipeline_name": "weekly_office_program_performance",
    "week_start": date(2026, 11, 2),
    "status": "completed",
    "started_at": datetime(2026, 11, 9, tzinfo=timezone.utc),
    "finished_at": datetime(2026, 11, 9, 0, 1, tzinfo=timezone.utc),
    "records_processed": 4,
    "records_inserted": 1,
    "records_updated": 0,
    "records_rejected": 0,
    "error_message": None,
    "trigger_type": "manual",
}
ROW = {
    "office": "Valencia",
    "programme_id": "prog-1",
    "week_start": date(2026, 11, 2),
    "total_material_cost": Decimal("12.50"),
    "kits_delivered_count": 1,
    "shortage_events_count": 0,
    "cost_variance_events_count": 0,
    "currency": "EUR",
    "computed_at": datetime(2026, 11, 9, tzinfo=timezone.utc),
}


def user(role: UserRole = UserRole.ADMIN) -> User:
    return User(
        id=1,
        email="reporting@example.test",
        hashed_password="not-returned",
        role=role,
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestReportingAPI:
    def setup_method(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: user()

    def teardown_method(self) -> None:
        app.dependency_overrides.clear()

    def test_endpoints_require_authentication(self) -> None:
        app.dependency_overrides.clear()
        response = self.client.get("/api/reporting/pipeline-runs/latest")
        assert response.status_code == 401

    def test_latest_run_and_empty_history(self) -> None:
        repository = SimpleNamespace(latest_pipeline_run=lambda: RUN)
        app.dependency_overrides[get_reporting_repository] = lambda: repository
        response = self.client.get("/api/reporting/pipeline-runs/latest")
        assert response.status_code == 200
        assert response.json()["pipeline_name"] == "weekly_office_program_performance"
        repository.latest_pipeline_run = lambda: None
        assert self.client.get("/api/reporting/pipeline-runs/latest").status_code == 404

    def test_latest_run_storage_error_is_sanitized(self) -> None:
        def fail():
            raise ReportingStorageUnavailable("secret url")

        app.dependency_overrides[get_reporting_repository] = lambda: SimpleNamespace(latest_pipeline_run=fail)
        response = self.client.get("/api/reporting/pipeline-runs/latest")
        assert response.status_code == 503
        assert "secret" not in response.text

    def test_performance_filters_and_monday_validation(self) -> None:
        calls = []

        def list_rows(**kwargs):
            calls.append(kwargs)
            return [ROW]

        app.dependency_overrides[get_reporting_repository] = lambda: SimpleNamespace(weekly_performance=list_rows)
        response = self.client.get(
            "/api/reporting/weekly-office-program-performance?week_start=2026-11-02&office=Valencia"
        )
        assert response.status_code == 200
        assert response.json()[0]["currency"] == "EUR"
        assert calls[0]["office"] == "Valencia"
        assert self.client.get(
            "/api/reporting/weekly-office-program-performance?week_start=2026-11-03"
        ).status_code == 422

    def test_run_trigger_admin_only_and_validates_iso_week(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: user(UserRole.USER)
        assert self.client.post("/api/reporting/pipeline-runs", json={}).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: user(UserRole.ADMIN)
        assert self.client.post(
            "/api/reporting/pipeline-runs", json={"week_start": "2026-11-03"}
        ).status_code == 422
        expected_id = uuid4()
        with patch(
            "app.reporting.router.trigger_weekly_office_program_performance_flow",
            return_value=expected_id,
        ) as trigger:
            response = self.client.post(
                "/api/reporting/pipeline-runs", json={"week_start": "2026-11-02"}
            )
        assert response.status_code == 202
        assert response.json()["run_id"] == str(expected_id)
        trigger.assert_called_once_with(date(2026, 11, 2))

    def test_trigger_failure_is_sanitized(self) -> None:
        with patch(
            "app.reporting.router.trigger_weekly_office_program_performance_flow",
            side_effect=ReportingOrchestrationUnavailable("private deployment details"),
        ):
            response = self.client.post("/api/reporting/pipeline-runs", json={})
        assert response.status_code == 503
        assert "private" not in response.text
