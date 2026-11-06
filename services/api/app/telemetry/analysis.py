"""Independent metric analysis functions for telemetry.

Each function follows the pipeline:
    **cargar (SQL) → refine (Pandas) → convert types → group → aggregate**

- *cargar*: Data loaded externally via ``load_events()`` in ``report.py``.
- *refine*: Filter rows to the relevant event type(s).
- *convert types*: Ensure ``timestamp`` is ``datetime`` with ``utc=True``,
  numeric columns are cast, etc.
- *group*: Create a grouped structure by a meaningful dimension.
- *aggregate*: Compute the metric within each group.

Each function returns ``list[dict]`` — directly serializable to JSON.

Each metric answers a **technical / operational question** about the system,
not a business question, and has at least one **grouping dimension**.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# A1 — Login success rate by day
# ---------------------------------------------------------------------------


def compute_login_rates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Login success rate grouped by day.

    Pipeline
    --------
    cargar (SQL via ``load_events``) → refine (filter login events) →
    convert types (timestamp → utc datetime) → group (by *date*) →
    aggregate (count succeeded / failed, compute rate %)

    Technical question
    ------------------
    *What percentage of login attempts succeed each day?*

    Grouping dimension
    ------------------
    ``date`` (derived from ``timestamp``).
    """
    # --- refine ---
    login_mask = df["event_type"].isin({"login_succeeded", "login_failed"})
    login_df = df[login_mask].copy()

    if login_df.empty:
        return []

    # --- convert types ---
    login_df["timestamp"] = pd.to_datetime(login_df["timestamp"], utc=True)

    # --- group (temporal — must be after utc=True conversion) ---
    login_df["date"] = login_df["timestamp"].dt.date
    login_df["is_success"] = login_df["event_type"] == "login_succeeded"
    login_df["is_failure"] = login_df["event_type"] == "login_failed"

    # --- aggregate (single chained Pandas — no loops) ---
    grouped = (
        login_df.groupby("date")
        .agg(
            login_succeeded=("is_success", "sum"),
            login_failed=("is_failure", "sum"),
        )
        .reset_index()
    )
    grouped["total_attempts"] = grouped["login_succeeded"] + grouped["login_failed"]
    grouped["success_rate_pct"] = round(
        grouped["login_succeeded"] / grouped["total_attempts"] * 100, 1
    ).fillna(0.0).replace([float("inf"), float("nan")], 0.0)
    # Cast numeric count columns to int for JSON serialization
    for col in ("login_succeeded", "login_failed", "total_attempts"):
        grouped[col] = grouped[col].astype(int)
    grouped["date"] = grouped["date"].astype(str)
    grouped.rename(columns={"date": "dimension_value"}, inplace=True)
    grouped.insert(0, "dimension", "date")
    return grouped.to_dict(orient="records")


# ---------------------------------------------------------------------------
# A2 — API error rate by endpoint (path)
# ---------------------------------------------------------------------------


def compute_api_error_rates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """API error rate per endpoint.

    Pipeline
    --------
    cargar (SQL) → refine (api_request_completed + unhandled_api_error) →
    convert types (timestamp → utc, numeric) → group (by *path*) →
    aggregate (error count / total, compute rate %)

    Technical question
    ------------------
    *Which API endpoints have the highest error rate?*

    Grouping dimension
    ------------------
    ``tag_path`` (endpoint path).
    """
    # --- refine ---
    api_events = df[df["event_type"].isin({"api_request_completed", "unhandled_api_error"})].copy()

    if api_events.empty or "tag_path" not in api_events.columns:
        return []

    # --- convert types ---
    api_events["timestamp"] = pd.to_datetime(api_events["timestamp"], utc=True)

    # --- group & aggregate (single chained Pandas — no loops) ---
    api_events["is_error"] = api_events["event_type"] == "unhandled_api_error"
    grouped = (
        api_events.groupby("tag_path")
        .agg(total_requests=("event_id", "count"), errors=("is_error", "sum"))
        .reset_index()
    )
    grouped["error_rate_pct"] = round(grouped["errors"] / grouped["total_requests"] * 100, 2).fillna(0.0).replace([float("inf"), float("nan")], 0.0)
    grouped.rename(columns={"tag_path": "dimension_value"}, inplace=True)
    grouped.insert(0, "dimension", "path")
    # Cast numeric count columns to int for JSON serialization
    for col in ("total_requests", "errors"):
        grouped[col] = grouped[col].astype(int)
    return grouped.to_dict(orient="records")


# ---------------------------------------------------------------------------
# A3 — API latency percentiles by endpoint (path)
# ---------------------------------------------------------------------------


def compute_api_latency(df: pd.DataFrame) -> list[dict[str, Any]]:
    """API latency percentiles (P50, P95, P99) per endpoint.

    Pipeline
    --------
    cargar (SQL) → refine (api_request_completed) → convert types
    (timestamp → utc, duration_ms → numeric) → group (by *path*) →
    aggregate (describe → percentiles)

    Technical question
    ------------------
    *How does API latency vary across endpoints?*

    Grouping dimension
    ------------------
    ``tag_path`` (endpoint path).
    """
    # --- refine ---
    api_df = df[df["event_type"] == "api_request_completed"].copy()

    if api_df.empty or "tag_duration_ms" not in api_df.columns:
        return []

    # --- convert types ---
    api_df["timestamp"] = pd.to_datetime(api_df["timestamp"], utc=True)
    api_df["tag_duration_ms"] = pd.to_numeric(api_df["tag_duration_ms"], errors="coerce")
    api_df = api_df.dropna(subset=["tag_duration_ms"])

    if api_df.empty or "tag_path" not in api_df.columns:
        return []

    # --- group & aggregate (single chained Pandas — no loops) ---
    grouped = (
        api_df.groupby("tag_path")["tag_duration_ms"]
        .describe(percentiles=[0.5, 0.95, 0.99])
        .round(1)
        .reset_index()
    )
    grouped.rename(
        columns={
            "tag_path": "dimension_value",
            "50%": "p50",
            "95%": "p95",
            "99%": "p99",
        },
        inplace=True,
    )
    grouped.insert(0, "dimension", "path")
    grouped["count"] = grouped["count"].astype(int)
    # Replace any NaN in percentiles with 0.0 for safe JSON serialization
    for col in ("mean", "p50", "p95", "p99"):
        grouped[col] = grouped[col].fillna(0.0)
    return grouped[["dimension", "dimension_value", "count", "mean", "p50", "p95", "p99"]].to_dict(
        orient="records"
    )


# ---------------------------------------------------------------------------
# A4 — Form validation errors by form
# ---------------------------------------------------------------------------


def compute_form_validation_rates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Form validation failure rate per form.

    Pipeline
    --------
    cargar (SQL) → refine (form_opened + form_validation_failed) →
    convert types (timestamp → utc) → group (by *form_id*) →
    aggregate (count opens & failures, compute validation failure rate %)

    Technical question
    ------------------
    *Which forms have the highest validation failure rate?*

    Grouping dimension
    ------------------
    ``tag_form_id`` (form identifier).
    """
    # --- refine ---
    form_events = df[df["event_type"].isin({"form_opened", "form_validation_failed"})].copy()

    if form_events.empty or "tag_form_id" not in form_events.columns:
        return []

    # --- convert types ---
    form_events["timestamp"] = pd.to_datetime(form_events["timestamp"], utc=True)

    # --- group & aggregate (single chained Pandas — no loops) ---
    form_events["is_failure"] = form_events["event_type"] == "form_validation_failed"
    # Also get form_opens for denominator
    form_events["is_open"] = form_events["event_type"] == "form_opened"

    grouped = (
        form_events.groupby("tag_form_id")
        .agg(
            form_opens=("is_open", "sum"),
            validation_failures=("is_failure", "sum"),
        )
        .reset_index()
    )
    grouped["validation_failure_rate_pct"] = round(
        grouped["validation_failures"] / grouped["form_opens"] * 100, 2
    ).fillna(0.0).replace([float("inf"), float("nan")], 0.0)
    grouped.rename(columns={"tag_form_id": "dimension_value"}, inplace=True)
    grouped.insert(0, "dimension", "form_id")
    # Cast numeric count columns to int for JSON serialization
    for col in ("form_opens", "validation_failures"):
        grouped[col] = grouped[col].astype(int)
    return grouped.to_dict(orient="records")


# ---------------------------------------------------------------------------
# A5 — Section engagement by section
# ---------------------------------------------------------------------------


def compute_section_engagement(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Section view count per section.

    Pipeline
    --------
    cargar (SQL) → refine (section_viewed) → convert types (timestamp → utc) →
    group (by *section_id*) → aggregate (count views)

    Technical question
    ------------------
    *Which sections of the application are viewed the most?*

    Grouping dimension
    ------------------
    ``tag_section_id`` (section identifier).
    """
    # --- refine ---
    section_df = df[df["event_type"] == "section_viewed"].copy()

    if section_df.empty or "tag_section_id" not in section_df.columns:
        return []

    # --- convert types ---
    section_df["timestamp"] = pd.to_datetime(section_df["timestamp"], utc=True)

    # --- group & aggregate (single chained Pandas — no loops) ---
    grouped = (
        section_df.groupby("tag_section_id")
        .agg(views=("event_id", "count"))
        .reset_index()
        .sort_values("views", ascending=False)
    )
    grouped.rename(columns={"tag_section_id": "dimension_value"}, inplace=True)
    grouped.insert(0, "dimension", "section_id")
    grouped["views"] = grouped["views"].astype(int)
    return grouped.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Registry — used by build_report to auto-compute all metrics
# ---------------------------------------------------------------------------

METRIC_FUNCTIONS: list[tuple[str, Any]] = [
    ("a1", compute_login_rates),
    ("a2", compute_api_error_rates),
    ("a3", compute_api_latency),
    ("a4", compute_form_validation_rates),
    ("a5", compute_section_engagement),
]