import { apiPost } from "./client";
import type { FeedbackRequest, FeedbackResponse } from "@/types/feedback";

export function sendFeedback(request: FeedbackRequest): Promise<FeedbackResponse> {
  return apiPost<FeedbackResponse>("/feedback", request);
}
