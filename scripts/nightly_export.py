"""Run the weekly business pipeline and write a daily telemetry audit CSV.

The audit CSV is a separate backup artifact. The business pipeline continues to
read telemetry directly from its configured source database.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

import psycopg

from csv_artifact_lock import artifact_lock

SERVICES_DIRECTORY = Path(__file__).resolve().parents[1] / "services"
if str(SERVICES_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIRECTORY))

from job_runner import DEFAULT_JOB_NAME, JobRunner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SCRIPT = PROJECT_ROOT / "data" / "pipelines" / "pipeline.py"
TELEMETRY_DATABASE_URL_ENV = "TELEMETRY_DATABASE_URL"
AUDIT_DIRECTORY_ENV = "NIGHTLY_EXPORT_AUDIT_DIR"
DEFAULT_AUDIT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "audit_exports"
AUDIT_COLUMNS = ("event_id", "event_type", "timestamp", "tags")
AUDIT_EVENT_TYPES = (
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "kit_cost_variance_detected",
)
TARGET_DATE_ENV = "TARGET_DATE"
logger = logging.getLogger("nightly_export")

ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def parse_target_date(value: str) -> date:
    """Parse a strict ISO calendar date (YYYY-MM-DD)."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("target date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("target date must use YYYY-MM-DD")
    return parsed


def default_target_date(now: datetime | None = None) -> date:
    """Return yesterday according to UTC, independent of the host timezone."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(timezone.utc).date() - timedelta(days=1)


def iso_week_start(target: date) -> date:
    """Return the Monday starting the ISO week containing target."""
    return target - timedelta(days=target.weekday())


def resolve_target_date(cli_value: date | None, environ: dict[str, str] | None = None) -> date:
    """Select CLI date, then TARGET_DATE, then yesterday in UTC."""
    if cli_value is not None:
        return cli_value
    env = os.environ if environ is None else environ
    env_value = env.get(TARGET_DATE_ENV, "").strip()
    if env_value:
        try:
            return parse_target_date(env_value)
        except argparse.ArgumentTypeError as exc:
            raise ValueError(f"invalid {TARGET_DATE_ENV}: {exc}") from exc
    return default_target_date()


def _telemetry_database_url() -> str:
    value = os.environ.get(TELEMETRY_DATABASE_URL_ENV, "").strip()
    if not value:
        raise RuntimeError(f"{TELEMETRY_DATABASE_URL_ENV} is not configured")
    if not value.startswith(("postgresql://", "postgres://")):
        raise RuntimeError(f"{TELEMETRY_DATABASE_URL_ENV} must use a PostgreSQL URL")
    return value


def _audit_directory() -> Path:
    configured = os.environ.get(AUDIT_DIRECTORY_ENV, "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_AUDIT_DIRECTORY


def export_daily_audit_csv(target: date, destination_dir: Path | None = None) -> Path:
    """Export supported telemetry events for target UTC day to a local CSV."""
    start = datetime.combine(target, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    query = (
        "SELECT event_id, event_type, timestamp, tags "
        "FROM public.telemetry_events "
        "WHERE timestamp >= %s AND timestamp < %s "
        "AND event_type = ANY(%s) ORDER BY timestamp ASC, event_id ASC"
    )
    with psycopg.connect(_telemetry_database_url(), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (start, end, list(AUDIT_EVENT_TYPES)))
            rows = cursor.fetchall()

    output_dir = destination_dir or _audit_directory()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"telemetry-events-{target.isoformat()}.csv"
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        # The cleaner takes the same OS lock before inspecting/deleting this
        # path. Hold it across writing and atomic publication so it cannot
        # remove the previous CSV or race the replacement.
        with artifact_lock(output_path):
            with temporary_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS)
                writer.writeheader()
                for event_id, event_type, timestamp, tags in rows:
                    writer.writerow(
                        {
                            "event_id": str(event_id),
                            "event_type": event_type,
                            "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                            "tags": tags if isinstance(tags, str) else json.dumps(
                                tags if tags is not None else {}, sort_keys=True, separators=(",", ":")
                            ),
                        }
                    )
            os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path


def pipeline_command(week_start: date) -> list[str]:
    """Build the subprocess command for the existing business pipeline CLI."""
    return [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--week-start",
        week_start.isoformat(),
        "--trigger-type",
        "scheduled",
    ]


def run_nightly_export(
    target: date,
    *,
    runner: JobRunner | None = None,
    process_runner: ProcessRunner = subprocess.run,
    audit_exporter: Callable[[date], Path] = export_daily_audit_csv,
) -> int:
    """Run the daily audit and weekly pipeline while retaining the global lease."""
    job_runner = runner or JobRunner()
    context = {"job_name": DEFAULT_JOB_NAME, "status": "starting", "target_date": target.isoformat()}
    logger.info("Nightly job starting", extra=context)
    lease = job_runner.acquire(DEFAULT_JOB_NAME, target)
    if lease is None:
        logger.info(
            "Nightly job skipped: lock held or target already completed",
            extra={**context, "status": "skipped"},
        )
        return 0

    try:
        audit_path = audit_exporter(target)
        logger.info(
            "Daily audit CSV exported: %s",
            audit_path,
            extra={**context, "status": "audit_exported"},
        )
        logger.info(
            "Launching weekly business pipeline for week_start=%s",
            iso_week_start(target).isoformat(),
            extra={**context, "status": "pipeline_started"},
        )
        completed = process_runner(
            pipeline_command(iso_week_start(target)),
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                f"pipeline subprocess exited with status {completed.returncode}"
                + (f": {detail[:3000]}" if detail else "")
            )
    except BaseException as exc:
        logger.error(
            "Nightly job execution failed: %s: %s",
            type(exc).__name__,
            exc,
            extra={**context, "status": "failed"},
            exc_info=True,
        )
        try:
            lease.fail(f"{type(exc).__name__}: {exc}")
        except Exception as state_error:
            # The lease closes its connection even if terminal-state persistence
            # fails; preserve both failures for operational diagnosis.
            exc.add_note(
                "Additionally, failed-state persistence failed: "
                f"{type(state_error).__name__}: {state_error}"
            )
        raise

    # complete() persists the terminal state transactionally before it closes
    # the lease connection, which is what releases the session-level lock.
    try:
        lease.complete()
    except BaseException as exc:
        logger.error(
            "Could not persist completed state: %s: %s",
            type(exc).__name__,
            exc,
            extra={**context, "status": "terminal_state_error"},
            exc_info=True,
        )
        raise
    logger.info(
        "Nightly job completed; audit CSV: %s",
        audit_path,
        extra={**context, "status": "completed"},
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-date",
        type=parse_target_date,
        help="UTC target date in YYYY-MM-DD format (overrides TARGET_DATE)",
    )
    args = parser.parse_args(argv)
    try:
        target = resolve_target_date(args.target_date)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        return run_nightly_export(target)
    except Exception as exc:
        logger.error(
            "Nightly job failed: %s: %s",
            type(exc).__name__,
            exc,
            extra={
                "job_name": DEFAULT_JOB_NAME,
                "status": "failed",
                "target_date": target.isoformat(),
            },
            exc_info=True,
        )
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s job_name=%(job_name)s status=%(status)s target_date=%(target_date)s %(message)s",
    )
    raise SystemExit(main())