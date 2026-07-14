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

/**
 * Resolve a pinned `skillId` to its display name via the SkillTaxonomy (C-3).
 * The taxonomy resolves by `key`, not `id`, so we `list()` and match on `id`.
 * Returns null on a null/empty id, an unknown id, or any load failure — the
 * coach history line then omits a name rather than echoing a raw `s-*` id
 * (honest-null: an unresolved label is absent, never a fabricated one).
 */
export async function skillNameById(
  ports: Pick<EnginePortBag, "skillTaxonomy">,
  subject: string,
  skillId: string | null | undefined,
): Promise<string | null> {
  if (skillId == null || skillId === "") return null;
  try {
    const skills = await ports.skillTaxonomy.list(subject);
    return skills.find((s) => s.id === skillId)?.name ?? null;
  } catch {
    return null;
  }
}

export function useCoachSurface(): {
  countMissesOnSkill: (
    args: CountMissesOnSkillArgs,
  ) => Promise<number | null>;
  skillNameById: (
    subject: string,
    skillId: string | null | undefined,
  ) => Promise<string | null>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      countMissesOnSkill: (args: CountMissesOnSkillArgs) =>
        countMissesOnSkill(ports, args),
      skillNameById: (subject: string, skillId: string | null | undefined) =>
        skillNameById(ports, subject, skillId),
    }),
    [ports],
  );
}
