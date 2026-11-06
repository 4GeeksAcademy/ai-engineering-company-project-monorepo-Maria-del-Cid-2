/**
 * Types describing the System Analytics (telemetry) report returned by the
 * backend GET /api/telemetry/report endpoint.
 *
 * Response structure:
 *   {"period": {"start": ..., "end": ..., "days": N}, "metrics": {...}}
 *
 * Each metric under ``metrics`` is a ``list[dict]`` where every dict has
 * at least ``dimension`` and ``dimension_value`` keys (the grouping
 * dimension), plus metric-specific keys.
 */

// ---------------------------------------------------------------------------
// Period
// ---------------------------------------------------------------------------

export interface TelemetryPeriod {
  start: string;
  end: string;
  days: number;
}

// ---------------------------------------------------------------------------
// Metric dimension rows (each is one group from the analysis functions)
// ---------------------------------------------------------------------------

/** A1 — Login success/failure by day */
export interface TelemetryLoginRateRow {
  dimension: "date";
  dimension_value: string;
  login_succeeded: number;
  login_failed: number;
  total_attempts: number;
  success_rate_pct: number;
}

/** A2 — API error rate by endpoint path */
export interface TelemetryApiErrorRow {
  dimension: "path";
  dimension_value: string;
  total_requests: number;
  errors: number;
  error_rate_pct: number;
}

/** A3 — API latency percentiles by endpoint path */
export interface TelemetryLatencyRow {
  dimension: "path";
  dimension_value: string;
  count: number;
  mean: number;
  p50: number;
  p95: number;
  p99: number;
}

/** A4 — Form validation failure rate by form_id */
export interface TelemetryFormValidationRow {
  dimension: "form_id";
  dimension_value: string;
  form_opens: number;
  validation_failures: number;
  validation_failure_rate_pct: number;
}

/** A5 — Section engagement by section_id */
export interface TelemetrySectionEngagementRow {
  dimension: "section_id";
  dimension_value: string;
  views: number;
}

// ---------------------------------------------------------------------------
// Top-level report
// ---------------------------------------------------------------------------

export interface TelemetryReport {
  period: TelemetryPeriod;
  metrics: {
    a1: TelemetryLoginRateRow[];
    a2: TelemetryApiErrorRow[];
    a3: TelemetryLatencyRow[];
    a4: TelemetryFormValidationRow[];
    a5: TelemetrySectionEngagementRow[];
    [key: string]: unknown[];
  };
}
