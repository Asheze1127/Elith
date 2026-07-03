"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiRequestError } from "@/lib/api/client";
import { ingestDocument, listDocuments } from "@/lib/api/documents";
import { useTenantConfig } from "@/hooks/useTenantConfig";
import type { DocumentRecord } from "@/types/documents";

export function DocumentsContainer() {
  const { config, isLoading: isConfigLoading, error: configError } = useTenantConfig();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [sourceUpdatedAt, setSourceUpdatedAt] = useState("");
  const [content, setContent] = useState("");

  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((items) => {
        if (cancelled) return;
        setDocuments(items);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiRequestError
            ? cause.message
            : "ドキュメント一覧の取得に失敗しました。",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit() {
    if (!title.trim() || !content.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const document = await ingestDocument({
        title: title.trim(),
        content: content.trim(),
        source_uri: sourceUri.trim() || null,
        source_updated_at: sourceUpdatedAt
          ? `${sourceUpdatedAt}T00:00:00Z`
          : null,
      });
      setDocuments((current) => [...current, document]);
      setTitle("");
      setSourceUri("");
      setSourceUpdatedAt("");
      setContent("");
    } catch (cause: unknown) {
      setError(
        cause instanceof ApiRequestError
          ? cause.message
          : "ドキュメントの取り込みに失敗しました。",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isConfigLoading) {
    return <main className="chat-shell">読み込み中</main>;
  }

  if (configError || !config) {
    return <main className="chat-shell chat-shell--error">{configError}</main>;
  }

  return (
    <main className="chat-shell">
      <header className="chat-header">
        <div>
          <h1>ドキュメント管理</h1>
          <p>{config.display_name}</p>
        </div>
        <nav className="top-nav" aria-label="画面">
          <Link href="/">チャット</Link>
          <Link href="/review">改善候補</Link>
        </nav>
      </header>
      <div className="admin-layout">
        <section className="admin-panel" aria-label="取り込み">
          <h2>取り込み</h2>
          <label className="field">
            <span>タイトル</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label className="field">
            <span>出典URL</span>
            <input
              value={sourceUri}
              onChange={(event) => setSourceUri(event.target.value)}
            />
          </label>
          <label className="field">
            <span>資料更新日</span>
            <input
              type="date"
              value={sourceUpdatedAt}
              onChange={(event) => setSourceUpdatedAt(event.target.value)}
            />
          </label>
          <label className="field">
            <span>本文</span>
            <textarea
              rows={8}
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="primary-button"
            disabled={isSubmitting || !title.trim() || !content.trim()}
            onClick={handleSubmit}
          >
            取り込む
          </button>
        </section>
        <section className="admin-panel" aria-label="資料一覧">
          <h2>資料一覧</h2>
          {error ? (
            <p className="chat-alert" role="alert">
              {error}
            </p>
          ) : null}
          {isLoading ? <p>読み込み中</p> : null}
          {!isLoading && documents.length === 0 ? (
            <div className="empty-state" aria-label="空状態">
              <p>資料はまだありません。</p>
            </div>
          ) : null}
          {documents.length > 0 ? (
            <ul className="record-list">
              {documents.map((document) => (
                <li key={document.id} className="record-list__item">
                  <div>
                    <strong>{document.title}</strong>
                    <p>{document.chunk_count} chunks</p>
                  </div>
                  {document.source_uri ? <span>{document.source_uri}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </div>
    </main>
  );
}
