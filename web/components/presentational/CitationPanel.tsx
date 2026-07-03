import type { Citation } from "@/types/chat";

interface CitationPanelProps {
  citations: Citation[];
  showSourceMetadata: boolean;
}

export function CitationPanel({
  citations,
  showSourceMetadata,
}: CitationPanelProps) {
  return (
    <section className="citation-panel" aria-label="引用">
      <h2>引用</h2>
      {citations.length === 0 ? (
        <p className="citation-panel__empty">引用はありません</p>
      ) : (
        <ol className="citation-panel__list">
          {citations.map((citation, index) => (
            <li
              className="citation-panel__item"
              key={`${citation.document_id ?? "document"}-${citation.chunk_id ?? index}`}
            >
              <div className="citation-panel__title">
                {citation.title ?? "資料名未設定"}
              </div>
              {citation.snippet ? (
                <blockquote className="citation-panel__snippet">
                  {citation.snippet}
                </blockquote>
              ) : null}
              {showSourceMetadata ? (
                <dl className="citation-panel__meta">
                  {citation.source_uri ? (
                    <>
                      <dt>URL</dt>
                      <dd>
                        {/^https?:\/\//i.test(citation.source_uri) ? (
                          <a href={citation.source_uri}>{citation.source_uri}</a>
                        ) : (
                          <span>{citation.source_uri}</span>
                        )}
                      </dd>
                    </>
                  ) : null}
                  {citation.source_updated_at ? (
                    <>
                      <dt>更新日</dt>
                      <dd>{citation.source_updated_at.slice(0, 10)}</dd>
                    </>
                  ) : null}
                </dl>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
