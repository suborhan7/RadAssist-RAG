import { defineConfig } from "vitest/config";
import path from "node:path";

/**
 * Phase 18: this project's first frontend test runner (previously zero
 * *.test.ts files existed anywhere -- see phase18_diff_view_architecture.md
 * Step 2). Vitest, not Jest, chosen for near-zero-config native ESM/TS
 * support matching this Next.js 16 App Router stack -- confirmed with the
 * user before adding, same discipline as confirming `diff` wasn't already
 * a dependency before installing it.
 *
 * Only the `@/*` alias needs wiring here (tsconfig.json's existing path
 * mapping) -- Vitest runs on Vite, which doesn't read tsconfig `paths`
 * automatically the way Next.js's own bundler does.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
  },
});
