export interface DocumentRecord {
  id: number;
  tenant_id: number;
  workspace_id: number | null;
  title: string;
  source_uri: string | null;
  chunk_count: number;
  created_at: string;
}

export interface IngestDocumentRequest {
  title: string;
  content: string;
  workspace_id?: number | null;
  source_uri?: string | null;
  source_updated_at?: string | null;
}
