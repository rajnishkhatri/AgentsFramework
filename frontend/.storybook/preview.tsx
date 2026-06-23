import * as React from "react";
import type { Preview, Decorator } from "@storybook/nextjs-vite";
// Pulls in Tailwind v4 + the generated @theme tokens (the §2 pipeline),
// so every story renders with the real Cursor warm-neutral tokens.
import "../app/globals.css";

/**
 * Theme decorator (PS1): drives `[data-theme]` from a toolbar toggle so the
 * §6 "dark mode (each of the above)" states are first-class. Sets the warm
 * canvas background + base text color from tokens.
 */
const withTheme: Decorator = (Story, context) => {
  const theme = context.globals.theme ?? "light";
  React.useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  return (
    <div
      data-theme={theme}
      style={{
        background: "var(--color-bg)",
        color: "var(--color-fg)",
        fontFamily: "var(--font-sans)",
        padding: "2rem",
        minHeight: "100vh",
      }}
    >
      <Story />
    </div>
  );
};

const preview: Preview = {
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    // Our decorator paints the canvas; disable SB's own backgrounds addon.
    backgrounds: { disable: true },
    a11y: { test: "todo" },
  },
  globalTypes: {
    theme: {
      description: "Cursor warm-neutral — light / dark",
      defaultValue: "light",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", title: "Light", icon: "sun" },
          { value: "dark", title: "Dark", icon: "moon" },
        ],
        dynamicTitle: true,
      },
    },
  },
  decorators: [withTheme],
};

export default preview;
