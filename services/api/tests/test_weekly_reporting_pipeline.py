"""Focused unit tests for the weekly business-reporting pipeline."""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from prefect.states import Failed


PIPELINE_DIR = Path(__file__).resolve().parents[3] / "data" / "pipelines"
sys.path.insert(0, str(PIPELINE_DIR))

import pipeline  # noqa: E402


WEEK_START = date(2026, 11, 2)


def event(event_id: str, event_type: str, **tags: object) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2026-11-03T12:00:00+00:00",
        "tags": {"office": "Valencia", "programme_id": "programme-a", **tags},
    }


def test_iso_week_bounds_are_utc_and_half_open() -> None:
    start, end = pipeline._iso_week_bounds(WEEK_START)

    assert start == datetime(2026, 11, 2, tzinfo=timezone.utc)
    assert end == start + timedelta(days=7)
    with pytest.raises(ValueError, match="Monday"):
        pipeline._iso_week_bounds(date(2026, 11, 3))


def test_transform_aggregates_and_deduplicates_events() -> None:
    inbound = event(
        "in-1", "inbound_order_created", currency="EUR", quantity=3,
        unit_cost="2.50",
    )
    events = [
        inbound,
        inbound.copy(),
        event("out-1", "outbound_order_created", quantity=1, exit_type="allocation"),
        event(
            "short-1", "stock_threshold_triggered", product_id=3, threshold=2,
            current_stock=1, stock_level="low",
        ),
        event(
            "variance-1", "kit_cost_variance_detected", currency="EUR",
            product_id=8, expected_cost="10", actual_cost="12", variance_percent="20",
        ),
    ]

    result = pipeline.transform_weekly_office_program_performance.fn(events, WEEK_START)

    assert result["records_processed"] == 5
    assert result["records_rejected"] == 0
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["total_material_cost"] == Decimal("7.50")
    assert row["kits_delivered_count"] == 1
    assert row["shortage_events_count"] == 1
    assert row["cost_variance_events_count"] == 1


def test_transform_rejects_bad_events_and_nonfinite_numbers() -> None:
    events = [
        event("bad-cost", "inbound_order_created", currency="EUR", quantity="NaN", unit_cost=2),
        event("wrong-week", "outbound_order_created", quantity=1, exit_type="allocation")
        | {"timestamp": "2026-11-09T00:00:00+00:00"},
        event("unsupported", "login_succeeded", user_uuid="user"),
    ]

    result = pipeline.transform_weekly_office_program_performance.fn(events, WEEK_START)

    assert result == {"rows": [], "records_processed": 3, "records_rejected": 3}


def test_transform_rejects_conflicting_duplicate_event_ids() -> None:
    first = event("same-id", "outbound_order_created", quantity=1, exit_type="allocation")
    conflicting = event("same-id", "outbound_order_created", quantity=2, exit_type="allocation")

    with pytest.raises(pipeline.EventValidationError, match="Conflicting duplicate"):
        pipeline.transform_weekly_office_program_performance.fn([first, conflicting], WEEK_START)


def test_transform_cache_uses_exact_inputs_and_one_hour_ttl() -> None:
    events = [event("out-1", "outbound_order_created", quantity=1, exit_type="allocation")]
    changed_events = [event("out-2", "outbound_order_created", quantity=1, exit_type="allocation")]

    key = pipeline._transform_cache_key(None, {"week_start": WEEK_START, "events": events})
    reordered_key = pipeline._transform_cache_key(
        None, {"events": events, "week_start": WEEK_START},
    )
    changed_key = pipeline._transform_cache_key(
        None, {"week_start": WEEK_START, "events": changed_events},
    )

    assert key == reordered_key
    assert key != changed_key
    assert pipeline.transform_weekly_office_program_performance.cache_expiration == timedelta(hours=1)
    assert pipeline.extract_telemetry_events.cache_key_fn is None


@pytest.mark.parametrize(
    ("exception", "should_retry"),
    [
        (psycopg.OperationalError("network unavailable"), True),
        (psycopg.InterfaceError("connection closed"), True),
        (TimeoutError("timeout"), True),
        (ConnectionError("offline"), True),
        (pipeline.EventValidationError("invalid event"), False),
        (ValueError("bad date"), False),
        (RuntimeError("SQL logic error"), False),
    ],
)
def test_retry_policy_only_retries_transient_errors(
    exception: Exception, should_retry: bool,
) -> None:
    assert pipeline._transient_retry(None, None, Failed(data=exception)) is should_retry


def test_load_empty_rows_needs_no_database() -> None:
    with patch.object(pipeline.psycopg, "connect") as connect:
        assert pipeline.load_weekly_office_program_performance.fn([]) == {
            "records_inserted": 0,
            "records_updated": 0,
        }
    connect.assert_not_called()


def test_load_upserts_all_rows_in_one_transaction() -> None:
    cursor = MagicMock()
    cursor.fetchone.side_effect = [(True,), (False,)]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.__enter__.return_value = connection
    rows = [
        {
            "office": "Valencia", "programme_id": "programme-a", "week_start": WEEK_START,
            "total_material_cost": Decimal("1.00"), "kits_delivered_count": 0,
            "shortage_events_count": 0, "cost_variance_events_count": 0, "currency": "EUR",
        },
        {
            "office": "Miami", "programme_id": "programme-b", "week_start": WEEK_START,
            "total_material_cost": Decimal("0.00"), "kits_delivered_count": 1,
            "shortage_events_count": 0, "cost_variance_events_count": 0, "currency": "USD",
        },
    ]

    with (
        patch.dict("os.environ", {pipeline.REPORTING_DATABASE_URL_ENV: "postgresql://reporting/test"}),
        patch.object(pipeline.psycopg, "connect", return_value=connection) as connect,
    ):
        result = pipeline.load_weekly_office_program_performance.fn(rows)

    assert result == {"records_inserted": 1, "records_updated": 1}
    connect.assert_called_once_with("postgresql://reporting/test", connect_timeout=10)
    assert cursor.execute.call_count == 2
    connection.commit.assert_called_once_with()


class FakeTask:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result_value = result
        self.error = error

    def __call__(self, *args: object, return_state: bool = False, **kwargs: object) -> object:
        from prefect.states import Completed

        state = Failed(data=self.error) if self.error is not None else Completed(data=self.result_value)
        if return_state:
            return state
        return state.result(raise_on_failure=True)


def test_flow_marks_critical_failure_as_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    finished: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(pipeline, "_create_run", lambda *_: "run-1")
    monkeypatch.setattr(pipeline, "_finish_run", lambda *args, **kwargs: finished.append((args, kwargs)))
    monkeypatch.setattr(pipeline, "get_run_logger", lambda: MagicMock())
    monkeypatch.setattr(
        pipeline, "extract_telemetry_events",
        FakeTask(error=psycopg.OperationalError("secret database host")),
    )

    with pytest.raises(Exception):
        pipeline.weekly_office_program_performance_flow.fn(WEEK_START)

    assert len(finished) == 1
    assert finished[0][0][:2] == ("run-1", "failed")
    assert finished[0][1]["error_message"] == "OperationalError: pipeline execution failed"
    assert "secret database host" not in finished[0][1]["error_message"]


def test_flow_treats_snapshot_failure_as_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    finished: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(pipeline, "_create_run", lambda *_: "run-2")
    monkeypatch.setattr(pipeline, "_finish_run", lambda *args, **kwargs: finished.append((args, kwargs)))
    monkeypatch.setattr(pipeline, "get_run_logger", lambda: MagicMock())
    monkeypatch.setattr(pipeline, "extract_telemetry_events", FakeTask(result=[]))
    monkeypatch.setattr(
        pipeline,
        "transform_weekly_office_program_performance",
        FakeTask(result={"rows": [], "records_processed": 0, "records_rejected": 0}),
    )
    monkeypatch.setattr(
        pipeline,
        "load_weekly_office_program_performance",
        FakeTask(result={"records_inserted": 0, "records_updated": 0}),
    )
    monkeypatch.setattr(
        pipeline, "capture_optional_snapshot", FakeTask(error=OSError("disk full")),
    )

    result = pipeline.weekly_office_program_performance_flow.fn(WEEK_START)

    assert result == {
        "run_id": "run-2",
        "status": "completed",
        "snapshot_error": "Optional reporting snapshot failed",
    }
    assert len(finished) == 1
    assert finished[0][0][:2] == ("run-2", "completed")
    assert finished[0][1]["error_message"] == "Optional reporting snapshot failed"
