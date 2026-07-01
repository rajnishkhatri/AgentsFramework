/**
 * useDashboard — the Dashboard screen's read-only seam onto the engine ports
 * (FR-C1..C5).
 *
 * Per F-R1 the Dashboard component owns NO domain logic. Gathering the six bucket
 * cards, picking today's weakest+due focus, and counting review-misses live here,
 * as React-free async functions exercised in node against a seeded
 * InMemoryEngineDb (the analogue of openQuizItem/runQuizSubmit in use_quiz.ts).
 *
 * READ-ONLY (FR-A2): the dashboard is a *view* — rendering it must not write
 * skill_state. So it reads via `learnerRead.listSkillState` (the ADR-0011 read
 * port) + `skillTaxonomy.list` and does NOT call `scheduler.next()` (which seeds
 * and upserts skill_state for a new learner). Today's-focus is derived read-only
 * by `pickFocusSkillId` (scheduler-parity selection) + a read-only reviewed-
 * question lookup, so the Scheduler stays the sole skill_state writer.
 *
 * Imports engine ports (via the injected bag) + wire shapes + the two dashboard
 * translators only. The default bag comes from `useEngine()` context (C3); tests
 * inject a seeded bag directly.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type { SkillState } from "@/lib/wire/engine_entities";
import { toBucketCardVM, type BucketCardVM } from "@/lib/translators/bucket_card_vm";
import { toTodayFocusVM, type TodayFocusVM } from "@/lib/translators/today_focus_vm";

export interface DashboardVM {
  /** One card per bucket (FR-C3), in skill `order` — six for English. */
  readonly buckets: readonly BucketCardVM[];
  /** The weakest+due focus banner (FR-C2); `present:false` on a cold start. */
  readonly todayFocus: TodayFocusVM;
  /** "Review my misses (N)" count (FR-C5); 0 for a learner with no misses. */
  readonly reviewMissesCount: number;
}

/**
 * Pure: the weakest+due focus skill id, or null when there are no rows. Mirrors
 * `FsrsScheduler.next`'s selection EXACTLY (so the dashboard's banner points at
 * the same skill the Scheduler would serve) but without the seeding write:
 * prefer due (`due_at <= now`), then lowest mastery, then earliest due_at, then
 * `skill_id.localeCompare` as a deterministic tie-break.
 */
export function pickFocusSkillId(
  states: readonly SkillState[],
  nowISO: string,
): string | null {
  if (states.length === 0) return null;
  const nowMs = Date.parse(nowISO);
  const due = states.filter((s) => Date.parse(s.due_at) <= nowMs);
  const pool = [...(due.length > 0 ? due : states)];
  pool.sort(
    (a, b) =>
      a.mastery - b.mastery ||
      Date.parse(a.due_at) - Date.parse(b.due_at) ||
      a.skill_id.localeCompare(b.skill_id),
  );
  return pool[0]!.skill_id;
}

export interface LoadDashboardArgs {
  readonly subject: string;
  readonly learnerId: string;
  /** Injected clock (T1 purity): "due" is computed against this, not Date.now(). */
  readonly nowISO: string;
}

/**
 * Read-only gather of everything the Dashboard renders. Runs the three
 * independent reads concurrently, then composes VMs with the pure translators.
 */
export async function loadDashboard(
  ports: EnginePortBag,
  args: LoadDashboardArgs,
): Promise<DashboardVM> {
  const { subject, learnerId, nowISO } = args;

  const [skills, states, misses] = await Promise.all([
    ports.skillTaxonomy.list(subject),
    ports.learnerRead.listSkillState(subject, learnerId),
    ports.attemptRepo.misses(subject, learnerId),
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

  return { buckets, todayFocus, reviewMissesCount: misses.length };
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

  // Read-only reviewed-question lookup for the focus skill (no write). Absent a
  // reviewed item, the banner hides rather than showing a CTA that can't start.
  const question = await ports.questionRepo.nextReviewed(args.subject, focusSkillId);
  if (question == null) return { present: false };

  return toTodayFocusVM(
    { skill_id: focusSkillId, question_id: question.id },
    skill,
  );
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * read-only loader bound to it. The component calls this; it holds no port logic.
 * Tests exercise `loadDashboard` / `pickFocusSkillId` directly with an injected
 * bag, so the hook stays a trivial context binding.
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
