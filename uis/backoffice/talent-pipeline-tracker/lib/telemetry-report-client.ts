/**
 * HTTP client for the System Analytics report — GET /api/telemetry/report.
 * Uses the same base URL as the telemetry ingestion client.
 */

import { TELEMETRY_REPORT_ENDPOINT } from "./telemetry/telemetry-constants.ts";
import type { TelemetryReport } from "../types/reports.ts";

export interface TelemetryReportQuery {
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export class TelemetryReportError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly kind: "network" | "timeout" | "http" | "parse" | "cancelled",
  ) {
    super(message);
    this.name = "TelemetryReportError";
  }
}

async function fetchTelemetryReport(
  query: TelemetryReportQuery = {},
  timeoutMs = 15000,
): Promise<TelemetryReport> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const params = new URLSearchParams();
    if (query.start_date) params.set("start_date", query.start_date);
    if (query.end_date) params.set("end_date", query.end_date);
    if (query.limit !== undefined) params.set("limit", String(query.limit));

    const qs = params.toString();
    const url = qs ? `${TELEMETRY_REPORT_ENDPOINT}?${qs}` : TELEMETRY_REPORT_ENDPOINT;

    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new TelemetryReportError(
        `Telemetry report request failed with HTTP ${response.status}`,
        response.status,
        "http",
      );
    }

    return (await response.json()) as TelemetryReport;
  } catch (error) {
    if (error instanceof TelemetryReportError) throw error;
    if (error instanceof Error && error.name === "AbortError") {
      throw new TelemetryReportError(
        `Telemetry report request timed out after ${timeoutMs}ms`,
        0,
        "timeout",
      );
    }
    throw new TelemetryReportError(
      "Unable to reach the telemetry report API",
      0,
      "network",
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Fetch the System Analytics report for the dashboard.
 */
export async function getTelemetryReport(
  query: TelemetryReportQuery = {},
): Promise<TelemetryReport> {
  return fetchTelemetryReport(query);
}
