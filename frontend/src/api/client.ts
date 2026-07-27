import { ofetch, FetchError, type FetchOptions } from "ofetch";

/**
 * Normalized API error — surfaces the backend's `error` field when present,
 * matching the behavior of the legacy vanilla `api()` helper.
 */
export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface ErrorPayload {
  error?: string;
}

function hasMessage(data: unknown): data is ErrorPayload {
  return typeof data === "object" && data !== null && "error" in data;
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
    return await raw<T>(path, options);
  } catch (err) {
    if (err instanceof FetchError) {
      const data: unknown = err.data;
      const message =
        hasMessage(data) && typeof data.error === "string"
          ? data.error
          : err.message || err.statusText || "Request failed";
      throw new ApiError(message, err.statusCode ?? undefined);
    }
    throw err;
  }
}

export const http = {
  get: <T>(path: string, options?: FetchOptions<"json">) =>
    request<T>(path, { method: "GET", ...options }),
  post: <T>(path: string, body?: unknown, options?: FetchOptions<"json">) =>
    request<T>(path, { method: "POST", body: body as BodyInit, ...options }),
};
