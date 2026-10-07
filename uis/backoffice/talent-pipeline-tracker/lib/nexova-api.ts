import type { AuthenticatedUser, SessionSnapshot, UserProfile } from "@/types/auth";

const configuredApiBase = process.env.NEXT_PUBLIC_NEXOVA_API_BASE?.trim();
export const NEXOVA_API_BASE = (
  configuredApiBase || "http://localhost:8000/api"
).replace(/\/+$/, "");

export const ACCESS_TOKEN_KEY = "nexova_access_token";

export interface TokenStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface NexovaApiClientOptions {
  baseUrl?: string;
  fetcher?: typeof fetch;
  storage?: TokenStorage;
  redirectToExpiredLogin?: (url: string) => void;
}

export interface NexovaRequestOptions extends Omit<RequestInit, "body" | "headers"> {
  auth?: boolean;
  body?: BodyInit | null;
  headers?: HeadersInit;
  json?: unknown;
}

export type NexovaApiErrorKind = "http" | "network";

export class NexovaApiError extends Error {
  readonly kind: NexovaApiErrorKind;
  readonly status: number | null;

  constructor(
    kind: NexovaApiErrorKind,
    status: number | null,
    message: string,
  ) {
    super(message);
    this.name = "NexovaApiError";
    this.kind = kind;
    this.status = status;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isServerError(): boolean {
    return this.status !== null && this.status >= 500;
  }
}

const initialSession: SessionSnapshot = {
  status: "loading",
  user: null,
  error: null,
};

function browserStorage(): TokenStorage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function getErrorMessage(body: unknown, fallback: string): string {
  if (typeof body === "string" && body) return body;
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return fallback;
  }

  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String(item.msg);
        }
        return String(item);
      })
      .join("; ");
  }
  return fallback;
}

async function readResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("json")) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return text;
}

export class NexovaApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;
  private readonly injectedStorage: TokenStorage | undefined;
  private readonly redirectToExpiredLogin: (url: string) => void;
  private readonly listeners = new Set<(session: SessionSnapshot) => void>();
  private session: SessionSnapshot = initialSession;
  private validationPromise: Promise<SessionSnapshot> | null = null;
  private sessionRevision = 0;
  private expirationHandled = false;

  constructor(options: NexovaApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? NEXOVA_API_BASE).replace(/\/+$/, "");
    this.fetcher = options.fetcher ?? globalThis.fetch.bind(globalThis);
    this.injectedStorage = options.storage;
    this.redirectToExpiredLogin =
      options.redirectToExpiredLogin ?? this.defaultExpiredLoginRedirect;
  }

  getSession(): SessionSnapshot {
    return this.session;
  }

  subscribe(listener: (session: SessionSnapshot) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getAccessToken(): string | null {
    try {
      return this.getStorage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
    } catch {
      return null;
    }
  }

  setAccessToken(token: string): void {
    if (!token.trim()) throw new Error("Access token must not be empty");
    const storage = this.getStorage();
    if (!storage) throw new Error("Browser storage is unavailable");

    storage.setItem(ACCESS_TOKEN_KEY, token);
    this.sessionRevision += 1;
    this.validationPromise = null;
    this.expirationHandled = false;
    this.publish({ status: "loading", user: null, error: null });
  }

  logout(): void {
    this.sessionRevision += 1;
    this.validationPromise = null;
    try {
      this.getStorage()?.removeItem(ACCESS_TOKEN_KEY);
    } catch {
      // Session state is still cleared if browser storage is unavailable.
    }
    this.expirationHandled = false;
    this.publish({ status: "unauthenticated", user: null, error: null });
  }

  updateProfile(profile: UserProfile): void {
    if (this.session.status !== "authenticated" || !this.session.user) return;

    this.publish({
      ...this.session,
      user: { ...this.session.user, profile },
    });
  }

  async validateSession(): Promise<SessionSnapshot> {
    if (this.validationPromise) return this.validationPromise;

    if (!this.getAccessToken()) {
      if (this.session.status !== "unauthenticated") {
        this.publish({ status: "unauthenticated", user: null, error: null });
      }
      return this.session;
    }

    const revision = this.sessionRevision;
    const token = this.getAccessToken();
    this.publish({ status: "loading", user: null, error: null });
    const validation = this.request<AuthenticatedUser>("/auth/me", { auth: true })
      .then((user) => {
        if (revision !== this.sessionRevision || token !== this.getAccessToken()) {
          return this.session;
        }
        this.publish({ status: "authenticated", user, error: null });
        return this.session;
      })
      .catch((error: unknown) => {
        if (revision !== this.sessionRevision || token !== this.getAccessToken()) {
          return this.session;
        }
        if (!(error instanceof NexovaApiError && error.isUnauthorized)) {
          this.publish({
            status: "error",
            user: null,
            error: error instanceof Error ? error.message : "Unable to validate session",
          });
        }
        return this.session;
      })
      .finally(() => {
        if (this.validationPromise === validation) this.validationPromise = null;
      });

    this.validationPromise = validation;
    return validation;
  }

  async request<T>(
    endpoint: string,
    options: NexovaRequestOptions = {},
  ): Promise<T> {
    const { auth = false, body: inputBody, headers: inputHeaders, json, ...init } = options;
    const revision = this.sessionRevision;
    const headers = new Headers(inputHeaders);
    let body = inputBody;

    if (Object.prototype.hasOwnProperty.call(options, "json")) {
      if (body !== undefined && body !== null) {
        throw new TypeError("Pass either json or body, not both");
      }
      const serialized = JSON.stringify(json);
      if (serialized === undefined) {
        throw new TypeError("Request JSON body is not serializable");
      }
      body = serialized;
      headers.set("Content-Type", "application/json");
    } else if (typeof FormData !== "undefined" && body instanceof FormData) {
      headers.delete("Content-Type");
    } else if (
      typeof URLSearchParams !== "undefined" &&
      body instanceof URLSearchParams &&
      !headers.has("Content-Type")
    ) {
      headers.set("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8");
    }

    if (auth) {
      const token = this.getAccessToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      else headers.delete("Authorization");
    } else {
      headers.delete("Authorization");
    }

    let response: Response;
    try {
      response = await this.fetcher(
        `${this.baseUrl}/${endpoint.replace(/^\/+/, "")}`,
        { ...init, body, headers },
      );
    } catch {
      throw new NexovaApiError("network", null, "Unable to reach Nexova API");
    }

    const responseBody = await readResponseBody(response);
    if (!response.ok) {
      if (response.status === 401 && auth && revision === this.sessionRevision) {
        this.handleUnauthorized();
      }
      throw new NexovaApiError(
        "http",
        response.status,
        getErrorMessage(responseBody, `Nexova API error ${response.status}`),
      );
    }

    if (response.status === 204 || responseBody === undefined) {
      return undefined as T;
    }
    return responseBody as T;
  }

  private getStorage(): TokenStorage | null {
    return this.injectedStorage ?? browserStorage();
  }

  private publish(session: SessionSnapshot): void {
    this.session = session;
    for (const listener of this.listeners) listener(session);
  }

  private handleUnauthorized(): void {
    if (this.expirationHandled) return;
    this.expirationHandled = true;
    this.sessionRevision += 1;
    this.validationPromise = null;

    try {
      this.getStorage()?.removeItem(ACCESS_TOKEN_KEY);
    } catch {
      // Session state is still invalidated if storage cannot be accessed.
    }
    this.publish({ status: "unauthenticated", user: null, error: null });

    if (typeof window !== "undefined" || this.injectedStorage !== undefined) {
      this.redirectToExpiredLogin("/login?expired=1");
    }
  }

  private defaultExpiredLoginRedirect(url: string): void {
    if (typeof window === "undefined") return;
    if (
      window.location.pathname === "/login" &&
      new URLSearchParams(window.location.search).get("expired") === "1"
    ) {
      return;
    }
    window.location.replace(url);
  }
}

export const nexovaApi = new NexovaApiClient();