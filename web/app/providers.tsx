"use client";

import type { ReactNode } from "react";
import { TenantConfigProvider } from "@/context/TenantConfigContext";

// Single place to mount all client-side context providers so app/layout.tsx
// (a server component) stays free of "use client" concerns.
export function Providers({ children }: { children: ReactNode }) {
  return <TenantConfigProvider>{children}</TenantConfigProvider>;
}
