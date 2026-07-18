/**
 * CoachPanel — the iPad quiz split's persistent live coach panel (FR-J3/J3a).
 *
 * Rendered beside the quiz item on the iPad surface. Contracts:
 *
 *  - ONE thread (FR-J3): shared `coach_thread_store` via `useCoach`.
 *  - Two-tier hint (FR-J3a × FR-D5): "One more nudge" reveals deeper reviewed
 *    ladder rungs; exhausted → disabled (FR-B5).
 *  - B1 chrome (D1+D6): shared `CoachChrome` above the nudge ladder, driven by
 *    host-supplied pin + derived mode + skill-scoped misses (ADR-0025).
 *
 * Per F-R1 the panel owns no run logic (useCoach) and no hint logic (ladder
 * arrives as props). Callers should key the panel by question id so nudge
 * state resets per item.
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
import { CoachChrome, CoachChips } from "./CoachChrome";
import { CoachView } from "./CoachView";
import { useCoach } from "./use_coach";
import { useCoachSurface } from "./use_coach_surface";
import { setCoachPin } from "./coach_thread_store";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

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
}): React.JSX.Element {
  const {
    runtime,
    hintLadder,
    mode = "pre_submit",
    pin = null,
    skillLabel = null,
  } = props;
  const { learnerId } = useLearnIdentity();
  const { turns, busy, ask, retry } = useCoach(runtime, { mode });
  const { countMissesOnSkill } = useCoachSurface();

  const [missesOnSkill, setMissesOnSkill] = React.useState<number | null>(null);

  // C1: keep the shared store pin + advisory mode in sync with the live quiz
  // item so standalone `/learn/coach` shows honest chrome after panel → coach.
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

  return (
    <aside
      data-testid="coach-panel"
      aria-label="Live coach panel"
      className="flex w-80 shrink-0 flex-col gap-3 rounded-[16px] border border-border bg-surface p-4"
    >
      <CoachChrome
        vm={surfaceVm}
        busy={busy}
        onAsk={ask}
        layout="stacked"
        showChips={false}
      />

      <header className="flex flex-col gap-0.5">
        <p className="text-sm font-semibold">Socratic mode · watching this item</p>
        <p className="text-xs text-muted">
          Same coach, same thread — pick it up on the Coach screen anytime.
        </p>
      </header>

      <div className="flex flex-col gap-2">
        {deeperRungs.slice(0, revealed).map((h) => (
          <p
            key={h.id}
            data-testid={`panel-nudge-${h.rung}`}
            className="rounded-[13px] bg-accent-light px-3 py-2 text-sm"
          >
            {h.body_md}
          </p>
        ))}
        <button
          type="button"
          data-testid="one-more-nudge"
          disabled={exhausted}
          title={
            exhausted
              ? "That's every nudge for this one — try the coach below."
              : undefined
          }
          onClick={() => setRevealed((n) => Math.min(n + 1, deeperRungs.length))}
          className="min-h-11 w-fit rounded-full border border-dashed border-accent px-4 py-2 text-sm text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          One more nudge
        </button>
      </div>

      <div
        data-testid="coach-panel-composer"
        className="flex min-h-0 flex-1 flex-col gap-3"
      >
        <CoachChips seeds={surfaceVm.chips} busy={busy} onAsk={ask} />
        <div className="min-h-0 flex-1">
          <CoachView
            turns={turns}
            busy={busy}
            onAsk={ask}
            onRetry={retry}
            placeholder="Ask about this item…"
            openerMarkdown={openerMarkdown}
          />
        </div>
      </div>
    </aside>
  );
}
