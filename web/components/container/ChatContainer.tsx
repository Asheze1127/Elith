"use client";

import Link from "next/link";
import { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useTenantConfig } from "@/hooks/useTenantConfig";
import { AnswerMessage } from "@/components/presentational/AnswerMessage";
import { ChatComposer } from "@/components/presentational/ChatComposer";
import { CitationPanel } from "@/components/presentational/CitationPanel";
import { FeedbackButtons } from "@/components/presentational/FeedbackButtons";
import { StatusBadge } from "@/components/presentational/StatusBadge";
import { WarningList } from "@/components/presentational/WarningList";

export function ChatContainer() {
  const { config, isLoading, error: configError } = useTenantConfig();
  const { response, isSubmitting, error: chatError, submit } = useChat();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("");

  if (isLoading) {
    return <main className="chat-shell">読み込み中</main>;
  }

  if (configError || !config) {
    return <main className="chat-shell chat-shell--error">{configError}</main>;
  }

  const selectedMode = mode || config.answer.default_mode || config.answer.modes[0] || "";

  async function handleSubmit() {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;
    await submit({
      query: trimmedQuery,
      mode: selectedMode || undefined,
    });
  }

  return (
    <main className="chat-shell">
      <header className="chat-header">
        <div>
          <h1>{config.display_name}</h1>
          <p>RAG Chat</p>
        </div>
      </header>
      <div className="chat-layout">
        <ChatComposer
          config={config}
          query={query}
          mode={selectedMode}
          isSubmitting={isSubmitting}
          onQueryChange={setQuery}
          onModeChange={setMode}
          onSubmit={handleSubmit}
        />
        {chatError ? (
          <p className="chat-alert" role="alert">
            {chatError}
          </p>
        ) : null}
        {!response && !chatError ? (
          <section className="empty-state" aria-label="空状態">
            <p>資料が未投入の場合はサンプルデータから始められます。</p>
            <Link href="/documents">ドキュメント管理</Link>
          </section>
        ) : null}
        {response ? (
          <>
            <div className="answer-toolbar">
              <StatusBadge status={response.status} />
            </div>
            <WarningList warnings={response.warnings} />
            <AnswerMessage response={response} />
            {config.answer.citation === "required" ||
            response.citations.length > 0 ? (
              <CitationPanel
                citations={response.citations}
                showSourceMetadata={config.answer.show_source_metadata}
              />
            ) : null}
            {config.feedback.enabled ? (
              <FeedbackButtons
                answerId={response.answer_id}
                reasonCategories={config.feedback.reason_categories}
              />
            ) : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
