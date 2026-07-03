// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatContainer } from "./ChatContainer";
import { TenantConfigProvider } from "@/context/TenantConfigContext";
import { sendChatMessage } from "@/lib/api/chat";
import { getTenantConfig } from "@/lib/api/tenant";
import type { TenantConfig } from "@/types/tenant-config";

vi.mock("@/lib/api/chat", () => ({
  sendChatMessage: vi.fn(),
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
  pipeline: ["ground_check", "cite"],
  warnings: { stale_sources: true, contradiction: true },
  category_policies: {},
  feedback: { enabled: true, reason_categories: [] },
};

describe("ChatContainer", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("submits a question and renders the answer", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(sendChatMessage).mockResolvedValue({
      answer: "請求処理は月末締めです。",
      citations: [],
      status: "answered",
      warnings: [],
    });

    render(
      <TenantConfigProvider>
        <ChatContainer />
      </TenantConfigProvider>,
    );

    await screen.findByRole("heading", { name: "東雲ビジネスサポート" });
    fireEvent.change(screen.getByLabelText("質問"), {
      target: { value: "請求処理の締め日は？" },
    });
    fireEvent.change(screen.getByLabelText("回答モード"), {
      target: { value: "external" },
    });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));

    await waitFor(() =>
      expect(sendChatMessage).toHaveBeenCalledWith({
        query: "請求処理の締め日は？",
        mode: "external",
      }),
    );
    expect((await screen.findByLabelText("回答")).textContent).toContain(
      "請求処理は月末締めです。",
    );
  });

  it("renders a user-facing error when chat submission fails", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(sendChatMessage).mockRejectedValue(new Error("boom"));

    render(
      <TenantConfigProvider>
        <ChatContainer />
      </TenantConfigProvider>,
    );

    await screen.findByRole("heading", { name: "東雲ビジネスサポート" });
    fireEvent.change(screen.getByLabelText("質問"), {
      target: { value: "請求処理" },
    });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "回答の取得に失敗しました",
    );
  });
});
