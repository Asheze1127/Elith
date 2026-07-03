// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { useTenantConfig } from "./useTenantConfig";
import { TenantConfigProvider } from "@/context/TenantConfigContext";
import { getTenantConfig } from "@/lib/api/tenant";
import type { TenantConfig } from "@/types/tenant-config";

vi.mock("@/lib/api/tenant", () => ({
  getTenantConfig: vi.fn(),
}));

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
  pipeline: ["retrieve", "cite"],
  warnings: { stale_sources: true, contradiction: true },
  category_policies: {},
  feedback: { enabled: true, reason_categories: [] },
};

function Consumer() {
  const { config, isLoading } = useTenantConfig();
  return (
    <div data-testid="result">
      {isLoading ? "loading" : `loaded:${config?.display_name}`}
    </div>
  );
}

describe("useTenantConfig", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("throws a clear developer-facing error when used outside TenantConfigProvider", () => {
    // React logs the render-time throw to console.error; silence it so the
    // expected failure path doesn't pollute test output.
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    expect(() => render(<Consumer />)).toThrow(
      "useTenantConfig must be used within a TenantConfigProvider",
    );

    consoleErrorSpy.mockRestore();
  });

  it("reads the loaded config through TenantConfigProvider", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);

    render(
      <TenantConfigProvider>
        <Consumer />
      </TenantConfigProvider>,
    );

    expect(screen.getByTestId("result").textContent).toBe("loading");

    await waitFor(() =>
      expect(screen.getByTestId("result").textContent).toBe(
        "loaded:東雲ビジネスサポート",
      ),
    );
  });
});
