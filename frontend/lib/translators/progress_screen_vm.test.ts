/**
 * L1 tests for toProgressScreenVM (Epic F FR-1..3, FR-6/7/8/10/11/12).
 * Failure / empty / honesty rows first (TAP-4).
 */

import { describe, expect, it } from "vitest";
import type { QuizSession } from "../wire/engine_entities";
import type { BucketCardVM } from "./bucket_card_vm";
import { toStreakVM } from "./streak_vm";
import { toProgressScreenVM } from "./progress_screen_vm";

const NOW = "2026-07-13T12:00:00.000Z";

function session(
  over: Partial<QuizSession> & { ended_at: string },
): QuizSession {
  return {
    id: over.id ?? "s1",
    subject: "act-english",
    learner_id: "Garvit",
    mode: "adaptive",
    skill_focus: null,
    started_at: "2026-07-01T00:00:00.000Z",
    ended_at: over.ended_at,
    score_correct: over.score_correct ?? 3,
    score_total: over.score_total ?? 5,
    target_count: 30,
  };
}

function bucket(over: Partial<BucketCardVM> = {}): BucketCardVM {
  return {
    skillId: over.skillId ?? "s-punc",
    name: over.name ?? "Punctuation",
    masteryKnown: over.masteryKnown ?? true,
    masteryPct: over.masteryPct ?? 42,
    shareOfTestPct: over.shareOfTestPct ?? 15,
    accentVar: over.accentVar ?? "--color-bucket-punctuation",
    due: over.due ?? false,
  };
}

function sixBuckets(): BucketCardVM[] {
  return [
    bucket({ skillId: "s-rhet", name: "Rhetoric" }),
    bucket({ skillId: "s-usage", name: "Usage" }),
    bucket({ skillId: "s-punc", name: "Punctuation", due: true }),
    bucket({ skillId: "s-org", name: "Organization" }),
    bucket({ skillId: "s-struct", name: "Sentence Structure" }),
    bucket({ skillId: "s-conc", name: "Conciseness" }),
  ];
}

describe("toProgressScreenVM — honesty / empty (FR-1/2/3)", () => {
  it("empty_history_renders_empty_state_no_line", () => {
    const vm = toProgressScreenVM({
      closedSessions: [],
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    expect(vm.trend).not.toBeNull();
    expect(vm.trend!.points).toEqual([]);
  });

  it("single_session_no_synthetic_slope", () => {
    const vm = toProgressScreenVM({
      closedSessions: [
        session({
          ended_at: "2026-07-10T10:00:00.000Z",
          score_correct: 4,
          score_total: 5,
        }),
      ],
      buckets: sixBuckets(),
      range: "30d",
      nowISO: NOW,
    });
    expect(vm.trend!.points).toHaveLength(1);
    expect(vm.trend!.points[0]).toEqual({
      atISO: "2026-07-10T10:00:00.000Z",
      accuracyPct: 80,
    });
    // No fabricated delta / second point (FR-2).
    expect(vm.trend!.points).toHaveLength(1);
  });

  it("vm_has_no_projected_score_field", () => {
    const vm = toProgressScreenVM({
      closedSessions: [
        session({ ended_at: "2026-07-10T10:00:00.000Z" }),
      ],
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    const trendKeys = Object.keys(vm.trend!);
    expect(trendKeys.some((k) => /projected|goal|score/i.test(k))).toBe(false);
    expect("projectedScore" in (vm.trend as object)).toBe(false);
    expect("goal" in (vm.trend as object)).toBe(false);
  });
});

describe("toProgressScreenVM — trend series (FR-6/7)", () => {
  it("score_total_zero_excluded_from_series", () => {
    const vm = toProgressScreenVM({
      closedSessions: [
        session({
          id: "zero",
          ended_at: "2026-07-09T10:00:00.000Z",
          score_correct: 0,
          score_total: 0,
        }),
        session({
          id: "ok",
          ended_at: "2026-07-10T10:00:00.000Z",
          score_correct: 2,
          score_total: 4,
        }),
      ],
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    expect(vm.trend!.points).toHaveLength(1);
    expect(vm.trend!.points[0]!.accuracyPct).toBe(50);
  });

  it("trend_points_oldest_first_accuracy", () => {
    const vm = toProgressScreenVM({
      closedSessions: [
        // newest-first input (as listByLearner returns) — translator must sort asc
        session({
          id: "newer",
          ended_at: "2026-07-12T10:00:00.000Z",
          score_correct: 9,
          score_total: 10,
        }),
        session({
          id: "older",
          ended_at: "2026-07-08T10:00:00.000Z",
          score_correct: 1,
          score_total: 4,
        }),
      ],
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    expect(vm.trend!.points.map((p) => p.atISO)).toEqual([
      "2026-07-08T10:00:00.000Z",
      "2026-07-12T10:00:00.000Z",
    ]);
    expect(vm.trend!.points.map((p) => p.accuracyPct)).toEqual([25, 90]);
  });

  it("range_label_forwarded", () => {
    const vm30 = toProgressScreenVM({
      closedSessions: [],
      buckets: sixBuckets(),
      range: "30d",
      nowISO: NOW,
    });
    const vmAll = toProgressScreenVM({
      closedSessions: [],
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    expect(vm30.trend!.range).toBe("30d");
    expect(vmAll.trend!.range).toBe("all");
  });
});

describe("toProgressScreenVM — header + buckets (FR-10/11/12)", () => {
  it("items_reviewed_sums_score_total_in_range", () => {
    const vm = toProgressScreenVM({
      closedSessions: [
        session({
          id: "a",
          ended_at: "2026-07-10T10:00:00.000Z",
          score_total: 5,
        }),
        session({
          id: "b",
          ended_at: "2026-07-11T10:00:00.000Z",
          score_total: 0,
        }),
        session({
          id: "c",
          ended_at: "2026-07-12T10:00:00.000Z",
          score_total: 10,
        }),
      ],
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    // Σ score_total includes the 0-total row (adds 0).
    expect(vm.header.itemsReviewed).toBe(15);
  });

  it("streak_forwarded_from_toStreakVM", () => {
    const sessions = [
      session({ ended_at: NOW, id: "today" }),
    ];
    const vm = toProgressScreenVM({
      closedSessions: sessions,
      buckets: sixBuckets(),
      range: "all",
      nowISO: NOW,
    });
    expect(vm.header.streak).toEqual(toStreakVM(sessions, NOW));
  });

  it("six_bucket_bars_passthrough", () => {
    const buckets = sixBuckets();
    const vm = toProgressScreenVM({
      closedSessions: [],
      buckets,
      range: "all",
      nowISO: NOW,
    });
    expect(vm.buckets).toBe(buckets);
    expect(vm.buckets).toHaveLength(6);
  });
});
