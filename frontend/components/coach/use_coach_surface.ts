/**
 * use_coach_surface — gather skill-scoped misses for coach chrome (B1 / ADR-0025).
 *
 * React-free async helper (Dashboard `loadDashboard` precedent): joins
 * `AttemptRepo.misses` with `QuestionRepo.get` because Attempt has no `skill_id`.
 * Errors / missing skillId → `null` (FR-1 honest absent — never fabricate).
 *
 * The thin React hook binds the engine bag from context; hosts compose
 * `toCoachSurfaceVM` with pin + derived mode themselves.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";

export interface CountMissesOnSkillArgs {
  readonly subject: string;
  readonly learnerId: string;
  /** When omitted, returns null (no honest skill scope). */
  readonly skillId?: string;
}

/**
 * Unique miss question_ids whose Question.skill_id matches `skillId`.
 * Returns null on missing skillId or any load failure (FR-1).
 */
export async function countMissesOnSkill(
  ports: Pick<EnginePortBag, "attemptRepo" | "questionRepo">,
  args: CountMissesOnSkillArgs,
): Promise<number | null> {
  const { subject, learnerId, skillId } = args;
  if (skillId == null || skillId === "") return null;

  try {
    const misses = await ports.attemptRepo.misses(subject, learnerId);
    const uniqueIds = [...new Set(misses.map((m) => m.question_id))];
    let count = 0;
    for (const qid of uniqueIds) {
      const q = await ports.questionRepo.get(qid);
      if (q != null && q.skill_id === skillId) count += 1;
    }
    return count;
  } catch {
    return null;
  }
}

export function useCoachSurface(): {
  countMissesOnSkill: (
    args: CountMissesOnSkillArgs,
  ) => Promise<number | null>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      countMissesOnSkill: (args: CountMissesOnSkillArgs) =>
        countMissesOnSkill(ports, args),
    }),
    [ports],
  );
}
