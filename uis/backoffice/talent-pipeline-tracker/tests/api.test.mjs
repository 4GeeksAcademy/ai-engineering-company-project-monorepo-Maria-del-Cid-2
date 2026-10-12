import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { ApiClientError } from "../lib/api-errors.ts";
import { apiFetch } from "../lib/api.ts";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function rejectingOnAbort() {
  return (_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
  });
}

describe("Tracker API client", () => {
  it("parses JSON, empty responses, and successful text responses", async () => {
    globalThis.fetch = async (url, init) => {
      if (url.endsWith("/json")) return Response.json({ ok: true });
      if (new Headers(init.headers).get("X-Empty") === "yes") {
        return new Response(null, { status: 204 });
      }
      return new Response("accepted", { headers: { "Content-Type": "text/plain" } });
    };

    assert.deepEqual(await apiFetch("/json"), { ok: true });
    assert.equal(await apiFetch("/empty", { headers: { "X-Empty": "yes" } }), undefined);
    assert.equal(await apiFetch("/text", { method: "POST" }), "accepted");
  });

  it("classifies invalid JSON in a successful response as a parse error", async () => {
    globalThis.fetch = async () => new Response("not-json", {
      headers: { "Content-Type": "application/json" },
    });

    await assert.rejects(apiFetch("/invalid"), (error) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.kind, "parse");
      assert.equal(error.status, 200);
      return true;
    });
  });

  it("uses safe HTTP messages for JSON, text, and empty error bodies", async () => {
    for (const response of [
      Response.json({ detail: "database secret and /internal/path" }, { status: 500 }),
      new Response("provider secret", { status: 502, headers: { "Content-Type": "text/plain" } }),
      new Response(null, { status: 503 }),
    ]) {
      globalThis.fetch = async () => response;
      await assert.rejects(apiFetch("/failure"), (error) => {
        assert.ok(error instanceof ApiClientError);
        assert.equal(error.kind, "http");
        assert.equal(error.status, response.status);
        assert.match(error.message, /server could not complete/i);
        assert.equal(error.message.includes("secret"), false);
        return true;
      });
    }
  });

  it("redacts personal data from known client-error details", async () => {
    globalThis.fetch = async () => Response.json({
      detail: "Account user@example.com is invalid at /users/42?token=secret",
    }, { status: 400 });

    await assert.rejects(apiFetch("/failure"), (error) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.message.includes("user@example.com"), false);
      assert.equal(error.message.includes("secret"), false);
      assert.equal(error.message.includes("/users/42"), false);
      return true;
    });
  });

  it("distinguishes network failure, timeout, and external cancellation", async () => {
    globalThis.fetch = async () => {
      throw new TypeError("socket details");
    };
    await assert.rejects(apiFetch("/network"), (error) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.kind, "network");
      assert.equal(error.message.includes("socket details"), false);
      return true;
    });

    globalThis.fetch = rejectingOnAbort();
    await assert.rejects(apiFetch("/timeout", { timeoutMs: 1 }), (error) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.kind, "timeout");
      return true;
    });

    const controller = new AbortController();
    const request = apiFetch("/cancelled", { signal: controller.signal, timeoutMs: 1_000 });
    controller.abort();
    await assert.rejects(request, (error) => {
      assert.ok(error instanceof ApiClientError);
      assert.equal(error.kind, "cancelled");
      return true;
    });
  });
});
