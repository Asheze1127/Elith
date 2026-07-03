// DTOs for the POST /chat response (docs/details/process-flow.md §2):
// {answer, citations, status, warnings}.

// "ok" = normal answer, "needs_review" = grounding was weak (ground_check),
// "no_data" = retrieval hit zero chunks.
export type AnswerStatus = "ok" | "needs_review" | "no_data";

export interface Citation {
  document_id: string;
  title: string;
  snippet?: string;
  // Source metadata shown when tenant_config.answer.show_source_metadata is true.
  updated_at?: string;
}

export interface Warning {
  // Named after the pipeline step that raised it, e.g. "stale_sources" | "contradiction".
  type: string;
  message: string;
}

export interface Answer {
  answer: string;
  citations: Citation[];
  status: AnswerStatus;
  warnings: Warning[];
}

export interface ChatRequest {
  query: string;
  // Answer mode selected by the user, one of tenant_config.answer.modes.
  mode?: string;
}
