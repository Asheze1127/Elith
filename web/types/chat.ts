// DTOs for the POST /chat response (docs/details/process-flow.md §2):
// {answer, citations, status, warnings}.

// Built-in statuses are defined by backend/app/models/answer.py. The backend
// intentionally stores status as tenant-config data, so future tenants may add
// their own string statuses without a frontend schema migration.
export type AnswerStatus =
  | "answered"
  | "needs_review"
  | "no_data"
  | (string & {});

export interface Citation {
  chunk_id: number | null;
  document_id: number | null;
  title: string | null;
  snippet: string | null;
  // Source metadata shown when tenant_config.answer.show_source_metadata is true.
  source_uri: string | null;
  source_updated_at: string | null;
}

export interface Warning {
  // Named after the pipeline step that raised it, e.g. "stale_sources" | "contradiction".
  type: string;
  message: string;
}

export interface ChatResponse {
  answer_id: number;
  answer: string;
  citations: Citation[];
  status: AnswerStatus;
  warnings: Warning[];
}

export interface ChatRequest {
  query: string;
  // Answer mode selected by the user, one of tenant_config.answer.modes.
  mode?: string;
  workspace_id?: number | null;
}
