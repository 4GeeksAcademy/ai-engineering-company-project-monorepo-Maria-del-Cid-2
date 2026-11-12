"""Unit tests for CSV retention, isolated to pytest temporary directories."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from csv_artifact_lock import artifact_lock, artifact_lock_path
import retention_manager

TODAY = date(2026, 11, 12)


def csv_path(directory: Path, export_date: date) -> Path:
    return directory / f"telemetry-events-{export_date.isoformat()}.csv"


def test_retains_files_from_zero_through_thirty_days_inclusive(tmp_path: Path) -> None:
    for age in (0, 1, 29, 30):
        csv_path(tmp_path, TODAY - timedelta(days=age)).write_text("csv", encoding="utf-8")

    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
    assert len(list(tmp_path.glob("telemetry-events-*.csv"))) == 4


def test_deletes_files_older_than_thirty_days(tmp_path: Path) -> None:
    expired = csv_path(tmp_path, TODAY - timedelta(days=31))
    expired.write_text("csv", encoding="utf-8")

    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 1
    assert not expired.exists()


def test_exact_thirty_day_boundary_is_retained(tmp_path: Path) -> None:
    at_boundary = csv_path(tmp_path, date(2026, 10, 13))
    at_boundary.write_text("csv", encoding="utf-8")

    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
    assert at_boundary.exists()


def test_utc_date_controls_boundary_across_timezone_offset(tmp_path: Path) -> None:
    # Local clock says Nov 12, but the instant is Nov 13 in UTC.
    now = datetime(2026, 11, 12, 23, 30, tzinfo=timezone(timedelta(hours=-2)))
    utc_30 = csv_path(tmp_path, date(2026, 10, 14))
    utc_31 = csv_path(tmp_path, date(2026, 10, 13))
    utc_30.write_text("keep", encoding="utf-8")
    utc_31.write_text("delete", encoding="utf-8")

    assert retention_manager.clean_expired_csvs(tmp_path, now=now) == 1
    assert utc_30.exists()
    assert not utc_31.exists()


def test_utc_today_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        retention_manager.utc_today(datetime(2026, 11, 12))


def test_temporary_and_nonmatching_files_are_ignored(tmp_path: Path) -> None:
    candidates = [
        "telemetry-events-2026-10-01.csv.tmp",
        "telemetry-events-2026-10-01.tmp",
        "other-2026-10-01.csv",
        "telemetry-events-2026-02-30.csv",
        "telemetry-events-2026-1-01.csv",
    ]
    for name in candidates:
        (tmp_path / name).write_text("keep", encoding="utf-8")

    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
    assert all((tmp_path / name).exists() for name in candidates)


def test_active_publisher_lock_protects_csv_from_cleaner(tmp_path: Path) -> None:
    target = csv_path(tmp_path, TODAY - timedelta(days=31))
    target.write_text("old csv", encoding="utf-8")

    with artifact_lock(target):
        assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
        assert target.exists()

    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 1
    assert not target.exists()


def test_shared_lock_is_observed_by_independent_process(tmp_path: Path) -> None:
    target = csv_path(tmp_path, TODAY - timedelta(days=31))
    target.write_text("old csv", encoding="utf-8")
    lock_path = artifact_lock_path(target)
    source = (
        "import sys; from pathlib import Path; "
        "from csv_artifact_lock import shared_file_lock, LockBusyError; "
        "p=Path(sys.argv[1]); "
        "\ntry:\n shared_file_lock(p, blocking=False).__enter__()\n"
        "except LockBusyError:\n print('BUSY')\n raise SystemExit(0)\n"
        "print('ACQUIRED')\n"
    )

    with artifact_lock(target):
        result = subprocess.run(
            [sys.executable, "-c", source, str(lock_path)],
            cwd=SCRIPTS,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "BUSY"
        assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
        assert target.exists()


def test_missing_file_after_directory_scan_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = csv_path(tmp_path, TODAY - timedelta(days=31))
    target.write_text("csv", encoding="utf-8")
    original_is_file = Path.is_file

    def vanish_before_check(path: Path) -> bool:
        if path == target:
            path.unlink(missing_ok=True)
            return True
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", vanish_before_check)
    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
    assert not target.exists()


def test_permission_error_is_logged_and_other_files_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    denied = csv_path(tmp_path, TODAY - timedelta(days=32))
    deleted = csv_path(tmp_path, TODAY - timedelta(days=31))
    denied.write_text("denied", encoding="utf-8")
    deleted.write_text("delete", encoding="utf-8")
    original_unlink = Path.unlink

    def selective_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == denied:
            raise PermissionError("denied for test")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", selective_unlink)
    with caplog.at_level(logging.ERROR, logger="retention_manager"):
        count = retention_manager.clean_expired_csvs(tmp_path, today=TODAY)

    assert count == 1
    assert denied.exists()
    assert not deleted.exists()
    error = next(record for record in caplog.records if record.result == "error")
    assert error.artifact_filename == denied.name
    assert error.export_date == (TODAY - timedelta(days=32)).isoformat()
    assert error.deletion_date == TODAY.isoformat()
    assert "PermissionError" in error.error


def test_success_log_has_file_and_deletion_fields(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target = csv_path(tmp_path, TODAY - timedelta(days=31))
    target.write_text("csv", encoding="utf-8")

    with caplog.at_level(logging.INFO, logger="retention_manager"):
        assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 1

    record = next(record for record in caplog.records if record.result == "deleted")
    assert record.artifact_filename == target.name
    assert record.export_date == (TODAY - timedelta(days=31)).isoformat()
    assert record.deletion_date == TODAY.isoformat()
    assert record.error is None


def test_reexecution_is_safe_and_reports_already_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target = csv_path(tmp_path, TODAY - timedelta(days=31))
    target.write_text("csv", encoding="utf-8")
    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 1

    # A repeated run sees no CSV and does not fail or delete anything else.
    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
    assert not target.exists()


def test_concurrent_cleaner_run_is_skipped(tmp_path: Path) -> None:
    target = csv_path(tmp_path, TODAY - timedelta(days=31))
    target.write_text("csv", encoding="utf-8")
    global_lock = tmp_path / ".locks" / "retention-manager.lock"

    with retention_manager.shared_file_lock(global_lock):
        assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 0
        assert target.exists()

    assert retention_manager.clean_expired_csvs(tmp_path, today=TODAY) == 1
    assert not target.exists()


def test_malformed_dates_are_not_parsed_as_exports() -> None:
    assert retention_manager.parse_export_date("telemetry-events-2026-02-30.csv") is None
    assert retention_manager.parse_export_date("telemetry-events-2026-10-01.csv.tmp") is None
    assert retention_manager.parse_export_date("telemetry-events-2026-10-01.csv") == date(2026, 10, 1)
