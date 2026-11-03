/**
 * TelemetryService - Frontend telemetry event collection and emission.
 *
 * Core responsibilities:
 * 1. Collect events from instrumented components
 * 2. Queue events in memory
 * 3. Batch and send to backend periodically
 * 4. Handle retries with exponential backoff
 * 5. Use sendBeacon for best-effort delivery on page unload
 */

import type {
  QueueEntry,
  TelemetryBatch,
  TelemetryEvent,
  TelemetryServiceConfig,
  TelemetrySessionContext,
} from "./telemetry-types.ts";
import {
  TELEMETRY_DEFAULTS,
  EVENT_SOURCE_MAP,
  APPROVED_FRONTEND_EVENTS,
} from "./telemetry-constants.ts";
import {
  sendTelemetryBatch,
  sendTelemetryBatchViaBeacon,
} from "./telemetry-client.ts";

/**
 * Generate a UUID v4.
 * Uses crypto.randomUUID() if available (modern browsers, Node.js 15.7+).
 */
function generateUUID(): string {
  // Browser crypto API
  if (typeof window !== "undefined" && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }

  // Node.js crypto API (for tests)
  if (typeof global !== "undefined" && global.crypto) {
    return global.crypto.randomUUID();
  }

  // Fallback: Simple UUID v4 implementation
  // xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * TelemetryService - Singleton for telemetry event management.
 */
export class TelemetryService {
  private static instance: TelemetryService | null = null;

  private queue: QueueEntry[] = [];
  private sessionContext: TelemetrySessionContext | null = null;
  private batchTimerId: NodeJS.Timeout | null = null;
  private visibilityChangeListener: ((e: Event) => void) | null = null;
  private beforeUnloadListener: ((e: Event) => void) | null = null;
  private isInitialized = false;
  private isDestroyed = false;
  private config: TelemetryServiceConfig;

  private constructor(config: Partial<TelemetryServiceConfig> = {}) {
    this.config = {
      endpoint: TELEMETRY_DEFAULTS.ENDPOINT,
      batchIntervalMs: TELEMETRY_DEFAULTS.BATCH_INTERVAL_MS,
      batchSizeMax: TELEMETRY_DEFAULTS.BATCH_SIZE_MAX,
      retryAttempts: TELEMETRY_DEFAULTS.RETRY_ATTEMPTS,
      retryBackoffMs: TELEMETRY_DEFAULTS.RETRY_BACKOFF_MS,
      requestTimeoutMs: TELEMETRY_DEFAULTS.REQUEST_TIMEOUT_MS,
      enableLogging: TELEMETRY_DEFAULTS.ENABLE_LOGGING,
      ...config,
    };
  }

  /**
   * Get or create singleton instance.
   */
  public static getInstance(
    config?: Partial<TelemetryServiceConfig>,
  ): TelemetryService {
    if (!TelemetryService.instance) {
      TelemetryService.instance = new TelemetryService(config);
    }
    return TelemetryService.instance;
  }

  /**
   * Reset singleton (for testing only).
   */
  public static resetInstance(): void {
    if (TelemetryService.instance) {
      if (TelemetryService.instance.isInitialized) {
        TelemetryService.instance.destroy();
      }
    }
    TelemetryService.instance = null;
  }

  /**
   * Initialize the service (set up listeners, start batch timer).
   */
  public initialize(): void {
    if (this.isInitialized) {
      this.log("warn", "Service already initialized");
      return;
    }

    // Allow re-initialization after destroy (e.g. React StrictMode remount)
    this.isDestroyed = false;

    // Generate session ID
    this.sessionContext = {
      sessionId: generateUUID(),
      isAuthenticated: false,
    };

    // Only set up listeners in browser environment
    if (typeof window !== "undefined") {
      // Set up visibility change listener
      this.visibilityChangeListener = (e: Event) =>
        this.onVisibilityChange(e as Event);
      document.addEventListener("visibilitychange", this.visibilityChangeListener);

      // Set up before unload listener
      this.beforeUnloadListener = (e: Event) => this.onBeforeUnload(e as Event);
      window.addEventListener("beforeunload", this.beforeUnloadListener);

      // Start batch timer
      this.startBatchTimer();
    }

    this.isInitialized = true;
    this.log("info", "Service initialized");
  }

  /**
   * Destroy the service (remove listeners, cancel timers).
   */
  public destroy(): void {
    if (this.isDestroyed) {
      return;
    }

    // Flush pending events
    this.flush();

    // Remove listeners
    if (this.visibilityChangeListener) {
      document.removeEventListener(
        "visibilitychange",
        this.visibilityChangeListener,
      );
    }
    if (this.beforeUnloadListener) {
      window.removeEventListener("beforeunload", this.beforeUnloadListener);
    }

    // Cancel batch timer
    this.stopBatchTimer();

    this.isDestroyed = true;
    this.isInitialized = false;
    this.log("info", "Service destroyed");
  }

  /**
   * Update session context (e.g., after login).
   */
  public updateSession(session: {
    userId?: string | number;
    userUuid?: string;
    isAuthenticated?: boolean;
  }): void {
    if (!this.sessionContext) {
      this.sessionContext = {
        sessionId: generateUUID(),
        isAuthenticated: false,
      };
    }

    if (session.userUuid) {
      this.sessionContext.userId = session.userUuid;
    } else if (session.userId !== undefined) {
      this.sessionContext.userId = String(session.userId);
    }

    if (session.isAuthenticated !== undefined) {
      this.sessionContext.isAuthenticated = session.isAuthenticated;
    }

    this.log("debug", "Session updated", {
      userId: this.sessionContext.userId,
      isAuthenticated: this.sessionContext.isAuthenticated,
    });
  }

  /**
   * Track a telemetry event.
   *
   * @param eventType - Event type from approved catalog
   * @param properties - Event-specific payload
   */
  public track(
    eventType: string,
    properties: Record<string, unknown> = {},
  ): void {
    if (!this.isInitialized || this.isDestroyed) {
      this.log(
        "warn",
        `Cannot track event: service not initialized or destroyed`,
      );
      return;
    }

    // Validate event type is approved for frontend
    if (
      !Object.prototype.hasOwnProperty.call(APPROVED_FRONTEND_EVENTS, eventType)
    ) {
      this.log("warn", `Event type not approved for frontend: ${eventType}`);
      return;
    }

    // Generate event
    const event = this.createEvent(eventType, properties);

    // Add to queue
    this.queue.push({
      event,
      retries: 0,
    });

    this.log("debug", `Event queued: ${eventType}`, { queueSize: this.queue.length });

    // Check if should flush immediately
    if (this.queue.length >= this.config.batchSizeMax) {
      this.log("debug", "Queue max size reached, flushing");
      this.flush();
    }
  }

  /**
   * Manually flush pending events.
   */
  public async flush(): Promise<void> {
    if (this.queue.length === 0) {
      return;
    }

    const batch: TelemetryBatch = {
      events: this.queue.map((entry) => entry.event),
    };

    this.log("debug", `Flushing ${batch.events.length} events`);

    // Try to send via fetch first
    const received = await sendTelemetryBatch(
      this.config.endpoint,
      batch,
      this.config.requestTimeoutMs,
    );

    if (received !== null) {
      // Success: clear queue
      this.log("info", `Events sent successfully: ${received} received`);
      this.queue = [];
    } else {
      // Fetch failed or timed out - attempt retry
      this.log("debug", "Fetch failed, attempting retries");
      await this.retryQueue();
    }
  }

  /**
   * Retry queue with exponential backoff.
   */
  private async retryQueue(): Promise<void> {
    for (const entry of this.queue) {
      if (entry.retries >= this.config.retryAttempts) {
        this.log(
          "warn",
          `Event discarded after ${entry.retries} retries: ${entry.event.type}`,
        );
        continue;
      }

      entry.retries += 1;

      // Exponential backoff: 1s, 2s, 4s
      const delayMs =
        this.config.retryBackoffMs * Math.pow(2, entry.retries - 1);

      this.log("debug", `Retry ${entry.retries} after ${delayMs}ms`);

      // Wait before retrying
      await new Promise((resolve) => setTimeout(resolve, delayMs));

      const batch: TelemetryBatch = {
        events: [entry.event],
      };

      const received = await sendTelemetryBatch(
        this.config.endpoint,
        batch,
        this.config.requestTimeoutMs,
      );

      if (received !== null) {
        this.log(
          "info",
          `Event sent after ${entry.retries} retries: ${entry.event.type}`,
        );
        // Mark for removal
        entry.retries = this.config.retryAttempts + 1; // Signal removal
      }
    }

    // Remove successfully sent entries
    this.queue = this.queue.filter(
      (entry) => entry.retries <= this.config.retryAttempts,
    );

    if (this.queue.length > 0) {
      this.log(
        "warn",
        `${this.queue.length} events still pending after retries`,
      );
    }
  }

  /**
   * Create a CloudEvents 1.0 envelope for an event.
   */
  private createEvent(
    eventType: string,
    properties: Record<string, unknown>,
  ): TelemetryEvent {
    const now = new Date().toISOString();
    const source = EVENT_SOURCE_MAP[eventType] || "/nexova/frontend";

    return {
      specversion: "1.0",
      source,
      id: generateUUID(),
      type: eventType,
      time: now,
      datacontenttype: "application/json",
      data: properties,
      sessionId: this.sessionContext?.sessionId,
      schemaVersion: TELEMETRY_DEFAULTS.SCHEMA_VERSION,
    };
  }

  /**
   * Batch timer callback - flush queue periodically.
   */
  private onBatchTimer = (): void => {
    if (this.queue.length > 0) {
      this.log("debug", "Batch timer triggered");
      this.flush().catch((error) => {
        this.log("error", "Flush error", error);
      });
    }

    this.startBatchTimer();
  };

  /**
   * Visibility change handler - flush on page hide.
   */
  private onVisibilityChange(e: Event): void {
    if (document.visibilityState === "hidden") {
      this.log("debug", "Page hidden, using sendBeacon");
      this.flushViaBeacon();
    }
  }

  /**
   * Before unload handler - try to send remaining events.
   */
  private onBeforeUnload(e: Event): void {
    this.log("debug", "Before unload, attempting flush");
    this.flushViaBeacon();
  }

  /**
   * Flush pending events via sendBeacon (best-effort).
   */
  private flushViaBeacon(): void {
    if (this.queue.length === 0) {
      return;
    }

    const batch: TelemetryBatch = {
      events: this.queue.map((entry) => entry.event),
    };

    const sent = sendTelemetryBatchViaBeacon(this.config.endpoint, batch);

    if (sent) {
      this.log("info", `Beacon sent: ${batch.events.length} events`);
      this.queue = []; // Clear queue (sendBeacon doesn't guarantee delivery)
    } else {
      this.log("warn", "Beacon send failed");
    }
  }

  /**
   * Start the batch timer.
   */
  private startBatchTimer(): void {
    if (typeof window === "undefined") return;

    this.batchTimerId = setTimeout(this.onBatchTimer, this.config.batchIntervalMs);
  }

  /**
   * Stop the batch timer.
   */
  private stopBatchTimer(): void {
    if (this.batchTimerId) {
      clearTimeout(this.batchTimerId);
      this.batchTimerId = null;
    }
  }

  /**
   * Internal logging utility.
   */
  private log(
    level: "info" | "warn" | "error" | "debug",
    message: string,
    data?: unknown,
  ): void {
    if (!this.config.enableLogging && level === "debug") {
      return;
    }

    const prefix = `[Telemetry:${level.toUpperCase()}]`;
    if (data) {
      console[level](prefix, message, data);
    } else {
      console[level](prefix, message);
    }
  }

  /**
   * Get queue size (for testing/debugging).
   */
  public getQueueSize(): number {
    return this.queue.length;
  }

  /**
   * Get session context (for testing/debugging).
   */
  public getSessionContext(): TelemetrySessionContext | null {
    return this.sessionContext;
  }

  /**
   * Is service initialized (for testing/debugging).
   */
  public isServiceInitialized(): boolean {
    return this.isInitialized;
  }
}
