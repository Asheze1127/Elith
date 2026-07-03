"use client";

import type { ReactNode } from "react";
import { TenantConfigProvider } from "@/context/TenantConfigContext";

// Single place to mount all client-side context providers so app/layout.tsx
// (a server component) stays free of "use client" concerns.
//
// NOTE: TenantConfigProvider is a passthrough stub for now (#13, scaffold
// only). #14 will replace it with the real GET /tenant/config fetch + cache.
export function Providers({ children }: { children: ReactNode }) {
  return <TenantConfigProvider>{children}</TenantConfigProvider>;
}
