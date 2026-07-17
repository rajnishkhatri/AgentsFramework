/**
 * CoachPanel — Direction 2b Zone A/B/C stack (ADR-0035 / FR-5/10–15/20).
 *
 * Zones:
 *   A fixed — status / mode chrome
 *   B scroll — HintLadderList + separator + conversation (role=log)
 *   C pinned — "+ One more nudge" + chips + composer (Q-C1 / FR-12)
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
import { useCoach } from "./use_coach";
import { useCoachSurface } from "./use_coach_surface";
import { setCoachPin } from "./coach_thread_store";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import { useSurface } from "@/components/shell/use_surface";

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

  const openerMarkdown = React.useMemo(
    () =>
      honestCoachOpener({
        pin,
        missesOnSkill,
        transcriptEmpty: turns.length === 0,
      }),
    [pin, missesOnSkill, turns.length],
  );

  const deeperRungs = React.useMemo(
    () => hintLadder.filter((h) => h.rung > 1),
    [hintLadder],
  );
  const [revealed, setRevealed] = React.useState(0);
  const exhausted = revealed >= deeperRungs.length;
  const revealedHints = deeperRungs.slice(0, revealed);
  const isDesktop = surface === "desktop";

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
      {/* Zone A — fixed header */}
      <div
        data-testid="coach-zone-a"
        className="shrink-0 border-b border-border px-[18px] pb-3 pt-4"
      >
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

      {/* Zone B — scroll: ladder + conversation */}
      <div
        data-testid="coach-zone-b"
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto overscroll-contain px-4 py-3.5"
      >
        <HintLadderList revealed={revealedHints} totalDeeper={deeperRungs.length} />
        {revealedHints.length > 0 ? (
          <div
            role="separator"
            aria-hidden="true"
            className="my-3.5 border-t border-border"
          />
        ) : null}
        <div className="mb-2 shrink-0">
          <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
            Conversation
          </h3>
        </div>
        {/* Flow content — Zone B is the only vertical scroll (FR-11/12). */}
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
      </div>

      {/* Zone C — pinned: nudge + chips + composer */}
      <div
        data-testid="coach-zone-c"
        className="flex shrink-0 flex-col gap-3 border-t border-border px-4 py-3"
      >
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
          className="min-h-11 w-fit rounded-md border border-dashed border-accent px-[15px] py-1.5 text-sm font-semibold text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          + One more nudge
        </button>
        <div data-testid="coach-panel-composer" className="flex flex-col gap-3">
          <CoachChips seeds={surfaceVm.chips} busy={busy} onAsk={ask} />
          <Composer
            onSend={(body) => ask(body)}
            busy={busy}
            placeholder="Ask about this item…"
            {...(composerFocusRef != null
              ? { textareaRef: composerFocusRef }
              : {})}
          />
        </div>
      </div>
    </aside>
  );
}
