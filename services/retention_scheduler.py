"""Run the local CSV retention manager daily at a configurable UTC time."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path


ENTRY_POINT = Path(__file__).resolve().parents[1] / "scripts" / "retention_manager.py"
SCHEDULE_ENV = "RETENTION_SCHEDULE_UTC"
DEFAULT_SCHEDULE_UTC = "03:00"
logger = logging.getLogger("retention_scheduler")
shutdown_requested = False


class JsonLogFormatter(logging.Formatter):
    """Format scheduler lifecycle messages as JSON lines on stdout/stderr."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def parse_schedule(value: str) -> datetime_time:
    """Parse a strict HH:MM UTC schedule value."""
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError(f"{SCHEDULE_ENV} must use HH:MM in UTC")
    try:
        hour, minute = (int(part) for part in value.split(":"))
        return datetime_time(hour, minute, tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{SCHEDULE_ENV} must be a valid HH:MM time") from exc


def configured_schedule() -> datetime_time:
    return parse_schedule(os.environ.get(SCHEDULE_ENV, DEFAULT_SCHEDULE_UTC).strip())


def next_run(now: datetime, run_time: datetime_time | None = None) -> datetime:
    """Return the next scheduled UTC instant, strictly after ``now``."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    utc_now = now.astimezone(timezone.utc)
    schedule = run_time or configured_schedule()
    candidate = utc_now.replace(
        hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0
    )
    if candidate <= utc_now:
        candidate += timedelta(days=1)
    return candidate


def _request_shutdown(_signum: int, _frame: object) -> None:
    global shutdown_requested
    shutdown_requested = True


def main() -> int:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(), handlers=[handler]
    )
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    try:
        schedule = configured_schedule()
    except ValueError:
        logger.exception("Invalid retention schedule configuration")
        return 2

    while not shutdown_requested:
        scheduled_for = next_run(datetime.now(timezone.utc), schedule)
        logger.info("Next CSV retention run scheduled for %s", scheduled_for.isoformat())
        deadline = time.monotonic() + max(
            0.0, (scheduled_for - datetime.now(timezone.utc)).total_seconds()
        )
        while not shutdown_requested:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(remaining, 60.0))
        if shutdown_requested:
            break
        try:
            result = subprocess.run([sys.executable, str(ENTRY_POINT)], check=False)
            if result.returncode:
                logger.error("CSV retention manager exited with status %d", result.returncode)
            else:
                logger.info("CSV retention manager completed successfully")
        except Exception:
            logger.exception("Could not launch CSV retention manager")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
