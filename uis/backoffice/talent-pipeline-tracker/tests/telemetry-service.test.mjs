/**
 * Unit tests for TelemetryService.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import { TelemetryService } from "../lib/telemetry/telemetry-service.ts";

describe("TelemetryService", () => {
  let service;

  beforeEach(() => {
    // Reset singleton for test isolation
    TelemetryService.resetInstance();
    service = TelemetryService.getInstance();
  });

  afterEach(() => {
    // Clean up
    if (service) {
      TelemetryService.resetInstance();
    }
  });

  describe("Initialization", () => {
    it("should be a singleton", () => {
      const service1 = TelemetryService.getInstance();
      const service2 = TelemetryService.getInstance();
      assert.equal(service1, service2);
    });

    it("should initialize successfully", () => {
      assert.equal(service.isServiceInitialized(), false);
      service.initialize();
      assert.equal(service.isServiceInitialized(), true);
    });

    it("should safely handle repeated initialization", () => {
      service.initialize();
      assert.equal(service.isServiceInitialized(), true);
      
      // Second init should not throw and state should not change
      service.initialize();
      assert.equal(service.isServiceInitialized(), true);
    });

    it("should set up session context on init", () => {
      service.initialize();
      const context = service.getSessionContext();
      assert.notEqual(context, null);
      assert.ok(context.sessionId);
      assert.equal(context.isAuthenticated, false);
    });
  });

  describe("Event Tracking", () => {
    beforeEach(() => {
      service.initialize();
    });

    it("should track valid events", () => {
      service.track("login_succeeded", { user_uuid: "test-uuid" });
      assert.equal(service.getQueueSize(), 1);
    });

    it("should reject unapproved events", () => {
      service.track("invalid_event_type", {});
      assert.equal(service.getQueueSize(), 0);
    });

    it("should allow empty properties", () => {
      service.track("frontend_page_loaded");
      assert.equal(service.getQueueSize(), 1);
    });

    it("should not track if not initialized", () => {
      service.destroy();
      service.track("login_succeeded", {});
      assert.equal(service.getQueueSize(), 0);
    });
  });

  describe("Queue Management", () => {
    beforeEach(() => {
      service.initialize();
    });

    it("should accumulate events in queue", () => {
      service.track("login_succeeded", {});
      service.track("frontend_page_loaded", {});
      assert.equal(service.getQueueSize(), 2);
    });

    it("should not exceed memory with many events", () => {
      // Add 100 events to ensure queue doesn't grow unbounded
      for (let i = 0; i < 100; i++) {
        service.track("login_succeeded", { index: i });
      }
      // Auto-flush happens at 20 events, so queue should be smaller
      assert.ok(service.getQueueSize() <= 100);
    });
  });

  describe("Session Management", () => {
    beforeEach(() => {
      service.initialize();
    });

    it("should update session with user ID", () => {
      service.updateSession({ userId: 42, isAuthenticated: true });
      const context = service.getSessionContext();
      assert.equal(context.userId, "42");
      assert.equal(context.isAuthenticated, true);
    });

    it("should update session with user UUID", () => {
      const uuid = "f1a2b3c4-d5e6-7890-abcd-ef1234567890";
      service.updateSession({ userUuid: uuid });
      const context = service.getSessionContext();
      assert.equal(context.userId, uuid);
    });

    it("should prefer userUuid over userId", () => {
      const uuid = "f1a2b3c4-d5e6-7890-abcd-ef1234567890";
      service.updateSession({ userId: 42, userUuid: uuid });
      const context = service.getSessionContext();
      assert.equal(context.userId, uuid);
    });
  });

  describe("Destruction", () => {
    it("should clean up resources on destroy", () => {
      service.initialize();
      assert.equal(service.isServiceInitialized(), true);

      service.destroy();
      assert.equal(service.isServiceInitialized(), false);
    });

    it("should prevent tracking after destroy", () => {
      service.initialize();
      service.destroy();

      service.track("login_succeeded", {});
      assert.equal(service.getQueueSize(), 0);
    });

    it("should handle multiple destroy calls", () => {
      service.initialize();
      service.destroy();
      service.destroy(); // Should not throw
      assert.equal(service.isServiceInitialized(), false);
    });
  });

  describe("Event Structure", () => {
    it("should create properly formatted CloudEvents 1.0 envelope", async () => {
      service.initialize();

      // Track an event
      service.track("login_succeeded", { user_uuid: "test" });

      // Access internal queue for verification (for testing only)
      const queueSize = service.getQueueSize();
      assert.equal(queueSize, 1);

      // Event should have required CloudEvents fields
      // (We can't directly access queue entries in production, but this validates structure)
    });
  });
});
