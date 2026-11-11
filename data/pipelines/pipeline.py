"""Resilient weekly business-reporting ETL, orchestrated with Prefect 3."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg
from prefect import flow, get_run_logger, task
from prefect.states import State
from psycopg import OperationalError

PIPELINE_NAME = "weekly_office_program_performance"
TELEMETRY_DATABASE_URL_ENV = "TELEMETRY_DATABASE_URL"
REPORTING_DATABASE_URL_ENV = "REPORTING_DATABASE_URL"
EVENT_TYPES = {
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "kit_cost_variance_detected",
}
OFFICE_CURRENCY = {"Valencia": "EUR", "Miami": "USD"}


class PipelineConfigurationError(RuntimeError):
    """Raised for permanent configuration problems; these are not retried."""


class EventValidationError(ValueError):
    """Raised for invalid event data, not transient infrastructure failures."""


def _database_url(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PipelineConfigurationError(f"{name} is not configured")
    return value


def _iso_week_bounds(week_start: date) -> tuple[datetime, datetime]:
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday (ISO week, UTC)")
    start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def _transient_retry(task: Any, task_run: Any, state: State) -> bool:
    """Retry only network/connection failures; never retry invalid data or SQL logic."""
    exception = state.result(raise_on_failure=False)
    return isinstance(
        exception,
        (OperationalError, psycopg.InterfaceError, TimeoutError, ConnectionError),
    )


def _transform_cache_key(_context: Any, parameters: dict[str, Any]) -> str:
    """Key by processed week and canonical event content, so new/late events miss cache."""
    payload = {"week_start": parameters["week_start"], "events": parameters["events"]}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "weekly-transform:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _extract_events(week_start: date) -> list[dict[str, Any]]:
    start, end = _iso_week_bounds(week_start)
    query = (
        "SELECT event_id, event_type, timestamp, tags "
        "FROM public.telemetry_events "
        "WHERE timestamp >= %s AND timestamp < %s "
        "AND event_type = ANY(%s) ORDER BY timestamp ASC, event_id ASC"
    )
    # Extraction is always uncached: late source events must be visible on every run.
    # Two retries with a short delay handle brief database/network interruptions.
    with psycopg.connect(_database_url(TELEMETRY_DATABASE_URL_ENV), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (start, end, list(EVENT_TYPES)))
            rows = cursor.fetchall()
    return [
        {
            "event_id": str(row[0]),
            "event_type": row[1],
            "timestamp": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
            "tags": row[3] if isinstance(row[3], dict) else {},
        }
        for row in rows
    ]


@task(
    name="extract_telemetry_events",
    retries=2,
    retry_delay_seconds=5,
    retry_condition_fn=_transient_retry,
)
def extract_telemetry_events(week_start: date) -> list[dict[str, Any]]:
    """Critical, uncached extraction of every source event in the requested week."""
    return _extract_events(week_start)


@task(
    name="transform_weekly_office_program_performance",
    cache_key_fn=_transform_cache_key,
    cache_expiration=timedelta(hours=1),
    persist_result=True,
)
def transform_weekly_office_program_performance(
    events: list[dict[str, Any]], week_start: date,
) -> dict[str, Any]:
    """Validate and aggregate events; cache for one hour per week and exact inputs."""
    _iso_week_bounds(week_start)
    processed = len(events)
    rejected = 0
    deduplicated: dict[str, dict[str, Any]] = {}
    aggregates: dict[tuple[str, str, date], dict[str, Any]] = {}

    for event in events:
        event_id = event.get("event_id")
        if not event_id:
            rejected += 1
            continue
        previous = deduplicated.get(event_id)
        if previous is not None:
            if previous != event:
                raise EventValidationError(f"Conflicting duplicate event_id: {event_id}")
            continue
        deduplicated[event_id] = event

    for event in deduplicated.values():
        try:
            event_type = event["event_type"]
            tags = event["tags"]
            if not isinstance(tags, dict):
                raise EventValidationError("Event tags must be an object")
            office = tags["office"]
            programme_id = tags["programme_id"]
            if office not in OFFICE_CURRENCY or not isinstance(programme_id, str) or not programme_id:
                raise EventValidationError("Missing or invalid office/programme_id")
            expected_currency = OFFICE_CURRENCY[office]
            currency = tags.get("currency")
            if currency is not None and currency != expected_currency:
                raise EventValidationError("Currency does not match canonical office currency")
            timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise EventValidationError("Timestamp must include a timezone")
            event_date = timestamp.astimezone(timezone.utc).date()
            if event_date < week_start or event_date >= week_start + timedelta(days=7):
                raise EventValidationError("Timestamp is outside the requested UTC week")

            if event_type == "inbound_order_created":
                if currency != expected_currency:
                    raise EventValidationError("Inbound currency is required and must match office")
                quantity = Decimal(str(tags["quantity"]))
                unit_cost = Decimal(str(tags["unit_cost"]))
                if not quantity.is_finite() or not unit_cost.is_finite() or quantity <= 0 or unit_cost < 0:
                    raise EventValidationError("Inbound quantity/cost is invalid")
            elif event_type == "outbound_order_created":
                quantity = Decimal(str(tags["quantity"]))
                if not quantity.is_finite() or quantity <= 0 or not tags.get("exit_type"):
                    raise EventValidationError("Outbound quantity/exit_type is invalid")
            elif event_type == "stock_threshold_triggered":
                for field in ("product_id", "threshold", "current_stock", "stock_level"):
                    if field not in tags:
                        raise EventValidationError(f"Missing required tag: {field}")
            elif event_type == "kit_cost_variance_detected":
                if currency != expected_currency or not (tags.get("product_id") or tags.get("product_sku")):
                    raise EventValidationError("Variance currency/product is missing or invalid")
                for field in ("expected_cost", "actual_cost", "variance_percent"):
                    value = Decimal(str(tags[field]))
                    if not value.is_finite():
                        raise EventValidationError(f"Invalid variance value: {field}")
            else:
                raise EventValidationError("Unsupported event type")

            key = (office, programme_id, week_start)
            row = aggregates.setdefault(key, {
                "office": office,
                "programme_id": programme_id,
                "week_start": week_start,
                "total_material_cost": Decimal("0"),
                "kits_delivered_count": 0,
                "shortage_events_count": 0,
                "cost_variance_events_count": 0,
                "currency": expected_currency,
            })
            if event_type == "inbound_order_created":
                row["total_material_cost"] += quantity * unit_cost
            elif event_type == "outbound_order_created":
                row["kits_delivered_count"] += 1
            elif event_type == "stock_threshold_triggered":
                row["shortage_events_count"] += 1
            elif event_type == "kit_cost_variance_detected":
                row["cost_variance_events_count"] += 1
        except (KeyError, TypeError, ValueError, InvalidOperation):
            rejected += 1
    rows = []
    for row in aggregates.values():
        row["total_material_cost"] = row["total_material_cost"].quantize(Decimal("0.01"))
        rows.append(row)
    return {"rows": rows, "records_processed": processed, "records_rejected": rejected}


@task(
    name="load_weekly_office_program_performance",
    retries=2,
    retry_delay_seconds=5,
    retry_condition_fn=_transient_retry,
)
def load_weekly_office_program_performance(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Critical all-or-nothing upsert; retry only transient database connectivity."""
    if not rows:
        return {"records_inserted": 0, "records_updated": 0}
    query = """
        INSERT INTO reporting.weekly_office_program_performance (
            office, programme_id, week_start, total_material_cost,
            kits_delivered_count, shortage_events_count,
            cost_variance_events_count, currency, computed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (office, programme_id, week_start) DO UPDATE SET
            total_material_cost = EXCLUDED.total_material_cost,
            kits_delivered_count = EXCLUDED.kits_delivered_count,
            shortage_events_count = EXCLUDED.shortage_events_count,
            cost_variance_events_count = EXCLUDED.cost_variance_events_count,
            currency = EXCLUDED.currency,
            computed_at = EXCLUDED.computed_at
        RETURNING (xmax = 0) AS inserted
    """
    inserted = 0
    # One transaction covers every weekly upsert: any failure rolls all results back.
    with psycopg.connect(_database_url(REPORTING_DATABASE_URL_ENV), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(query, (
                    row["office"], row["programme_id"], row["week_start"],
                    row["total_material_cost"], row["kits_delivered_count"],
                    row["shortage_events_count"], row["cost_variance_events_count"],
                    row["currency"],
                ))
                inserted += int(cursor.fetchone()[0])
        connection.commit()
    return {"records_inserted": inserted, "records_updated": len(rows) - inserted}


def _create_run(week_start: date, trigger_type: str) -> str:
    query = """
        INSERT INTO reporting.pipeline_runs (pipeline_name, week_start, status, trigger_type)
        VALUES (%s, %s, 'running', %s) RETURNING id
    """
    with psycopg.connect(_database_url(REPORTING_DATABASE_URL_ENV), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (PIPELINE_NAME, week_start, trigger_type))
            run_id = str(cursor.fetchone()[0])
        connection.commit()
    return run_id


def _finish_run(
    run_id: str,
    status: str,
    *,
    records_processed: int = 0,
    records_inserted: int = 0,
    records_updated: int = 0,
    records_rejected: int = 0,
    error_message: str | None = None,
) -> None:
    query = """
        UPDATE reporting.pipeline_runs SET status = %s, finished_at = now(),
            records_processed = %s, records_inserted = %s, records_updated = %s,
            records_rejected = %s, error_message = %s WHERE id = %s
    """
    with psycopg.connect(_database_url(REPORTING_DATABASE_URL_ENV), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (
                status, records_processed, records_inserted, records_updated,
                records_rejected, error_message[:1000] if error_message else None, run_id,
            ))
            if cursor.rowcount != 1:
                raise RuntimeError("Pipeline run metadata row disappeared")
        connection.commit()


@task(name="capture_optional_snapshot")
def capture_optional_snapshot(summary: dict[str, int], week_start: date) -> None:
    """Optional local snapshot; callers explicitly consume its Prefect state."""
    output_dir = os.environ.get("REPORTING_SNAPSHOT_DIR", "data/eval")
    os.makedirs(output_dir, exist_ok=True)
    snapshot = {
        "week_start": week_start.isoformat(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
    path = os.path.join(output_dir, f"weekly-report-{week_start.isoformat()}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, sort_keys=True, default=str)


@flow(name="extract_weekly_telemetry_events")
def extract_weekly_telemetry_events_flow(week_start: date) -> list[dict[str, Any]]:
    """Extract uncached telemetry events for one requested ISO week."""
    extraction_state = extract_telemetry_events(week_start, return_state=True)
    return extraction_state.result(raise_on_failure=True)


@flow(name="transform_weekly_office_program_performance")
def transform_weekly_office_program_performance_flow(
    events: list[dict[str, Any]], week_start: date,
) -> dict[str, Any]:
    """Validate and aggregate telemetry into weekly office/programme KPIs."""
    transform_state = transform_weekly_office_program_performance(
        events, week_start, return_state=True,
    )
    return transform_state.result(raise_on_failure=True)


@flow(name="load_weekly_office_program_performance")
def load_weekly_office_program_performance_flow(
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Persist weekly office/programme KPI rows using the existing atomic upsert task."""
    load_state = load_weekly_office_program_performance(rows, return_state=True)
    return load_state.result(raise_on_failure=True)


@flow(name=PIPELINE_NAME)
def weekly_office_program_performance_flow(
    week_start: date | None = None,
    trigger_type: str = "manual",
) -> dict[str, Any]:
    """Run weekly business ETL with durable run metadata and explicit failure states."""
    logger = get_run_logger()
    requested_at = datetime.now(timezone.utc)
    if week_start is None:
        # A scheduled run computes the most recently closed ISO week.
        previous_week = requested_at.date() - timedelta(days=requested_at.weekday() + 7)
        week_start = previous_week
    _iso_week_bounds(week_start)
    if trigger_type not in {"scheduled", "manual"}:
        raise ValueError("trigger_type must be 'scheduled' or 'manual'")

    run_id = _create_run(week_start, trigger_type)
    processed = rejected = inserted = updated = 0
    try:
        extracted = extract_weekly_telemetry_events_flow(week_start)
        transformed = transform_weekly_office_program_performance_flow(extracted, week_start)
        processed = transformed["records_processed"]
        rejected = transformed["records_rejected"]

        # Critical ETL states are consumed explicitly; failures are re-raised.
        loaded = load_weekly_office_program_performance_flow(transformed["rows"])
        inserted, updated = loaded["records_inserted"], loaded["records_updated"]

        # Secondary snapshot is best-effort, but its failure is recorded and does not hide ETL success.
        snapshot_state = capture_optional_snapshot(
            {"records_processed": processed, "records_rejected": rejected},
            week_start,
            return_state=True,
        )
        if not snapshot_state.is_completed():
            logger.warning("Optional reporting snapshot failed")
            _finish_run(
                run_id, "completed", records_processed=processed,
                records_inserted=inserted, records_updated=updated,
                records_rejected=rejected,
                error_message="Optional reporting snapshot failed",
            )
            return {"run_id": run_id, "status": "completed", "snapshot_error": "Optional reporting snapshot failed"}

        _finish_run(
            run_id, "completed", records_processed=processed,
            records_inserted=inserted, records_updated=updated,
            records_rejected=rejected,
        )
        return {
            "run_id": run_id,
            "status": "completed",
            "records_processed": processed,
            "records_rejected": rejected,
            "records_inserted": inserted,
            "records_updated": updated,
        }
    except Exception as exc:
        logger.exception("Business reporting run failed")
        try:
            _finish_run(
                run_id, "failed", records_processed=processed,
                records_inserted=inserted, records_updated=updated,
                records_rejected=rejected,
                error_message=f"{type(exc).__name__}: pipeline execution failed",
            )
        except Exception:
            logger.exception("Unable to persist failed pipeline run metadata")
        # Re-raise: a failed critical stage must remain a failed Prefect flow.
        raise


def main(argv: list[str] | None = None) -> int:
    """CLI entry point, also callable from tests and other working directories."""
    import argparse

    parser = argparse.ArgumentParser(description="Run weekly business reporting ETL")
    parser.add_argument(
        "--week-start",
        type=date.fromisoformat,
        help="ISO week Monday (YYYY-MM-DD); defaults to the most recently closed week",
    )
    parser.add_argument(
        "--trigger-type",
        choices=("scheduled", "manual"),
        default="manual",
    )
    arguments = parser.parse_args(argv)
    weekly_office_program_performance_flow(arguments.week_start, arguments.trigger_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())