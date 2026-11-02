/**
 * HTTP client for sending telemetry events to backend.
 */

import type { TelemetryBatch, TelemetryResponse } from "./telemetry-types.ts";

/**
 * Send a batch of telemetry events to the backend.
 *
 * @param endpoint - URL of the telemetry endpoint
 * @param batch - Batch of events to send
 * @param timeoutMs - Request timeout in milliseconds
 * @returns Number of events received by backend, or null if failed
 */
export async function sendTelemetryBatch(
  endpoint: string,
  batch: TelemetryBatch,
  timeoutMs: number = 5000,
): Promise<number | null> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(batch),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      console.error(
        `[Telemetry] Send failed: HTTP ${response.status}`,
      );
      return null;
    }

    const data: TelemetryResponse = await response.json();
    return data.received;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      console.error(`[Telemetry] Send timeout after ${timeoutMs}ms`);
    } else {
      console.error("[Telemetry] Send failed:", error);
    }
    return null;
  }
}

/**
 * Send a batch using Navigator.sendBeacon (best-effort, no response).
 * Used when page is unloading.
 *
 * @param endpoint - URL of the telemetry endpoint
 * @param batch - Batch of events to send
 * @returns true if sendBeacon queued the request, false otherwise
 */
export function sendTelemetryBatchViaBeacon(
  endpoint: string,
  batch: TelemetryBatch,
): boolean {
  if (!navigator.sendBeacon) {
    console.warn("[Telemetry] navigator.sendBeacon not available");
    return false;
  }

  try {
    const blob = new Blob([JSON.stringify(batch)], {
      type: "application/json",
    });
    return navigator.sendBeacon(endpoint, blob);
  } catch (error) {
    console.error("[Telemetry] sendBeacon failed:", error);
    return false;
  }
}
