/**
 * CoachPanel — Direction 2b Zone A/B/C stack (ADR-0035 / FR-5/10–15/20).
 *
 * Column (ADR-0037, single-scroll; header unpinned FR-27/M8):
 *   B scroll — CoachChrome header (title/status/current-item/history + mode
 *              chips) + dismiss, then ladder + conversation (role=log) + chips.
 *              The ONLY scroll region; header scrolls away with it.
 *   C pinned — composer (text entry + send). The SOLE pinned region (FR-23).
 *   (There is no fixed Zone A: the ~187px header used to starve the transcript.)
 *
 * ONE thread via coach_thread_store / useCoach. Hint ladder arrives as props.
 */

"use client";

import * as React from "react";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import type { Hint } from "@/lib/wire/engine_entities";
import type { CoachMode } from "@/lib/translators/coach_context_sanitizer";
import {
  COACH_CHIP_SEEDS,
  toCoachSurfaceVM,
  type CoachSurfacePin,
  type CoachSurfaceVM,
} from "@/lib/translators/coach_surface_vm";
import { honestCoachOpener } from "@/lib/translators/honest_coach_opener";
import { Composer } from "@/components/chat/Composer";
import { cn } from "@/lib/utils";
import { CoachChrome, CoachChips } from "./CoachChrome";
import { CoachView } from "./CoachView";
import { HintLadderList, NUDGE_EXHAUSTED_REASON } from "./HintLadderList";
import { CoachedLoopSection } from "./CoachedLoopSection";
import { CoachedConfirmSection } from "./CoachedConfirmSection";
import { useCoach } from "./use_coach";
import { useCoachSurface } from "./use_coach_surface";
import { setCoachPin } from "./coach_thread_store";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import { useSurface } from "@/components/shell/use_surface";
import type {
  CoachedConfirmState,
  CoachedLoopState,
} from "@/components/quiz/quiz_screen_reducer";

/** Idle copy when commit-first is ON and the learner has not yet submitted (FR-2). */
export const COMMIT_FIRST_IDLE_COPY =
  "Commit to a choice — coaching starts from what you pick. Ask me anything below; I never reveal the answer.";

export function CoachPanel(props: {
  runtime: AgentRuntimeClient;
  /** The current item's reviewed ladder (rung-ascending, ADR-0014). */
  hintLadder: ReadonlyArray<Hint>;
  /** Derived coach mode from quiz phase (display-only; ADR-0012). */
  mode?: CoachMode;
  /** Pinned item for C-3 / skill-scoped C-4; omit → honest absent. */
  pin?: CoachSurfacePin | null;
  /** Optional skill display name for the history line. */
  skillLabel?: string | null;
  /** Optional dismiss control (A3) — host owns panelDismissed. */
  onDismiss?: () => void;
  /** Imperative focus for Feedback→coach bridge (FR-14). */
  composerFocusRef?: React.RefObject<HTMLTextAreaElement | null>;
  /** Optional className override (drawer vs inline). */
  className?: string;
  /** Inline host sets true so e2e can find `coach-panel-inline`. */
  inlineHost?: boolean;
  /**
   * Commit-first (FR-2/13): retire quiz-pin HintLadderList + nudge; show idle
   * copy pre-submit. Wrong-pick loop also mirrors in this panel (v3).
   */
  commitFirstCoach?: boolean;
  /** Active wrong-pick loop; when set, idle opener is suppressed (MOM-8). */
  coachedLoop?: CoachedLoopState | null;
  /** FR-15 coached-solve confirmation. */
  coachedConfirm?: CoachedConfirmState | null;
  readonly onNudge?: () => void;
  readonly onTryAgain?: () => void;
  readonly onEscape?: () => void;
  readonly onSeeBreakdown?: () => void;
  /**
   * MOM-3 / VOICE-1: the current item, used to compose the shared-ground
   * acknowledgment above rung 1 in the panel's coached section.
   */
  readonly ackQuestion?: import("@/lib/wire/engine_entities").Question;
}): React.JSX.Element {
  const {
    runtime,
    hintLadder,
    mode = "pre_submit",
    pin = null,
    skillLabel = null,
    onDismiss,
    composerFocusRef,
    className,
    inlineHost = false,
    commitFirstCoach = false,
    coachedLoop = null,
    coachedConfirm = null,
    onNudge,
    onTryAgain,
    onEscape,
    onSeeBreakdown,
    ackQuestion,
  } = props;
  const surface = useSurface();
  const { learnerId } = useLearnIdentity();
  const { turns, busy, ask, retry } = useCoach(runtime, { mode });
  const { countMissesOnSkill } = useCoachSurface();

  const [missesOnSkill, setMissesOnSkill] = React.useState<number | null>(null);

  React.useEffect(() => {
    setCoachPin(pin, mode);
  }, [pin, mode]);

  React.useEffect(() => {
    let cancelled = false;
    if (pin?.skillId == null) {
      setMissesOnSkill(null);
      return;
    }
    void countMissesOnSkill({
      subject: DEFAULT_SUBJECT,
      learnerId,
      skillId: pin.skillId,
    }).then((n) => {
      if (!cancelled) setMissesOnSkill(n);
    });
    return () => {
      cancelled = true;
    };
  }, [
    pin?.skillId,
    pin?.kind === "item" ? pin.questionId : null,
    countMissesOnSkill,
    learnerId,
  ]);

  const surfaceVm: CoachSurfaceVM = React.useMemo(
    () =>
      toCoachSurfaceVM({
        mode,
        pin,
        missesOnSkill,
        skillLabel,
        chipSeeds: COACH_CHIP_SEEDS,
      }),
    [mode, pin, missesOnSkill, skillLabel],
  );

  const openerMarkdown = React.useMemo(() => {
    // V10 / T19 / FR-15: coached loop or confirm owns the exchange.
    if (commitFirstCoach && (coachedLoop != null || coachedConfirm != null)) {
      return null;
    }
    if (commitFirstCoach && turns.length === 0 && mode === "pre_submit") {
      return COMMIT_FIRST_IDLE_COPY;
    }
    return honestCoachOpener({
      pin,
      missesOnSkill,
      skillLabel,
      transcriptEmpty: turns.length === 0,
    });
  }, [
    commitFirstCoach,
    coachedLoop,
    coachedConfirm,
    mode,
    pin,
    missesOnSkill,
    skillLabel,
    turns.length,
  ]);

  const deeperRungs = React.useMemo(
    () => hintLadder.filter((h) => h.rung > 1),
    [hintLadder],
  );
  const [revealed, setRevealed] = React.useState(0);
  const exhausted = revealed >= deeperRungs.length;
  const revealedHints = deeperRungs.slice(0, revealed);
  const isDesktop = surface === "desktop";
  const showQuizLadder = !commitFirstCoach;

  return (
    <aside
      data-testid={inlineHost ? "coach-panel-inline" : "coach-panel"}
      data-inline={inlineHost ? "true" : undefined}
      aria-label="Live coach panel"
      style={
        isDesktop
          ? { width: "clamp(400px, 30vw, 480px)" }
          : { width: "360px" }
      }
      className={cn(
        "flex min-h-0 shrink-0 flex-col border-border bg-surface",
        "min-w-0",
        className,
      )}
    >
      {/* Zone B — the single scroll region. FR-27/M8: the identity header
          (CoachChrome + dismiss) is unpinned and rides at the top of this body,
          so it scrolls away with the transcript instead of eating a fixed
          ~187px. The composer (Zone C) is the ONLY pinned region. */}
      <div
        data-testid="coach-zone-b"
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto overscroll-contain px-4 py-3.5"
      >
        {/* Identity header — scrolls with the body (FR-27). Bottom hairline +
            spacing keep it visually separated from the transcript below. */}
        <div className="mb-3.5 shrink-0 border-b border-border pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <CoachChrome
                vm={surfaceVm}
                busy={busy}
                onAsk={ask}
                layout="stacked"
                showChips={false}
              />
            </div>
            {onDismiss != null ? (
              <button
                type="button"
                data-testid="coach-panel-dismiss"
                aria-label="Hide coach panel"
                onClick={onDismiss}
                className="flex size-8 shrink-0 items-center justify-center rounded-md text-muted hover:bg-selected hover:text-fg"
              >
                ✕
              </button>
            ) : null}
          </div>
        </div>

        {showQuizLadder ? (
          <>
            <HintLadderList
              revealed={revealedHints}
              totalDeeper={deeperRungs.length}
            />
            {revealedHints.length > 0 ? (
              <div
                role="separator"
                aria-hidden="true"
                className="my-3.5 border-t border-border"
              />
            ) : null}
          </>
        ) : null}
        {commitFirstCoach && coachedConfirm != null ? (
          <div className="mb-3.5 shrink-0">
            <CoachedConfirmSection
              confirm={coachedConfirm}
              {...(onSeeBreakdown != null ? { onSeeBreakdown } : {})}
            />
          </div>
        ) : commitFirstCoach && coachedLoop != null ? (
          <div className="mb-3.5 shrink-0">
            <CoachedLoopSection
              coachedLoop={coachedLoop}
              hintLadder={hintLadder.map((h) => ({
                rung: h.rung,
                body_md: h.body_md,
              }))}
              {...(onNudge != null ? { onNudge } : {})}
              {...(onTryAgain != null ? { onTryAgain } : {})}
              {...(onEscape != null ? { onEscape } : {})}
              {...(ackQuestion != null ? { ackQuestion } : {})}
            />
          </div>
        ) : null}
        <div className="mb-2 shrink-0">
          <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
            Conversation
          </h3>
        </div>
        {/* Flow content — Zone B is the ONLY scroll region (FR-25); the single
            vertical scroll now also carries the nudge control + quick-action
            chips (FR-22/23), which used to live in the pinned bar. */}
        <div className="min-w-0 break-words">
          <CoachView
            turns={turns}
            busy={busy}
            onAsk={ask}
            onRetry={retry}
            placeholder="Ask about this item…"
            openerMarkdown={openerMarkdown}
            showComposer={false}
          />
        </div>

        {/* "One more nudge" — scrolls with the body (FR-23: not in the pinned
            bar). Kept below the conversation, above the chips. */}
        {showQuizLadder ? (
          <button
            type="button"
            data-testid="one-more-nudge"
            disabled={exhausted}
            aria-disabled={exhausted ? "true" : undefined}
            title={exhausted ? NUDGE_EXHAUSTED_REASON : undefined}
            onClick={() => {
              if (exhausted) return;
              setRevealed((n) => Math.min(n + 1, deeperRungs.length));
            }}
            className="mt-3 min-h-11 w-fit shrink-0 rounded-md border border-dashed border-accent px-[15px] py-1.5 text-sm font-semibold text-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            + One more nudge
          </button>
        ) : null}

        {/* Quick-action chips — in the scroll body (FR-22), wrapping (FR-21). */}
        <div className="mt-3 shrink-0">
          <CoachChips seeds={surfaceVm.chips} busy={busy} onAsk={ask} />
        </div>
      </div>

      {/* Zone C — pinned bar: composer only (FR-23). */}
      <div
        data-testid="coach-zone-c"
        className="flex shrink-0 flex-col gap-3 border-t border-border px-4 py-3"
      >
        <div data-testid="coach-panel-composer" className="flex flex-col gap-3">
          <Composer
            onSend={(body) => ask(body)}
            busy={busy}
            placeholder="Ask about this item…"
            // M3 / FR-24: coach composer is slim — no attach or model picker.
            showToolbar={false}
            {...(composerFocusRef != null
              ? { textareaRef: composerFocusRef }
              : {})}
          />
          {commitFirstCoach && coachedLoop == null ? (
            <p
              data-testid="coach-composer-footer"
              className="text-xs text-muted"
            >
              Coaching starts after you submit — it works from what your pick
              reveals.
            </p>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
