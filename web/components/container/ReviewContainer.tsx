"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiRequestError } from "@/lib/api/client";
import { getReviewCandidates } from "@/lib/api/review";
import { StatusBadge } from "@/components/presentational/StatusBadge";
import { useTenantConfig } from "@/hooks/useTenantConfig";
import type { ReviewItem } from "@/types/review";

export function ReviewContainer() {
  const { config, isLoading: isConfigLoading, error: configError } = useTenantConfig();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getReviewCandidates()
      .then((nextItems) => {
        if (cancelled) return;
        setItems(nextItems);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof ApiRequestError
            ? cause.message
            : "改善候補の取得に失敗しました。",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
          <h1>改善候補</h1>
          <p>{config.display_name}</p>
        </div>
        <nav className="top-nav" aria-label="画面">
          <Link href="/">チャット</Link>
          <Link href="/documents">ドキュメント管理</Link>
        </nav>
      </header>
      <section className="admin-panel review-panel" aria-label="改善候補一覧">
        {error ? (
          <p className="chat-alert" role="alert">
            {error}
          </p>
        ) : null}
        {isLoading ? <p>読み込み中</p> : null}
        {!isLoading && items.length === 0 ? (
          <div className="empty-state" aria-label="空状態">
            <p>改善候補はありません。</p>
          </div>
        ) : null}
        {items.length > 0 ? (
          <ul className="review-list">
            {items.map((item) => (
              <li key={item.answer_id} className="review-list__item">
                <div className="review-list__header">
                  <strong>{item.query}</strong>
                  <StatusBadge status={item.status} />
                </div>
                <p>{item.answer}</p>
                {item.feedback.length > 0 ? (
                  <ul className="review-list__feedback">
                    {item.feedback.map((feedback) => (
                      <li key={feedback.id}>
                        <span>{feedback.reason_category ?? "理由なし"}</span>
                        {feedback.comment ? <p>{feedback.comment}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </main>
  );
}
