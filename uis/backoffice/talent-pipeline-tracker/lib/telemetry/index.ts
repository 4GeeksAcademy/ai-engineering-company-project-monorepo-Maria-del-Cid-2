/**
 * Export barrel for telemetry module.
 */

export { TelemetryService } from "./telemetry-service.ts";
export type {
  TelemetryEvent,
  TelemetryBatch,
  TelemetryResponse,
  TelemetrySessionContext,
  TelemetryServiceConfig,
  QueueEntry,
} from "./telemetry-types.ts";
export { TELEMETRY_DEFAULTS, EVENT_SOURCE_MAP, APPROVED_FRONTEND_EVENTS } from "./telemetry-constants.ts";
export { sendTelemetryBatch, sendTelemetryBatchViaBeacon } from "./telemetry-client.ts";
