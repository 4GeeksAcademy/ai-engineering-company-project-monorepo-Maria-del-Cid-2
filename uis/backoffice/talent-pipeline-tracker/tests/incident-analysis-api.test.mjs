import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { ApiClientError } from "../lib/api-errors.ts";
import { IncidentAnalysisApiError } from "../types/incident-analysis.ts";
import { analyzeIncidents, exportIncidentResults, getIncidentAnalysisTask } from "../lib/incident-analysis-api.ts";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function rejectingOnAbort() {
  return (_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
  });
}

describe("Incident Analysis API client", () => {
  it("submits an async analysis, polls its task, and exports by task ID", async () => {
    const taskId = "a".repeat(32);
    const calls = [];
    globalThis.fetch = async (url, options) => {
      calls.push({ url: String(url), options });
      if (String(url).endsWith("/incidents/analyze")) {
        return Response.json({ task_id: taskId }, { status: 202 });
      }
      if (String(url).endsWith(`/tasks/${taskId}`)) {
        return Response.json({ task_id: taskId, status: "success", result: { total_records: 1 } });
      }
      if (String(url).endsWith(`/incidents/tasks/${taskId}/export`)) {
        return new Response(new Blob(["a,b\n1,2\n"], { type: "text/csv" }));
      }
      throw new Error(`Unexpected URL: ${url}`);
    };

    const accepted = await analyzeIncidents(new Blob(["csv"]));
    assert.deepEqual(accepted, { task_id: taskId });
    assert.equal(calls[0].options.method, "POST");
    assert.ok(calls[0].options.body instanceof FormData);

    const status = await getIncidentAnalysisTask(taskId);
    assert.deepEqual(status, { task_id: taskId, status: "success", result: { total_records: 1 } });

    const exportResult = await exportIncidentResults(taskId);
    assert.equal(await exportResult.text(), "a,b\n1,2\n");
    assert.equal(calls[2].url, `/api/incidents/tasks/${taskId}/export`);
  });

  it("classifies invalid JSON in a successful analysis response", async () => {
    globalThis.fetch = async () => new Response("not-json", {
      headers: { "Content-Type": "application/json" },
    });

    await assert.rejects(analyzeIncidents(new Blob(["csv"])), (error) => {
      assert.ok(error instanceof IncidentAnalysisApiError);
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.kind, "parse");
      assert.equal(error.status, 200);
      return true;
    });
  });

  it("uses safe messages for HTTP errors regardless of body format", async () => {
    for (const response of [
      Response.json({ detail: "database secret and /internal/path" }, { status: 500 }),
      new Response("provider secret", { status: 502, headers: { "Content-Type": "text/plain" } }),
      new Response(null, { status: 503 }),
    ]) {
      globalThis.fetch = async () => response;
      await assert.rejects(analyzeIncidents(new Blob(["csv"])), (error) => {
        assert.ok(error instanceof IncidentAnalysisApiError);
        assert.equal(error.kind, "http");
        assert.equal(error.status, response.status);
        assert.match(error.message, /server could not complete/i);
        assert.equal(error.message.includes("secret"), false);
        return true;
      });
    }
  });

  it("distinguishes network failure, timeout, and external cancellation", async () => {
    globalThis.fetch = async () => {
      throw new TypeError("socket details");
    };
    await assert.rejects(analyzeIncidents(new Blob(["csv"])), (error) => {
      assert.ok(error instanceof IncidentAnalysisApiError);
      assert.equal(error.kind, "network");
      assert.equal(error.message.includes("socket details"), false);
      return true;
    });

    globalThis.fetch = rejectingOnAbort();
    await assert.rejects(analyzeIncidents(new Blob(["csv"]), { timeoutMs: 1 }), (error) => {
      assert.ok(error instanceof IncidentAnalysisApiError);
      assert.equal(error.kind, "timeout");
      return true;
    });

    const controller = new AbortController();
    const request = analyzeIncidents(new Blob(["csv"]), {
      signal: controller.signal,
      timeoutMs: 1_000,
    });
    controller.abort();
    await assert.rejects(request, (error) => {
      assert.ok(error instanceof IncidentAnalysisApiError);
      assert.equal(error.kind, "cancelled");
      return true;
    });
  });
});
