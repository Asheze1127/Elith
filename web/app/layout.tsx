import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Elith",
  description: "Elith RAG chat platform",
};

// Routing-only layer: this file only wires up global styles and the
// client-side Providers wrapper. Actual UI lives in components/.
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
