"use client";

import { createContext, type ReactNode } from "react";
import type { TenantConfig } from "@/types/tenant-config";

// Config-driven-rendering supply source: the rest of the UI reads
// tenant_config from here instead of branching on tenant identity directly.
//
// Stub only (#13, scaffold). #14 replaces this with a real provider that
// fetches GET /tenant/config once and exposes { config, isLoading, error }.
export const TenantConfigContext = createContext<TenantConfig | null>(null);

export function TenantConfigProvider({ children }: { children: ReactNode }) {
  return (
    <TenantConfigContext.Provider value={null}>
      {children}
    </TenantConfigContext.Provider>
  );
}
