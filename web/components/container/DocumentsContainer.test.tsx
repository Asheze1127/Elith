// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DocumentsContainer } from "./DocumentsContainer";
import { TenantConfigProvider } from "@/context/TenantConfigContext";
import { ingestDocument, listDocuments } from "@/lib/api/documents";
import { getTenantConfig } from "@/lib/api/tenant";
import type { TenantConfig } from "@/types/tenant-config";

vi.mock("@/lib/api/documents", () => ({
  listDocuments: vi.fn(),
  ingestDocument: vi.fn(),
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

describe("DocumentsContainer", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders empty state and ingests a document", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(listDocuments).mockResolvedValue([]);
    vi.mocked(ingestDocument).mockResolvedValue({
      id: 1,
      tenant_id: 322,
      workspace_id: null,
      title: "FAQ",
      source_uri: null,
      chunk_count: 2,
      created_at: "2026-07-03T00:00:00Z",
    });

    render(
      <TenantConfigProvider>
        <DocumentsContainer />
      </TenantConfigProvider>,
    );

    await screen.findByRole("heading", { name: "ドキュメント管理" });
    expect(await screen.findByText("資料はまだありません。")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("タイトル"), { target: { value: "FAQ" } });
    fireEvent.change(screen.getByLabelText("本文"), { target: { value: "本文" } });
    fireEvent.click(screen.getByRole("button", { name: "取り込む" }));

    await waitFor(() =>
      expect(ingestDocument).toHaveBeenCalledWith({
        title: "FAQ",
        content: "本文",
        source_uri: null,
        source_updated_at: null,
      }),
    );
    expect(await screen.findByText("FAQ")).toBeTruthy();
  });
});
