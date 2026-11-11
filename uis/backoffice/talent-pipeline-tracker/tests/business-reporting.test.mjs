import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { getWeeklyBusinessPerformance } from "../lib/business-reporting.ts";

describe("business reporting client", () => {
  it("requests the weekly performance endpoint with authentication", async () => {
    let request;
    const response = [];
    const client = {
      request: async (...args) => {
        request = args;
        return response;
      },
    };

    assert.equal(await getWeeklyBusinessPerformance(client), response);
    assert.deepEqual(request, [
      "/reporting/weekly-office-program-performance",
      { auth: true },
    ]);
  });

  it("encodes an optional ISO week filter", async () => {
    let endpoint;
    const client = {
      request: async (path, options) => {
        endpoint = path;
        assert.deepEqual(options, { auth: true });
        return [];
      },
    };

    await getWeeklyBusinessPerformance(client, { week_start: "2026-04-06" });
    assert.equal(
      endpoint,
      "/reporting/weekly-office-program-performance?week_start=2026-04-06",
    );
  });
});