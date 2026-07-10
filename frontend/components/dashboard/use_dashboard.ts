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
import { pickFocusSkillId } from "@/lib/translators/focus_pick";
import { uniqueMissQuestionIds } from "@/lib/miss_pool";

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

  return {
    buckets,
    todayFocus,
    reviewMissesCount: uniqueMissQuestionIds(misses).length,
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
