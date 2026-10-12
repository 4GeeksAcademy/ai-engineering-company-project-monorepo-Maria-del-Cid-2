import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { ApiClientError } from "../lib/api-errors.ts";
import { getUserFacingApiError } from "../lib/api-error-messages.ts";

describe("user-facing API error messages", () => {
  it("maps transport and HTTP failures to safe messages", () => {
    assert.match(
      getUserFacingApiError(new ApiClientError("network", null, "secret"), "fallback"),
      /conectar/,
    );
    assert.match(
      getUserFacingApiError(new ApiClientError("timeout", null, "secret"), "fallback"),
      /demasiado/,
    );
    assert.match(
      getUserFacingApiError(new ApiClientError("http", 422, "secret"), "fallback"),
      /Revisa los datos/,
    );
    assert.match(
      getUserFacingApiError(new ApiClientError("http", 503, "secret"), "fallback"),
      /servidor no está disponible/,
    );
  });

  it("does not expose error details or show expected cancellations", () => {
    const cancellation = new ApiClientError("cancelled", null, "token=secret@example.com");

    assert.equal(getUserFacingApiError(cancellation, "fallback"), null);
    assert.equal(
      getUserFacingApiError(new Error("token=secret@example.com"), "fallback"),
      "fallback",
    );
  });
});