/**
 * Telemetry constants and configuration.
 */

/**
 * Base URL for telemetry API calls, derived from the ingestion endpoint.
 */
const TELEMETRY_API_BASE = (process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT || "http://localhost:8000/api/telemetry/events").replace(/\/events$/, "");

export const TELEMETRY_REPORT_ENDPOINT = `${TELEMETRY_API_BASE}/report`;

export const TELEMETRY_DEFAULTS = {
  // Endpoint where events are sent
  ENDPOINT: process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT || "http://localhost:8000/api/telemetry/events",

  // Batching configuration
  BATCH_INTERVAL_MS: 10_000, // Flush every 10 seconds
  BATCH_SIZE_MAX: 20, // Or when 20 events accumulated

  // Retry configuration
  RETRY_ATTEMPTS: 3, // Max retry attempts
  RETRY_BACKOFF_MS: 1_000, // Start with 1s, exponential: 2s, 4s

  // Request timeout
  REQUEST_TIMEOUT_MS: 5_000, // 5 second timeout

  // Enable debug logging
  ENABLE_LOGGING: process.env.NODE_ENV === "development",

  // Session timeout (inactivity)
  SESSION_TIMEOUT_MS: 30 * 60 * 1_000, // 30 minutes

  // Form heartbeat interval (for form_abandoned detection)
  FORM_HEARTBEAT_INTERVAL_MS: 30_000, // 30 seconds

  // Form inactivity timeout (before sending form_abandoned)
  FORM_INACTIVITY_TIMEOUT_MS: 60_000, // 60 seconds

  // Schema version for events
  SCHEMA_VERSION: "1.0.0",
} as const;

/**
 * Event source mapping - maps event types to their source URI.
 */
export const EVENT_SOURCE_MAP: Record<string, string> = {
  // Inventory events
  inbound_order_created: "/nexova/inventory",
  outbound_order_created: "/nexova/inventory",
  stock_threshold_triggered: "/nexova/inventory",
  direct_stock_edit_rejected: "/nexova/inventory",
  kit_cost_variance_detected: "/nexova/inventory",

  // Auth events
  login_succeeded: "/nexova/auth",
  login_failed: "/nexova/auth",
  account_created: "/nexova/auth",
  session_expired: "/nexova/auth",

  // Infrastructure events
  api_request_completed: "/nexova/infra",
  unhandled_api_error: "/nexova/infra",

  // Frontend events
  frontend_render_error: "/nexova/frontend",
  frontend_page_loaded: "/nexova/frontend",
  form_validation_failed: "/nexova/frontend",
  section_viewed: "/nexova/frontend",
  form_opened: "/nexova/frontend",
  form_abandoned: "/nexova/frontend",

  // Talent events
  candidate_record_created: "/nexova/talent",

  // Incidents events
  incident_analysis_completed: "/nexova/incidents",
  incident_status_changed: "/nexova/incidents",

  // Suppliers events
  supplier_rate_updated: "/nexova/suppliers",
};

/**
 * Approved event types from telemetry plan.
 * Frontend-captureable events only (13 + 1 auxiliary).
 */
export const APPROVED_FRONTEND_EVENTS = {
  // Auth
  login_succeeded: true,
  login_failed: true,
  account_created: true,
  session_expired: true,

  // Frontend UI
  frontend_render_error: true,
  frontend_page_loaded: true,
  form_validation_failed: true,
  section_viewed: true,
  form_opened: true,
  form_abandoned: true,

  // Inventory (from client context)
  inbound_order_created: true,
  outbound_order_created: true,
  stock_threshold_triggered: true,

  // Incidents (from client context)
  incident_status_changed: true,

  // Suppliers (from client context)
  supplier_rate_updated: true,
} as const;

/**
 * Approved event types from telemetry plan - backend only.
 * These events should NOT be emitted from frontend.
 */
export const BACKEND_ONLY_EVENTS = {
  api_request_completed: true,
  unhandled_api_error: true,
  incident_analysis_completed: true,
} as const;
