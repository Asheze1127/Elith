"use client";

import { useState } from "react";
import { ApiRequestError } from "@/lib/api/client";
import { sendFeedback } from "@/lib/api/feedback";
import type { FeedbackRating } from "@/types/feedback";

interface FeedbackButtonsProps {
  answerId: number;
  reasonCategories: string[];
}

export function FeedbackButtons({
  answerId,
  reasonCategories,
}: FeedbackButtonsProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedRating, setSelectedRating] = useState<FeedbackRating | null>(null);
  const [reasonCategory, setReasonCategory] = useState(reasonCategories[0] ?? "");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submitFeedback(rating: FeedbackRating) {
    setIsSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await sendFeedback({
        answer_id: answerId,
        rating,
        reason_category: rating === "bad" ? reasonCategory || null : null,
        comment: rating === "bad" ? comment.trim() || null : null,
      });
      setMessage("送信しました");
      setSelectedRating(null);
      setComment("");
    } catch (cause: unknown) {
      setError(
        cause instanceof ApiRequestError
          ? cause.message
          : "フィードバックの送信に失敗しました。",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="feedback-panel" aria-label="フィードバック">
      <div className="feedback-panel__actions">
        <button
          type="button"
          className="feedback-panel__button"
          disabled={isSubmitting}
          onClick={() => submitFeedback("good")}
        >
          良い
        </button>
        <button
          type="button"
          className="feedback-panel__button feedback-panel__button--bad"
          disabled={isSubmitting}
          aria-pressed={selectedRating === "bad"}
          onClick={() => setSelectedRating("bad")}
        >
          悪い
        </button>
      </div>
      {selectedRating === "bad" ? (
        <div className="feedback-panel__details">
          {reasonCategories.length > 0 ? (
            <label className="field">
              <span>理由カテゴリ</span>
              <select
                value={reasonCategory}
                onChange={(event) => setReasonCategory(event.target.value)}
              >
                {reasonCategories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="field">
            <span>コメント</span>
            <textarea
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              rows={3}
            />
          </label>
          <button
            type="button"
            className="feedback-panel__submit"
            disabled={isSubmitting || (reasonCategories.length > 0 && !reasonCategory)}
            onClick={() => submitFeedback("bad")}
          >
            送信
          </button>
        </div>
      ) : null}
      {message ? <p className="inline-status">{message}</p> : null}
      {error ? (
        <p className="chat-alert" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
