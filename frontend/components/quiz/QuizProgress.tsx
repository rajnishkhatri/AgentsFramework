/**
 * QuizProgress — the "Question N of M" session-progress bar (S4).
 *
 * Presentational only (F-R1): renders a `QuizProgressVM` (from quiz_progress_vm).
 * All the counting/clamp math lives in that pure translator; this component holds
 * no logic — it maps the VM to a counter line + an ARIA progressbar, styling off
 * the VM fields (§13). No engine call, no state (FR-9).
 *
 * FR-1/FR-2 rendering: the counter shows "of M" only when `vm.total` is non-null
 * (dropped for endless AND over-run). FR-5: the bar fill width is `vm.fraction`.
 * FR-7: a `role="progressbar"` carries aria-valuenow/min/max + a text alternative,
 * so a screen reader announces position; the counter text is real text, not
 * color-only (WCAG 2.2 AA).
 *
 * No `t()` — this codebase has no i18n helper yet (QuizView/FeedbackView use inline
 * literals); matching the surrounding code is correct here.
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { QuizProgressVM } from "@/lib/translators/quiz_progress_vm";

export interface QuizProgressProps {
  readonly vm: QuizProgressVM;
}

export function QuizProgress(props: QuizProgressProps): React.JSX.Element {
  const { position, total, fraction, bounded } = props.vm;
  const label =
    total != null ? `Question ${position} of ${total}` : `Question ${position}`;
  const pct = `${Math.round(fraction * 100)}%`;

  return (
    <section
      aria-label="Session progress"
      data-testid="quiz-progress"
      className="mx-auto flex max-w-[760px] flex-col gap-2"
    >
      <p className="text-sm font-medium text-muted">{label}</p>
      <div
        role="progressbar"
        aria-valuemin={0}
        // FR-7 / WAI-ARIA: a DETERMINATE progressbar carries valuenow/valuemax
        // (position of the fixed target). An INDETERMINATE one — an endless session
        // (bounded false) OR one that has run past its target (total null) — has no
        // meaningful measured value, so both aria-valuenow and aria-valuemax are
        // OMITTED (undefined ⇒ React drops the attribute), which is exactly how AT
        // announces "indeterminate" rather than a misleading "0%"/"100%".
        aria-valuemax={total != null ? total : undefined}
        aria-valuenow={total != null ? position : undefined}
        aria-valuetext={label}
        data-bounded={bounded ? "true" : "false"}
        className="h-2 w-full overflow-hidden rounded-full bg-selected"
      >
        <div
          data-testid="quiz-progress-fill"
          className={cn(
            "h-full rounded-full bg-accent transition-[width]",
            // Indeterminate sessions render no visible fill (FR-1): width 0 via the
            // VM's fraction, which is 0 when unbounded.
          )}
          style={{ width: pct }}
        />
      </div>
    </section>
  );
}
