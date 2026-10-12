export type ApiErrorKind = "http" | "network" | "timeout" | "parse" | "cancelled";

export interface ParsedApiError {
  message: string;
  field: string | null;
}

export interface ReadResponseBodyResult {
  value: unknown;
  hasBody: boolean;
  isJson: boolean;
  isValidJson: boolean;
}

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly field: string | null;

  constructor(
    kind: ApiErrorKind,
    status: number | null,
    message: string,
    field: string | null = null,
  ) {
    super(message);
    this.name = "ApiClientError";
    this.kind = kind;
    this.status = status;
    this.field = field;
  }
}

export const DEFAULT_API_TIMEOUT_MS = 10_000;

const SAFE_STATUS_MESSAGES: Record<number, string> = {
  400: "The request could not be completed.",
  401: "Authentication is required.",
  403: "You are not authorized to complete this request.",
  404: "The requested resource was not found.",
  409: "The request conflicts with existing data.",
  422: "The request contains invalid data.",
};

export function safeHttpFallback(status: number): string {
  if (status >= 500) return "The server could not complete the request.";
  return SAFE_STATUS_MESSAGES[status] ?? `The request failed (${status}).`;
}

function isValidField(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/.test(value);
}

function sanitizeKnownMessage(value: string, fallback: string): string {
  const normalized = value.trim().replace(/\s+/g, " ");
  if (!normalized || normalized.length > 240 || /traceback|stack trace/i.test(normalized)) {
    return fallback;
  }

  return normalized
    .replace(/Bearer\s+[^\s]+/gi, "Bearer [redacted]")
    .replace(/(access[_-]?token|refresh[_-]?token|token|password|api[_-]?key)=?[^\s,;]+/gi, "$1=[redacted]")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[redacted email]")
    .replace(/https?:\/\/\S+/gi, "[redacted URL]")
    .replace(/\/(?:[A-Za-z0-9_.-]+\/)+[A-Za-z0-9_.-]+/g, "[redacted path]");
}

export function parseHttpError(status: number, body: unknown): ParsedApiError {
  const fallback = safeHttpFallback(status);
  if (status >= 500 || typeof body !== "object" || body === null) {
    return { message: fallback, field: null };
  }

  if (
    "field" in body &&
    "message" in body &&
    isValidField(body.field) &&
    typeof body.message === "string"
  ) {
    return {
      message: sanitizeKnownMessage(body.message, fallback),
      field: body.field,
    };
  }

  if (!("detail" in body)) return { message: fallback, field: null };
  const detail = body.detail;
  if (typeof detail === "string") {
    return { message: sanitizeKnownMessage(detail, fallback), field: null };
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item && typeof item.msg === "string") {
          return item.msg;
        }
        return null;
      })
      .filter((message): message is string => message !== null);
    if (messages.length > 0) {
      return { message: sanitizeKnownMessage(messages.join("; "), fallback), field: null };
    }
  }

  return { message: fallback, field: null };
}

export async function readResponseBody(response: Response): Promise<ReadResponseBodyResult> {
  const text = await response.text();
  if (!text) {
    return { value: undefined, hasBody: false, isJson: false, isValidJson: true };
  }

  const isJson = (response.headers.get("content-type") ?? "").includes("json");
  if (!isJson) {
    return { value: text, hasBody: true, isJson: false, isValidJson: true };
  }

  try {
    return { value: JSON.parse(text) as unknown, hasBody: true, isJson: true, isValidJson: true };
  } catch {
    return { value: undefined, hasBody: true, isJson: true, isValidJson: false };
  }
}

export function createRequestSignal(
  externalSignal: AbortSignal | null | undefined,
  timeoutMs: number,
): { signal: AbortSignal; didTimeout: () => boolean; cleanup: () => void } {
  const controller = new AbortController();
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const abortFromExternalSignal = () => controller.abort(externalSignal?.reason);
  if (externalSignal) {
    if (externalSignal.aborted) abortFromExternalSignal();
    else externalSignal.addEventListener("abort", abortFromExternalSignal, { once: true });
  }
  if (!externalSignal?.aborted && timeoutMs > 0) {
    timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
  }

  return {
    signal: controller.signal,
    didTimeout: () => timedOut,
    cleanup: () => {
      if (timer !== undefined) clearTimeout(timer);
      externalSignal?.removeEventListener("abort", abortFromExternalSignal);
    },
  };
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}