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
      answer_id: 1,
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
    fireEvent.click(screen.getByRole("button", { name: "external" }));
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

  it("renders citations from the chat response", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(sendChatMessage).mockResolvedValue({
      answer_id: 1,
      answer: "請求処理は月末締めです。",
      citations: [
        {
          chunk_id: 1,
          document_id: 2,
          title: "請求処理FAQ",
          snippet: "請求処理は月末締めです。",
          source_uri: "https://example.test/billing",
          source_updated_at: "2026-01-02T00:00:00Z",
        },
      ],
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
      target: { value: "請求処理" },
    });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(await screen.findByLabelText("引用")).toBeTruthy();
    expect(screen.getByLabelText("引用").textContent).toContain("請求処理FAQ");
    expect(screen.getByLabelText("引用").textContent).toContain("2026-01-02");
  });

  it("renders status and warnings from the chat response", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(sendChatMessage).mockResolvedValue({
      answer_id: 1,
      answer: "確認が必要な回答です。",
      citations: [],
      status: "needs_review",
      warnings: [
        {
          type: "stale_sources",
          message: "古い資料を参照しています。",
        },
      ],
    });

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

    expect(await screen.findByLabelText("回答ステータス")).toBeTruthy();
    expect(screen.getByLabelText("回答ステータス").textContent).toBe(
      "確認が必要",
    );
    expect(screen.getByLabelText("警告").textContent).toContain(
      "古い資料を参照しています。",
    );
  });

  it("renders the feedback panel after an answer", async () => {
    vi.mocked(getTenantConfig).mockResolvedValue(sampleConfig);
    vi.mocked(sendChatMessage).mockResolvedValue({
      answer_id: 123,
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
      target: { value: "請求処理" },
    });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));

    expect(await screen.findByLabelText("フィードバック")).toBeTruthy();
  });
});
