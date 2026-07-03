// Generic API envelope/error types shared by lib/api/*.
// Kept backend-agnostic: individual endpoint DTOs live in chat.ts / tenant-config.ts.

// Error surfaced to callers by lib/api/client.ts, for both non-2xx HTTP
// responses and network-level failures (fetch rejecting outright).
export interface ApiError {
  // User-facing message (Japanese), safe to render directly in the UI.
  message: string;
  // HTTP status code, or null when the request never reached the server
  // (network failure, CORS, offline, etc).
  status: number | null;
  // Raw parsed response body, if any, for callers that want more detail.
  details?: unknown;
}
