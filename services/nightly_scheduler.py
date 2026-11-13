"""Run the nightly export entry point daily at 10:00 Europe/Madrid."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ENTRY_POINT = Path(__file__).resolve().parents[1] / "scripts" / "nightly_export.py"
SCHEDULE_TIMEZONE = ZoneInfo("Europe/Madrid")
SCHEDULE_HOUR = 10
SCHEDULE_MINUTE = 0
logger = logging.getLogger("nightly_scheduler")
shutdown_requested = False


def _request_shutdown(_signum: int, _frame: object) -> None:
    global shutdown_requested
    shutdown_requested = True


def next_run(now: datetime) -> datetime:
    """Return the next 10:00 Europe/Madrid boundary, strictly after ``now``.

    Constructing the next local calendar date in the IANA timezone lets the
    UTC offset follow Madrid's winter/summer time changes automatically.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = now.astimezone(SCHEDULE_TIMEZONE)
    candidate = local_now.replace(
        hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0
    )
    if candidate <= local_now:
        next_date = local_now.date() + timedelta(days=1)
        candidate = datetime(
            next_date.year,
            next_date.month,
            next_date.day,
            SCHEDULE_HOUR,
            SCHEDULE_MINUTE,
            tzinfo=SCHEDULE_TIMEZONE,
        )
    return candidate


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)
    while not shutdown_requested:
        scheduled_for = next_run(datetime.now(timezone.utc))
        wait_seconds = max(
            0.0,
            (scheduled_for.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds(),
        )
        logger.info("Next nightly export scheduled for %s", scheduled_for.isoformat())
        deadline = time.monotonic() + wait_seconds
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
                logger.error("Nightly export exited with status %d", result.returncode)
            else:
                logger.info("Nightly export completed successfully")
        except Exception:
            logger.exception("Could not launch nightly export")


if __name__ == "__main__":
    raise SystemExit(main())