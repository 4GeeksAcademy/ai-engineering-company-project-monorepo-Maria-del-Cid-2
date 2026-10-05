import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import {
  ACCESS_TOKEN_KEY,
  NexovaApiClient,
  NexovaApiError,
} from "../lib/nexova-api.ts";

class MemoryStorage {
  values = new Map();
  removals = 0;

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, value);
  }

  removeItem(key) {
    this.removals += 1;
    this.values.delete(key);
  }
}

function makeClient({ fetcher, storage = new MemoryStorage(), redirect } = {}) {
  return new NexovaApiClient({
    baseUrl: "http://localhost:8000/api/",
    fetcher: fetcher ?? (async () => Response.json({ ok: true })),
    storage,
    redirectToExpiredLogin: redirect,
  });
}

function userResponse() {
  return Response.json({
    id: 1,
    email: "user@example.com",
    is_active: true,
    role: "user",
    created_at: "2026-01-01T00:00:00Z",
    profile: null,
  });
}

const originalWindow = globalThis.window;
afterEach(() => {
  if (originalWindow === undefined) delete globalThis.window;
  else globalThis.window = originalWindow;
});

describe("NexovaApiClient", () => {
  it("uses the local API base and parses JSON responses", async () => {
    let requestedUrl;
    const client = makeClient({
      fetcher: async (url) => {
        requestedUrl = url;
        return Response.json({ result: "ok" });
      },
    });

    assert.deepEqual(await client.request("/health"), { result: "ok" });
    assert.equal(requestedUrl, "http://localhost:8000/api/health");
  });

  it("sets JSON content type and encodes the body", async () => {
    let requestInit;
    const client = makeClient({
      fetcher: async (_url, init) => {
        requestInit = init;
        return Response.json({ created: true });
      },
    });

    await client.request("/users", { method: "POST", json: { email: "a@b.com" } });

    assert.equal(new Headers(requestInit.headers).get("Content-Type"), "application/json");
    assert.equal(requestInit.body, JSON.stringify({ email: "a@b.com" }));
  });

  it("does not set multipart Content-Type for FormData", async () => {
    let requestInit;
    const client = makeClient({
      fetcher: async (_url, init) => {
        requestInit = init;
        return Response.json({ uploaded: true });
      },
    });
    const formData = new FormData();
    formData.append("file", new Blob(["data"]), "data.csv");

    await client.request("/upload", {
      method: "POST",
      body: formData,
      headers: { "Content-Type": "multipart/form-data" },
    });

    assert.equal(new Headers(requestInit.headers).has("Content-Type"), false);
    assert.ok(requestInit.body instanceof FormData);
  });

  it("sends Bearer only for requests explicitly marked authenticated", async () => {
    const requests = [];
    const storage = new MemoryStorage();
    storage.setItem(ACCESS_TOKEN_KEY, "jwt-value");
    const client = makeClient({
      storage,
      fetcher: async (_url, init) => {
        requests.push({
          headers: new Headers(init.headers),
          body: init.body,
        });
        return Response.json({ ok: true });
      },
    });

    await client.request("/auth/me", { auth: true });
    await client.request("/auth/login", {
      method: "POST",
      auth: false,
      body: new URLSearchParams({ username: "user@example.com", password: "pw" }),
      headers: { Authorization: "Bearer caller-token" },
    });

    assert.equal(requests[0].headers.get("Authorization"), "Bearer jwt-value");
    assert.equal(requests[1].headers.get("Authorization"), null);
    assert.equal(
      requests[1].headers.get("Content-Type"),
      "application/x-www-form-urlencoded;charset=UTF-8",
    );
    assert.ok(requests[1].body instanceof URLSearchParams);
  });

  it("does not access browser storage during server rendering", () => {
    assert.equal(typeof globalThis.window, "undefined");
    const client = new NexovaApiClient();

    assert.equal(client.getAccessToken(), null);
  });

  it("validates a saved session once and publishes loading then authenticated", async () => {
    let resolveFetch;
    let requestCount = 0;
    const storage = new MemoryStorage();
    const client = makeClient({
      storage,
      fetcher: () => {
        requestCount += 1;
        return new Promise((resolve) => {
          resolveFetch = resolve;
        });
      },
    });
    client.setAccessToken("jwt-value");

    const firstValidation = client.validateSession();
    const secondValidation = client.validateSession();
    assert.equal(client.getSession().status, "loading");
    assert.equal(requestCount, 1);

    resolveFetch(userResponse());
    const [first, second] = await Promise.all([firstValidation, secondValidation]);
    assert.equal(first.status, "authenticated");
    assert.equal(second.user.email, "user@example.com");
    assert.equal(requestCount, 1);
  });

  it("clears the session and redirects once when concurrent protected requests return 401", async () => {
    const storage = new MemoryStorage();
    storage.setItem(ACCESS_TOKEN_KEY, "expired-token");
    const redirects = [];
    const client = makeClient({
      storage,
      redirect: (url) => redirects.push(url),
      fetcher: async () => Response.json({ detail: "Invalid credentials" }, { status: 401 }),
    });

    const results = await Promise.allSettled([
      client.request("/auth/me", { auth: true }),
      client.request("/suppliers", { auth: true }),
    ]);

    assert.ok(results.every((result) => result.status === "rejected"));
    assert.ok(results[0].reason instanceof NexovaApiError);
    assert.equal(results[0].reason.status, 401);
    assert.equal(client.getAccessToken(), null);
    assert.equal(client.getSession().status, "unauthenticated");
    assert.equal(storage.removals, 1);
    assert.deepEqual(redirects, ["/login?expired=1"]);
  });

  it("does not expire the existing session when a public request returns 401", async () => {
    const storage = new MemoryStorage();
    storage.setItem(ACCESS_TOKEN_KEY, "valid-token");
    const redirects = [];
    const client = makeClient({
      storage,
      redirect: (url) => redirects.push(url),
      fetcher: async () => Response.json({ detail: "Invalid credentials" }, { status: 401 }),
    });

    await assert.rejects(client.request("/auth/login", { auth: false }));

    assert.equal(client.getAccessToken(), "valid-token");
    assert.deepEqual(redirects, []);
  });

  it("does not request /me when there is no stored token", async () => {
    let requestCount = 0;
    const client = makeClient({
      storage: new MemoryStorage(),
      fetcher: async () => {
        requestCount += 1;
        return userResponse();
      },
    });

    const session = await client.validateSession();

    assert.equal(session.status, "unauthenticated");
    assert.equal(requestCount, 0);
  });

  it("preserves the session on 403 and 5xx responses", async () => {
    for (const status of [403, 503]) {
      const storage = new MemoryStorage();
      storage.setItem(ACCESS_TOKEN_KEY, "valid-token");
      const redirects = [];
      const client = makeClient({
        storage,
        redirect: (url) => redirects.push(url),
        fetcher: async () => Response.json({ detail: "Request failed" }, { status }),
      });

      await assert.rejects(client.request("/protected", { auth: true }), (error) => {
        assert.ok(error instanceof NexovaApiError);
        assert.equal(error.status, status);
        assert.equal(error.isForbidden, status === 403);
        assert.equal(error.isServerError, status === 503);
        return true;
      });

      assert.equal(client.getAccessToken(), "valid-token");
      assert.equal(storage.removals, 0);
      assert.deepEqual(redirects, []);
    }
  });

  it("classifies network failures without clearing the session", async () => {
    const storage = new MemoryStorage();
    storage.setItem(ACCESS_TOKEN_KEY, "valid-token");
    const client = makeClient({
      storage,
      fetcher: async () => {
        throw new TypeError("Failed to fetch");
      },
    });

    await assert.rejects(client.request("/protected", { auth: true }), (error) => {
      assert.ok(error instanceof NexovaApiError);
      assert.equal(error.kind, "network");
      assert.equal(error.status, null);
      return true;
    });
    assert.equal(client.getAccessToken(), "valid-token");
    assert.equal(storage.removals, 0);
  });

  it("clears local state on logout without calling a backend endpoint", () => {
    const storage = new MemoryStorage();
    storage.setItem(ACCESS_TOKEN_KEY, "valid-token");
    const client = makeClient({ storage });
    client.logout();

    assert.equal(client.getAccessToken(), null);
    assert.equal(client.getSession().status, "unauthenticated");
  });
});