import {
  ApiClientError,
  createRequestSignal,
  DEFAULT_API_TIMEOUT_MS,
  isAbortError,
  parseHttpError,
  readResponseBody,
} from "./api-errors.ts";

const API_BASE = process.env.NEXT_PUBLIC_TALENT_PIPELINE_API_BASE?.trim() || "/api";

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | undefined>;
  timeoutMs?: number;
}

async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, timeoutMs = DEFAULT_API_TIMEOUT_MS, ...init } = options;

  let url = `${API_BASE}${endpoint}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") {
        searchParams.set(key, String(value));
      }
    }
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const requestSignal = createRequestSignal(init.signal, timeoutMs);
  try {
    let response: Response;
    try {
      response = await fetch(url, {
        headers: {
          "Content-Type": "application/json",
          ...init.headers,
        },
        ...init,
        signal: requestSignal.signal,
      });
    } catch (error) {
      if (requestSignal.didTimeout()) {
        throw new ApiClientError("timeout", null, "The request timed out.");
      }
      if (requestSignal.signal.aborted || isAbortError(error)) {
        throw new ApiClientError("cancelled", null, "The request was cancelled.");
      }
      throw new ApiClientError("network", null, "Unable to reach the Tracker API.");
    }

    const responseBody = await readResponseBody(response);
    if (!response.ok) {
      const details = parseHttpError(response.status, responseBody.value);
      throw new ApiClientError("http", response.status, details.message, details.field);
    }

    if (response.status === 204 || !responseBody.hasBody) {
      return undefined as T;
    }
    if (responseBody.isJson && !responseBody.isValidJson) {
      throw new ApiClientError("parse", response.status, "The Tracker API returned an invalid response.");
    }
    return responseBody.value as T;
  } finally {
    requestSignal.cleanup();
  }
}

export { apiFetch };
