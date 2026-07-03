import { afterEach, describe, expect, it, vi } from "vitest";

function mockResponse(status: number, body: unknown) {
  const text = body === undefined ? "" : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(text),
  } as Response;
}

describe("documents api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("lists documents for the configured local tenant", async () => {
    vi.stubEnv("NEXT_PUBLIC_LOCAL_TENANT_ID", "322");
    const { listDocuments } = await import("./documents");
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    await listDocuments();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/documents?tenant_id=322"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts document ingestion with tenant_id from env", async () => {
    vi.stubEnv("NEXT_PUBLIC_LOCAL_TENANT_ID", "322");
    const { ingestDocument } = await import("./documents");
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(201, {
        id: 1,
        tenant_id: 322,
        workspace_id: null,
        title: "FAQ",
        source_uri: null,
        chunk_count: 1,
        created_at: "2026-07-03T00:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await ingestDocument({ title: "FAQ", content: "本文" });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/documents"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          tenant_id: 322,
          title: "FAQ",
          content: "本文",
        }),
      }),
    );
  });
});
