/**
 * use_progress_screen — host I/O for `/learn/progress` (Epic F FR-8/13/14).
 *
 * Gathers SessionRepo + skill taxonomy + learner skill states, builds the 6
 * BucketCardVMs (same composition as use_dashboard), runs toProgressScreenVM.
 * Presentational ProgressView owns no I/O (F-R1). progressRepo is intentionally
 * unconsumed (D4 dormant seam / FR-3).
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type { SkillState } from "@/lib/wire/engine_entities";
import { toBucketCardVM } from "@/lib/translators/bucket_card_vm";
import {
  toProgressScreenVM,
  type ProgressRange,
  type ProgressScreenVM,
} from "@/lib/translators/progress_screen_vm";
import { listExamForms } from "@/lib/adapters/engine/exam_forms";
import { examAnalytics } from "@/components/exam/exam_analytics";
import type { ExamAnalytics } from "@/lib/wire/exam_entities";

export interface LoadProgressScreenArgs {
  readonly subject: string;
  readonly learnerId: string;
  readonly range: ProgressRange;
  readonly nowISO: string;
}

/** Pure: `nowISO` minus `days` (no `Date.now()`). Mirrors use_dashboard. */
export function computeProgressSinceISO(nowISO: string, days: number): string {
  const ms = new Date(nowISO).getTime() - days * 24 * 60 * 60 * 1000;
  return new Date(ms).toISOString();
}

/**
 * Pure async load (node-testable against a seeded bag). Range "30d" passes
 * sinceISO; "all" omits it (FR-8).
 */
export async function loadProgressScreen(
  ports: EnginePortBag,
  args: LoadProgressScreenArgs,
): Promise<ProgressScreenVM> {
  const { subject, learnerId, range, nowISO } = args;

  const sessionsPromise =
    range === "30d"
      ? ports.sessionRepo.listByLearner(subject, learnerId, {
          sinceISO: computeProgressSinceISO(nowISO, 30),
        })
      : ports.sessionRepo.listByLearner(subject, learnerId);

  const [closedSessions, skills, states] = await Promise.all([
    sessionsPromise,
    ports.skillTaxonomy.list(subject),
    ports.learnerRead.listSkillState(subject, learnerId),
  ]);

  const stateBySkill = new Map<string, SkillState>(
    states.map((s) => [s.skill_id, s]),
  );
  const buckets = skills.map((skill) =>
    toBucketCardVM(skill, stateBySkill.get(skill.id) ?? null, nowISO),
  );

  let examPerformance: ExamAnalytics | null = null;
  const examRepo = ports.examRunRepo;
  if (examRepo != null) {
    const [examItems, examEntries] = await Promise.all([
      examRepo.listItemsByLearner({ learnerId }),
      examRepo.listRunEntries({ learnerId }),
    ]);
    const attempts = examEntries.flatMap((e) => e.attempts);
    const finished = attempts.some(
      (a) => a.status === "submitted" || a.status === "expired",
    );
    if (finished) {
      examPerformance = examAnalytics({
        learnerId,
        runId: null,
        items: examItems,
        sections: listExamForms().flatMap((f) => f.sections),
        attempts,
      });
    }
  }

  return toProgressScreenVM({
    closedSessions,
    buckets,
    range,
    nowISO,
    examPerformance,
  });
}

export function useProgressScreen(args: {
  readonly subject: string;
  readonly learnerId: string;
  readonly range: ProgressRange;
}): {
  readonly vm: ProgressScreenVM | null;
  readonly loading: boolean;
} {
  const ports = useEngine();
  const [vm, setVm] = React.useState<ProgressScreenVM | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void loadProgressScreen(ports, {
      subject: args.subject,
      learnerId: args.learnerId,
      range: args.range,
      nowISO: new Date().toISOString(),
    }).then((result) => {
      if (!cancelled) {
        setVm(result);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [ports, args.subject, args.learnerId, args.range]);

  return { vm, loading };
}
