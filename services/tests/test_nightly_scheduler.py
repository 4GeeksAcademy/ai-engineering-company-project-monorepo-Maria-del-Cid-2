"""Tests for the nightly scheduler's Europe/Madrid wall-clock schedule."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "services"
sys.path.insert(0, str(SERVICES_DIR))

import nightly_scheduler  # noqa: E402


MADRID = ZoneInfo("Europe/Madrid")


@pytest.mark.parametrize(
    ("now", "expected_local", "expected_utc"),
    [
        (
            datetime(2026, 1, 15, 8, 59, tzinfo=timezone.utc),
            datetime(2026, 1, 15, 10, 0, tzinfo=MADRID),
            datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 7, 15, 7, 59, tzinfo=timezone.utc),
            datetime(2026, 7, 15, 10, 0, tzinfo=MADRID),
            datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc),
        ),
    ],
)
def test_next_run_is_ten_madrid_time_in_winter_and_summer(
    now: datetime, expected_local: datetime, expected_utc: datetime
) -> None:
    result = nightly_scheduler.next_run(now)

    assert result == expected_local
    assert result.astimezone(timezone.utc) == expected_utc


def test_next_run_advances_to_next_madrid_calendar_day() -> None:
    now = datetime(2026, 11, 13, 9, 1, tzinfo=timezone.utc)

    assert nightly_scheduler.next_run(now) == datetime(
        2026, 11, 14, 10, 0, tzinfo=MADRID
    )


def test_next_run_is_strictly_after_exact_schedule_time() -> None:
    now = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)

    assert nightly_scheduler.next_run(now) == datetime(
        2026, 11, 14, 10, 0, tzinfo=MADRID
    )


def test_next_run_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        nightly_scheduler.next_run(datetime(2026, 11, 13, 9, 0))
