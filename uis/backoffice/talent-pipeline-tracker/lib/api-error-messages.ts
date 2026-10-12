import { ApiClientError } from "./api-errors.ts";

export function getUserFacingApiError(
  error: unknown,
  fallback: string,
): string | null {
  if (!(error instanceof ApiClientError)) return fallback;
  if (error.kind === "cancelled") return null;
  if (error.kind === "network") {
    return "No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.";
  }
  if (error.kind === "timeout") {
    return "La solicitud tardó demasiado. Inténtalo de nuevo.";
  }
  if (error.status === 401) return "Tu sesión ya no es válida. Inicia sesión de nuevo.";
  if (error.status === 403) return "No tienes permisos para completar esta acción.";
  if (error.status === 404) return "No se encontró el recurso solicitado.";
  if (error.status === 409) return "La solicitud entra en conflicto con los datos existentes.";
  if (error.status === 422) return "Revisa los datos introducidos e inténtalo de nuevo.";
  if (error.status !== null && error.status >= 500) {
    return "El servidor no está disponible. Inténtalo de nuevo más tarde.";
  }
  return fallback;
}