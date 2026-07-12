/**
 * newest_due_miss — pure client-side join for the returning callout (E1a FR-16a/b).
 *
 * Takes already-fetched arrays (the host hook does I/O). Walks misses newest-first
 * × skillStates.due_at × questions.misconception. Returns the newest miss whose
 * skill is due + its verbatim tag, or null (tier-3 hide).
 *
 * Mirrors use_summary.ts deriveMisconception; no new port. Imports wire/ only.
 */

import type { Attempt, Question, SkillState } from "../wire/engine_entities";

export interface NewestDueMiss {
  readonly attempt: Attempt;
  readonly skillId: string;
  /** Verbatim author-written misconception tag (tier-2). */
  readonly tag: string;
}

export interface NewestDueMissInputs {
  /** Newest-first misses (AttemptRepo.misses contract). */
  readonly misses: readonly Attempt[];
  readonly skillStates: readonly SkillState[];
  readonly questions: readonly Question[];
  /** ISO now for due_at comparison (injected — T1 purity). */
  readonly nowISO: string;
  /** Optional: restrict to one skill (the lesson target). */
  readonly skillId?: string;
}

/**
 * Identify the newest due miss and its verbatim misconception tag.
 * Returns null when: no due miss, due miss has no tag, or skill filter misses.
 */
export function newestDueMiss(inputs: NewestDueMissInputs): NewestDueMiss | null {
  const now = Date.parse(inputs.nowISO);
  // Malformed nowISO would make every `due_at <= now` comparison silently false
  // (x <= NaN === false), hiding all due misses. Degrade explicitly to null
  // rather than a silent tier-3 that looks like "no due miss".
  if (Number.isNaN(now)) return null;
  const dueSkillIds = new Set(
    inputs.skillStates
      .filter((s) => Date.parse(s.due_at) <= now)
      .map((s) => s.skill_id),
  );
  const questionById = new Map(inputs.questions.map((q) => [q.id, q]));

  for (const miss of inputs.misses) {
    const q = questionById.get(miss.question_id);
    if (q == null) continue;
    if (inputs.skillId != null && q.skill_id !== inputs.skillId) continue;
    if (!dueSkillIds.has(q.skill_id)) continue;
    const tag = q.misconception?.trim() ?? "";
    if (tag === "") return null; // untagged due miss → tier-3 hide (FR-16b / FR-6c)
    return { attempt: miss, skillId: q.skill_id, tag };
  }
  return null;
}
