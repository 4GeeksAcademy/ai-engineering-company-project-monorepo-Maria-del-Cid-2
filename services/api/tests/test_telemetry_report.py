"""Tests for the Pandas analytics pipeline (``app.telemetry.report``).

The pipeline loads data from a real PostgreSQL, but for unit tests we
feed synthetic DataFrames to ``compute_metrics()`` directly.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import pandas as pd

from app.telemetry.report import compute_metrics, generate_dashboard_html


def _make_df(events: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame as it comes from ``load_events``."""
    rows = []
    for ev in events:
        row = {
            "event_id": ev.get("id", "00000000-0000-0000-0000-000000000000"),
            "event_type": ev["type"],
            "timestamp": pd.Timestamp(
                ev.get("time", "2026-11-06T12:00:00Z"), tz=timezone.utc
            ),
            "source": ev.get("source", "/nexova/test"),
            "session_id": ev.get("session_id"),
            "schema_version": ev.get("schema_version", "1.0.0"),
        }
        # Expand tags with prefix
        for key, value in ev.get("tags", {}).items():
            row[f"tag_{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


class ReportMetricsTests(unittest.TestCase):
    """Verify metric computations with known data."""

    def test_empty_dataframe(self) -> None:
        """An empty DataFrame returns an empty report."""
        df = _make_df([])
        report = compute_metrics(df)
        self.assertTrue(report.get("empty"))
        self.assertEqual(report["total_events"], 0)

    def test_a1_login_success_rate(self) -> None:
        """A1: login success rate calculation."""
        df = _make_df([
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_failed", "tags": {}},
        ])
        report = compute_metrics(df)
        a1 = report["a1"]
        self.assertEqual(a1["login_succeeded"], 3)
        self.assertEqual(a1["login_failed"], 1)
        self.assertEqual(a1["success_rate_pct"], 75.0)

    def test_a1_no_login_attempts(self) -> None:
        """A1: no login events returns None."""
        df = _make_df([{"type": "frontend_page_loaded", "tags": {}}])
        report = compute_metrics(df)
        self.assertIsNone(report["a1"]["success_rate_pct"])

    def test_a2_api_error_rate(self) -> None:
        """A2: API error rate calculation."""
        df = _make_df([
            {"type": "api_request_completed", "tags": {"status_code": 200}},
            {"type": "api_request_completed", "tags": {"status_code": 200}},
            {"type": "api_request_completed", "tags": {"status_code": 404}},
            {"type": "unhandled_api_error", "tags": {"status_code": 500}},
        ])
        report = compute_metrics(df)
        a2 = report["a2"]
        self.assertEqual(a2["api_requests"], 3)
        self.assertEqual(a2["api_errors"], 1)
        # 1 error out of 3 requests ≈ 33.33%
        self.assertAlmostEqual(a2["error_rate_pct"], 33.33, delta=0.01)

    def test_a3_api_latency_percentiles(self) -> None:
        """A3: P50, P95, P99 latency calculation."""
        df = _make_df([
            {"type": "api_request_completed", "tags": {"duration_ms": 10}},
            {"type": "api_request_completed", "tags": {"duration_ms": 20}},
            {"type": "api_request_completed", "tags": {"duration_ms": 30}},
            {"type": "api_request_completed", "tags": {"duration_ms": 100}},
            {"type": "api_request_completed", "tags": {"duration_ms": 200}},
        ])
        report = compute_metrics(df)
        a3 = report["a3"]
        self.assertIsNotNone(a3)
        self.assertEqual(a3["count"], 5)
        self.assertEqual(a3["min"], 10)
        self.assertEqual(a3["max"], 200)

    def test_a3_no_api_events(self) -> None:
        """A3: no API events returns None."""
        df = _make_df([{"type": "login_succeeded", "tags": {}}])
        report = compute_metrics(df)
        self.assertIsNone(report["a3"])

    def test_a3_per_endpoint_latency(self) -> None:
        """A3: latency grouped by endpoint path."""
        df = _make_df([
            {"type": "api_request_completed", "tags": {"duration_ms": 50, "path": "/api/auth/login"}},
            {"type": "api_request_completed", "tags": {"duration_ms": 150, "path": "/api/auth/login"}},
            {"type": "api_request_completed", "tags": {"duration_ms": 300, "path": "/api/inventory/orders"}},
        ])
        report = compute_metrics(df)
        self.assertIn("a3_by_endpoint", report)
        self.assertEqual(len(report["a3_by_endpoint"]), 2)

    def test_a4_form_validation_rate(self) -> None:
        """A4: form validation error rate."""
        df = _make_df([
            {"type": "form_opened", "tags": {"form_id": "inbound"}},
            {"type": "form_opened", "tags": {"form_id": "outbound"}},
            {"type": "form_validation_failed", "tags": {"form_id": "inbound", "field": "quantity"}},
            {"type": "form_validation_failed", "tags": {"form_id": "inbound", "field": "sku"}},
        ])
        report = compute_metrics(df)
        a4 = report["a4"]
        self.assertEqual(a4["form_opens"], 2)
        self.assertEqual(a4["form_validations_failed"], 2)
        self.assertEqual(a4["validation_rate_pct"], 100.0)

    def test_a5_section_views(self) -> None:
        """A5: section engagement counts."""
        df = _make_df([
            {"type": "section_viewed", "tags": {"section_id": "inventory-products"}},
            {"type": "section_viewed", "tags": {"section_id": "inventory-products"}},
            {"type": "section_viewed", "tags": {"section_id": "suppliers-list"}},
        ])
        report = compute_metrics(df)
        self.assertEqual(report["a5"]["total_section_views"], 3)
        self.assertIn("a5_by_section", report)

    def test_a6_form_abandonment(self) -> None:
        """A6: form abandonment rate."""
        df = _make_df([
            {"type": "form_opened", "tags": {"form_id": "inbound"}},
            {"type": "form_opened", "tags": {"form_id": "outbound"}},
            {"type": "form_abandoned", "tags": {"form_id": "inbound"}},
        ])
        report = compute_metrics(df)
        a6 = report["a6"]
        self.assertEqual(a6["form_abandoned"], 1)
        self.assertEqual(a6["form_opens"], 2)
        self.assertEqual(a6["abandonment_rate_pct"], 50.0)

    def test_a7_accounts_created(self) -> None:
        """A7: account creation count."""
        df = _make_df([
            {"type": "account_created", "tags": {}},
            {"type": "account_created", "tags": {}},
        ])
        report = compute_metrics(df)
        self.assertEqual(report["a7"]["accounts_created"], 2)

    def test_a8_inbound_costs(self) -> None:
        """A8: average cost per unit received."""
        df = _make_df([
            {"type": "inbound_order_created", "tags": {"quantity": 10, "unit_cost": 5.0}},
            {"type": "inbound_order_created", "tags": {"quantity": 5, "unit_cost": 8.0}},
        ])
        report = compute_metrics(df)
        a8 = report["a8"]
        self.assertEqual(a8["total_inbound_orders"], 2)
        self.assertTrue(a8["has_cost_data"])
        # total cost = 10*5 + 5*8 = 90, total quantity = 15, avg = 6
        self.assertEqual(a8["avg_cost_per_unit"], 6.0)
        self.assertEqual(a8["total_cost"], 90.0)

    def test_a10_supplier_rate_variance(self) -> None:
        """A10: supplier rate update variance."""
        df = _make_df([
            {"type": "supplier_rate_updated", "tags": {"old_rate": 1000, "new_rate": 1100}},
            {"type": "supplier_rate_updated", "tags": {"old_rate": 2000, "new_rate": 2500}},
        ])
        report = compute_metrics(df)
        a10 = report["a10"]
        self.assertEqual(a10["supplier_rate_updates"], 2)
        # 100->1100 = 10%, 2000->2500 = 25%, avg = 17.5
        self.assertAlmostEqual(a10["avg_variance_pct"], 17.5, delta=0.01)
        self.assertAlmostEqual(a10["max_variance_pct"], 25.0, delta=0.01)

    def test_a11_incident_changes(self) -> None:
        """A11: incident status change count."""
        df = _make_df([
            {"type": "incident_status_changed", "tags": {"incident_id": 1}},
        ])
        report = compute_metrics(df)
        self.assertEqual(report["a11"]["incident_status_changes"], 1)

    def test_event_type_distribution(self) -> None:
        """Report includes event type distribution."""
        df = _make_df([
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_failed", "tags": {}},
        ])
        report = compute_metrics(df)
        dist = report["event_type_distribution"]
        self.assertEqual(dist.get("login_succeeded"), 2)
        self.assertEqual(dist.get("login_failed"), 1)

    def test_report_metadata(self) -> None:
        """Report includes generation timestamp and date range."""
        df = _make_df([
            {"type": "login_succeeded", "time": "2026-11-01T10:00:00Z", "tags": {}},
            {"type": "login_failed", "time": "2026-11-06T12:00:00Z", "tags": {}},
        ])
        report = compute_metrics(df)
        self.assertIn("report_generated_at", report)
        self.assertIn("total_events", report)
        self.assertEqual(report["total_events"], 2)
        dr = report["date_range"]
        self.assertIn("2026-11-01", dr["start"])
        self.assertIn("2026-11-06", dr["end"])


class DashboardHtmlTests(unittest.TestCase):
    """Verify dashboard HTML generation."""

    def test_empty_report_generates_html(self) -> None:
        """Empty report still generates valid HTML."""
        report = {"empty": True, "total_events": 0, "report_generated_at": "2026-11-06T12:00:00"}
        html = generate_dashboard_html(report)
        self.assertIn("No hay datos de telemetría", html)
        self.assertIn("</html>", html)

    def test_full_report_generates_html(self) -> None:
        """Full report generates HTML with metric sections."""
        df = _make_df([
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_failed", "tags": {}},
            {"type": "api_request_completed", "tags": {"duration_ms": 42, "status_code": 200}},
        ])
        report = compute_metrics(df)
        html = generate_dashboard_html(report)
        # Should contain key metric labels
        self.assertIn("A1 — Logins exitosos", html)
        self.assertIn("A2 — Error API", html)
        self.assertIn("A3 — Latencia de API", html)
        self.assertIn("</html>", html)

    def test_html_contains_total_events(self) -> None:
        """HTML includes total event count."""
        df = _make_df([
            {"type": "login_succeeded", "tags": {}},
            {"type": "login_failed", "tags": {}},
        ])
        report = compute_metrics(df)
        html = generate_dashboard_html(report)
        self.assertIn("2</strong> eventos", html)
