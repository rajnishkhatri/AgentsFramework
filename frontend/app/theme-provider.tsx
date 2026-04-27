// B1: 'use client' required — ThemeProvider from next-themes uses React context.
"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider(
  props: React.ComponentProps<typeof NextThemesProvider>,
): React.JSX.Element {
  return <NextThemesProvider {...props} />;
}
