/**
 * FocusModeChrome — the iPhone focus-screen wrapper (FR-B2).
 *
 * Presentational only (F-R1). On an iPhone focus screen (Quiz/Feedback/Coach/
 * Summary) the shell hides the bottom tab bar (the layout omits <AppNav>) and
 * this chrome supplies the back affordance: a "✕" close that returns to the
 * prior screen. The close is a real <Link> with a destination — never a dead ✕
 * (FR-B5). `returnTo` defaults to the coach Dashboard (`COACH_BASE` = `/learn`),
 * matching the prototype iphone test (✕ from Quiz returns to Dashboard); callers
 * pass the actual prior route when it differs (e.g. Feedback→Coach returns to
 * Feedback).
 */

import * as React from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { screenTitle, COACH_BASE, type ScreenId } from "./nav_model";

export function FocusModeChrome(props: {
  screenId: ScreenId;
  /** Route the ✕ returns to; defaults to the coach Dashboard (COACH_BASE). */
  returnTo?: string;
  children: React.ReactNode;
}): React.JSX.Element {
  const { screenId, returnTo = COACH_BASE, children } = props;
  const title = screenTitle(screenId);
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <h1 className="text-base font-semibold">{title}</h1>
        <Link
          href={returnTo}
          data-testid="focus-close"
          aria-label={`Close ${title}`}
          className="grid size-9 place-items-center rounded-full text-muted hover:bg-selected hover:text-fg"
        >
          <X aria-hidden="true" className="size-5" />
        </Link>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
