/**
 * Commit-first wrong-pick coaching block (FR-3…5 / MOM-4 / ESC-2).
 * Shared by QuizView (always visible) and CoachPanel (v3 coach surface).
 */

"use client";

import * as React from "react";
import type { CoachedLoopState } from "@/components/quiz/quiz_screen_reducer";

export const ESCAPE_COST =
  "The breakdown shows the answer — this one won't count as solved.";
export const ESCAPE_COST_ID = "quiz-escape-cost";

export const EXHAUSTION_COPY =
  "That's all three nudges — I don't have more, and I never tell the answer. Re-read the sentence with the last prompt in mind and try again — or have the breakdown walk you through it.";

export function CoachedLoopSection(props: {
  readonly coachedLoop: CoachedLoopState;
  readonly hintLadder: ReadonlyArray<{ rung: number; body_md: string }>;
  readonly onNudge?: () => void;
  readonly onTryAgain?: () => void;
  readonly onEscape?: () => void;
}): React.JSX.Element {
  const { coachedLoop, hintLadder, onNudge, onTryAgain, onEscape } = props;
  const rungCap = coachedLoop.rungCap;
  const rungsRevealed =
    coachedLoop.activeLetter != null
      ? (coachedLoop.rungsRevealed[coachedLoop.activeLetter] ?? 0)
      : 0;
  const revealedBodies = hintLadder
    .filter((h) => h.rung <= rungsRevealed)
    .sort((a, b) => a.rung - b.rung);
  const letter = coachedLoop.activeLetter ?? "?";
  // CTRL-2: escalate CTA when one rung remains after this click.
  const nudgeLabel =
    rungsRevealed >= rungCap - 1 ? "I'm still stuck →" : "Show me more →";

  const [announce, setAnnounce] = React.useState("");
  const prevRungs = React.useRef(0);
  React.useEffect(() => {
    if (rungsRevealed > prevRungs.current) {
      setAnnounce(`Coaching rung ${rungsRevealed} of ${rungCap} revealed`);
      const t = window.setTimeout(() => setAnnounce(""), 1000);
      prevRungs.current = rungsRevealed;
      return () => window.clearTimeout(t);
    }
    prevRungs.current = rungsRevealed;
    return undefined;
  }, [rungsRevealed, rungCap]);

  return (
    <div
      data-testid="quiz-coached-section"
      role="region"
      aria-label="Coaching"
      className="flex flex-col gap-3 rounded-[16px] border border-dashed border-accent bg-accent-light/40 px-4 py-3"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
          Coaching
        </h3>
        <span
          data-testid="quiz-rung-counter"
          aria-label={`${rungsRevealed} of ${rungCap} coaching rungs revealed`}
          className="text-xs text-muted"
        >
          {rungsRevealed} of {rungCap}
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {revealedBodies.map((h) => (
          <li
            key={h.rung}
            data-testid={`quiz-rung-${h.rung}`}
            className="text-sm leading-relaxed"
          >
            {h.body_md}
          </li>
        ))}
      </ul>
      {coachedLoop.exhausted ? (
        <div
          data-testid="quiz-exhaustion-actions"
          className="flex flex-col gap-2"
        >
          <p data-testid="quiz-exhaustion-copy" className="text-sm text-muted">
            {EXHAUSTION_COPY}
          </p>
          <button
            type="button"
            data-testid="quiz-try-again"
            onClick={onTryAgain}
            className="min-h-11 w-fit rounded-full border border-accent px-4 py-2 text-sm font-semibold text-accent"
          >
            Let me try again
          </button>
          <button
            type="button"
            data-testid="quiz-escape"
            aria-describedby={ESCAPE_COST_ID}
            onClick={onEscape}
            className="min-h-11 w-fit rounded-full bg-accent px-4 py-2 text-sm font-semibold text-on-accent"
          >
            Walk me through it
          </button>
          <p
            id={ESCAPE_COST_ID}
            data-testid="quiz-escape-cost"
            className="text-xs text-muted"
          >
            {ESCAPE_COST}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            data-testid="quiz-nudge"
            onClick={onNudge}
            className="min-h-11 w-fit rounded-full border border-dashed border-accent px-4 py-2 text-sm font-semibold text-accent"
          >
            {nudgeLabel}
          </button>
          <p data-testid="quiz-nudge-footnote" className="text-xs text-muted">
            Nudge {rungsRevealed} of {rungCap} used — these questions follow
            your pick of {letter}.
          </p>
        </div>
      )}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announce}
      </div>
    </div>
  );
}
