/**
 * useDashboard — the Dashboard screen's read-only seam onto the engine ports
 * (FR-C1..C5 + C1 rail/greeting + C1-fix hardening).
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
 * `rail.status = "unavailable"`; header + mastery stay honest. The fail-once
 * e2e seam lives in the composition root (FR-2), not here.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type { QuizSession, Skill, SkillState } from "@/lib/wire/engine_entities";
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
  /** Personalized greeting from injected clock + optional display name (FR-11). */
  readonly greeting: GreetingVM;
  /** Trust rail: streak + weekly (FR-1/FR-2/FR-7/FR-8). */
  readonly rail: RailVM;
}

export interface LoadDashboardArgs {
  readonly subject: string;
  readonly learnerId: string;
  /** Caller-supplied display name; omitted → bare "Good <time>" (FR-11). */
  readonly displayName?: string;
  /** Injected clock (T1 purity): "due" is computed against this, not Date.now(). */
  readonly nowISO: string;
}

/** Hook-local rail read result (FR-6 / Rule W3). Not a wire contract. */
type RailResult =
  | { readonly ok: true; readonly sessions: readonly QuizSession[] }
  | { readonly ok: false };

const RAIL_LOOKBACK_DAYS = 30;

/**
 * Speculative focus skill for concurrent `nextReviewed` (FR-4/FR-5, plan
 * §2.5.1a). Must be known synchronously at fan-out so the fifth read starts
 * before any of the other four resolve. `s-punc` is act-english order:1 (dev
 * seed + bank); reconcile drops the prefetch when `pickFocusSkillId` differs.
 */
const SPECULATIVE_FOCUS_SKILL_ID = "s-punc";

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

function toRailVM(result: RailResult, nowISO: string): RailVM {
  if (!result.ok) return UNAVAILABLE_RAIL;
  return {
    status: "ok",
    streak: toStreakVM(result.sessions, nowISO),
    weekly: toWeeklySessionsVM(result.sessions, nowISO),
  };
}

/**
 * Rail-only reload (FR-8): re-fires `listByLearner` without touching greeting /
 * buckets / focus / misses.
 */
export async function loadRail(
  ports: EnginePortBag,
  args: LoadDashboardArgs,
): Promise<RailVM> {
  const { subject, learnerId, nowISO } = args;
  const sinceISO = computeSinceISO(nowISO, RAIL_LOOKBACK_DAYS);
  const result: RailResult = await ports.sessionRepo
    .listByLearner(subject, learnerId, { sinceISO })
    .then(
      (sessions): RailResult => ({ ok: true, sessions }),
      (): RailResult => ({ ok: false }),
    );
  return toRailVM(result, nowISO);
}

/**
 * Read-only gather of everything the Dashboard renders. Runs five independent
 * reads concurrently (FR-4/FR-15) — skills, states, misses, rail, and a
 * speculative focus-question prefetch — then composes VMs with pure translators.
 */
export async function loadDashboard(
  ports: EnginePortBag,
  args: LoadDashboardArgs,
): Promise<DashboardVM> {
  const { subject, learnerId, displayName, nowISO } = args;
  const sinceISO = computeSinceISO(nowISO, RAIL_LOOKBACK_DAYS);

  const [skills, states, misses, railResult, speculativeQuestion] =
    await Promise.all([
      ports.skillTaxonomy.list(subject),
      ports.learnerRead.listSkillState(subject, learnerId),
      ports.attemptRepo.misses(subject, learnerId),
      ports.sessionRepo
        .listByLearner(subject, learnerId, { sinceISO })
        .then(
          (sessions): RailResult => ({ ok: true, sessions }),
          (): RailResult => ({ ok: false }),
        ),
      // Speculative prefetch — invoked synchronously so it starts with the
      // other four (FR-4/FR-5). Reconcile below if pick differs.
      ports.questionRepo.nextReviewed(subject, SPECULATIVE_FOCUS_SKILL_ID),
    ]);

  const stateBySkill = new Map<string, SkillState>(
    states.map((s) => [s.skill_id, s]),
  );

  const buckets = skills.map((skill) =>
    toBucketCardVM(skill, stateBySkill.get(skill.id) ?? null, nowISO),
  );

  const todayFocus = await resolveTodayFocus(ports, {
    subject,
    skills,
    states,
    nowISO,
    speculativeQuestion,
  });

  return {
    buckets,
    todayFocus,
    reviewMissesCount: misses.length,
    greeting: toGreetingVM(nowISO, displayName),
    rail: toRailVM(railResult, nowISO),
  };
}

async function resolveTodayFocus(
  ports: EnginePortBag,
  args: {
    subject: string;
    skills: readonly Skill[];
    states: readonly SkillState[];
    nowISO: string;
    speculativeQuestion: Awaited<
      ReturnType<EnginePortBag["questionRepo"]["nextReviewed"]>
    >;
  },
): Promise<TodayFocusVM> {
  const focusSkillId = pickFocusSkillId(args.states, args.nowISO);
  if (focusSkillId == null) return { present: false };

  const skill = args.skills.find((s) => s.id === focusSkillId) ?? null;
  if (skill == null) return { present: false };

  const question =
    focusSkillId === SPECULATIVE_FOCUS_SKILL_ID &&
    args.speculativeQuestion != null
      ? args.speculativeQuestion
      : await ports.questionRepo.nextReviewed(args.subject, focusSkillId);
  if (question == null) return { present: false };

  return toTodayFocusVM(
    { skill_id: focusSkillId, question_id: question.id },
    skill,
  );
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * read-only loaders bound to it.
 */
export function useDashboard(): {
  load: (args: LoadDashboardArgs) => Promise<DashboardVM>;
  loadRail: (args: LoadDashboardArgs) => Promise<RailVM>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      load: (a: LoadDashboardArgs) => loadDashboard(ports, a),
      loadRail: (a: LoadDashboardArgs) => loadRail(ports, a),
    }),
    [ports],
  );
}
