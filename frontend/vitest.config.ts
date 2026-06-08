import { defineConfig } from "vitest/config";
import path from "node:path";

const sharedTest = {
  globals: false,
  exclude: ["node_modules", ".next", "dist"],
  testTimeout: 10_000,
};

const resolveAlias = {
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
};

export default defineConfig({
  ...resolveAlias,
  test: {
    projects: [
      {
        ...resolveAlias,
        test: {
          ...sharedTest,
          name: "jsdom",
          environment: "jsdom",
          include: [
            "lib/components/**/*.test.ts",
            "lib/components/**/*.test.tsx",
            "tests/components/**/*.test.ts",
            "tests/components/**/*.test.tsx",
            "components/**/*.test.ts",
            "components/**/*.test.tsx",
          ],
        },
      },
      {
        ...resolveAlias,
        test: {
          ...sharedTest,
          name: "node",
          environment: "node",
          include: [
            "lib/**/*.test.ts",
            "lib/**/*.test.tsx",
            "tests/**/*.test.ts",
            "tests/**/*.test.tsx",
            "middleware.test.ts",
            "app/**/*.test.ts",
            "app/**/*.test.tsx",
            "scripts/**/*.test.ts",
          ],
          exclude: [
            ...sharedTest.exclude,
            "lib/components/**",
            "tests/components/**",
            "components/**",
          ],
        },
      },
    ],
  },
});
