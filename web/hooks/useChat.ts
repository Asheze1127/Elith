"use client";

import { useCallback, useState } from "react";
import { ApiRequestError } from "@/lib/api/client";
import { sendChatMessage } from "@/lib/api/chat";
import type { ChatRequest, ChatResponse } from "@/types/chat";

export interface UseChatResult {
  response: ChatResponse | null;
  isSubmitting: boolean;
  error: string | null;
  submit: (request: ChatRequest) => Promise<ChatResponse | null>;
}

export function useChat(): UseChatResult {
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (request: ChatRequest) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const nextResponse = await sendChatMessage(request);
      setResponse(nextResponse);
      return nextResponse;
    } catch (cause: unknown) {
      const message =
        cause instanceof ApiRequestError
          ? cause.message
          : "回答の取得に失敗しました。時間をおいて再度お試しください。";
      setResponse(null);
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  return { response, isSubmitting, error, submit };
}
