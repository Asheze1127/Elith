// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FeedbackButtons } from "./FeedbackButtons";
import { sendFeedback } from "@/lib/api/feedback";

vi.mock("@/lib/api/feedback", () => ({
  sendFeedback: vi.fn(),
}));

describe("FeedbackButtons", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("submits good feedback immediately", async () => {
    vi.mocked(sendFeedback).mockResolvedValue({
      id: 1,
      answer_id: 10,
      rating: "good",
      reason_category: null,
      comment: null,
      created_at: "2026-07-03T00:00:00Z",
    });

    render(<FeedbackButtons answerId={10} reasonCategories={["古い根拠"]} />);
    fireEvent.click(screen.getByRole("button", { name: "良い" }));

    await waitFor(() =>
      expect(sendFeedback).toHaveBeenCalledWith({
        answer_id: 10,
        rating: "good",
        reason_category: null,
        comment: null,
      }),
    );
    expect(screen.getByText("送信しました")).toBeTruthy();
  });

  it("submits bad feedback with a reason category", async () => {
    vi.mocked(sendFeedback).mockResolvedValue({
      id: 2,
      answer_id: 10,
      rating: "bad",
      reason_category: "誤った引用",
      comment: "引用先が違います",
      created_at: "2026-07-03T00:00:00Z",
    });

    render(<FeedbackButtons answerId={10} reasonCategories={["古い根拠", "誤った引用"]} />);
    fireEvent.click(screen.getByRole("button", { name: "悪い" }));
    fireEvent.change(screen.getByLabelText("理由カテゴリ"), {
      target: { value: "誤った引用" },
    });
    fireEvent.change(screen.getByLabelText("コメント"), {
      target: { value: "引用先が違います" },
    });
    fireEvent.click(screen.getByRole("button", { name: "送信" }));

    await waitFor(() =>
      expect(sendFeedback).toHaveBeenCalledWith({
        answer_id: 10,
        rating: "bad",
        reason_category: "誤った引用",
        comment: "引用先が違います",
      }),
    );
  });
});
