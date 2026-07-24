/**
 * session_summary_vm — (QuizSession, RecommendedNext, Skill, masteryDeltaPct,
 * misconception, selfCorrected, scoreRatioMet) → SessionSummaryVM (FR-G1..G3 +
 * C2 FR-7/FR-8/FR-11/FR-13).
 *
 * Pure T1 map for Screen 5. FR-G1: the score tile reads the STORED session
 * score (`score_correct`/`score_total`) — the VM never re-tallies attempts. The
 * mastery delta is computed upstream (the hook diffs skill_state before/after)
 * and passed IN as `masteryDeltaPct`, keeping this map pure. Time is derived
 * from the stored ISO timestamps (whole minutes). The recommended-next card
 * (FR-G1) carries the skill + mode so its CTA re-opens Quiz (FR-G2).
 *
 * C2 payoff: misconception / selfCorrected / scoreRatioMet are passed by the
 * hook (never synthesized here). Framed title flips at
 * SUMMARY_FRAMED_TITLE_RATIO; drillTitle is deterministic from target_count.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type {
  Attempt,
  AttemptResolution,
  Question,
  QuizSession,
  RecommendedNext,
  Skill,
} from "../wire/engine_entities";
import { resolvingAttemptForQuestion } from "./resolving_attempt";

/** Score ratio at which the Summary title flips to framed "Nice work" copy. */
export const SUMMARY_FRAMED_TITLE_RATIO = 0.6;

export interface RecommendedNextVM {
  readonly skillId: string;
  readonly skillName: string;
  readonly mode: RecommendedNext["mode"];
  readonly accentVar: string;
  readonly drillTitle: string;
}

/** Honest outcome tallies for the Summary row (FR-11). */
export interface OutcomeCountsVM {
  readonly firstTry: number;
  readonly coached: number;
  readonly walkedThrough: number;
}

type SessionAttemptProjection = Pick<
  Attempt,
  "id" | "question_id" | "correct" | "resolution" | "created_at"
>;

export interface SessionMissVM {
  readonly questionId: string;
  readonly stem: string;
  readonly skillId: string;
  readonly skillName: string;
  readonly resolution: AttemptResolution | null;
}

export interface SessionSkillPerformanceVM {
  readonly skillId: string;
  readonly skillName: string;
  readonly correct: number;
  readonly total: number;
  readonly accuracyPct: number;
  readonly strength: "strong" | "weak";
}

export interface SessionInsightsVM {
  readonly misses: readonly SessionMissVM[];
  readonly skillPerformance: readonly SessionSkillPerformanceVM[];
}

export interface SessionSummaryVM {
  readonly scoreCorrect: number;
  readonly scoreTotal: number;
  readonly scoreTile: string; // "7/10"
  readonly masteryDeltaTile: string; // "+8%" / "-3%"
  readonly timeTile: string; // "12 min", "<1 min" (sub-minute), or "—" (unknown)
  readonly recommended: RecommendedNextVM;
  readonly title: string;
  readonly body: string;
  readonly misconception: string | null;
  readonly selfCorrected: boolean;
  readonly showFramedTitle: boolean;
  /**
   * Commit-first outcome counts (FR-11). Null when no resolving-row signal
   * exists (legacy session with only null resolutions → hide the row, AP-6).
   */
  readonly outcomeCounts: OutcomeCountsVM | null;
  readonly misses: readonly SessionMissVM[];
  readonly skillPerformance: readonly SessionSkillPerformanceVM[];
}

/**
 * Phase D projections from rows supplied by the coarse Summary response.
 * This reshapes session attempts; it never recomputes the authoritative score.
 */
export function projectSessionInsights(
  attempts: ReadonlyArray<SessionAttemptProjection>,
  questions: ReadonlyArray<Pick<Question, "id" | "skill_id" | "stem">>,
  skills: ReadonlyArray<Pick<Skill, "id" | "name">>,
): SessionInsightsVM {
  const questionsById = new Map(questions.map((question) => [question.id, question]));
  const skillsById = new Map(skills.map((skill) => [skill.id, skill]));
  const misses: SessionMissVM[] = [];
  const tallies = new Map<string, { correct: number; total: number }>();

  for (const attempt of resolvingAttemptForQuestion(attempts).values()) {
    const question = questionsById.get(attempt.question_id);
    // G9 / AP-6: an attempt without its content row cannot be identified or
    // assigned to a skill honestly, so omit it instead of fabricating labels.
    if (question == null) continue;
    const skill = skillsById.get(question.skill_id);
    if (skill == null) continue;

    const tally = tallies.get(skill.id) ?? { correct: 0, total: 0 };
    tally.total += 1;
    if (attempt.correct) tally.correct += 1;
    tallies.set(skill.id, tally);

    if (!attempt.correct || attempt.resolution === "walked_through") {
      misses.push({
        questionId: question.id,
        stem: question.stem,
        skillId: skill.id,
        skillName: skill.name,
        resolution: attempt.resolution ?? null,
      });
    }
  }

  const skillPerformance: SessionSkillPerformanceVM[] = [];
  for (const [skillId, tally] of tallies) {
    const skill = skillsById.get(skillId);
    if (skill == null) continue;
    const accuracy = tally.correct / tally.total;
    skillPerformance.push({
      skillId,
      skillName: skill.name,
      correct: tally.correct,
      total: tally.total,
      accuracyPct: Math.round(accuracy * 100),
      // Reuse the Summary's existing positive-performance threshold; Phase D
      // adds no second, competing definition of "strong".
      strength:
        accuracy >= SUMMARY_FRAMED_TITLE_RATIO ? "strong" : "weak",
    });
  }

  return { misses, skillPerformance };
}

/**
 * Derive per-item outcomes from session attempts (FR-11 / AP-6).
 * Uses the §6 resolving attempt per question_id (greatest `created_at`, ties by
 * greatest `id`); legacy single-attempt rule: correct ⇒ first_try when
 * resolution is null. Non-resolving retries ignored when the winner has no resolution
 * and is incorrect.
 */
export function countSessionOutcomes(
  attempts: ReadonlyArray<
    Pick<Attempt, "id" | "question_id" | "correct" | "resolution" | "created_at">
  >,
): OutcomeCountsVM | null {
  if (attempts.length === 0) return null;

  let firstTry = 0;
  let coached = 0;
  let walkedThrough = 0;
  let anyResolution = false;

  for (const a of resolvingAttemptForQuestion(attempts).values()) {
    const res: AttemptResolution | null | undefined = a.resolution;
    if (res == null) {
      // Legacy: one attempt per item; correct ⇒ first_try (AP-6 — no fabricate).
      if (a.correct) firstTry += 1;
      continue;
    }
    anyResolution = true;
    if (res === "first_try") firstTry += 1;
    else if (res === "coached") coached += 1;
    else if (res === "walked_through") walkedThrough += 1;
  }

  // Hide the row when the session has zero resolution-bearing rows AND zero
  // legacy corrects — i.e. nothing honest to show. Legacy sessions with
  // corrects still surface firstTry via the legacy rule above; return counts.
  if (!anyResolution && firstTry === 0 && coached === 0 && walkedThrough === 0) {
    // All-wrong legacy session: still no outcome row (would show 0/0/0 noise).
    return null;
  }
  // G9: the prior `!anyResolution && coached === 0 && walkedThrough === 0`
  // branch was dead — under `!anyResolution` the coached/walkedThrough counts
  // are structurally zero (they only increment when a row carries a resolution,
  // which also flips anyResolution true). The fall-through return produces the
  // identical { firstTry, coached: 0, walkedThrough: 0 } for the legacy
  // correct-only case, so the branch was unreachable in intent and redundant.
  return { firstTry, coached, walkedThrough };
}

function signedPct(delta: number): string {
  // Round FIRST, then choose the sign from the rounded value: a tiny negative
  // delta (e.g. -0.4) rounds to 0 and must read "+0%", not "-0%" (Math.round
  // returns -0, and picking the sign from the raw delta would print "-0%").
  const rounded = Math.round(delta);
  const sign = rounded >= 0 ? "+" : "-";
  return `${sign}${Math.abs(rounded)}%`;
}

function timeTile(session: QuizSession): string {
  if (session.ended_at == null) return "—";
  const ms = Date.parse(session.ended_at) - Date.parse(session.started_at);
  if (!Number.isFinite(ms) || ms < 0) return "—";
  // S-2b (honest-null discipline): a real but sub-minute session is not zero
  // time. Rounding to whole minutes prints "0 min" — indistinguishable from an
  // instant/no-op. Below one minute reads "<1 min" instead of a fabricated 0.
  if (ms < 60000) return "<1 min";
  return `${Math.round(ms / 60000)} min`;
}

function drillTitle(session: QuizSession, skillName: string): string {
  if (session.target_count == null) return `Drill: ${skillName}`;
  return `${session.target_count}-item drill: ${skillName}`;
}

function titleAndBody(
  skillName: string,
  misconception: string | null,
  selfCorrected: boolean,
  scoreRatioMet: boolean,
): { title: string; body: string } {
  if (!scoreRatioMet) {
    return {
      title: "Session summary",
      body: "Here's how this session went.",
    };
  }
  const title = "Nice work — you found the pattern.";
  if (selfCorrected && misconception != null) {
    return { title, body: `The pattern: ${misconception}.` };
  }
  return { title, body: `You cleared the ${skillName} bar.` };
}

export function toSessionSummaryVM(
  session: QuizSession,
  recommended: RecommendedNext,
  nextSkill: Skill,
  masteryDeltaPct: number,
  misconception: string | null,
  selfCorrected: boolean,
  scoreRatioMet: boolean,
  sessionAttempts: ReadonlyArray<
    Pick<Attempt, "id" | "question_id" | "correct" | "resolution" | "created_at">
  > = [],
  sessionQuestions: ReadonlyArray<
    Pick<Question, "id" | "skill_id" | "stem">
  > = [],
  insightSkills: ReadonlyArray<Pick<Skill, "id" | "name">> = [],
): SessionSummaryVM {
  const { title, body } = titleAndBody(
    nextSkill.name,
    misconception,
    selfCorrected,
    scoreRatioMet,
  );
  const insights = projectSessionInsights(
    sessionAttempts,
    sessionQuestions,
    insightSkills,
  );
  return {
    scoreCorrect: session.score_correct,
    scoreTotal: session.score_total,
    // FR-11 / FR-G1: score tile is the STORED session tally (first_try under
    // commit-first; identical for legacy single-attempt sessions).
    scoreTile: `${session.score_correct}/${session.score_total}`,
    masteryDeltaTile: signedPct(masteryDeltaPct),
    timeTile: timeTile(session),
    recommended: {
      skillId: nextSkill.id,
      skillName: nextSkill.name,
      mode: recommended.mode,
      accentVar: nextSkill.accent_var,
      drillTitle: drillTitle(session, nextSkill.name),
    },
    title,
    body,
    misconception,
    selfCorrected,
    showFramedTitle: scoreRatioMet,
    outcomeCounts: countSessionOutcomes(sessionAttempts),
    misses: insights.misses,
    skillPerformance: insights.skillPerformance,
  };
}
