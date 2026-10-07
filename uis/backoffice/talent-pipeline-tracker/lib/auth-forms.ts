import type { NexovaApiClient } from "./nexova-api";
import type { RegisteredUser, SessionSnapshot, TokenResponse } from "@/types/auth";

type AuthClient = Pick<
  NexovaApiClient,
  "request" | "setAccessToken" | "validateSession"
>;

export interface AuthFieldErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
}

export type AuthFormMode = "login" | "register";

interface NexovaErrorLike extends Error {
  kind: "http" | "network";
  status: number | null;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLoginFields(
  email: string,
  password: string,
): AuthFieldErrors {
  const errors: AuthFieldErrors = {};
  const normalizedEmail = email.trim();

  if (!normalizedEmail) errors.email = "El correo electrónico es obligatorio.";
  else if (!EMAIL_PATTERN.test(normalizedEmail)) {
    errors.email = "Introduce un correo electrónico válido.";
  }

  if (!password) errors.password = "La contraseña es obligatoria.";
  return errors;
}

export function validateRegistrationFields(
  email: string,
  password: string,
  confirmPassword: string,
): AuthFieldErrors {
  const errors = validateLoginFields(email, password);

  if (!confirmPassword) {
    errors.confirmPassword = "Confirma la contraseña.";
  } else if (password !== confirmPassword) {
    errors.confirmPassword = "Las contraseñas no coinciden.";
  }

  return errors;
}

export function hasSessionExpired(value: string | string[] | undefined): boolean {
  return value === "1";
}

export class AuthSubmissionGate {
  private active = false;

  tryStart(): boolean {
    if (this.active) return false;
    this.active = true;
    return true;
  }

  finish(): void {
    this.active = false;
  }
}

export async function signIn(
  client: AuthClient,
  email: string,
  password: string,
): Promise<SessionSnapshot> {
  const token = await client.request<TokenResponse>("/auth/login", {
    method: "POST",
    auth: false,
    body: new URLSearchParams({ username: email.trim(), password }),
  });

  client.setAccessToken(token.access_token);
  const session = await client.validateSession();
  if (session.status !== "authenticated") {
    throw new Error(
      session.error ?? "No se pudo verificar la sesión. Inténtalo de nuevo.",
    );
  }

  return session;
}

export function registerUser(
  client: Pick<NexovaApiClient, "request">,
  email: string,
  password: string,
): Promise<RegisteredUser> {
  return client.request<RegisteredUser>("/users", {
    method: "POST",
    auth: false,
    json: { email: email.trim(), password },
  });
}

function translateValidationDetail(detail: string): string {
  return detail
    .replace(/body\./gi, "")
    .replace(/value is not a valid email address/gi, "formato de correo no válido")
    .replace(/field required/gi, "campo obligatorio")
    .replace(/email/gi, "correo electrónico")
    .replace(/password/gi, "contraseña");
}

function isNexovaError(error: unknown): error is NexovaErrorLike {
  if (!(error instanceof Error) || !("kind" in error) || !("status" in error)) {
    return false;
  }
  return (
    (error.kind === "http" || error.kind === "network") &&
    (typeof error.status === "number" || error.status === null)
  );
}

export function getAuthErrorMessage(
  error: unknown,
  mode: AuthFormMode,
): string {
  const action = mode === "login" ? "iniciar sesión" : "crear la cuenta";

  if (isNexovaError(error)) {
    if (error.kind === "network") {
      return "No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.";
    }
    if (mode === "login" && error.status === 401) {
      return "El correo electrónico o la contraseña no son correctos.";
    }
    if (mode === "register" && error.status === 409) {
      return "Ya existe una cuenta con ese correo electrónico.";
    }
    if (error.status === 422) {
      const detail = translateValidationDetail(error.message);
      return detail
        ? `Revisa los datos introducidos: ${detail}`
        : "Revisa los datos introducidos e inténtalo de nuevo.";
    }
    return `No se pudo ${action}: ${error.message}`;
  }

  if (error instanceof Error) return `No se pudo ${action}: ${error.message}`;
  return `Ocurrió un error inesperado al ${action}.`;
}