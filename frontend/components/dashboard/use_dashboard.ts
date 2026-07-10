/**
 * useDashboard — the Dashboard screen's read-only seam onto the engine ports
 * (FR-C1..C5 + C1 rail/greeting).
 *
 * Per F-R1 the Dashboard component owns NO domain logic. Gathering the six bucket
 * cards, picking today's weakest+due focus, counting review-misses, and composing
 * the greeting + trust-rail VMs live here, as React-free async functions exercised
 * in node against a seeded InMemoryEngineDb.
 *
 * READ-ONLY (FR-A2): the dashboard is a *view* — rendering it must not write
 * skill_state. So it reads via `learnerRead.listSkillState` (the ADR-0011 read
 * port) + `skillTaxonomy.list` and does NOT call `scheduler.next()`.
 *
 * Rail failure is scoped (FR-1): `listByLearner` rejection becomes
 * `rail.status = "unavailable"`; header + mastery stay honest.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type { QuizSession, SkillState } from "@/lib/wire/engine_entities";
import { toBucketCardVM, type BucketCardVM } from "@/lib/translators/bucket_card_vm";
import { toTodayFocusVM, type TodayFocusVM } from "@/lib/translators/today_focus_vm";
import { toGreetingVM, type GreetingVM } from "@/lib/translators/greeting_vm";
import { toStreakVM, type StreakVM } from "@/lib/translators/streak_vm";
import {
  toWeeklySessionsVM,
  type WeeklySessionsVM,
} from "@/lib/translators/weekly_sessions_vm";
import { pickFocusSkillId } from "@/lib/translators/focus_pick";

export interface RailVM {
  readonly status: "ok" | "unavailable";
  readonly streak: StreakVM;
  readonly weekly: WeeklySessionsVM;
}

export interface DashboardVM {
  /** One card per bucket (FR-C3), in skill `order` — six for English. */
  readonly buckets: readonly BucketCardVM[];
  /** The weakest+due focus banner (FR-C2); `present:false` on a cold start. */
  readonly todayFocus: TodayFocusVM;
  /**
   * "Review my misses (N)" count (FR-C5) — unique missed question ids, matching
   * the review-session pool / target_count (FR-A6). Duplicate misses of the same
   * item count once.
   */
  readonly reviewMissesCount: number;
  /** Personalized greeting from injected clock + learner id (FR-9/FR-10). */
  readonly greeting: GreetingVM;
  /** Trust rail: streak + weekly (FR-1/FR-2/FR-7/FR-8). */
  readonly rail: RailVM;
}

export interface LoadDashboardArgs {
  readonly subject: string;
  readonly learnerId: string;
  /** Injected clock (T1 purity): "due" is computed against this, not Date.now(). */
  readonly nowISO: string;
}

const RAIL_UNAVAILABLE = "rail-unavailable" as const;
const RAIL_LOOKBACK_DAYS = 30;

/** Pure: `nowISO` minus `days` (no `Date.now()`). */
export function computeSinceISO(nowISO: string, days: number): string {
  const ms = new Date(nowISO).getTime() - days * 24 * 60 * 60 * 1000;
  return new Date(ms).toISOString();
}

const UNAVAILABLE_RAIL: RailVM = {
  status: "unavailable",
  streak: { present: false, days: 0 },
  weekly: { count: 0, target: 3, label: "—" },
};

/**
 * Read-only gather of everything the Dashboard renders. Runs the four
 * independent reads concurrently (FR-15), then composes VMs with pure translators.
 */
export async function loadDashboard(
  ports: EnginePortBag,
  args: LoadDashboardArgs,
): Promise<DashboardVM> {
  const { subject, learnerId, nowISO } = args;
  const sinceISO = computeSinceISO(nowISO, RAIL_LOOKBACK_DAYS);

  const [skills, states, misses, railSessions] = await Promise.all([
    ports.skillTaxonomy.list(subject),
    ports.learnerRead.listSkillState(subject, learnerId),
    ports.attemptRepo.misses(subject, learnerId),
    (async () => {
      // Non-prod e2e hook: force one rail failure then clear (T7.1 retry row).
      if (
        process.env.NODE_ENV !== "production" &&
        typeof window !== "undefined"
      ) {
        const w = window as unknown as {
          __PREACT_E2E_RAIL_FAIL_ONCE__?: boolean;
        };
        if (w.__PREACT_E2E_RAIL_FAIL_ONCE__) {
          w.__PREACT_E2E_RAIL_FAIL_ONCE__ = false;
          throw new Error("e2e forced rail failure");
        }
      }
      return ports.sessionRepo.listByLearner(subject, learnerId, { sinceISO });
    })().catch(() => RAIL_UNAVAILABLE),
  ]);

  const stateBySkill = new Map<string, SkillState>(
    states.map((s) => [s.skill_id, s]),
  );

  const buckets = skills.map((skill) =>
    toBucketCardVM(skill, stateBySkill.get(skill.id) ?? null, nowISO),
  );

  const todayFocus = await buildTodayFocus(ports, {
    subject,
    states,
    skills,
    nowISO,
  });

  const greeting = toGreetingVM(nowISO, learnerId);
  const rail: RailVM =
    railSessions === RAIL_UNAVAILABLE
      ? UNAVAILABLE_RAIL
      : {
          status: "ok",
          streak: toStreakVM(railSessions as QuizSession[], nowISO),
          weekly: toWeeklySessionsVM(railSessions as QuizSession[], nowISO),
        };

  return {
    buckets,
    todayFocus,
    reviewMissesCount: misses.length,
    greeting,
    rail,
  };
}

async function buildTodayFocus(
  ports: EnginePortBag,
  args: {
    subject: string;
    states: readonly SkillState[];
    skills: Awaited<ReturnType<EnginePortBag["skillTaxonomy"]["list"]>>;
    nowISO: string;
  },
): Promise<TodayFocusVM> {
  const focusSkillId = pickFocusSkillId(args.states, args.nowISO);
  if (focusSkillId == null) return { present: false };

  const skill = args.skills.find((s) => s.id === focusSkillId) ?? null;
  if (skill == null) return { present: false };

  const question = await ports.questionRepo.nextReviewed(args.subject, focusSkillId);
  if (question == null) return { present: false };

  return toTodayFocusVM(
    { skill_id: focusSkillId, question_id: question.id },
    skill,
  );
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * read-only loader bound to it.
 */
export function useDashboard(): {
  load: (args: LoadDashboardArgs) => Promise<DashboardVM>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({ load: (args: LoadDashboardArgs) => loadDashboard(ports, args) }),
    [ports],
  );
}
