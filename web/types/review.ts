import type { FeedbackResponse } from "./feedback";
import type { AnswerStatus } from "./chat";

export interface ReviewItem {
  answer_id: number;
  query: string;
  answer: string;
  status: AnswerStatus;
  mode: string | null;
  created_at: string;
  feedback: FeedbackResponse[];
}
