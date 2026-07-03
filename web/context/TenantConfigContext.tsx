"use client";

import { createContext, useEffect, useState, type ReactNode } from "react";
import type { TenantConfig } from "@/types/tenant-config";
import { getTenantConfig } from "@/lib/api/tenant";
import { ApiRequestError } from "@/lib/api/client";

// Config-driven-rendering supply source: the rest of the UI reads
// tenant_config from here instead of branching on tenant identity directly
// (docs/details/directory.md §2).
export interface TenantConfigContextValue {
  config: TenantConfig | null;
  isLoading: boolean;
  error: string | null;
}

// `null` is reserved for "no provider mounted" so hooks/useTenantConfig.ts can
// tell that case apart from "provider mounted, still loading" (which is a
// real, non-null value with isLoading: true).
export const TenantConfigContext =
  createContext<TenantConfigContextValue | null>(null);

export function TenantConfigProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<TenantConfigContextValue>({
    config: null,
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    // Guards against setting state after unmount if the fetch resolves late.
    let cancelled = false;

    getTenantConfig()
      .then((config) => {
        if (cancelled) return;
        setValue({ config, isLoading: false, error: null });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        // ApiRequestError.message is already a user-facing Japanese message
        // (lib/api/client.ts normalizes both HTTP and network failures into
        // it), so surface it as-is. Anything else is an unexpected bug
        // rather than a handled API failure, so fall back to a generic
        // message instead of leaking internals to the user.
        const message =
          cause instanceof ApiRequestError
            ? cause.message
            : "テナント設定の取得に失敗しました。時間をおいて再度お試しください。";
        setValue({ config: null, isLoading: false, error: message });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <TenantConfigContext.Provider value={value}>
      {children}
    </TenantConfigContext.Provider>
  );
}
