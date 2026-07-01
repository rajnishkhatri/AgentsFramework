/**
 * session_summary_vm — (QuizSession, RecommendedNext, Skill, masteryDeltaPct)
 * → SessionSummaryVM (FR-G1..G3).
 *
 * Pure T1 map for Screen 5. FR-G1: the score tile reads the STORED session
 * score (`score_correct`/`score_total`) — the VM never re-tallies attempts. The
 * mastery delta is computed upstream (the hook diffs skill_state before/after)
 * and passed IN as `masteryDeltaPct`, keeping this map pure. Time is derived
 * from the stored ISO timestamps (whole minutes). The recommended-next card
 * (FR-G1) carries the skill + mode so its CTA re-opens Quiz (FR-G2).
 *
 * The misconception write-up itself (FR-G3) is generated content shown in the
 * coach card; it is passed through by the hook, not synthesized here.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type {
  QuizSession,
  RecommendedNext,
  Skill,
} from "../wire/engine_entities";

export interface RecommendedNextVM {
  readonly skillId: string;
  readonly skillName: string;
  readonly mode: RecommendedNext["mode"];
  readonly accentVar: string;
}

export interface SessionSummaryVM {
  readonly scoreCorrect: number;
  readonly scoreTotal: number;
  readonly scoreTile: string; // "7/10"
  readonly masteryDeltaTile: string; // "+8%" / "-3%"
  readonly timeTile: string; // "12 min" or "—"
  readonly recommended: RecommendedNextVM;
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
  return `${Math.round(ms / 60000)} min`;
}

export function toSessionSummaryVM(
  session: QuizSession,
  recommended: RecommendedNext,
  nextSkill: Skill,
  masteryDeltaPct: number,
): SessionSummaryVM {
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
    },
  };
}
