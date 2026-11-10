"""Independent at-least-once delivery worker for the Inventory telemetry outbox."""

from __future__ import annotations

import logging
import math
import os
import random
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import psycopg
from sqlalchemy import and_, delete, or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.inventory.database import get_engine
from app.inventory.models import TelemetryOutboxEvent
from app.telemetry.repository import (
    TelemetryRecord,
    TelemetryRepository,
    TelemetryStorageUnavailable,
)
from app.telemetry.tags import filter_tags

logger = logging.getLogger("inventory_outbox_worker")
STOP = False
MAX_ERROR_LENGTH = 1000


@dataclass(frozen=True)
class WorkerSettings:
    poll_seconds: float = 2
    batch_size: int = 50
    lease_seconds: int = 60
    max_attempts: int = 10
    backoff_base_seconds: float = 2
    backoff_max_seconds: float = 900
    retention_days: int = 90
    jitter_fraction: float = 0.2

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.poll_seconds)
            or self.poll_seconds <= 0
            or self.batch_size < 1
            or self.lease_seconds < 1
            or self.max_attempts < 1
            or not math.isfinite(self.backoff_base_seconds)
            or self.backoff_base_seconds <= 0
            or not math.isfinite(self.backoff_max_seconds)
            or self.backoff_max_seconds < self.backoff_base_seconds
            or self.retention_days < 1
            or not math.isfinite(self.jitter_fraction)
            or not 0 <= self.jitter_fraction <= 1
        ):
            raise ValueError("Invalid inventory outbox worker configuration")

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        settings = cls(
            poll_seconds=float(os.getenv("OUTBOX_POLL_SECONDS", "2")),
            batch_size=int(os.getenv("OUTBOX_BATCH_SIZE", "50")),
            lease_seconds=int(os.getenv("OUTBOX_LEASE_SECONDS", "60")),
            max_attempts=int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10")),
            backoff_base_seconds=float(os.getenv("OUTBOX_BACKOFF_BASE_SECONDS", "2")),
            backoff_max_seconds=float(os.getenv("OUTBOX_BACKOFF_MAX_SECONDS", "900")),
            retention_days=int(os.getenv("OUTBOX_RETENTION_DAYS", "90")),
            jitter_fraction=float(os.getenv("OUTBOX_JITTER_FRACTION", "0.2")),
        )
        return settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _claim_batch(engine: Any, settings: WorkerSettings, now: datetime) -> list[TelemetryOutboxEvent]:
    """Claim eligible events atomically and return detached event snapshots."""

    lease_expiry = now + timedelta(seconds=settings.lease_seconds)
    claimed: list[TelemetryOutboxEvent] = []
    dialect = engine.dialect.name
    with Session(engine) as session:
        with session.begin():
            eligible = and_(
                TelemetryOutboxEvent.status == "pending",
                TelemetryOutboxEvent.attempt_count < settings.max_attempts,
                TelemetryOutboxEvent.available_at <= now,
                or_(TelemetryOutboxEvent.locked_until.is_(None), TelemetryOutboxEvent.locked_until <= now),
            )
            statement = (
                select(TelemetryOutboxEvent)
                .where(eligible)
                .order_by(TelemetryOutboxEvent.timestamp, TelemetryOutboxEvent.event_id)
                .limit(settings.batch_size)
            )
            if dialect == "postgresql":
                statement = statement.with_for_update(skip_locked=True)
            rows = session.exec(statement).all()
            for row in rows:
                token = str(uuid4())
                changed = session.exec(
                    update(TelemetryOutboxEvent)
                    .where(
                        TelemetryOutboxEvent.event_id == row.event_id,
                        TelemetryOutboxEvent.status == "pending",
                        TelemetryOutboxEvent.attempt_count < settings.max_attempts,
                        or_(TelemetryOutboxEvent.locked_until.is_(None), TelemetryOutboxEvent.locked_until <= now),
                    )
                    .values(locked_until=lease_expiry, lease_token=token)
                ).rowcount
                if changed:
                    claimed.append(
                        TelemetryOutboxEvent(
                            event_id=row.event_id,
                            event_type=row.event_type,
                            timestamp=row.timestamp,
                            source=row.source,
                            tags=dict(row.tags),
                            movement_type=row.movement_type,
                            movement_id=row.movement_id,
                            attempt_count=row.attempt_count,
                            lease_token=token,
                        )
                    )
    return claimed


def _to_record(event: TelemetryOutboxEvent) -> TelemetryRecord:
    if event.event_type not in {
        "inbound_order_created", "outbound_order_created",
        "stock_threshold_triggered", "kit_cost_variance_detected",
    }:
        raise ValueError("unsupported business event type")
    tags = filter_tags(event.event_type, event.tags)
    if not tags or tags.get("product_id") is None:
        raise ValueError("business event is missing required product tag")
    if event.event_type in {"inbound_order_created", "outbound_order_created"} and tags.get("quantity") is None:
        raise ValueError("movement event is missing quantity")
    if tags.get("programme_id") is None:
        raise ValueError("business event is missing programme_id")
    if event.event_type == "inbound_order_created":
        if tags.get("unit_cost") is None or tags.get("office") is None or tags.get("currency") is None:
            raise ValueError("inbound event is missing cost or office dimensions")
    elif tags.get("exit_type") is None or tags.get("office") is None or tags.get("currency") is None:
        if event.event_type == "outbound_order_created":
            raise ValueError("outbound event is missing exit or office dimensions")
    if event.event_type == "stock_threshold_triggered":
        if any(tags.get(key) is None for key in ("office", "currency", "current_stock", "threshold", "stock_level")):
            raise ValueError("stock threshold event is missing required dimensions")
        expected_currency = {"Valencia": "EUR", "Miami": "USD"}.get(tags["office"])
        if expected_currency != tags["currency"]:
            raise ValueError("stock threshold office and currency do not match")
        if tags.get("programme_id") is None:
            raise ValueError("stock threshold event requires programme attribution")
    if event.event_type == "kit_cost_variance_detected":
        if any(tags.get(key) is None for key in (
            "office", "currency", "expected_cost", "actual_cost", "variance_percent", "kit_composition",
        )):
            raise ValueError("kit variance event is missing required cost dimensions")
        if tags.get("programme_id") is None:
            raise ValueError("kit variance event requires programme attribution")
        expected_currency = {"Valencia": "EUR", "Miami": "USD"}.get(tags["office"])
        if expected_currency != tags["currency"]:
            raise ValueError("kit variance office and currency do not match")
        if tags.get("preparation_id") is None or tags.get("variance_percent", 0) <= 0:
            raise ValueError("kit variance event is missing preparation trace or positive variance")
    return TelemetryRecord(
        event_id=event.event_id,
        event_type=event.event_type,
        timestamp=event.timestamp.isoformat().replace("+00:00", "Z"),
        source=event.source,
        session_id=None,
        schema_version="1.0.0",
        tags=tags,
    )


def _retry_delay(attempt: int, settings: WorkerSettings, random_value: float | None = None) -> float:
    exponent = min(max(0, attempt - 1), 30)
    base = min(settings.backoff_max_seconds, settings.backoff_base_seconds * (2**exponent))
    sample = random.random() if random_value is None else random_value
    return min(
        settings.backoff_max_seconds,
        base * (1 + settings.jitter_fraction * (2 * sample - 1)),
    )


def _finish_failure(
    engine: Any,
    event: TelemetryOutboxEvent,
    error: Exception,
    settings: WorkerSettings,
    now: datetime,
    *,
    permanent: bool,
) -> str:
    attempt_count = event.attempt_count + 1
    dead = permanent or attempt_count >= settings.max_attempts
    # Exception text may contain connection details or credentials. Keep only
    # the class name in the durable outbox diagnostic.
    message = type(error).__name__[:MAX_ERROR_LENGTH]
    with Session(engine) as session:
        with session.begin():
            row = session.exec(
                select(TelemetryOutboxEvent)
                .where(
                    TelemetryOutboxEvent.event_id == event.event_id,
                    TelemetryOutboxEvent.status == "pending",
                    TelemetryOutboxEvent.lease_token == event.lease_token,
                )
                .with_for_update()
            ).first()
            if row is None:
                return "stale"
            row.attempt_count = attempt_count
            row.last_error = message
            row.locked_until = None
            row.lease_token = None
            if dead:
                row.status = "dead"
                row.dead_lettered_at = now
            else:
                row.available_at = now + timedelta(seconds=_retry_delay(attempt_count, settings))
    return "dead" if dead else "retry"


def _mark_delivered(engine: Any, event: TelemetryOutboxEvent, now: datetime) -> bool:
    with Session(engine) as session:
        with session.begin():
            row = session.exec(
                select(TelemetryOutboxEvent)
                .where(
                    TelemetryOutboxEvent.event_id == event.event_id,
                    TelemetryOutboxEvent.status == "pending",
                    TelemetryOutboxEvent.lease_token == event.lease_token,
                )
                .with_for_update()
            ).first()
            if row is None:
                return False
            row.status = "delivered"
            row.delivered_at = now
            row.locked_until = None
            row.lease_token = None
            row.last_error = None
            return True


def deliver_batch(
    engine: Any,
    repository: TelemetryRepository,
    settings: WorkerSettings,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Claim and deliver one bounded batch; external calls occur outside DB locks."""

    current = now or _utcnow()
    stats = {"claimed": 0, "delivered": 0, "retried": 0, "dead": 0}
    events = _claim_batch(engine, settings, current)
    stats["claimed"] = len(events)
    for event in events:
        try:
            record = _to_record(event)
        except (TypeError, ValueError, KeyError) as exc:
            result = _finish_failure(engine, event, exc, settings, current, permanent=True)
            stats["dead" if result == "dead" else "retried"] += int(result != "stale")
            continue
        try:
            # One at a time: an uncertain commit is safe to replay by event_id.
            repository.insert_many([record])
        except TelemetryStorageUnavailable as exc:
            cause = exc.__cause__
            permanent = cause is None or isinstance(
                cause,
                (psycopg.errors.InvalidPassword, psycopg.errors.InvalidCatalogName),
            )
            result = _finish_failure(engine, event, exc, settings, current, permanent=permanent)
            stats["dead" if result == "dead" else "retried"] += int(result != "stale")
            logger.warning("Outbox event %s delivery %s", event.event_id, result)
            continue
        except (TypeError, ValueError) as exc:
            result = _finish_failure(engine, event, exc, settings, current, permanent=True)
            stats["dead" if result == "dead" else "retried"] += int(result != "stale")
            continue
        except Exception as exc:  # Defensive: preserve event and release/retry lease.
            result = _finish_failure(engine, event, exc, settings, current, permanent=False)
            stats["dead" if result == "dead" else "retried"] += int(result != "stale")
            logger.exception("Unexpected delivery failure for outbox event %s", event.event_id)
            continue
        if _mark_delivered(engine, event, _utcnow()):
            stats["delivered"] += 1
    return stats


def purge_terminal_events(engine: Any, retention_days: int, *, now: datetime | None = None) -> int:
    """Delete only delivered/dead records beyond retention; pending data is preserved."""

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")

    cutoff = (now or _utcnow()) - timedelta(days=retention_days)
    with Session(engine) as session:
        with session.begin():
            result = session.exec(
                delete(TelemetryOutboxEvent).where(
                    TelemetryOutboxEvent.status.in_(("delivered", "dead")),
                    or_(TelemetryOutboxEvent.delivered_at < cutoff, TelemetryOutboxEvent.dead_lettered_at < cutoff),
                )
            )
            return int(result.rowcount or 0)


def _request_stop(_signum: int, _frame: Any) -> None:
    global STOP
    STOP = True


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    settings = WorkerSettings.from_env()
    engine = get_engine()
    repository = TelemetryRepository()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, _request_stop)
    logger.info("Inventory outbox worker started")
    last_purge = 0.0
    while not STOP:
        try:
            stats = deliver_batch(engine, repository, settings)
            if stats["claimed"]:
                logger.info("Outbox batch result: %s", stats)
            if time.monotonic() - last_purge >= 3600:
                purged = purge_terminal_events(engine, settings.retention_days)
                if purged:
                    logger.info("Purged %s terminal outbox events", purged)
                last_purge = time.monotonic()
            if not stats["claimed"]:
                time.sleep(settings.poll_seconds)
        except SQLAlchemyError:
            logger.exception("Inventory outbox database operation failed")
            time.sleep(settings.poll_seconds)
        except Exception:
            logger.exception("Inventory outbox worker iteration failed")
            time.sleep(settings.poll_seconds)
    engine.dispose()
    logger.info("Inventory outbox worker stopped")


if __name__ == "__main__":
    main()
