import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
    exclude: ["node_modules", ".next"],
  },
  resolve: {
    // Mirror tsconfig.json's "@/*" -> "./*" path alias for test runs.
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
