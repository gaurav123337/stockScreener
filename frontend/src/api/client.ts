import { ofetch, FetchError, type FetchOptions } from "ofetch";

/**
 * Normalized API error — surfaces the backend's structured error field.
 * The backend now always returns:
 *   { error: { code: "...", message: "...", details: {...} } }
 */
export class ApiError extends Error {
  readonly status: number | undefined;
  readonly code: string | undefined;
  readonly details: Record<string, unknown> | undefined;

  constructor(message: string, status?: number, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

function hasMessage(data: unknown): data is ErrorPayload {
  return typeof data === "object" && data !== null && "error" in data;
}

// ------------------------------------------------------------------ //
// Token storage
// ------------------------------------------------------------------ //

const TOKEN_KEY = "stockScreener_token";
const USER_KEY = "stockScreener_user";
export const AUTH_STATE_CHANGED_EVENT = "stockScreener:auth-state-changed";

// In-memory mirror of the token/user. Some embedding contexts (sandboxed
// iframes, private browsing) make localStorage unavailable or throw on
// access; without this fallback a freshly-logged-in session would read back
// no token, every authenticated call would 401, and the app would bounce the
// user back to the sign-in page immediately after they log in.
let memoryToken: string | null = null;
let memoryUser: string | null = null;

export function getToken(): string | null {
  try {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) return stored;
  } catch {
    // localStorage unavailable — fall through to the in-memory mirror
  }
  return memoryToken;
}

export function setToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // localStorage unavailable — the in-memory mirror keeps the session alive
  }
}

export function getStoredUser(): {
  user_id: string;
  username: string;
  display_name: string | null;
  role?: "user" | "product_owner";
  status?: "active" | "suspended";
  tier?: "free" | "pro";
} | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (raw) return JSON.parse(raw) as ReturnType<typeof getStoredUser>;
  } catch {
    // localStorage unavailable — fall through to the in-memory mirror
  }
  return memoryUser ? (JSON.parse(memoryUser) as ReturnType<typeof getStoredUser>) : null;
}

export function setStoredUser(
  user: {
    user_id: string;
    username: string;
    display_name: string | null;
    role?: string;
    status?: string;
    tier?: string;
  } | null,
): void {
  memoryUser = user ? JSON.stringify(user) : null;
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  } catch {
    // localStorage unavailable — the in-memory mirror keeps the session alive
  }
}

export function clearAuth(): void {
  setToken(null);
  setStoredUser(null);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_STATE_CHANGED_EVENT));
  }
}

// ------------------------------------------------------------------ //
// HTTP client with auth header
// ------------------------------------------------------------------ //

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

const raw = ofetch.create({
  baseURL: "/",
  retry: 0,
  onRequestError({ error }) {
    throw new ApiError(error.message || "Network error");
  },
});

async function request<T>(path: string, options?: FetchOptions<"json">): Promise<T> {
  const headers = {
    ...authHeaders(),
    ...(options?.headers as Record<string, string> | undefined),
  };
  const hadToken = Boolean(headers.Authorization);
  try {
    return await raw<T>(path, {
      ...options,
      headers,
    });
  } catch (err) {
    if (err instanceof FetchError) {
      const data: unknown = err.data;
      let message = err.message || err.statusText || "Request failed";
      let code: string | undefined;
      let details: Record<string, unknown> | undefined;

      if (hasMessage(data) && data.error) {
        if (typeof data.error.message === "string") {
          message = data.error.message;
        }
        if (typeof data.error.code === "string") {
          code = data.error.code;
        }
        if (typeof data.error.details === "object" && data.error.details !== null) {
          details = data.error.details as Record<string, unknown>;
        }
      }

      // Auto-logout on 401 only when this request was authenticated. A 401 on
      // a request that never carried a token is an access-control response
      // (e.g. a strict endpoint hit by a guest), not a dead session — clearing
      // auth and bouncing to the sign-in screen for those would log people out
      // for reasons unrelated to their login.
      if (err.statusCode === 401 && hadToken) {
        clearAuth();
        // Force redirect to login if we're in the SPA
        if (typeof window !== "undefined" && !window.location.hash.includes("/auth")) {
          window.location.hash = "#/auth/login";
        }
      }

      throw new ApiError(message, err.statusCode ?? undefined, code, details);
    }
    throw err;
  }
}

export const http = {
  get: <T>(path: string, options?: FetchOptions<"json">) =>
    request<T>(path, { method: "GET", ...options }),
  post: <T>(path: string, body?: unknown, options?: FetchOptions<"json">) =>
    request<T>(path, { method: "POST", body: body as BodyInit, ...options }),
  postForm: <T>(path: string, form: FormData, options?: FetchOptions<"json">) =>
    request<T>(path, { method: "POST", body: form, ...options }),
  delete: <T>(path: string, options?: FetchOptions<"json">) =>
    request<T>(path, { method: "DELETE", ...options }),
};
