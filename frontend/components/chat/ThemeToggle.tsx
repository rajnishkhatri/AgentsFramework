/**
 * Theme toggle (S3.8.8, F9) — Cursor warm-neutral (§2.6).
 *
 * Ghost icon button (Button primitive) showing a sun in dark mode / moon in
 * light mode — quiet header chrome, no rationed accent spent here. Uses
 * `next-themes` for theme management per Style Guide §2 prescription. CSS
 * variables in `app/globals.css` are flipped via `[data-theme="dark"]`.
 */

// B1: 'use client' required — useTheme hook from next-themes, onClick handler.
"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ThemeToggle(): React.JSX.Element {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => setMounted(true), []);

  // Pre-mount: render the same-sized ghost shell with the generic label so
  // there is no layout shift and SSR/CSR markup matches until theme resolves.
  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="size-8 px-0"
        aria-label="Toggle theme"
      >
        <span className="size-4" aria-hidden="true" />
      </Button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="sm"
      className="size-8 px-0 hover:bg-selected"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
    >
      {isDark ? (
        <Sun className="size-4" aria-hidden="true" />
      ) : (
        <Moon className="size-4" aria-hidden="true" />
      )}
    </Button>
  );
}
