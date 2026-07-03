"use client";

import { useContext } from "react";
import {
  TenantConfigContext,
  type TenantConfigContextValue,
} from "@/context/TenantConfigContext";

// Standard context-hook pattern (docs/details/directory.md §2:
// "hooks/useTenantConfig.ts # context から config を読む"). Throws a clear
// developer-facing error when used outside <TenantConfigProvider> instead of
// silently returning null and pushing a confusing crash onto the caller.
export function useTenantConfig(): TenantConfigContextValue {
  const context = useContext(TenantConfigContext);
  if (context === null) {
    throw new Error(
      "useTenantConfig must be used within a TenantConfigProvider",
    );
  }
  return context;
}
