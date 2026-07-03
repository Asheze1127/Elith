// DTO for the tenant_config DB row (docs/details/multi-tenant-design.md §3).
// This is the sole place per-tenant differences are expressed: never branch
// on tenant identity in components, only on fields of this config.

export interface TenantConfigSearch {
  // e.g. "all" (A-company) or a department/line/equipment filter (B-company).
  scope: string;
}

export interface TenantConfigAnswer {
  // Answer modes the tenant supports, e.g. ["external", "internal"].
  modes: string[];
  default_mode: string;
  citation: "required" | "optional";
  // Action to take when grounding is weak, e.g. "needs_review".
  low_confidence_action: string;
  show_source_metadata: boolean;
}

export interface TenantConfigWarnings {
  stale_sources: boolean;
  contradiction: boolean;
}

export interface TenantConfigCategoryPolicy {
  tone?: string;
  require_human_check?: boolean;
  // Additional bespoke policy fields the backend may add per category.
  [key: string]: unknown;
}

export interface TenantConfigFeedback {
  enabled: boolean;
  reason_categories: string[];
}

export interface TenantConfig {
  tenant_id: string;
  display_name: string;
  search: TenantConfigSearch;
  answer: TenantConfigAnswer;
  // Named pipeline steps to run in order, e.g. ["retrieve", "stale_warning", ...].
  pipeline: string[];
  warnings: TenantConfigWarnings;
  category_policies: Record<string, TenantConfigCategoryPolicy>;
  feedback: TenantConfigFeedback;
}
