/**
 * Streaming markdown surface (S3.8.1, F2).
 *
 * RSC by default? No -- streaming display needs client state, so this is a
 * leaf "use client" boundary (B1, U2). The parent shell is RSC.
 *
 * - ARIA live region uses `aria-live="polite"` (NEVER `assertive`,
 *   FE-AP-5 AUTO-REJECT).
 * - Focus does not move on incoming tokens (U5).
 * - No `dangerouslySetInnerHTML` -- markdown lands as text. Full markdown
 *   rendering (code highlighting + copy button) lands in S3.8.x +1.
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function StreamingMarkdown(props: {
  text: string;
  modelBadge?: string;
  step?: { count: number; name: string };
}): React.JSX.Element {
  return (
    <article className="grid gap-2 p-3 bg-bg text-fg">
      <header className="flex gap-2 items-center text-xs text-muted">
        {props.modelBadge ? (
          <span
            data-testid="model-badge"
            className={cn(
              "px-2 py-0.5 rounded-sm",
              "bg-accent-light text-accent font-semibold",
            )}
          >
            {props.modelBadge}
          </span>
        ) : null}
        {props.step ? (
          <span data-testid="step-meter">
            step {props.step.count} · {props.step.name}
          </span>
        ) : null}
      </header>
      <div
        aria-live="polite"
        aria-atomic="false"
        className="whitespace-pre-wrap leading-relaxed"
      >
        {props.text}
      </div>
    </article>
  );
}
