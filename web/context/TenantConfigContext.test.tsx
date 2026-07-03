// @vitest-environment jsdom
import { useContext } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { TenantConfigContext, TenantConfigProvider } from "./TenantConfigContext";
import { ApiRequestError } from "@/lib/api/client";
import { getTenantConfig } from "@/lib/api/tenant";
import type { TenantConfig } from "@/types/tenant-config";

// The fetch boundary itself (lib/api/tenant.ts) is unit-tested separately in
// lib/api/tenant.test.ts, so here getTenantConfig is mocked directly -- these
// tests only exercise the provider's own loading/success/error state machine.
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

// Reads the context directly via useContext (not through useTenantConfig) so
// these tests stay isolated from the hook's own logic, which is covered in
// hooks/useTenantConfig.test.tsx.
function Probe() {
  const value = useContext(TenantConfigContext);
  if (!value) return null;
  return (
    <>
      <div data-testid="isLoading">{String(value.isLoading)}</div>
      <div data-testid="error">{value.error ?? "none"}</div>
      <div data-testid="displayName">{value.config?.display_name ?? "none"}</div>
    </>
  );
}

describe("TenantConfigProvider", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("starts in a loading state with no config or error", () => {
    // A promise that never settles, to inspect the synchronous initial state.
    vi.mocked(getTenantConfig).mockReturnValue(new Promise(() => {}));

    render(
      <TenantConfigProvider>
        <Probe />
      </TenantConfigProvider>,
    );

    expect(screen.getByTestId("isLoading").textContent).toBe("true");
    expect(screen.getByTestId("error").textContent).toBe("none");
    expect(screen.getByTestId("displayName").textContent).toBe("none");
  });

  it("fetches on mount and exposes the loaded config", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);

    render(
      <TenantConfigProvider>
        <Probe />
      </TenantConfigProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("displayName").textContent).toBe(
        "東雲ビジネスサポート",
      ),
    );
    expect(screen.getByTestId("isLoading").textContent).toBe("false");
    expect(screen.getByTestId("error").textContent).toBe("none");
    expect(getTenantConfig).toHaveBeenCalledTimes(1);
  });

  it("surfaces an ApiRequestError as its user-facing message instead of hanging or crashing", async () => {
    vi.mocked(getTenantConfig).mockRejectedValue(
      new ApiRequestError("テナントが見つかりません", 404),
    );

    render(
      <TenantConfigProvider>
        <Probe />
      </TenantConfigProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("error").textContent).toBe(
        "テナントが見つかりません",
      ),
    );
    expect(screen.getByTestId("isLoading").textContent).toBe("false");
    expect(screen.getByTestId("displayName").textContent).toBe("none");
  });

  it("falls back to a generic Japanese message for a non-ApiRequestError rejection", async () => {
    vi.mocked(getTenantConfig).mockRejectedValue(new Error("unexpected bug"));

    render(
      <TenantConfigProvider>
        <Probe />
      </TenantConfigProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("error").textContent).toBe(
        "テナント設定の取得に失敗しました。時間をおいて再度お試しください。",
      ),
    );
  });
});
