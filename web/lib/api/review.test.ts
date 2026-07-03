import { afterEach, describe, expect, it, vi } from "vitest";
import { getReviewCandidates } from "./review";

function mockResponse(status: number, body: unknown) {
  const text = body === undefined ? "" : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  } as Response;
}

describe("getReviewCandidates", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests GET /review", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getReviewCandidates();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/review"),
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual([]);
  });
});
