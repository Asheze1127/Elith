import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost, ApiRequestError, apiRequest } from "./client";

// Helper to build a minimal Response-like object for mocking global.fetch.
function mockResponse(status: number, body: unknown) {
  const text = body === undefined ? "" : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  } as Response;
}

describe("apiRequest", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on a 2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(200, { answer: "hello" })),
    );

    const result = await apiRequest<{ answer: string }>("/chat");

    expect(result).toEqual({ answer: "hello" });
  });

  it("throws ApiRequestError with the backend detail message on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(404, { detail: "テナントが見つかりません" }),
      ),
    );

    await expect(apiRequest("/tenant/config")).rejects.toMatchObject({
      name: "ApiRequestError",
      message: "テナントが見つかりません",
      status: 404,
    });
  });

  it("falls back to a generic message when the error body has no detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse(500, undefined)));

    await expect(apiRequest("/chat")).rejects.toMatchObject({
      status: 500,
    });
    await expect(apiRequest("/chat")).rejects.toThrow(/500/);
  });

  it("joins FastAPI 422 validation errors (array-shaped detail) into one message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(422, {
          detail: [
            { loc: ["body", "title"], msg: "field required", type: "missing" },
            { loc: ["body", "content"], msg: "string too short", type: "too_short" },
          ],
        }),
      ),
    );

    await expect(apiRequest("/documents")).rejects.toMatchObject({
      status: 422,
      message: "field required / string too short",
    });
  });

  it("surfaces network failures as a user-readable ApiRequestError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed")),
    );

    const error: ApiRequestError = await apiRequest("/chat").catch((e) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error.status).toBeNull();
    expect(error.message).toMatch(/サーバーに接続できません/);
  });
});

describe("apiGet / apiPost", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("apiGet issues a GET request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiGet("/tenant/config");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/tenant/config"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("apiPost sends a JSON-serialized body with POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiPost("/chat", { query: "hi" });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ query: "hi" }),
      }),
    );
  });
});

describe("base URL normalization", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("strips a trailing slash from NEXT_PUBLIC_API_BASE_URL to avoid a double slash", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com/");
    vi.resetModules();
    const { apiGet: apiGetWithTrailingSlashBase } = await import("./client");

    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiGetWithTrailingSlashBase("/chat");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/chat",
      expect.anything(),
    );
  });
});
