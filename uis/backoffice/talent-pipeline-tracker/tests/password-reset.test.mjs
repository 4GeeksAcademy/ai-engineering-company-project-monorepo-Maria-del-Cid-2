import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  getPasswordResetErrorMessage,
  requestChangePassword,
  requestForgotPassword,
  requestResetPassword,
  validateChangePasswordFields,
  validateForgotPasswordFields,
  validateResetPasswordFields,
} from "../lib/password-reset.ts";
import { NexovaApiError } from "../lib/nexova-api.ts";

function makeClient(response = { message: "ok" }) {
  const requests = [];
  return {
    requests,
    request: async (endpoint, options) => {
      requests.push({ endpoint, options });
      return response;
    },
  };
}

describe("password reset validation", () => {
  it("validates forgot password email", () => {
    assert.deepEqual(validateForgotPasswordFields("",), {
      email: "El correo electrónico es obligatorio.",
    });
    assert.deepEqual(validateForgotPasswordFields("not-an-email"), {
      email: "Introduce un correo electrónico válido.",
    });
    assert.deepEqual(validateForgotPasswordFields("person@example.com"), {});
  });

  it("requires a token, minimum password length, and matching confirmation", () => {
    assert.equal(validateResetPasswordFields("", "short", "different").token, "El enlace de recuperación no es válido.");
    assert.equal(
      validateResetPasswordFields("token", "short", "short").newPassword,
      "La nueva contraseña debe tener al menos 8 caracteres.",
    );
    assert.equal(
      validateResetPasswordFields("token", "long-enough", "different").confirmPassword,
      "Las contraseñas no coinciden.",
    );
    assert.deepEqual(validateResetPasswordFields("token", "long-enough", "long-enough"), {});
  });

  it("validates change password fields", () => {
    const errors = validateChangePasswordFields("", "long-enough", "different");
    assert.equal(errors.currentPassword, "La contraseña actual es obligatoria.");
    assert.equal(errors.confirmPassword, "Las contraseñas no coinciden.");
    assert.deepEqual(validateChangePasswordFields("current", "long-enough", "long-enough"), {});
  });
});

describe("password reset API workflows", () => {
  it("sends forgot password without Bearer", async () => {
    const client = makeClient();
    await requestForgotPassword(client, " person@example.com ");

    assert.equal(client.requests[0].endpoint, "/auth/forgot-password");
    assert.equal(client.requests[0].options.method, "POST");
    assert.equal(client.requests[0].options.auth, false);
    assert.deepEqual(client.requests[0].options.json, { email: "person@example.com" });
  });

  it("sends reset password without Bearer and preserves the token only in the request", async () => {
    const client = makeClient();
    const token = "opaque-token-with-special_chars";
    await requestResetPassword(client, token, "long-enough", "long-enough");

    assert.equal(client.requests[0].endpoint, "/auth/reset-password");
    assert.equal(client.requests[0].options.auth, false);
    assert.deepEqual(client.requests[0].options.json, {
      token,
      new_password: "long-enough",
      confirm_password: "long-enough",
    });
  });

  it("sends change password with Bearer enabled", async () => {
    const client = makeClient();
    await requestChangePassword(client, "current", "long-enough", "long-enough");

    assert.equal(client.requests[0].endpoint, "/auth/change-password");
    assert.equal(client.requests[0].options.auth, true);
    assert.deepEqual(client.requests[0].options.json, {
      current_password: "current",
      new_password: "long-enough",
      confirm_password: "long-enough",
    });
  });
});

describe("password reset errors", () => {
  it("translates invalid token and current-password errors", () => {
    assert.equal(
      getPasswordResetErrorMessage(new NexovaApiError("http", 400, "Invalid"), "reset"),
      "El enlace de recuperación no es válido o ha caducado.",
    );
    assert.equal(
      getPasswordResetErrorMessage(new NexovaApiError("http", 400, "Invalid"), "change"),
      "La contraseña actual no es correcta.",
    );
    assert.match(
      getPasswordResetErrorMessage(new NexovaApiError("network", null, "offline"), "forgot"),
      /No se pudo conectar/,
    );
  });
});
