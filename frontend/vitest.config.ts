import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "node",
    globals: false,
    include: [
      "lib/**/*.test.ts",
      "lib/**/*.test.tsx",
      "tests/**/*.test.ts",
      "tests/**/*.test.tsx",
      "middleware.test.ts",
      "app/**/*.test.ts",
      "app/**/*.test.tsx",
      "components/**/*.test.ts",
      "components/**/*.test.tsx",
      "scripts/**/*.test.ts",
    ],
    exclude: ["node_modules", ".next", "dist"],
    testTimeout: 10_000,
    environmentMatchGlobs: [
      ["lib/components/**", "jsdom"],
      ["tests/components/**", "jsdom"],
      ["components/**", "jsdom"],
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
