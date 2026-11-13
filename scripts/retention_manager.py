"""Delete published telemetry CSV exports after their 30-day local retention.

Only files named ``telemetry-events-YYYY-MM-DD.csv`` are considered. The
exporter and cleaner share OS-managed locks stored on the persistent volume;
OS locks are released automatically when a process/container exits.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
from typing import Sequence

from csv_artifact_lock import LockBusyError, artifact_lock, shared_file_lock

AUDIT_DIRECTORY_ENV = "NIGHTLY_EXPORT_AUDIT_DIR"
DEFAULT_AUDIT_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "audit_exports"
RETENTION_DAYS = 30
CSV_NAME_PATTERN = re.compile(r"^telemetry-events-(\d{4}-\d{2}-\d{2})\.csv$")
logger = logging.getLogger("retention_manager")


class JsonLogFormatter(logging.Formatter):
    """Emit the retention event fields as one machine-readable JSON line."""

    fields = ("artifact_filename", "export_date", "deletion_date", "result", "error", "deleted_count", "directory")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self.fields:
            if hasattr(record, field):
                payload["filename" if field == "artifact_filename" else field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def utc_today(now: datetime | None = None) -> date:
    """Get today's UTC date, rejecting ambiguous naive datetimes."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return current.astimezone(timezone.utc).date()


def parse_export_date(filename: str) -> date | None:
    """Return the strict ISO export date for a matching CSV filename."""
    match = CSV_NAME_PATTERN.fullmatch(filename)
    if not match:
        return None
    try:
        parsed = date.fromisoformat(match.group(1))
    except ValueError:
        return None
    return parsed if parsed.isoformat() == match.group(1) else None


def _audit_directory() -> Path:
    configured = os.environ.get(AUDIT_DIRECTORY_ENV, "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_AUDIT_DIRECTORY


def _record(
    level: int,
    *,
    filename: str,
    export_date: date | None,
    deletion_date: date,
    result: str,
    error: str | None = None,
) -> None:
    logger.log(
        level,
        "CSV retention operation",
        extra={
            "artifact_filename": filename,
            "export_date": export_date.isoformat() if export_date else None,
            "deletion_date": deletion_date.isoformat(),
            "result": result,
            "error": error,
        },
    )


def clean_expired_csvs(
    directory: Path | None = None,
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> int:
    """Delete matching CSVs older than 30 UTC calendar days; return count.

    At exactly 30 days the file is retained. A non-blocking global lock makes
    concurrent cleaner runs a safe no-op. Per-file locks are identical to the
    exporter's locks; a file in publication is skipped rather than deleted.
    """
    deletion_date = today if today is not None else utc_today(now)
    if isinstance(deletion_date, datetime) or not isinstance(deletion_date, date):
        raise TypeError("today must be a datetime.date")
    root = directory or _audit_directory()
    root.mkdir(parents=True, exist_ok=True)
    global_lock = root / ".locks" / "retention-manager.lock"
    try:
        global_context = shared_file_lock(global_lock, blocking=False)
        global_context.__enter__()
    except LockBusyError:
        logger.info(
            "CSV retention run skipped: another cleaner holds the lock",
            extra={"result": "skipped_concurrent", "deletion_date": deletion_date.isoformat()},
        )
        return 0
    except OSError as exc:
        logger.error(
            "Could not acquire CSV retention lock",
            extra={
                "directory": str(root),
                "result": "error",
                "deletion_date": deletion_date.isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        return 0

    deleted = 0
    try:
        try:
            entries = list(root.iterdir())
        except OSError:
            logger.exception(
                "Could not list CSV retention directory",
                extra={"directory": str(root), "result": "error", "deletion_date": deletion_date.isoformat()},
            )
            return 0

        for path in entries:
            exported = parse_export_date(path.name)
            if exported is None or (deletion_date - exported).days <= RETENTION_DAYS:
                continue
            try:
                lock_context = artifact_lock(path, blocking=False)
                lock_context.__enter__()
            except LockBusyError:
                _record(
                    logging.INFO,
                    filename=path.name,
                    export_date=exported,
                    deletion_date=deletion_date,
                    result="skipped_in_use",
                )
                continue
            except OSError as exc:
                _record(
                    logging.ERROR,
                    filename=path.name,
                    export_date=exported,
                    deletion_date=deletion_date,
                    result="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue
            try:
                try:
                    if not path.is_file():
                        _record(
                            logging.INFO,
                            filename=path.name,
                            export_date=exported,
                            deletion_date=deletion_date,
                            result="skipped_not_file",
                        )
                        continue
                    path.unlink()
                    deleted += 1
                    _record(
                        logging.INFO,
                        filename=path.name,
                        export_date=exported,
                        deletion_date=deletion_date,
                        result="deleted",
                    )
                except FileNotFoundError:
                    _record(
                        logging.INFO,
                        filename=path.name,
                        export_date=exported,
                        deletion_date=deletion_date,
                        result="already_missing",
                    )
                except OSError as exc:
                    _record(
                        logging.ERROR,
                        filename=path.name,
                        export_date=exported,
                        deletion_date=deletion_date,
                        result="error",
                        error=f"{type(exc).__name__}: {exc}",
                    )
            finally:
                lock_context.__exit__(None, None, None)
        logger.info(
            "CSV retention run finished",
            extra={"result": "completed", "deleted_count": deleted, "deletion_date": deletion_date.isoformat()},
        )
        return deleted
    finally:
        global_context.__exit__(None, None, None)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, help="CSV export directory (defaults to configured persistent volume)")
    args = parser.parse_args(argv)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        handlers=[handler],
    )
    try:
        clean_expired_csvs(args.directory)
    except Exception:
        logger.exception("CSV retention run failed", extra={"result": "error"})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
