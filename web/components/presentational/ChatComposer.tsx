"use client";

import type { FormEvent } from "react";
import type { TenantConfig } from "@/types/tenant-config";

interface ChatComposerProps {
  config: TenantConfig;
  query: string;
  mode: string;
  isSubmitting: boolean;
  onQueryChange: (query: string) => void;
  onModeChange: (mode: string) => void;
  onSubmit: () => void;
}

export function ChatComposer({
  config,
  query,
  mode,
  isSubmitting,
  onQueryChange,
  onModeChange,
  onSubmit,
}: ChatComposerProps) {
  const modes = config.answer.modes;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <div className="chat-composer__row">
        <label className="chat-composer__label" htmlFor="chat-query">
          質問
        </label>
        {modes.length > 1 ? (
          <select
            className="chat-composer__mode"
            value={mode}
            onChange={(event) => onModeChange(event.target.value)}
            aria-label="回答モード"
          >
            {modes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <textarea
        id="chat-query"
        className="chat-composer__textarea"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        rows={4}
      />
      <div className="chat-composer__actions">
        <button
          className="chat-composer__submit"
          type="submit"
          disabled={isSubmitting || query.trim().length === 0}
        >
          {isSubmitting ? "送信中" : "送信"}
        </button>
      </div>
    </form>
  );
}
