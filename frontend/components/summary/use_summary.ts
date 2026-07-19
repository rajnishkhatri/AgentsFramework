/**
 * useSummary — the Session-Summary screen's read-only seam onto the engine
 * ports (FR-G1..G3 + C2 FR-1/FR-2/FR-12/FR-14).
 *
 * Per F-R1 the Summary component owns NO domain logic. Reading the STORED
 * session score (never a re-tally, FR-G1), computing the mastery delta from the
 * session-start snapshot vs. a fresh read (ADR-0011 §4), and picking the
 * recommended-next skill (FR-G1/G2) live here, as React-free async functions
 * exercised in node against a seeded InMemoryEngineDb.
 *
 * C2: misconception + self-correction + score-ratio are derived from existing
 * AttemptRepo.misses + servedQuestionIds + QuestionRepo.get — no new port
 * (ADR-0027 / G1).
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
import type {
  Attempt,
  RecommendedNext,
  SkillState,
} from "@/lib/wire/engine_entities";
import {
  SUMMARY_FRAMED_TITLE_RATIO,
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

function normalizeMisconception(value: string | null | undefined): string | null {
  if (value == null || value === "") return null;
  return value;
}

function deriveScoreRatioMet(scoreCorrect: number, scoreTotal: number): boolean {
  return (
    scoreTotal > 0 && scoreCorrect / scoreTotal >= SUMMARY_FRAMED_TITLE_RATIO
  );
}

/**
 * FR-12: newest session-scoped miss on the recommended skill → its misconception.
 * Misses are already newest-first from AttemptRepo; filter to served ids.
 */
async function deriveMisconception(
  ports: EnginePortBag,
  sessionScopedMisses: readonly Attempt[],
  recommendedSkillId: string,
): Promise<string | null> {
  for (const miss of sessionScopedMisses) {
    const q = await ports.questionRepo.get(miss.question_id);
    if (q != null && q.skill_id === recommendedSkillId) {
      return normalizeMisconception(q.misconception);
    }
  }
  return null;
}

/**
 * FR-14: attempt-index half-split on session attempts for the recommended skill.
 * served order ≈ session attempt order (in-memory insertion order; live seam
 * treats served as a set — half-split is best-effort without a new port).
 */
async function deriveSelfCorrection(
  ports: EnginePortBag,
  servedIds: readonly string[],
  sessionMissIds: ReadonlySet<string>,
  recommendedSkillId: string,
): Promise<boolean> {
  const onSkill: { correct: boolean }[] = [];
  for (const qid of servedIds) {
    const q = await ports.questionRepo.get(qid);
    if (q == null || q.skill_id !== recommendedSkillId) continue;
    onSkill.push({ correct: !sessionMissIds.has(qid) });
  }
  const n = onSkill.length;
  if (n === 0) return false;
  const mid = Math.floor(n / 2);
  const first = onSkill.slice(0, mid);
  const second = onSkill.slice(mid);
  const firstHasMiss = first.some((a) => !a.correct);
  const secondHasCorrect = second.some((a) => a.correct);
  const secondHasMiss = second.some((a) => !a.correct);
  return firstHasMiss && secondHasCorrect && !secondHasMiss;
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

  const [session, currentStates, skills, allMisses, servedIds, sessionAttempts] =
    await Promise.all([
      ports.sessionRepo.get(sessionId),
      ports.learnerRead.listSkillState(subject, learnerId),
      ports.skillTaxonomy.list(subject),
      ports.attemptRepo.misses(subject, learnerId),
      ports.attemptRepo.servedQuestionIds(sessionId),
      ports.attemptRepo.listForSession(sessionId),
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

  const servedSet = new Set(servedIds);
  // Newest-first order from misses is preserved after the session filter (FR-12).
  const sessionScopedMisses = allMisses.filter((m) =>
    servedSet.has(m.question_id),
  );
  const sessionMissIds = new Set(sessionScopedMisses.map((m) => m.question_id));

  const misconception = await deriveMisconception(
    ports,
    sessionScopedMisses,
    recommendedSkillId,
  );
  const selfCorrected = await deriveSelfCorrection(
    ports,
    servedIds,
    sessionMissIds,
    recommendedSkillId,
  );
  const scoreRatioMet = deriveScoreRatioMet(
    session.score_correct,
    session.score_total,
  );

  const summary = toSessionSummaryVM(
    session,
    recommended,
    nextSkill,
    masteryDeltaPct,
    misconception,
    selfCorrected,
    scoreRatioMet,
    sessionAttempts,
  );
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
