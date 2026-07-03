// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ReviewContainer } from "./ReviewContainer";
import { TenantConfigProvider } from "@/context/TenantConfigContext";
import { getReviewCandidates } from "@/lib/api/review";
import { getTenantConfig } from "@/lib/api/tenant";
import type { TenantConfig } from "@/types/tenant-config";

vi.mock("@/lib/api/review", () => ({
  getReviewCandidates: vi.fn(),
}));

vi.mock("@/lib/api/tenant", () => ({
  getTenantConfig: vi.fn(),
}));

const sampleConfig: TenantConfig = {
  tenant_id: "a_shinonome",
  display_name: "東雲ビジネスサポート",
  search: { scope: "all" },
  answer: {
    modes: ["internal", "external"],
    default_mode: "internal",
    citation: "required",
    low_confidence_action: "needs_review",
    show_source_metadata: true,
  },
  pipeline: ["retrieve", "stale_warning", "contradiction_check", "ground_check", "cite"],
  warnings: { stale_sources: true, contradiction: true },
  category_policies: {},
  feedback: { enabled: true, reason_categories: ["古い根拠"] },
};

describe("ReviewContainer", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders review candidates", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(getReviewCandidates).mockResolvedValue([
      {
        answer_id: 1,
        query: "請求書の再発行はできますか",
        answer: "可能です。",
        status: "answered",
        mode: "internal",
        created_at: "2026-07-03T00:00:00Z",
        feedback: [
          {
            id: 10,
            answer_id: 1,
            rating: "bad",
            reason_category: "古い根拠",
            comment: "旧資料です",
            created_at: "2026-07-03T00:00:00Z",
          },
        ],
      },
    ]);

    render(
      <TenantConfigProvider>
        <ReviewContainer />
      </TenantConfigProvider>,
    );

    expect(await screen.findByText("請求書の再発行はできますか")).toBeTruthy();
    expect(screen.getByText("古い根拠")).toBeTruthy();
    expect(screen.getByText("旧資料です")).toBeTruthy();
  });

  it("renders empty state", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(getReviewCandidates).mockResolvedValue([]);

    render(
      <TenantConfigProvider>
        <ReviewContainer />
      </TenantConfigProvider>,
    );

    expect(await screen.findByText("改善候補はありません。")).toBeTruthy();
  });
});
