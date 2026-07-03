// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useChat } from "./useChat";
import { ApiRequestError } from "@/lib/api/client";
import { sendChatMessage } from "@/lib/api/chat";

vi.mock("@/lib/api/chat", () => ({
  sendChatMessage: vi.fn(),
}));

function Probe() {
  const { response, isSubmitting, error, submit } = useChat();
  return (
    <>
      <button
        type="button"
        onClick={() => submit({ query: "請求処理", mode: "internal" })}
      >
        submit
      </button>
      <div data-testid="loading">{String(isSubmitting)}</div>
      <div data-testid="answer">{response?.answer ?? "none"}</div>
      <div data-testid="error">{error ?? "none"}</div>
    </>
  );
}

describe("useChat", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("stores the chat response after a successful submit", async () => {
    vi.mocked(sendChatMessage).mockResolvedValue({
      answer_id: 1,
      answer: "回答です",
      citations: [],
      status: "answered",
      warnings: [],
    });

    render(<Probe />);
    fireEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() =>
      expect(screen.getByTestId("answer").textContent).toBe("回答です"),
    );
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("error").textContent).toBe("none");
    expect(sendChatMessage).toHaveBeenCalledWith({
      query: "請求処理",
      mode: "internal",
    });
  });

  it("surfaces ApiRequestError messages for the UI", async () => {
    vi.mocked(sendChatMessage).mockRejectedValue(
      new ApiRequestError("回答生成に失敗しました", 502),
    );

    render(<Probe />);
    fireEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() =>
      expect(screen.getByTestId("error").textContent).toBe(
        "回答生成に失敗しました",
      ),
    );
    expect(screen.getByTestId("answer").textContent).toBe("none");
  });
});
