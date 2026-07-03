import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChatMessage } from "./chat";

function mockResponse(status: number, body: unknown) {
  const text = body === undefined ? "" : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  } as Response;
}

describe("sendChatMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the query and selected mode to /chat", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(200, {
        answer: "回答です",
        citations: [],
        status: "answered",
        warnings: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendChatMessage({
      query: "請求処理について",
      mode: "external",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/chat"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          query: "請求処理について",
          mode: "external",
        }),
      }),
    );
    expect(result.answer).toBe("回答です");
  });
});
