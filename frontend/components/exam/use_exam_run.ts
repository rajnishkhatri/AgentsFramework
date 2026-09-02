/**
 * use_exam_run — S-D2 loader for `/learn/exam/[runId]` results (FR-28/34).
 */

"use client";

import * as React from "react";
import { useEngine } from "@/app/engine-provider";
import type { ExamRunRepo } from "@/lib/ports/engine/exam_run_repo";
import type {
  ExamAnalytics,
  ExamForm,
  ExamRun,
  ExamSectionAttempt,
} from "@/lib/wire/exam_entities";
import { examAnalytics } from "./exam_analytics";

export type ExamRunResultsVM = {
  readonly run: ExamRun;
  readonly form: ExamForm;
  readonly attempts: readonly ExamSectionAttempt[];
  readonly analytics: ExamAnalytics | null;
};

export async function loadExamRunResults(
  repo: ExamRunRepo,
  args: {
    learnerId: string;
    runId: string;
    getForm: (id: string) => ExamForm;
  },
): Promise<ExamRunResultsVM | null> {
  const detail = await repo.getRunDetail({
    learnerId: args.learnerId,
    runId: args.runId,
  });
  if (detail == null) return null;
  const form = args.getForm(detail.run.form_id);
  const finished = detail.attempts.some(
    (a) => a.status === "submitted" || a.status === "expired",
  );
  const analytics = finished
    ? examAnalytics({
        learnerId: args.learnerId,
        runId: args.runId,
        items: detail.items,
        sections: form.sections,
        attempts: detail.attempts,
      })
    : null;
  return {
    run: detail.run,
    form,
    attempts: detail.attempts,
    analytics,
  };
}

export function useExamRunResults(args: {
  readonly learnerId: string;
  readonly runId: string;
  readonly getForm: (id: string) => ExamForm;
}): {
  readonly vm: ExamRunResultsVM | null;
  readonly loading: boolean;
} {
  const ports = useEngine();
  const [vm, setVm] = React.useState<ExamRunResultsVM | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const repo = ports.examRunRepo;
    if (repo == null) {
      setVm(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void loadExamRunResults(repo, {
      learnerId: args.learnerId,
      runId: args.runId,
      getForm: args.getForm,
    }).then((result) => {
      if (!cancelled) {
        setVm(result);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [ports, args.learnerId, args.runId, args.getForm]);

  return { vm, loading };
}
