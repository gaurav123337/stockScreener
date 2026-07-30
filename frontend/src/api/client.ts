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

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // localStorage unavailable
  }
}

export function getStoredUser(): {
  user_id: string;
  username: string;
  display_name: string | null;
} | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredUser(
  user: { user_id: string; username: string; display_name: string | null } | null,
): void {
  try {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  } catch {
    // localStorage unavailable
  }
}

export function clearAuth(): void {
  setToken(null);
  setStoredUser(null);
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
  try {
    return await raw<T>(path, {
      ...options,
      headers: {
        ...authHeaders(),
        ...(options?.headers as Record<string, string> | undefined),
      },
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

      // Auto-logout on 401
      if (err.statusCode === 401) {
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
};
