/**
 * useSummary — the Session-Summary screen's read-only seam onto the engine
 * ports (FR-G1..G3).
 *
 * Per F-R1 the Summary component owns NO domain logic. Reading the STORED
 * session score (never a re-tally, FR-G1), computing the mastery delta from the
 * session-start snapshot vs. a fresh read (ADR-0011 §4), and picking the
 * recommended-next skill (FR-G1/G2) live here, as React-free async functions
 * exercised in node against a seeded InMemoryEngineDb.
 *
 * READ-ONLY (FR-A2): Summary is a *view*. It reads via `sessionRepo.get` +
 * `learnerRead.listSkillState`; it never calls `scheduler.next()` (which would
 * seed/write skill_state). The recommended-next skill is derived read-only with
 * `pickFocusSkillId` (scheduler-parity selection), mirroring the Dashboard.
 *
 * Imports engine ports (via the injected bag) + wire shapes + the summary
 * translator only. The default bag comes from `useEngine()` context (C3); tests
 * inject a seeded bag directly.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type { RecommendedNext, SkillState } from "@/lib/wire/engine_entities";
import {
  toSessionSummaryVM,
  type SessionSummaryVM,
} from "@/lib/translators/session_summary_vm";
import { pickFocusSkillId } from "@/lib/translators/focus_pick";

export interface SummaryVM {
  /** The pure translator VM (stored score, signed delta, time, recommended). */
  readonly summary: SessionSummaryVM;
  /**
   * False when the session-start snapshot had no row for the focus skill — a
   * brand-new learner, or a resumed session that lost its in-memory snapshot
   * (ADR-0011 §4). The view renders the delta tile as "—" in that case rather
   * than the translator's fabricated "+0%".
   */
  readonly masteryDeltaKnown: boolean;
}

export interface LoadSummaryArgs {
  readonly subject: string;
  readonly learnerId: string;
  readonly sessionId: string;
  /**
   * The learner's per-skill mastery captured at session open (the "before" half
   * of the FR-G1 delta; produced by `openQuizSession`, ADR-0011 §4). Empty for a
   * brand-new learner or a resumed session.
   */
  readonly skillStateAtStart: ReadonlyMap<string, SkillState>;
  /** Injected clock (purity): recommended-next "due" is computed against this. */
  readonly nowISO: string;
}

/**
 * Read-only gather of everything the Summary renders. Reads the stored session
 * + a fresh skill_state snapshot concurrently, computes the focus-skill delta
 * against the start snapshot, and composes the pure VM.
 */
export async function loadSummary(
  ports: EnginePortBag,
  args: LoadSummaryArgs,
): Promise<SummaryVM> {
  const { subject, learnerId, sessionId, skillStateAtStart, nowISO } = args;

  const [session, currentStates, skills] = await Promise.all([
    ports.sessionRepo.get(sessionId),
    ports.learnerRead.listSkillState(subject, learnerId),
    ports.skillTaxonomy.list(subject),
  ]);

  if (session == null) {
    // The caller handed a session id the repo can't resolve — a seam defect,
    // surfaced rather than rendering an empty summary.
    throw new Error(`summary: session ${sessionId} not found`);
  }

  // The recommended-next skill is the weakest+due skill the Scheduler would
  // serve next (read-only parity with the Dashboard focus, FR-G1/G2). Fall back
  // to the session's own focus, then the first skill, so there is always a
  // destination for the CTA (never a dead control, FR-B5).
  const currentBySkill = new Map<string, SkillState>(
    currentStates.map((s) => [s.skill_id, s]),
  );
  const recommendedSkillId =
    pickFocusSkillId(currentStates, nowISO) ??
    session.skill_focus ??
    skills[0]?.id ??
    null;
  if (recommendedSkillId == null) {
    throw new Error(`summary: no skills for subject ${subject}`);
  }
  const nextSkill = skills.find((s) => s.id === recommendedSkillId);
  if (nextSkill == null) {
    throw new Error(`summary: recommended skill ${recommendedSkillId} not in taxonomy`);
  }
  const recommended: RecommendedNext = {
    skill_id: recommendedSkillId,
    mode: "drill",
  };

  // The FR-G1 delta is measured on the *session's focus skill* (what the learner
  // just practised), diffing the start snapshot against the fresh read. Absent a
  // start row → unknown (the view renders "—").
  const deltaSkillId = session.skill_focus ?? recommendedSkillId;
  const startRow = skillStateAtStart.get(deltaSkillId);
  const currentRow = currentBySkill.get(deltaSkillId);
  const masteryDeltaKnown = startRow != null && currentRow != null;
  const masteryDeltaPct = masteryDeltaKnown
    ? (currentRow!.mastery - startRow!.mastery) * 100
    : 0;

  const summary = toSessionSummaryVM(session, recommended, nextSkill, masteryDeltaPct);
  return { summary, masteryDeltaKnown };
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * read-only loader bound to it. The component calls this; it holds no port
 * logic. Tests exercise `loadSummary` directly with an injected bag.
 */
export function useSummary(): {
  load: (args: LoadSummaryArgs) => Promise<SummaryVM>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({ load: (args: LoadSummaryArgs) => loadSummary(ports, args) }),
    [ports],
  );
}
