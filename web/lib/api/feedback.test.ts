import { afterEach, describe, expect, it, vi } from "vitest";
import { sendFeedback } from "./feedback";

function mockResponse(status: number, body: unknown) {
  const text = body === undefined ? "" : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  } as Response;
}

describe("sendFeedback", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts feedback to /feedback", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(201, {
        id: 1,
        answer_id: 42,
        rating: "bad",
        reason_category: "古い根拠",
        comment: "旧資料です",
        created_at: "2026-07-03T00:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendFeedback({
      answer_id: 42,
      rating: "bad",
      reason_category: "古い根拠",
      comment: "旧資料です",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/feedback"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          answer_id: 42,
          rating: "bad",
          reason_category: "古い根拠",
          comment: "旧資料です",
        }),
      }),
    );
    expect(result.answer_id).toBe(42);
  });
});
