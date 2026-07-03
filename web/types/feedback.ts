export type FeedbackRating = "good" | "bad";

export interface FeedbackRequest {
  answer_id: number;
  rating: FeedbackRating;
  reason_category?: string | null;
  comment?: string | null;
}

export interface FeedbackResponse {
  id: number;
  answer_id: number;
  rating: FeedbackRating;
  reason_category: string | null;
  comment: string | null;
  created_at: string;
}
