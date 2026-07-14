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
  QuizSession,
  RecommendedNext,
  Skill,
} from "../wire/engine_entities";

/** Score ratio at which the Summary title flips to framed "Nice work" copy. */
export const SUMMARY_FRAMED_TITLE_RATIO = 0.6;

export interface RecommendedNextVM {
  readonly skillId: string;
  readonly skillName: string;
  readonly mode: RecommendedNext["mode"];
  readonly accentVar: string;
  readonly drillTitle: string;
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
): SessionSummaryVM {
  const { title, body } = titleAndBody(
    nextSkill.name,
    misconception,
    selfCorrected,
    scoreRatioMet,
  );
  return {
    scoreCorrect: session.score_correct,
    scoreTotal: session.score_total,
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
  };
}
