import { apiGet } from "./client";
import type { TenantConfig } from "@/types/tenant-config";

// Backend response envelope for GET /tenant/config (see
// backend/app/api/tenant.py TenantConfigResponse): the outer `tenant_id` is
// the DB row's integer id, kept separate from any human-readable slug (e.g.
// "a_shinonome") that also lives inside `config` per
// docs/details/multi-tenant-design.md §3. The two are not guaranteed to match,
// so this layer unwraps the envelope and only ever hands callers the inner
// `config` object -- the rest of the frontend deals exclusively with
// TenantConfig and never needs to know about the backend's row id.
interface TenantConfigResponse {
  tenant_id: number;
  config: TenantConfig;
}

export async function getTenantConfig(): Promise<TenantConfig> {
  const response = await apiGet<TenantConfigResponse>("/tenant/config");
  return response.config;
}
