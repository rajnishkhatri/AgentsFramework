/**
 * QuizView — the quiz item column (FR-D2/D3/D4/D5/A6) + D1 session-frame chrome.
 *
 * Presentational only (F-R1): renders a `QuizItemVM` + the caller-owned
 * selection/hint/frame state as props. All state lives in the screen hook /
 * page; this component raises callbacks and styles off `data-*` attributes
 * (§13), never its own logic.
 *
 * FR-D4 submit gate: `canSubmit(selectedLetter)` drives the button's `disabled`.
 * FR-D5 non-reveal: the hint text is passed in; the VM carries no answer letter.
 * D1 frame: skill chip (Q-7), End session (Q-8), collapsible timer (Q-9) — all
 * derived fields arrive as props; the leaf holds no join / clamp logic.
 *
 * `context_html` (FR-A6 underlined span) is REVIEWED, engine-authored content
 * (the `reviewed` gate guarantees it) — not agent/user output — so rendering it
 * via dangerouslySetInnerHTML is the sanctioned delivery of the underlined span,
 * distinct from FE-AP-12 (which bans agent-emitted HTML in the app origin).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { canSubmit, type QuizItemVM } from "@/lib/translators/quiz_item_vm";
import { formatElapsedFromStartedAt } from "@/lib/translators/quiz_frame_timer";
import { toQuizWhyItemVM } from "@/lib/translators/quiz_why_item_vm";
import { CoachedLoopSection } from "@/components/coach/CoachedLoopSection";
import type { CoachedLoopState } from "./quiz_screen_reducer";

export interface QuizFrameChromeProps {
  /** Q-7: joined skill name; omit chip when null (FR-Q7-1). */
  readonly skillName: string | null;
  /** Q-7: CSS custom-property name for the accent dot; null with skillName. */
  readonly accentVar: string | null;
  /** Q-8: whether End session is actionable (session open + answering/reviewing). */
  readonly endSessionEnabled: boolean;
  readonly onEndSession: () => void;
  /**
   * Q-9: ISO `session.started_at`; null → no timer reveal (FR-Q9-1).
   * Key the parent by question id so reveal resets on a new item (FR-Q9-7).
   */
  readonly startedAtIso: string | null;
}

/**
 * Session-frame chrome shared by answering (inside QuizView) and reviewing
 * (page-level, above Feedback) so the chip / End / timer persist across phases
 * (FR-Q7-4, FR-Q8-3) without duplicating markup.
 */
export function QuizFrameChrome(props: QuizFrameChromeProps): React.JSX.Element {
  const {
    skillName,
    accentVar,
    endSessionEnabled,
    onEndSession,
    startedAtIso,
  } = props;

  return (
    <div
      data-testid="quiz-frame"
      className="flex flex-wrap items-center gap-3"
    >
      {skillName != null ? (
        <span
          data-testid="quiz-skill-chip"
          className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-sm"
        >
          <span
            data-testid="bucket-dot"
            aria-hidden="true"
            className="size-2.5 shrink-0 rounded-full"
            style={
              accentVar != null
                ? { backgroundColor: `var(${accentVar})` }
                : undefined
            }
          />
          {skillName}
        </span>
      ) : null}

      <button
        type="button"
        data-testid="quiz-end-session"
        disabled={!endSessionEnabled}
        onClick={onEndSession}
        className={cn(
          "min-h-11 rounded-full border border-border px-4 py-2 text-sm",
          "disabled:pointer-events-none disabled:opacity-60",
        )}
      >
        End session
      </button>

      {startedAtIso != null ? (
        <QuizTimer startedAtIso={startedAtIso} />
      ) : null}
    </div>
  );
}

function QuizTimer({
  startedAtIso,
}: {
  startedAtIso: string;
}): React.JSX.Element {
  const [revealed, setRevealed] = React.useState(false);
  const [now, setNow] = React.useState(() => Date.now());

  React.useEffect(() => {
    if (!revealed) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [revealed]);

  if (!revealed) {
    return (
      <button
        type="button"
        data-testid="quiz-timer-reveal"
        onClick={() => setRevealed(true)}
        aria-label="Show timer"
        className="min-h-11 rounded-full border border-dashed border-border px-3 py-2 text-sm text-muted"
      >
        Show timer
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span data-testid="quiz-timer" role="timer" aria-live="off">
        {formatElapsedFromStartedAt(startedAtIso, now)}
      </span>
      <button
        type="button"
        onClick={() => setRevealed(false)}
        aria-label="Hide timer"
        className="min-h-11 rounded-full px-3 py-2 text-sm text-muted"
      >
        Hide
      </button>
    </div>
  );
}

export interface QuizViewProps {
  readonly vm: QuizItemVM;
  readonly selectedLetter: string | null;
  readonly onSelect: (letter: string) => void;
  readonly onSubmit: () => void;
  readonly hintOpen: boolean;
  readonly hint: string;
  readonly onToggleHint: () => void;
  /** D1 frame — optional so legacy callers (Test mode) stay compile-clean. */
  readonly endSessionEnabled?: boolean;
  readonly onEndSession?: () => void;
  readonly startedAtIso?: string | null;
  /**
   * Commit-first coaching (FR-1…5). When true: no pre-commit hint/reveal;
   * coached section under choices when `coachedLoop` is set.
   */
  readonly commitFirstCoach?: boolean;
  readonly coachedLoop?: CoachedLoopState | null;
  /** Current ladder bodies (choice-keyed or fallback), rung-ascending. */
  readonly hintLadder?: ReadonlyArray<{ rung: number; body_md: string }>;
  readonly onNudge?: () => void;
  readonly onTryAgain?: () => void;
  readonly onEscape?: () => void;
  /**
   * When true, render the coached loop under the choices (fullscreen / tests).
   * Default false — v3 hosts the loop in CoachPanel.
   */
  readonly renderCoachedInline?: boolean;
  /**
   * MOM-3 / VOICE-1: the current item, used to compose the shared-ground
   * acknowledgment above rung 1 in the inline coached section.
   */
  readonly ackQuestion?: import("@/lib/wire/engine_entities").Question;
  /**
   * SEQ-2: progress position (1-based) for the "why this item" line. Omit →
   * the line is hidden (legacy callers).
   */
  readonly whyItemPosition?: number;
  /** SEQ-2: display denominator (target_count), or null when endless. */
  readonly whyItemTotal?: number | null;
}

const COMMIT_FIRST_IDLE_HINT =
  "Pick a choice and submit — no hints until you commit.";

export function QuizView(props: QuizViewProps): React.JSX.Element {
  const {
    vm,
    selectedLetter,
    onSelect,
    onSubmit,
    hintOpen,
    hint,
    onToggleHint,
    endSessionEnabled = false,
    onEndSession,
    startedAtIso = null,
    commitFirstCoach = false,
    coachedLoop = null,
    hintLadder = [],
    onNudge,
    onTryAgain,
    onEscape,
    renderCoachedInline = false,
    ackQuestion,
    whyItemPosition,
    whyItemTotal,
  } = props;
  const submittable = canSubmit(selectedLetter);
  const showFrame =
    onEndSession != null || vm.skillName != null || startedAtIso != null;

  const whyItemLine =
    whyItemPosition != null
      ? toQuizWhyItemVM({
          skillName: vm.skillName,
          difficulty: vm.difficulty,
          position: whyItemPosition,
          total: whyItemTotal ?? null,
        }).line
      : null;

  return (
    <section
      aria-label="Quiz question"
      // Stable e2e hook for the served skill (S3.1 rotation, ADR-0024). Not
      // visible UI — the skill is not rendered until S4; this only lets the
      // rotation Playwright spec read the served skill deterministically.
      data-skill={vm.skillId}
      className="mx-auto flex max-w-[760px] flex-col gap-5"
    >
      {showFrame ? (
        <QuizFrameChrome
          skillName={vm.skillName}
          accentVar={vm.accentVar}
          endSessionEnabled={endSessionEnabled}
          onEndSession={onEndSession ?? (() => {})}
          startedAtIso={startedAtIso}
        />
      ) : null}

      {whyItemLine != null ? (
        <p
          data-testid="quiz-why-item"
          className="text-xs text-muted"
        >
          {whyItemLine}
        </p>
      ) : null}

      {/* FR-A6: reviewed engine-authored context carrying the underlined span. */}
      <p
        data-testid="quiz-context"
        className="text-[1.25rem] leading-[1.8]"
        // Reviewed engine content, not agent output — see file header.
        dangerouslySetInnerHTML={{ __html: vm.contextHtml }}
      />

      <p className="text-base font-medium">{vm.stem}</p>

      <ul className="flex flex-col gap-2">
        {vm.choices.map((c) => {
          const selected = c.letter === selectedLetter;
          return (
            <li key={c.letter}>
              <button
                type="button"
                data-testid={`choice-${c.letter}`}
                data-selected={selected ? "true" : "false"}
                onClick={() => onSelect(c.letter)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-[16px] border px-4 py-3 text-left",
                  "data-[selected=false]:border-border data-[selected=false]:bg-surface",
                  "data-[selected=true]:border-accent",
                  "data-[selected=true]:bg-accent-light",
                )}
              >
                <span
                  data-selected={selected ? "true" : "false"}
                  className={cn(
                    "grid size-7 place-items-center rounded-full font-semibold",
                    "data-[selected=false]:bg-selected data-[selected=false]:text-muted",
                    "data-[selected=true]:bg-accent data-[selected=true]:text-on-accent",
                  )}
                >
                  {c.letter}
                </span>
                <span className="flex-1">{c.label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      {commitFirstCoach ? (
        // Wrong-pick ladder lives in CoachPanel (v3). Item column keeps idle
        // helper + optional fallback when the host still passes renderInline.
        coachedLoop != null && props.renderCoachedInline === true ? (
          <CoachedLoopSection
            coachedLoop={coachedLoop}
            hintLadder={hintLadder}
            {...(onNudge != null ? { onNudge } : {})}
            {...(onTryAgain != null ? { onTryAgain } : {})}
            {...(onEscape != null ? { onEscape } : {})}
            {...(ackQuestion != null ? { ackQuestion } : {})}
          />
        ) : coachedLoop == null ? (
          <p data-testid="quiz-commit-idle-hint" className="text-xs text-muted">
            {COMMIT_FIRST_IDLE_HINT}
          </p>
        ) : null
      ) : (
        <>
          <div className="flex items-center gap-3">
            <button
              type="button"
              data-testid="quiz-hint-toggle"
              onClick={onToggleHint}
              className="min-h-11 rounded-full border border-dashed border-accent px-4 py-2 text-sm text-accent"
            >
              {hintOpen ? "Hide hint" : "Get a hint"}
            </button>
            {/* UI FR-D6 / FR-D6a: ghost control; gated submit alias (Sprint A1). */}
            <button
              type="button"
              data-testid="quiz-reveal"
              disabled={!submittable}
              onClick={onSubmit}
              data-enabled={submittable ? "true" : "false"}
              className={cn(
                "min-h-11 rounded-full px-4 py-2 text-sm text-muted",
                "data-[enabled=true]:text-fg",
                "data-[enabled=false]:opacity-60 data-[enabled=false]:pointer-events-none",
              )}
            >
              Reveal answer
            </button>
          </div>

          {hintOpen ? (
            <div
              data-testid="quiz-hint"
              role="note"
              className="rounded-[16px] border border-dashed border-accent bg-accent-light px-4 py-3 text-sm"
            >
              {hint}
            </div>
          ) : null}
        </>
      )}

      <button
        type="button"
        data-testid="quiz-submit"
        disabled={!submittable}
        onClick={onSubmit}
        data-enabled={submittable ? "true" : "false"}
        className={cn(
          "rounded-full bg-accent px-6 py-3 font-semibold text-on-accent",
          "data-[enabled=false]:opacity-60 data-[enabled=false]:pointer-events-none",
        )}
      >
        Submit answer
      </button>
    </section>
  );
}
