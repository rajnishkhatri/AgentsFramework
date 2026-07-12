/**
 * use_skill_detail — host I/O for `/learn/skill` (E1a FR-17/18/19).
 *
 * Gathers TutorialRepo + LearnerReadRepo + AttemptRepo + SkillTaxonomy reads,
 * runs pure translators (selectLessonContext, newestDueMiss, toSkillDetailVM).
 * Presentational view owns no I/O (F-R1).
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type { Skill, SkillState, Tutorial } from "@/lib/wire/engine_entities";
import {
  selectLessonContext,
  type LessonContext,
} from "@/lib/translators/select_lesson_context";
import { newestDueMiss } from "@/lib/translators/newest_due_miss";
import {
  toSkillDetailVM,
  type SkillDetailVM,
} from "@/lib/translators/skill_detail_vm";

export interface LoadSkillDetailArgs {
  readonly subject: string;
  readonly learnerId: string;
  readonly skillId: string;
  readonly nowISO: string;
  readonly requested?: LessonContext;
}

export type SkillDetailLoadResult =
  | { readonly status: "ok"; readonly vm: SkillDetailVM }
  | { readonly status: "not_found" }
  | { readonly status: "empty"; readonly vm: SkillDetailVM };

/**
 * Pure async load (node-testable against a seeded bag). Returns not_found when
 * the skill id is unknown; empty when the skill exists but has no reviewed
 * tutorial (FR-3 / FR-18).
 */
export async function loadSkillDetail(
  ports: EnginePortBag,
  args: LoadSkillDetailArgs,
): Promise<SkillDetailLoadResult> {
  const skills = await ports.skillTaxonomy.list(args.subject);
  const skill = skills.find((s) => s.id === args.skillId);
  if (skill == null) return { status: "not_found" };

  const [tutorial, skillStates, misses] = await Promise.all([
    ports.tutorialRepo.getTutorial(args.subject, args.skillId),
    ports.learnerRead.listSkillState(args.subject, args.learnerId),
    ports.attemptRepo.misses(args.subject, args.learnerId),
  ]);

  const stateForSkill = skillStates.find((s) => s.skill_id === args.skillId);
  const firstExposure = stateForSkill == null;
  const masteryPct =
    stateForSkill == null ? null : Math.round(stateForSkill.mastery * 100);

  // Resolve question rows for the due-miss join (already-fetched arrays).
  const questionIds = [...new Set(misses.map((m) => m.question_id))];
  const questions = (
    await Promise.all(questionIds.map((id) => ports.questionRepo.get(id)))
  ).filter((q): q is NonNullable<typeof q> => q != null);

  const dueMiss = newestDueMiss({
    misses,
    skillStates,
    questions,
    nowISO: args.nowISO,
    skillId: args.skillId,
  });

  // dueMisses for the selector: any due miss on THIS skill (boolean-ish).
  const dueMisses = dueMiss != null || hasDueMissOnSkill(misses, skillStates, questions, args.skillId, args.nowISO)
    ? 1
    : 0;

  const context = selectLessonContext({
    firstExposure,
    masteryPct,
    dueMisses,
    ...(args.requested != null ? { requested: args.requested } : {}),
  });

  const dueSkills = dueSkillRows(skills, skillStates, args.nowISO);

  const vm = toSkillDetailVM({
    context,
    tutorial,
    skill,
    misconceptionTag: dueMiss?.tag ?? null,
    dueSkills,
    accuracy: null, // E1a carve-out FR-16
    nowISO: args.nowISO,
    skillStates,
  });

  if (tutorial == null) return { status: "empty", vm };
  return { status: "ok", vm };
}

function hasDueMissOnSkill(
  misses: readonly { question_id: string }[],
  skillStates: readonly SkillState[],
  questions: readonly { id: string; skill_id: string }[],
  skillId: string,
  nowISO: string,
): boolean {
  const now = Date.parse(nowISO);
  const due = skillStates.some(
    (s) => s.skill_id === skillId && Date.parse(s.due_at) <= now,
  );
  if (!due) return false;
  const qById = new Map(questions.map((q) => [q.id, q]));
  return misses.some((m) => qById.get(m.question_id)?.skill_id === skillId);
}

function dueSkillRows(
  skills: readonly Skill[],
  skillStates: readonly SkillState[],
  nowISO: string,
): ReadonlyArray<{ readonly skillId: string; readonly name: string }> {
  const now = Date.parse(nowISO);
  const byId = new Map(skills.map((s) => [s.id, s]));
  const out: { skillId: string; name: string }[] = [];
  for (const st of skillStates) {
    if (Date.parse(st.due_at) > now) continue;
    const sk = byId.get(st.skill_id);
    if (sk == null) continue;
    out.push({ skillId: sk.id, name: sk.name });
  }
  return out;
}

export function useSkillDetail(args: {
  readonly subject: string;
  readonly learnerId: string;
  readonly skillId: string | null;
}): {
  readonly result: SkillDetailLoadResult | null;
  readonly loading: boolean;
} {
  const ports = useEngine();
  const [result, setResult] = React.useState<SkillDetailLoadResult | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    if (args.skillId == null || args.skillId.trim() === "") {
      setResult({ status: "not_found" });
      setLoading(false);
      return;
    }
    setLoading(true);
    void loadSkillDetail(ports, {
      subject: args.subject,
      learnerId: args.learnerId,
      skillId: args.skillId,
      nowISO: new Date().toISOString(),
    }).then((r) => {
      if (!cancelled) {
        setResult(r);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [ports, args.subject, args.learnerId, args.skillId]);

  return { result, loading };
}

/** Re-export for tests that seed a Tutorial directly. */
export type { Tutorial };
