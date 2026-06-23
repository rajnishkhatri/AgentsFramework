import type { StorybookConfig } from "@storybook/nextjs-vite";

/**
 * Storybook 9 config (PS1). Framework: nextjs-vite — aligns with the repo's
 * Vite 7 / Vitest 4 and Next 15 / React 19, avoids the webpack builder.
 *
 * Stories live next to components (`*.stories.tsx`). The primitive layer
 * (components/ui) is the design-sync "shape" source (plan §2.5 / PS1).
 */
const config: StorybookConfig = {
  stories: ["../components/**/*.stories.@(tsx|ts)"],
  addons: ["@storybook/addon-a11y", "@storybook/addon-docs"],
  framework: {
    name: "@storybook/nextjs-vite",
    options: {},
  },
  staticDirs: ["../public"],
};

export default config;
