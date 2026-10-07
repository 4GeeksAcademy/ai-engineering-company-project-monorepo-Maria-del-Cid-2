import type { NexovaApiClient, NexovaApiError } from "./nexova-api";

type RequestClient = Pick<NexovaApiClient, "request">;

export interface PasswordResetFieldErrors {
  email?: string;
  token?: string;
  currentPassword?: string;
  newPassword?: string;
  confirmPassword?: string;
}

export type PasswordResetErrorAction = "forgot" | "reset" | "change";

export interface GenericMessageResponse {
  message: string;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;

export const PASSWORD_RESET_SUCCESS_REDIRECT = "/login?reset=1";

export function validateForgotPasswordFields(email: string): PasswordResetFieldErrors {
  const normalizedEmail = email.trim();
  if (!normalizedEmail) return { email: "El correo electrónico es obligatorio." };
  if (!EMAIL_PATTERN.test(normalizedEmail)) {
    return { email: "Introduce un correo electrónico válido." };
  }
  return {};
}

function validateNewPassword(password: string): string | undefined {
  if (!password) return "La nueva contraseña es obligatoria.";
  if (password.length < MIN_PASSWORD_LENGTH) {
    return "La nueva contraseña debe tener al menos 8 caracteres.";
  }
  return undefined;
}

export function validateResetPasswordFields(
  token: string,
  newPassword: string,
  confirmPassword: string,
): PasswordResetFieldErrors {
  const errors: PasswordResetFieldErrors = {};
  if (!token.trim()) errors.token = "El enlace de recuperación no es válido.";
  const passwordError = validateNewPassword(newPassword);
  if (passwordError) errors.newPassword = passwordError;
  if (!confirmPassword) {
    errors.confirmPassword = "Confirma la nueva contraseña.";
  } else if (newPassword !== confirmPassword) {
    errors.confirmPassword = "Las contraseñas no coinciden.";
  }
  return errors;
}

export function validateChangePasswordFields(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
): PasswordResetFieldErrors {
  const errors: PasswordResetFieldErrors = {};
  if (!currentPassword) errors.currentPassword = "La contraseña actual es obligatoria.";
  const passwordError = validateNewPassword(newPassword);
  if (passwordError) errors.newPassword = passwordError;
  if (!confirmPassword) {
    errors.confirmPassword = "Confirma la nueva contraseña.";
  } else if (newPassword !== confirmPassword) {
    errors.confirmPassword = "Las contraseñas no coinciden.";
  }
  return errors;
}

export function requestForgotPassword(
  client: RequestClient,
  email: string,
): Promise<GenericMessageResponse> {
  return client.request<GenericMessageResponse>("/auth/forgot-password", {
    method: "POST",
    auth: false,
    json: { email: email.trim() },
  });
}

export function requestResetPassword(
  client: RequestClient,
  token: string,
  newPassword: string,
  confirmPassword: string,
): Promise<GenericMessageResponse> {
  return client.request<GenericMessageResponse>("/auth/reset-password", {
    method: "POST",
    auth: false,
    json: {
      token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    },
  });
}

export function requestChangePassword(
  client: RequestClient,
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
): Promise<GenericMessageResponse> {
  return client.request<GenericMessageResponse>("/auth/change-password", {
    method: "POST",
    auth: true,
    json: {
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    },
  });
}

function isNexovaError(error: unknown): error is NexovaApiError {
  return error instanceof Error && "kind" in error && "status" in error;
}

export function getPasswordResetErrorMessage(
  error: unknown,
  action: PasswordResetErrorAction,
): string {
  if (isNexovaError(error)) {
    if (error.kind === "network") {
      return "No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.";
    }
    if (action === "reset" && error.status === 400) {
      return "El enlace de recuperación no es válido o ha caducado.";
    }
    if (action === "change" && error.status === 400) {
      return "La contraseña actual no es correcta.";
    }
    if (action === "change" && error.status === 401) {
      return "Tu sesión ya no es válida. Inicia sesión de nuevo.";
    }
    if (error.status === 422) {
      return "Revisa los datos introducidos e inténtalo de nuevo.";
    }
    if (error.status !== null && error.status >= 500) {
      return "El servidor no está disponible. Inténtalo de nuevo más tarde.";
    }
  }

  return action === "reset"
    ? "No se pudo restablecer la contraseña. Inténtalo de nuevo."
    : action === "change"
      ? "No se pudo cambiar la contraseña. Inténtalo de nuevo."
      : "No se pudo solicitar la recuperación. Inténtalo de nuevo.";
}
