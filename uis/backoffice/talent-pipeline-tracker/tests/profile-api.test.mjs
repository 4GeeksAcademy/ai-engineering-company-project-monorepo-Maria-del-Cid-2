import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { NexovaApiClient, NexovaApiError } from "../lib/nexova-api.ts";
import { getMyProfile, updateMyProfile } from "../lib/profile-api.ts";

class MemoryStorage {
  values = new Map();

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, value);
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

const profile = {
  id: 4,
  user_id: 7,
  name: "Ana",
  phone: "+34 600 000 000",
  address: "Valencia",
};

function makeClient(fetcher) {
  const storage = new MemoryStorage();
  storage.setItem("nexova_access_token", "profile-jwt");
  const client = new NexovaApiClient({
    baseUrl: "http://localhost:8000/api",
    fetcher,
    storage,
    redirectToExpiredLogin: () => {},
  });
  return { client, storage };
}

describe("profile API", () => {
  it("loads the authenticated profile using GET and Bearer", async () => {
    let request;
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json(profile);
    });

    assert.deepEqual(await getMyProfile(client), profile);
    assert.equal(request.url, "http://localhost:8000/api/profiles/me");
    assert.equal(request.init.method, undefined);
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer profile-jwt");
  });

  it("treats a missing profile as an empty profile", async () => {
    const { client } = makeClient(async () =>
      Response.json({ detail: "Profile not found" }, { status: 404 }),
    );

    assert.equal(await getMyProfile(client), null);
  });

  it("preserves non-404 load errors for retry UI", async () => {
    const { client } = makeClient(async () =>
      Response.json({ detail: "Service unavailable" }, { status: 503 }),
    );

    await assert.rejects(getMyProfile(client), (error) => {
      assert.ok(error instanceof NexovaApiError);
      assert.equal(error.status, 503);
      return true;
    });
  });

  it("updates the profile with PUT, JSON payload, and Bearer", async () => {
    let request;
    const payload = { name: "Ana", phone: "", address: "Valencia" };
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json(profile);
    });

    assert.deepEqual(await updateMyProfile(client, payload), profile);
    assert.equal(request.url, "http://localhost:8000/api/profiles/me");
    assert.equal(request.init.method, "PUT");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer profile-jwt");
    assert.equal(new Headers(request.init.headers).get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(request.init.body), payload);
  });

  it("does not convert save errors into success", async () => {
    const { client } = makeClient(async () =>
      Response.json({ detail: "Save failed" }, { status: 500 }),
    );

    await assert.rejects(updateMyProfile(client, {
      name: "Ana",
      phone: "",
      address: "Valencia",
    }), (error) => {
      assert.ok(error instanceof NexovaApiError);
      assert.equal(error.status, 500);
      return true;
    });
  });
});