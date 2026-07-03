import { apiGet, apiPost, getLocalTenantId } from "./client";
import type { DocumentRecord, IngestDocumentRequest } from "@/types/documents";

export function listDocuments(): Promise<DocumentRecord[]> {
  const tenantId = getLocalTenantId();
  return apiGet<DocumentRecord[]>(`/documents?tenant_id=${tenantId}`);
}

export function ingestDocument(
  request: IngestDocumentRequest,
): Promise<DocumentRecord> {
  const tenantId = getLocalTenantId();
  return apiPost<DocumentRecord>("/documents", {
    tenant_id: tenantId,
    ...request,
  });
}
