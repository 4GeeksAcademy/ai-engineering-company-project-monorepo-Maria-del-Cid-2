"""Unit tests for weekly office/programme KPI transformation."""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parents[3] / "data" / "pipelines"
sys.path.insert(0, str(PIPELINE_DIR))

import pipeline  # noqa: E402

WEEK_START = date(2026, 11, 2)


def telemetry_event(
    event_id: str,
    event_type: str,
    *,
    office: str = "Valencia",
    programme_id: str = "programme-a",
    timestamp: str = "2026-11-03T12:00:00+00:00",
    **tags: object,
) -> dict[str, object]:
    """Build an event using the envelope and tags stored in telemetry_events."""
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "tags": {"office": office, "programme_id": programme_id, **tags},
    }


@pytest.fixture
def business_telemetry_events() -> list[dict[str, object]]:
    """In-memory source events spanning both canonical offices and all four KPIs."""
    return [
        telemetry_event(
            "val-in-1", "inbound_order_created", currency="EUR", quantity=3,
            unit_cost="2.50",
        ),
        telemetry_event(
            "val-in-2", "inbound_order_created", currency="EUR", quantity=2,
            unit_cost="1.25",
        ),
        telemetry_event(
            "val-out-1", "outbound_order_created", quantity=7, exit_type="allocation",
        ),
        telemetry_event(
            "val-out-2", "outbound_order_created", quantity=2, exit_type="allocation",
        ),
        telemetry_event(
            "val-short-1", "stock_threshold_triggered", product_id=3, threshold=2,
            current_stock=1, stock_level="low",
        ),
        telemetry_event(
            "val-variance-1", "kit_cost_variance_detected", currency="EUR",
            product_id=8, expected_cost="10", actual_cost="12", variance_percent="20",
        ),
        telemetry_event(
            "mia-in-1", "inbound_order_created", office="Miami", programme_id="programme-b",
            currency="USD", quantity=4, unit_cost="3.00",
        ),
        telemetry_event(
            "mia-out-1", "outbound_order_created", office="Miami", programme_id="programme-b",
            quantity=12, exit_type="allocation",
        ),
    ]


def test_transform_computes_all_kpis_per_office_without_mixing_currencies(
    business_telemetry_events: list[dict[str, object]],
) -> None:
    result = pipeline.transform_weekly_office_program_performance.fn(
        business_telemetry_events, WEEK_START,
    )

    assert result["records_processed"] == 8
    assert result["records_rejected"] == 0
    assert result["rows"] == [
        {
            "office": "Valencia",
            "programme_id": "programme-a",
            "week_start": WEEK_START,
            # Manual: (3 × EUR 2.50) + (2 × EUR 1.25) = EUR 10.00.
            "total_material_cost": Decimal("10.00"),
            # Two valid outbound events, even though their quantities total 9.
            "kits_delivered_count": 2,
            "shortage_events_count": 1,
            "cost_variance_events_count": 1,
            "currency": "EUR",
        },
        {
            "office": "Miami",
            "programme_id": "programme-b",
            "week_start": WEEK_START,
            # Manual: 4 × USD 3.00 = USD 12.00; not combined with Valencia's EUR.
            "total_material_cost": Decimal("12.00"),
            "kits_delivered_count": 1,
            "shortage_events_count": 0,
            "cost_variance_events_count": 0,
            "currency": "USD",
        },
    ]


def test_transform_counts_outbound_events_not_units() -> None:
    events = [
        telemetry_event("out-large", "outbound_order_created", quantity=100, exit_type="allocation"),
        telemetry_event("out-small", "outbound_order_created", quantity=1, exit_type="allocation"),
    ]

    result = pipeline.transform_weekly_office_program_performance.fn(events, WEEK_START)

    assert result["rows"][0]["kits_delivered_count"] == 2
    assert result["rows"][0]["currency"] == "EUR"


def test_transform_accepts_utc_week_start_and_rejects_exclusive_week_end() -> None:
    events = [
        telemetry_event(
            "at-week-start", "outbound_order_created", quantity=1, exit_type="allocation",
            timestamp="2026-11-02T00:00:00+00:00",
        ),
        telemetry_event(
            "before-week-end", "stock_threshold_triggered", product_id=3, threshold=2,
            current_stock=1, stock_level="low", timestamp="2026-11-08T23:59:59.999999+00:00",
        ),
        telemetry_event(
            "at-exclusive-week-end", "kit_cost_variance_detected", currency="EUR",
            product_id=8, expected_cost="10", actual_cost="12", variance_percent="20",
            timestamp="2026-11-09T00:00:00+00:00",
        ),
    ]

    result = pipeline.transform_weekly_office_program_performance.fn(events, WEEK_START)

    assert result["records_processed"] == 3
    assert result["records_rejected"] == 1
    row = result["rows"][0]
    assert row["kits_delivered_count"] == 1
    assert row["shortage_events_count"] == 1
    assert row["cost_variance_events_count"] == 0


def test_transform_rejects_malformed_dimensions_and_incoherent_currency() -> None:
    events = [
        {
            "event_id": "malformed-tags",
            "event_type": "outbound_order_created",
            "timestamp": "2026-11-03T12:00:00+00:00",
            "tags": ["not", "an", "object"],
        },
        telemetry_event(
            "missing-programme", "outbound_order_created", programme_id="",
            quantity=1, exit_type="allocation",
        ),
        telemetry_event(
            "wrong-office-currency", "inbound_order_created", currency="USD",
            quantity=1, unit_cost="1.00",
        ),
        telemetry_event(
            "nonfinite-quantity", "inbound_order_created", currency="EUR",
            quantity="NaN", unit_cost="1.00",
        ),
        telemetry_event(
            "noncanonical-office", "stock_threshold_triggered", office="valencia",
            product_id=3, threshold=2, current_stock=1, stock_level="low",
        ),
    ]

    result = pipeline.transform_weekly_office_program_performance.fn(events, WEEK_START)

    assert result == {"rows": [], "records_processed": 5, "records_rejected": 5}


def test_transform_assigns_office_currency_when_only_shortage_event_exists() -> None:
    events = [
        telemetry_event(
            "mia-shortage", "stock_threshold_triggered", office="Miami",
            programme_id="programme-c", product_id=9, threshold=4,
            current_stock=3, stock_level="low",
        ),
    ]

    result = pipeline.transform_weekly_office_program_performance.fn(events, WEEK_START)

    assert result["records_rejected"] == 0
    assert result["rows"] == [
        {
            "office": "Miami",
            "programme_id": "programme-c",
            "week_start": WEEK_START,
            "total_material_cost": Decimal("0.00"),
            "kits_delivered_count": 0,
            "shortage_events_count": 1,
            "cost_variance_events_count": 0,
            "currency": "USD",
        },
    ]
