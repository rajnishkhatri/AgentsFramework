/**
 * Commit-first wrong-pick coaching transcript (FR-3…5 / MOM-4 / ESC-2 / T19).
 * Shared by QuizView (inline fallback) and CoachPanel (v3 coach surface).
 *
 * Medium is a conversation: pick echo → ack turn → per-rung turns with
 * "I'm still stuck." learner echoes between escalations. Escalation CTA stays
 * "Show me more →" at every rung (V6); the stuck phrase is the user echo, not
 * the button label.
 */

"use client";

import * as React from "react";
import type { CoachedLoopState } from "@/components/quiz/quiz_screen_reducer";
import type { Question } from "@/lib/wire/engine_entities";
import { composeCoachedAck } from "@/lib/translators/coached_ack_vm";
import { cn } from "@/lib/utils";

export const ESCAPE_COST =
  "The breakdown shows the answer — this one won't count as solved.";
export const ESCAPE_COST_ID = "quiz-escape-cost";

export const EXHAUSTION_COPY =
  "That's all three nudges — I don't have more, and I never tell the answer. Re-read the sentence with the last prompt in mind and try again — or have the breakdown walk you through it.";

export const SHOW_ME_MORE_LABEL = "Show me more →";
export const STUCK_ECHO = "I'm still stuck.";

/** MOM-9 stages — least help first. Index = nudge number (1-based). */
export const LADDER_STAGES = [
  { id: "pump", label: "PUMP" },
  { id: "hint", label: "HINT" },
  { id: "prompt", label: "PROMPT" },
] as const;

function stageForRung(rung: number): (typeof LADDER_STAGES)[number] {
  return LADDER_STAGES[Math.min(Math.max(rung, 1), 3) - 1]!;
}

function UserBubble(props: {
  readonly testId: string;
  readonly children: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="flex justify-end">
      <p
        data-testid={props.testId}
        className="max-w-[92%] rounded-2xl rounded-br-md bg-accent-light px-3 py-2 text-sm leading-relaxed text-fg"
      >
        {props.children}
      </p>
    </div>
  );
}

function CoachBubble(props: {
  readonly testId: string;
  readonly children: React.ReactNode;
  readonly className?: string;
}): React.JSX.Element {
  return (
    <div className="flex justify-start">
      <div
        data-testid={props.testId}
        className={cn(
          "max-w-[92%] rounded-2xl rounded-bl-md border border-border bg-surface px-3 py-2 text-sm leading-relaxed text-fg",
          props.className,
        )}
      >
        {props.children}
      </div>
    </div>
  );
}

export function CoachedLoopSection(props: {
  readonly coachedLoop: CoachedLoopState;
  readonly hintLadder: ReadonlyArray<{ rung: number; body_md: string }>;
  readonly onNudge?: () => void;
  readonly onTryAgain?: () => void;
  readonly onEscape?: () => void;
  /**
   * MOM-3 / VOICE-1: when provided with an `activeLetter`, render the
   * shared-ground acknowledgment as its own coach turn above rung 1.
   */
  readonly ackQuestion?: Question;
}): React.JSX.Element {
  const {
    coachedLoop,
    hintLadder,
    onNudge,
    onTryAgain,
    onEscape,
    ackQuestion,
  } = props;
  const rungCap = coachedLoop.rungCap;
  const rungsRevealed =
    coachedLoop.activeLetter != null
      ? (coachedLoop.rungsRevealed[coachedLoop.activeLetter] ?? 0)
      : 0;
  const revealedBodies = hintLadder
    .filter((h) => h.rung <= rungsRevealed)
    .sort((a, b) => a.rung - b.rung);
  const letter = coachedLoop.activeLetter ?? "?";
  const ackBody =
    ackQuestion != null && coachedLoop.activeLetter != null
      ? composeCoachedAck({
          question: ackQuestion,
          pickedLetter: coachedLoop.activeLetter,
        }).body
      : null;

  const [announce, setAnnounce] = React.useState("");
  // R1: keep the newest turn + decision controls in view as the transcript
  // grows inside the panel's scroll area (pair-03/04 fold evidence).
  const actionsRef = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    // `scrollIntoView` is absent in some test DOMs — skipping the scroll there
    // degrades to today's behavior (no scroll), never an error.
    actionsRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [rungsRevealed, coachedLoop.exhausted]);

  const prevRungs = React.useRef(0);
  React.useEffect(() => {
    if (rungsRevealed > prevRungs.current) {
      // G6 / VOICE-3: learner-facing aria copy drops engine vocabulary
      // ("rung"); "nudge" matches the footnote wording the learner already sees.
      setAnnounce(`Coaching nudge ${rungsRevealed} of ${rungCap} revealed`);
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
      className="flex flex-col gap-3"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
          Coaching
        </h3>
        <span
          data-testid="quiz-rung-counter"
          aria-label={`${rungsRevealed} of ${rungCap} coaching nudges revealed`}
          className="text-xs text-muted"
        >
          {rungsRevealed} of {rungCap}
        </span>
      </div>

      {rungsRevealed > 0 ? (
        <div
          data-testid="quiz-ladder-rail"
          role="group"
          aria-label="Least help first: pump, then hint, then prompt"
          className="grid grid-cols-3 gap-1"
        >
          {LADDER_STAGES.map((stage, i) => {
            const filled = rungsRevealed > i;
            return (
              <div
                key={stage.id}
                data-testid={`quiz-ladder-stage-${stage.id}`}
                data-filled={filled ? "true" : "false"}
                className={cn(
                  "rounded-md px-2 py-1.5 text-center text-[10px] font-bold uppercase tracking-[0.08em]",
                  filled
                    ? "bg-accent text-on-accent"
                    : "bg-selected text-muted",
                )}
              >
                {stage.label}
              </div>
            );
          })}
        </div>
      ) : null}

      <div
        data-testid="quiz-coached-transcript"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Coached exchange"
        className="flex flex-col gap-2.5"
      >
        {coachedLoop.activeLetter != null ? (
          <UserBubble testId="quiz-pick-echo">
            {`I chose ${letter}.`}
          </UserBubble>
        ) : null}

        {ackBody != null ? (
          <CoachBubble testId="quiz-coached-ack">{ackBody}</CoachBubble>
        ) : null}

        {revealedBodies.map((h) => (
          <React.Fragment key={h.rung}>
            {h.rung > 1 ? (
              <UserBubble testId={`quiz-stuck-echo-${h.rung}`}>
                {STUCK_ECHO}
              </UserBubble>
            ) : null}
            <CoachBubble testId={`quiz-rung-${h.rung}`}>
              <p
                data-testid={`quiz-rung-stage-${h.rung}`}
                className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-accent"
              >
                {stageForRung(h.rung).label}
                {" · "}
                <span aria-label="does not name the answer">no answer</span>
              </p>
              <p>{h.body_md}</p>
            </CoachBubble>
          </React.Fragment>
        ))}
      </div>

      <div
        ref={actionsRef}
        data-testid={
          coachedLoop.exhausted
            ? "quiz-exhaustion-actions"
            : "quiz-coached-actions"
        }
        className={cn(
          "flex flex-col gap-2",
          // V4/R1: keep exhaustion CTAs in view (sticky within panel scroll);
          // fully opaque — a translucent footer bleeds transcript text through.
          coachedLoop.exhausted && "sticky bottom-0 z-10 bg-surface pb-1 pt-2",
        )}
      >
        {coachedLoop.exhausted ? (
          <p data-testid="quiz-exhaustion-copy" className="text-sm text-muted">
            {EXHAUSTION_COPY}
          </p>
        ) : null}

        {/* V5: try-again from rung 1; V7: primary at exhaustion, outline before. */}
        <button
          type="button"
          data-testid="quiz-try-again"
          data-priority={coachedLoop.exhausted ? "primary" : "secondary"}
          onClick={onTryAgain}
          className={cn(
            "min-h-11 w-fit rounded-full px-4 py-2 text-sm font-semibold",
            coachedLoop.exhausted
              ? "bg-accent text-on-accent"
              : "border border-accent text-accent",
          )}
        >
          Let me try again
        </button>

        {coachedLoop.exhausted ? (
          <>
            <button
              type="button"
              data-testid="quiz-escape"
              data-priority="secondary"
              aria-describedby={ESCAPE_COST_ID}
              onClick={onEscape}
              className="min-h-11 w-fit rounded-full border border-accent px-4 py-2 text-sm font-semibold text-accent"
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
          </>
        ) : (
          <>
            <button
              type="button"
              data-testid="quiz-nudge"
              onClick={onNudge}
              className="min-h-11 w-fit rounded-full border border-dashed border-accent px-4 py-2 text-sm font-semibold text-accent"
            >
              {SHOW_ME_MORE_LABEL}
            </button>
            <p data-testid="quiz-nudge-footnote" className="text-xs text-muted">
              Nudge {rungsRevealed} of {rungCap} used — these questions follow
              your pick of {letter}.
            </p>
          </>
        )}
      </div>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announce}
      </div>
    </div>
  );
}
