// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CitationPanel } from "./CitationPanel";
import type { Citation } from "@/types/chat";

const citation: Citation = {
  chunk_id: 10,
  document_id: 20,
  title: "請求処理FAQ",
  snippet: "請求処理は月末締めです。",
  source_uri: "https://example.test/billing",
  source_updated_at: "2026-01-02T00:00:00Z",
};

describe("CitationPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders citation title, snippet, URL, and source update date", () => {
    render(<CitationPanel citations={[citation]} showSourceMetadata />);

    expect(screen.getByLabelText("引用").textContent).toContain("請求処理FAQ");
    expect(screen.getByLabelText("引用").textContent).toContain(
      "請求処理は月末締めです。",
    );
    expect(screen.getByLabelText("引用").textContent).toContain(
      "https://example.test/billing",
    );
    expect(screen.getByLabelText("引用").textContent).toContain("2026-01-02");
  });

  it("hides URL and update date when source metadata is disabled", () => {
    render(
      <CitationPanel citations={[citation]} showSourceMetadata={false} />,
    );

    expect(screen.getByLabelText("引用").textContent).toContain("請求処理FAQ");
    expect(screen.getByLabelText("引用").textContent).not.toContain(
      "https://example.test/billing",
    );
    expect(screen.getByLabelText("引用").textContent).not.toContain(
      "2026-01-02",
    );
  });
});
