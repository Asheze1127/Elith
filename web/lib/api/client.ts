import type { ApiError } from "@/types/api";

// Falls back to the local docker-compose api service (see docker-compose.yml,
// port 8000) when the env var isn't set, e.g. when running `next dev` alone.
// Trailing slash is stripped so `buildUrl` can join it with a leading-slash
// path unambiguously (a base URL with a trailing slash, e.g. set by ops as
// "https://api.example.com/", would otherwise produce a double slash).
const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

const LOCAL_TENANT_ID = process.env.NEXT_PUBLIC_LOCAL_TENANT_ID?.trim();

function buildUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

// Thrown by apiRequest() for both non-2xx HTTP responses and network-level
// failures, so every caller can catch a single error type and show the user
// `error.message` directly instead of an opaque fetch rejection.
export class ApiRequestError extends Error implements ApiError {
  status: number | null;
  details?: unknown;

  constructor(message: string, status: number | null, details?: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.details = details;
  }
}

export function getLocalTenantId(): number {
  if (!LOCAL_TENANT_ID) {
    throw new ApiRequestError(
      "ローカルテナントIDが設定されていません。NEXT_PUBLIC_LOCAL_TENANT_IDを設定してください。",
      null,
    );
  }
  const tenantId = Number(LOCAL_TENANT_ID);
  if (!Number.isInteger(tenantId)) {
    throw new ApiRequestError(
      "ローカルテナントIDの形式が正しくありません。",
      null,
      LOCAL_TENANT_ID,
    );
  }
  return tenantId;
}

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

// The ONLY function in the app allowed to call fetch() directly (see
// docs/details/directory.md §2: "lib/api = 通信を一箇所に閉じ込め、コンポーネ
// ントから直接 fetch しない"). Resolves the base URL, serializes/parses JSON,
// and normalizes every failure mode into ApiRequestError.
export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { method = "GET", body, headers, signal } = options;

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(LOCAL_TENANT_ID ? { "X-Tenant-ID": LOCAL_TENANT_ID } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (cause) {
    // Server unreachable, DNS failure, CORS, offline, aborted, etc.
    throw new ApiRequestError(
      "サーバーに接続できませんでした。ネットワーク環境を確認して再度お試しください。",
      null,
      cause,
    );
  }

  const parsedBody = await parseBody(response);

  if (!response.ok) {
    const message =
      extractErrorMessage(parsedBody) ??
      `リクエストに失敗しました（status: ${response.status}）。時間をおいて再度お試しください。`;
    throw new ApiRequestError(message, response.status, parsedBody);
  }

  return parsedBody as T;
}

export function apiGet<T>(
  path: string,
  options: Omit<ApiRequestOptions, "method" | "body"> = {},
): Promise<T> {
  return apiRequest<T>(path, { ...options, method: "GET" });
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  options: Omit<ApiRequestOptions, "method" | "body"> = {},
): Promise<T> {
  return apiRequest<T>(path, { ...options, method: "POST", body });
}

// Reads the response body once as text, then tries JSON first (the
// expected shape) and falls back to raw text so non-JSON error pages
// (e.g. a proxy 502 HTML page) don't crash this layer.
async function parseBody(response: Response): Promise<unknown> {
  const raw = await response.text();
  if (!raw) return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

// Best-effort extraction of a human-readable message from a backend error
// payload. FastAPI's default error shape is {"detail": string | object}, but
// request-validation failures (422) shape `detail` as an array of
// {loc, msg, type} objects instead of a plain string, so that case is joined
// into one readable line rather than falling through to a generic message.
function extractErrorMessage(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.length > 0) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const messages = detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : null,
        )
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) return messages.join(" / ");
    }
  }
  if (typeof body === "string" && body.length > 0) return body;
  return null;
}
