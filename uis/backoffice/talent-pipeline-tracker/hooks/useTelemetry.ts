/**
 * React hook for initializing and using TelemetryService.
 */

"use client";

import { useEffect } from "react";
import { TelemetryService } from "../lib/telemetry/telemetry-service.ts";

/**
 * Initialize telemetry service on component mount.
 * This hook should only be used once in the app (e.g., in root layout).
 */
export function useTelemetryInit(): void {
  useEffect(() => {
    const service = TelemetryService.getInstance();
    service.initialize();

    return () => {
      service.destroy();
    };
  }, []);
}

/**
 * Get telemetry service instance for tracking events.
 * Only works after TelemetryService has been initialized.
 */
export function useTelemetry(): TelemetryService {
  return TelemetryService.getInstance();
}
