/**
 * progress_screen_vm — closed QuizSession[] + BucketCardVM[] → ProgressScreenVM
 * (Epic F FR-1..3, FR-6/7/8/10/11/12).
 *
 * Pure T1: accuracy trend from closed sessions, items-reviewed Σ, streak via
 * toStreakVM, buckets passthrough. No projectedScore (FR-3 — D4 deferred).
 * No Date.now(), no React, no I/O. Imports wire/ + sibling VMs only.
 */

import type { QuizSession } from "../wire/engine_entities";
import type { ExamAnalytics } from "../wire/exam_entities";
import type { BucketCardVM } from "./bucket_card_vm";
import { toStreakVM, type StreakVM } from "./streak_vm";

export type ProgressRange = "30d" | "all";

export interface TrendPoint {
  readonly atISO: string;
  readonly accuracyPct: number; // 0..100
}

export interface ProgressTrendVM {
  readonly points: readonly TrendPoint[]; // oldest→newest; [] → empty state (FR-1)
  readonly range: ProgressRange;
  // projectedScore is DELIBERATELY ABSENT until D4 (FR-3).
}

export interface ProgressHeaderVM {
  readonly itemsReviewed: number; // Σ score_total in range (FR-10)
  readonly streak: StreakVM;
}

export interface ProgressScreenVM {
  readonly header: ProgressHeaderVM;
  readonly trend: ProgressTrendVM | null;
  readonly buckets: readonly BucketCardVM[];
  /** FR-34: distinct exam panel; null when no finished section. */
  readonly examPerformance: ExamAnalytics | null;
}

export function toProgressScreenVM(inputs: {
  readonly closedSessions: readonly QuizSession[];
  readonly buckets: readonly BucketCardVM[];
  readonly range: ProgressRange;
  readonly nowISO: string;
  readonly examPerformance?: ExamAnalytics | null;
}): ProgressScreenVM {
  const { closedSessions, buckets, range, nowISO } = inputs;

  const points: TrendPoint[] = closedSessions
    .filter((s) => s.ended_at != null && s.score_total > 0)
    .map((s) => ({
      atISO: s.ended_at as string,
      accuracyPct: Math.round((100 * s.score_correct) / s.score_total),
    }))
    .sort((a, b) => Date.parse(a.atISO) - Date.parse(b.atISO));

  const itemsReviewed = closedSessions.reduce(
    (sum, s) => sum + s.score_total,
    0,
  );

  return {
    header: {
      itemsReviewed,
      streak: toStreakVM(closedSessions, nowISO),
    },
    // Empty history keeps a non-null trend with points:[] so the view can
    // render the honest empty-state copy (FR-1); null reserved for future
    // "no trend concept on this surface".
    trend: { points, range },
    buckets,
    examPerformance: inputs.examPerformance ?? null,
  };
}
