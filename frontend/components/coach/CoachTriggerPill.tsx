/**
 * CoachTriggerPill — floating control that opens CoachDrawer (FR-1/2).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export const CoachTriggerPill = React.forwardRef<
  HTMLButtonElement,
  {
    onClick: () => void;
    className?: string;
  }
>(function CoachTriggerPill(props, ref) {
  const { onClick, className } = props;
  return (
    <button
      ref={ref}
      type="button"
      data-testid="coach-trigger-pill"
      aria-label="Open coach"
      onClick={onClick}
      className={cn(
        "fixed bottom-6 right-6 z-40 flex h-11 items-center gap-2 rounded-full",
        "border border-border bg-surface px-4 text-sm font-semibold text-fg shadow-md",
        "hover:bg-selected focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="inline-block size-[11px] rounded-full bg-[var(--color-success)]"
      />
      Coach
    </button>
  );
});
