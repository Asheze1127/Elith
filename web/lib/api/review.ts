import { apiGet } from "./client";
import type { ReviewItem } from "@/types/review";

export function getReviewCandidates(): Promise<ReviewItem[]> {
  return apiGet<ReviewItem[]>("/review");
}
