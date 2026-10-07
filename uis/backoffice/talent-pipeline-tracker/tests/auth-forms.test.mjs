import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  AuthSubmissionGate,
  getAuthErrorMessage,
  hasSessionExpired,
  registerUser,
  signIn,
  validateLoginFields,
  validateRegistrationFields,
} from "../lib/auth-forms.ts";
import {
  ACCESS_TOKEN_KEY,
  NexovaApiClient,
  NexovaApiError,
} from "../lib/nexova-api.ts";

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

function authenticatedUser() {
  return Response.json({
    id: 7,
    email: "user@example.com",
    is_active: true,
    role: "user",
    created_at: "2026-01-01T00:00:00Z",
    profile: null,
  });
}

function makeClient(fetcher, storage = new MemoryStorage()) {
  return {
    client: new NexovaApiClient({
      baseUrl: "http://localhost:8000/api",
      fetcher,
      storage,
      redirectToExpiredLogin: () => {},
    }),
    storage,
  };
}

describe("auth form workflows", () => {
  it("validates required and malformed login fields", () => {
    assert.deepEqual(validateLoginFields("", ""), {
      email: "El correo electrónico es obligatorio.",
      password: "La contraseña es obligatoria.",
    });
    assert.equal(
      validateLoginFields("not-an-email", "secret").email,
      "Introduce un correo electrónico válido.",
    );
    assert.deepEqual(validateLoginFields("person@example.com", "secret"), {});
  });

  it("requires matching passwords for registration", () => {
    assert.deepEqual(
      validateRegistrationFields("person@example.com", "first", "second"),
      { confirmPassword: "Las contraseñas no coinciden." },
    );
    assert.deepEqual(
      validateRegistrationFields("person@example.com", "same", "same"),
      {},
    );
  });

  it("recognizes only the expired=1 query value", () => {
    assert.equal(hasSessionExpired("1"), true);
    assert.equal(hasSessionExpired(undefined), false);
    assert.equal(hasSessionExpired("0"), false);
    assert.equal(hasSessionExpired(["1", "0"]), false);
  });

  it("logs in with OAuth form fields, saves the JWT, validates /me, and updates session", async () => {
    const requests = [];
    const { client, storage } = makeClient(async (url, init) => {
      requests.push({ url, init });
      if (url.endsWith("/auth/login")) {
        return Response.json({ access_token: "jwt-token", token_type: "bearer" });
      }
      return authenticatedUser();
    });

    const session = await signIn(client, " user@example.com ", "secret");

    assert.equal(session.status, "authenticated");
    assert.equal(session.user.email, "user@example.com");
    assert.equal(storage.getItem(ACCESS_TOKEN_KEY), "jwt-token");
    assert.equal(requests[0].url, "http://localhost:8000/api/auth/login");
    assert.equal(
      new Headers(requests[0].init.headers).get("Content-Type"),
      "application/x-www-form-urlencoded;charset=UTF-8",
    );
    assert.equal(new Headers(requests[0].init.headers).get("Authorization"), null);
    assert.deepEqual(
      [...requests[0].init.body.entries()],
      [["username", "user@example.com"], ["password", "secret"]],
    );
    assert.equal(requests[1].url, "http://localhost:8000/api/auth/me");
    assert.equal(
      new Headers(requests[1].init.headers).get("Authorization"),
      "Bearer jwt-token",
    );
  });

  it("keeps invalid credentials unauthenticated and translates the 401", async () => {
    const { client, storage } = makeClient(async () =>
      Response.json({ detail: "Invalid credentials" }, { status: 401 }),
    );

    await assert.rejects(signIn(client, "person@example.com", "bad"));
    assert.equal(storage.getItem(ACCESS_TOKEN_KEY), null);
    assert.equal(
      getAuthErrorMessage(new NexovaApiError("http", 401, "Invalid credentials"), "login"),
      "El correo electrónico o la contraseña no son correctos.",
    );
  });

  it("registers with only email and password JSON and does not create a session", async () => {
    let request;
    const { client, storage } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json(
        {
          id: 8,
          email: "new@example.com",
          is_active: true,
          role: "user",
          created_at: "2026-01-01T00:00:00Z",
        },
        { status: 201 },
      );
    });

    const created = await registerUser(client, " new@example.com ", "secret");

    assert.equal(created.id, 8);
    assert.equal(request.url, "http://localhost:8000/api/users");
    assert.equal(new Headers(request.init.headers).get("Content-Type"), "application/json");
    assert.equal(new Headers(request.init.headers).get("Authorization"), null);
    assert.deepEqual(JSON.parse(request.init.body), {
      email: "new@example.com",
      password: "secret",
    });
    assert.equal(storage.getItem(ACCESS_TOKEN_KEY), null);
  });

  it("translates duplicate email and validation responses", () => {
    assert.match(
      getAuthErrorMessage(new NexovaApiError("http", 409, "Email already registered"), "register"),
      /Ya existe una cuenta/,
    );
    assert.equal(
      getAuthErrorMessage(
        new NexovaApiError("http", 422, "body.email: value is not a valid email address"),
        "register",
      ),
      "Revisa los datos introducidos: correo electrónico: formato de correo no válido",
    );
  });

  it("preserves unexpected backend detail instead of hiding it", () => {
    assert.equal(
      getAuthErrorMessage(new NexovaApiError("http", 500, "database unavailable"), "register"),
      "No se pudo crear la cuenta: database unavailable",
    );
  });

  it("prevents concurrent submissions and allows retry after completion", () => {
    const gate = new AuthSubmissionGate();

    assert.equal(gate.tryStart(), true);
    assert.equal(gate.tryStart(), false);
    gate.finish();
    assert.equal(gate.tryStart(), true);
  });
});