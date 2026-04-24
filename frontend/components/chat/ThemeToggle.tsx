/**
 * Theme toggle (S3.8.8, F9).
 *
 * Uses `next-themes` for theme management per Style Guide §2 prescription.
 * CSS variables in `app/globals.css` are flipped via `[data-theme="dark"]`.
 */

// B1: 'use client' required — useTheme hook from next-themes, onClick handler.
"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

export function ThemeToggle(): React.JSX.Element {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <button
        className={cn(
          "bg-transparent text-fg border border-border",
          "rounded-sm px-2.5 py-1 cursor-pointer",
        )}
        aria-label="Toggle theme"
      >
        &nbsp;
      </button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      className={cn(
        "bg-transparent text-fg border border-border",
        "rounded-sm px-2.5 py-1 cursor-pointer",
      )}
    >
      {isDark ? "Light" : "Dark"}
    </button>
  );
}
