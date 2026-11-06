/**
 * Types describing the System Analytics (telemetry) report returned by the
 * backend GET /api/telemetry/report endpoint. Mirrors the shape produced by
 * ``services/api/app/telemetry/report.py`` compute_metrics().
 */

export interface TelemetryDateRange {
  start: string;
  end: string;
}

export interface TelemetryA1 {
  login_succeeded: number;
  login_failed: number;
  total_attempts: number;
  success_rate: number | null;
  success_rate_pct: number | null;
}

export interface TelemetryA2 {
  api_requests: number;
  api_errors: number;
  error_rate_pct: number | null;
}

export interface TelemetryA3 {
  count: number;
  p50: number;
  p95: number;
  p99: number;
  mean: number;
  min: number;
  max: number;
}

export interface TelemetryEndpointLatency {
  path: string;
  count: number;
  mean: number;
  p50: number;
  p95: number;
  p99: number;
}

export interface TelemetryA4 {
  form_validations_failed: number;
  form_opens: number;
  validation_rate_pct: number | null;
}

export interface TelemetryA5 {
  total_section_views: number;
}

export interface TelemetryA5BySection {
  [sectionId: string]: { count: number };
}

export interface TelemetryA6 {
  form_abandoned: number;
  form_opens: number;
  abandonment_rate_pct: number | null;
}

export interface TelemetryA7 {
  accounts_created: number;
}

export interface TelemetryA8 {
  total_inbound_orders: number;
  has_cost_data?: boolean;
  avg_cost_per_unit?: number;
  total_cost?: number;
}

export interface TelemetryA9 {
  stock_thresholds_triggered: number;
}

export interface TelemetryA10 {
  supplier_rate_updates: number;
  avg_variance_pct?: number;
  max_variance_pct?: number;
}

export interface TelemetryA11 {
  incident_status_changes: number;
}

export interface TelemetryReport {
  report_generated_at: string;
  total_events: number;
  empty: boolean;
  date_range?: TelemetryDateRange;
  event_type_distribution?: Record<string, number>;
  a1?: TelemetryA1;
  a2?: TelemetryA2;
  a3?: TelemetryA3 | null;
  a3_by_endpoint?: TelemetryEndpointLatency[];
  a4?: TelemetryA4;
  a4_by_form?: Record<string, number>;
  a5?: TelemetryA5;
  a5_by_section?: TelemetryA5BySection;
  a6?: TelemetryA6;
  a7?: TelemetryA7;
  a8?: TelemetryA8;
  a9?: TelemetryA9;
  a10?: TelemetryA10;
  a11?: TelemetryA11;
}
