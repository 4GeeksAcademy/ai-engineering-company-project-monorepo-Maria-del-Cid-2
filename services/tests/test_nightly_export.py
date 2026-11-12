"""Focused tests for the nightly scheduler entry point."""

from __future__ import annotations

import csv
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest

SERVICES_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICES_DIR))

import nightly_export  # noqa: E402


class FakeLease:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = False

    def complete(self) -> None:
        assert not self.closed
        self.events.append("complete")
        self.closed = True

    def fail(self, message: str) -> None:
        assert not self.closed
        self.events.append(f"fail:{message}")
        self.closed = True


class FakeRunner:
    def __init__(self, lease: FakeLease | None) -> None:
        self.lease = lease
        self.acquired: tuple[str, date] | None = None

    def acquire(self, job_name: str, target_date: date) -> FakeLease | None:
        self.acquired = (job_name, target_date)
        return self.lease


def test_date_helpers_use_utc_yesterday_and_iso_monday() -> None:
    now = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)

    assert nightly_export.default_target_date(now) == date(2025, 12, 31)
    assert nightly_export.iso_week_start(date(2026, 1, 1)) == date(2025, 12, 29)
    assert nightly_export.parse_target_date("2026-01-01") == date(2026, 1, 1)
    with pytest.raises(nightly_export.argparse.ArgumentTypeError, match="YYYY-MM-DD"):
        nightly_export.parse_target_date("01-01-2026")


def test_target_date_environment_and_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_DATE", "2026-11-10")

    assert nightly_export.resolve_target_date(None) == date(2026, 11, 10)
    assert nightly_export.resolve_target_date(date(2026, 11, 11)) == date(2026, 11, 11)


def test_target_date_environment_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_DATE", "11/10/2026")

    with pytest.raises(ValueError, match="invalid TARGET_DATE.*YYYY-MM-DD"):
        nightly_export.resolve_target_date(None)


def test_target_date_environment_absent_uses_utc_yesterday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGET_DATE", raising=False)
    expected = date(2026, 11, 11)
    monkeypatch.setattr(nightly_export, "default_target_date", lambda: expected)

    assert nightly_export.resolve_target_date(None) == expected


def test_default_target_date_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        nightly_export.default_target_date(datetime(2026, 1, 1))


def test_pipeline_command_passes_week_start_and_scheduled_trigger() -> None:
    command = nightly_export.pipeline_command(date(2025, 12, 29))

    assert command[0] == sys.executable
    assert command[1] == str(nightly_export.PIPELINE_SCRIPT)
    assert command[2:] == ["--week-start", "2025-12-29", "--trigger-type", "scheduled"]


def test_success_keeps_lease_open_through_audit_and_child_process(caplog: pytest.LogCaptureFixture) -> None:
    events: list[str] = []
    lease = FakeLease(events)
    runner = FakeRunner(lease)
    target = date(2026, 11, 11)

    def audit_exporter(actual_target: date) -> Path:
        assert actual_target == target
        assert not lease.closed
        events.append("audit")
        return Path("audit.csv")

    def process_runner(command: list[str], **kwargs: Any) -> CompletedProcess[str]:
        assert not lease.closed
        assert command[command.index("--week-start") + 1] == "2026-11-09"
        assert kwargs == {
            "cwd": nightly_export.PROJECT_ROOT,
            "check": False,
            "text": True,
            "capture_output": True,
        }
        events.append("subprocess")
        return CompletedProcess(command, 0, stdout="ok", stderr="")

    with caplog.at_level(logging.INFO, logger="nightly_export"):
        result = nightly_export.run_nightly_export(
            target,
            runner=runner,  # type: ignore[arg-type]
            process_runner=process_runner,
            audit_exporter=audit_exporter,
        )

    assert result == 0
    assert runner.acquired == ("nightly_export", target)
    assert events == ["audit", "subprocess", "complete"]
    assert lease.closed
    assert [record.status for record in caplog.records] == [
        "starting",
        "audit_exported",
        "pipeline_started",
        "completed",
    ]
    for record in caplog.records:
        assert record.job_name == "nightly_export"
        assert record.target_date == target.isoformat()


def test_pipeline_failure_marks_lease_failed_after_child_exits() -> None:
    events: list[str] = []
    lease = FakeLease(events)
    runner = FakeRunner(lease)
    target = date(2026, 11, 11)

    def process_runner(command: list[str], **_kwargs: Any) -> CompletedProcess[str]:
        assert not lease.closed
        events.append("subprocess")
        return CompletedProcess(command, 2, stdout="", stderr="pipeline error")

    with pytest.raises(RuntimeError, match="pipeline error"):
        nightly_export.run_nightly_export(
            target,
            runner=runner,  # type: ignore[arg-type]
            process_runner=process_runner,
            audit_exporter=lambda _target: Path("audit.csv"),
        )

    assert events[0] == "subprocess"
    assert events[1].startswith("fail:RuntimeError: pipeline subprocess exited with status 2")
    assert lease.closed


def test_audit_failure_marks_job_failed_without_launching_pipeline() -> None:
    events: list[str] = []
    lease = FakeLease(events)

    def unexpected_process(*_args: Any, **_kwargs: Any) -> CompletedProcess[str]:
        pytest.fail("pipeline should not start if the audit backup fails")

    with pytest.raises(OSError, match="disk full"):
        nightly_export.run_nightly_export(
            date(2026, 11, 11),
            runner=FakeRunner(lease),  # type: ignore[arg-type]
            process_runner=unexpected_process,
            audit_exporter=lambda _target: (_ for _ in ()).throw(OSError("disk full")),
        )

    assert events == ["fail:OSError: disk full"]
    assert lease.closed


def test_skip_when_runner_does_not_grant_lease() -> None:
    called = False

    def unexpected_audit(_target: date) -> Path:
        nonlocal called
        called = True
        return Path("unused.csv")

    result = nightly_export.run_nightly_export(
        date(2026, 11, 11),
        runner=FakeRunner(None),  # type: ignore[arg-type]
        audit_exporter=unexpected_audit,
    )

    assert result == 0
    assert not called


def test_skip_log_has_required_context(caplog: pytest.LogCaptureFixture) -> None:
    target = date(2026, 11, 11)
    with caplog.at_level(logging.INFO, logger="nightly_export"):
        nightly_export.run_nightly_export(target, runner=FakeRunner(None))  # type: ignore[arg-type]

    record = caplog.records[-1]
    assert record.status == "skipped"
    assert record.job_name == "nightly_export"
    assert record.target_date == target.isoformat()


def test_csv_export_writes_header_and_serializes_tags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Cursor:
        def __enter__(self) -> "Cursor":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, query: str, params: tuple[object, ...]) -> None:
            assert "FROM public.telemetry_events" in query
            assert params[0].isoformat() == "2026-11-11T00:00:00+00:00"
            assert params[1].isoformat() == "2026-11-12T00:00:00+00:00"
            self.rows = [("event-1", "inbound_order_created", datetime(2026, 11, 11, tzinfo=timezone.utc), {"office": "Valencia"})]

        def fetchall(self) -> list[tuple[object, ...]]:
            return self.rows

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def cursor(self) -> Cursor:
            return Cursor()

    monkeypatch.setenv("TELEMETRY_DATABASE_URL", "postgresql://test")
    monkeypatch.setattr(nightly_export.psycopg, "connect", lambda *_args, **_kwargs: Connection())

    path = nightly_export.export_daily_audit_csv(date(2026, 11, 11), tmp_path)

    assert path.name == "telemetry-events-2026-11-11.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "event_id": "event-1",
            "event_type": "inbound_order_created",
            "timestamp": "2026-11-11T00:00:00+00:00",
            "tags": '{"office":"Valencia"}',
        }
    ]