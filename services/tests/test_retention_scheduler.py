"""Tests for the independent UTC retention scheduler."""

from __future__ import annotations

import sys
from datetime import datetime, time, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
sys.path.insert(0, str(SERVICES_DIR))

import retention_scheduler  # noqa: E402


def test_default_schedule_is_0300_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETENTION_SCHEDULE_UTC", raising=False)
    assert retention_scheduler.configured_schedule() == time(3, 0, tzinfo=timezone.utc)


def test_schedule_can_be_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETENTION_SCHEDULE_UTC", "04:35")
    assert retention_scheduler.configured_schedule() == time(4, 35, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", ["3:00", "24:00", "03:60", "03:00Z", "abc"])
def test_invalid_schedule_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="RETENTION_SCHEDULE_UTC"):
        retention_scheduler.parse_schedule(value)


def test_next_run_is_strictly_after_now() -> None:
    run_at = time(3, 0, tzinfo=timezone.utc)
    assert retention_scheduler.next_run(
        datetime(2026, 11, 12, 2, 59, tzinfo=timezone.utc), run_at
    ) == datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc)
    assert retention_scheduler.next_run(
        datetime(2026, 11, 12, 3, 0, tzinfo=timezone.utc), run_at
    ) == datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)


def test_next_run_normalizes_non_utc_datetime() -> None:
    schedule = time(3, 0, tzinfo=timezone.utc)
    now = datetime.fromisoformat("2026-11-12T04:00:00+02:00")
    assert retention_scheduler.next_run(now, schedule) == datetime(
        2026, 11, 12, 3, 0, tzinfo=timezone.utc
    )


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        retention_scheduler.next_run(datetime(2026, 11, 12, 2, 0))


def test_retention_manager_is_separate_entry_point() -> None:
    assert retention_scheduler.ENTRY_POINT == REPO_ROOT / "scripts" / "retention_manager.py"
    assert retention_scheduler.ENTRY_POINT.name != "nightly_export.py"
