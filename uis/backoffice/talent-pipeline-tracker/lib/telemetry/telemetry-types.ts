/**
 * Telemetry type definitions for frontend event tracking.
 *
 * These types define the contract for telemetry events that will be sent
 * to the backend POST /api/telemetry/events endpoint.
 */

/**
 * CloudEvents 1.0 envelope for a telemetry event.
 * https://cloudevents.io/
 */
export interface TelemetryEvent {
  specversion: "1.0";
  source: string; // e.g., "/nexova/inventory", "/nexova/auth", "/nexova/frontend"
  id: string; // UUID v4 (idempotency key)
  type: string; // event_type from catalog
  time: string; // RFC 3339 timestamp
  datacontenttype: "application/json";
  data: Record<string, unknown>; // Event-specific payload
  traceparent?: string; // Optional W3C Trace Context
  sessionId?: string; // Extension attribute: session identifier
  schemaVersion?: string; // Extension attribute: schema version
}

/**
 * Batch of telemetry events to send to backend.
 */
export interface TelemetryBatch {
  events: TelemetryEvent[];
}

/**
 * Response from backend POST /api/telemetry/events.
 */
export interface TelemetryResponse {
  received: number;
}

/**
 * Session context for telemetry.
 */
export interface TelemetrySessionContext {
  sessionId: string; // UUID generated at login
  userId?: string; // user.id (integer, as string) or user_uuid (UUID)
  isAuthenticated: boolean;
}

/**
 * Telemetry service configuration.
 */
export interface TelemetryServiceConfig {
  endpoint: string; // URL to POST /api/telemetry/events
  batchIntervalMs: number; // Interval to flush queue (ms)
  batchSizeMax: number; // Max events before auto-flush
  retryAttempts: number; // Number of retry attempts
  retryBackoffMs: number; // Initial backoff (exponential)
  requestTimeoutMs: number; // Fetch timeout (ms)
  enableLogging: boolean; // Log to console (dev only)
}

/**
 * Internal queue entry for an event.
 */
export interface QueueEntry {
  event: TelemetryEvent;
  retries: number;
  lastAttemptAt?: number;
}
