"""Allowlisted projection of telemetry payloads into PostgreSQL JSONB tags."""

from __future__ import annotations

from typing import Any


# Derived from docs/telemetry/event-schemas.json. Keeping the allowlist in the
# backend avoids loading repository documentation as a runtime dependency.
EVENT_TAG_ALLOWLIST: dict[str, frozenset[str]] = {
    "inbound_order_created": frozenset({"product_id", "product_sku", "product_category", "programme_id", "quantity", "supplier", "office", "currency", "unit_cost", "user_uuid"}),
    "outbound_order_created": frozenset({"product_id", "product_sku", "product_category", "programme_id", "quantity", "exit_type", "office", "currency", "user_uuid"}),
    "stock_threshold_triggered": frozenset({"product_id", "product_sku", "product_category", "programme_id", "office", "current_stock", "threshold", "stock_level"}),
    "direct_stock_edit_rejected": frozenset({"product_id", "product_sku", "attempted_action", "reason", "user_uuid"}),
    "kit_cost_variance_detected": frozenset({"product_id", "product_sku", "product_category", "programme_id", "kit_composition", "expected_cost", "actual_cost", "variance_percent", "currency", "office"}),
    "login_succeeded": frozenset({"user_uuid"}),
    "login_failed": frozenset({"user_uuid", "failure_reason"}),
    "account_created": frozenset({"user_uuid"}),
    "session_expired": frozenset({"user_uuid", "session_duration_seconds"}),
    "api_request_completed": frozenset({"method", "path", "status_code", "duration_ms"}),
    "unhandled_api_error": frozenset({"method", "path", "status_code", "error_type", "error_message"}),
    "frontend_render_error": frozenset({"component", "error_type", "error_message"}),
    "frontend_page_loaded": frozenset({"path", "page_load_ms", "user_uuid"}),
    "form_validation_failed": frozenset({"form_id", "field", "validation_error", "instance_id"}),
    "section_viewed": frozenset({"section_id", "user_uuid", "time_on_section_ms"}),
    "form_abandoned": frozenset({"form_id", "instance_id", "abandon_reason", "time_open_ms", "last_section"}),
    "candidate_record_created": frozenset({"candidate_id", "programme_id", "source"}),
    "incident_analysis_completed": frozenset({"analysis_id", "incident_count", "top_category", "analysis_duration_ms"}),
    "incident_status_changed": frozenset({"incident_id", "from_status", "to_status", "category", "origin", "branch", "user_uuid"}),
    "supplier_rate_updated": frozenset({"supplier_id", "supplier_name", "old_rate", "new_rate", "currency", "country"}),
    "form_opened": frozenset({"form_id", "instance_id", "user_uuid"}),
}


def filter_tags(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Return only the documented payload dimensions for one event type."""

    allowed_keys = EVENT_TAG_ALLOWLIST.get(event_type, frozenset())
    return {key: value for key, value in data.items() if key in allowed_keys}
