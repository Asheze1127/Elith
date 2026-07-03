import { afterEach, describe, expect, it, vi } from "vitest";
import { getTenantConfig } from "./tenant";
import type { TenantConfig } from "@/types/tenant-config";

// Helper to build a minimal Response-like object for mocking global.fetch
// (mirrors lib/api/client.test.ts's convention).
function mockResponse(status: number, body: unknown) {
  const text = body === undefined ? "" : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  } as Response;
}

const sampleConfig: TenantConfig = {
  tenant_id: "a_shinonome",
  display_name: "東雲ビジネスサポート",
  search: { scope: "all" },
  answer: {
    modes: ["external", "internal"],
    default_mode: "internal",
    citation: "required",
    low_confidence_action: "needs_review",
    show_source_metadata: true,
  },
  pipeline: ["retrieve", "stale_warning", "contradiction_check", "ground_check", "cite"],
  warnings: { stale_sources: true, contradiction: true },
  category_policies: { billing: { tone: "formal" } },
  feedback: { enabled: true, reason_categories: ["古い根拠"] },
};

describe("getTenantConfig", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests GET /tenant/config and unwraps the backend's {tenant_id, config} envelope", async () => {
    // Backend's outer tenant_id (see backend/app/api/tenant.py) is the DB
    // row's integer id, distinct from the string slug inside `config` --
    // this test asserts only the inner config is returned to callers.
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse(200, { tenant_id: 1, config: sampleConfig }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getTenantConfig();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/tenant/config"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(sampleConfig);
  });

  it("propagates ApiRequestError with the backend's message on a non-2xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse(404, { detail: "テナントが見つかりません" }),
      ),
    );

    await expect(getTenantConfig()).rejects.toMatchObject({
      name: "ApiRequestError",
      message: "テナントが見つかりません",
      status: 404,
    });
  });
});
