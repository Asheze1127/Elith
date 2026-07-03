import { apiPost } from "./client";
import type { ChatRequest, ChatResponse } from "@/types/chat";

export function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  return apiPost<ChatResponse>("/chat", request);
}
