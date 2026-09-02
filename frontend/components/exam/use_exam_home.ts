/**
 * use_exam_home — S-D1 loader for `/learn/exam` (FR-10–12).
 *
 * Pure async load + start against an injected ExamRunRepo. The React hook
 * is thin glue over useEngine() (B1). Pages stay presentational.
 */

"use client";

import * as React from "react";
import { useEngine } from "@/app/engine-provider";
import type { ExamRunRepo } from "@/lib/ports/engine/exam_run_repo";
import { EngineRepoError } from "@/lib/ports/engine/errors";
import type {
  ExamForm,
  ExamSectionAttemptStatus,
  ExamSectionCode,
} from "@/lib/wire/exam_entities";

export type ExamSectionStatusVM = {
  readonly code: ExamSectionCode;
  readonly title: string;
  readonly minutes: number;
  readonly officialOrder: number;
  readonly recommended: boolean;
  readonly status: ExamSectionAttemptStatus;
  readonly remainingMs: number | null;
  readonly startBlocked: boolean;
  readonly href: string | null;
};

export type ExamHomeFormVM = {
  readonly formId: string;
  readonly title: string;
  readonly runId: string | null;
  readonly sections: readonly ExamSectionStatusVM[];
};

export type ExamHomeVM = {
  readonly forms: readonly ExamHomeFormVM[];
};

export type LoadExamHomeArgs = {
  readonly learnerId: string;
  readonly forms: readonly ExamForm[];
  readonly now: Date;
};

export type StartExamSectionArgs = {
  readonly learnerId: string;
  readonly forms: readonly ExamForm[];
  readonly formId: string;
  readonly sectionCode: ExamSectionCode;
};

function statusOf(
  attempts: readonly { section_code: ExamSectionCode; status: ExamSectionAttemptStatus }[],
  code: ExamSectionCode,
): ExamSectionAttemptStatus {
  return attempts.find((a) => a.section_code === code)?.status ?? "not_started";
}

function remainingMsOf(
  attempts: readonly {
    section_code: ExamSectionCode;
    status: ExamSectionAttemptStatus;
    deadline_at: string | null;
  }[],
  code: ExamSectionCode,
  now: Date,
): number | null {
  const attempt = attempts.find((a) => a.section_code === code);
  if (attempt == null || attempt.status !== "in_progress") return null;
  if (attempt.deadline_at == null) return null;
  return Math.max(0, Date.parse(attempt.deadline_at) - now.getTime());
}

function pickEntry(
  entries: Awaited<ReturnType<ExamRunRepo["listRunEntries"]>>,
  form: ExamForm,
): (typeof entries)[number] | null {
  const forForm = entries.filter((e) => e.run.form_id === form.id);
  const open = forForm.find((e) =>
    form.sections.some((section) => {
      const status = statusOf(e.attempts, section.code);
      return status === "not_started" || status === "in_progress";
    }),
  );
  return open ?? forForm[0] ?? null;
}

export async function loadExamHome(
  repo: ExamRunRepo,
  args: LoadExamHomeArgs,
): Promise<ExamHomeVM> {
  const entries = await repo.listRunEntries({ learnerId: args.learnerId });
  return {
    forms: args.forms.map((form) => {
      const entry = pickEntry(entries, form);
      const inProgress = form.sections.find(
        (s) => statusOf(entry?.attempts ?? [], s.code) === "in_progress",
      );
      return {
        formId: form.id,
        title: form.title,
        runId: entry?.run.id ?? null,
        sections: form.sections.map((section, index) => {
          const status = statusOf(entry?.attempts ?? [], section.code);
          return {
            code: section.code,
            title: section.title,
            minutes: section.minutes,
            officialOrder: index + 1,
            recommended: index === 0,
            status,
            remainingMs: remainingMsOf(entry?.attempts ?? [], section.code, args.now),
            startBlocked: inProgress != null && inProgress.code !== section.code,
            href:
              entry == null ? null : `/learn/exam/${entry.run.id}/${section.code}`,
          };
        }),
      };
    }),
  };
}

export async function startExamSection(
  repo: ExamRunRepo,
  args: StartExamSectionArgs,
): Promise<{ runId: string; sectionCode: ExamSectionCode }> {
  const form = args.forms.find((f) => f.id === args.formId);
  if (form == null) {
    throw new EngineRepoError(`unknown exam form '${args.formId}'`);
  }
  const entries = await repo.listRunEntries({
    learnerId: args.learnerId,
    formId: args.formId,
  });
  const entry = pickEntry(entries, form);
  const inProgress = form.sections.find(
    (s) => statusOf(entry?.attempts ?? [], s.code) === "in_progress",
  );
  if (inProgress != null && inProgress.code !== args.sectionCode) {
    throw new EngineRepoError(
      "startExamSection: another section is in progress",
    );
  }
  const run =
    entry?.run ??
    (await repo.startRun({ learnerId: args.learnerId, formId: args.formId }));
  return { runId: run.id, sectionCode: args.sectionCode };
}

export function useExamHome(args: {
  readonly learnerId: string;
  readonly forms: readonly ExamForm[];
}): {
  readonly vm: ExamHomeVM | null;
  readonly loading: boolean;
  readonly start: (
    formId: string,
    sectionCode: ExamSectionCode,
  ) => Promise<{ runId: string; sectionCode: ExamSectionCode }>;
} {
  const ports = useEngine();
  const [vm, setVm] = React.useState<ExamHomeVM | null>(null);
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
    void loadExamHome(repo, {
      learnerId: args.learnerId,
      forms: args.forms,
      now: new Date(),
    }).then((result) => {
      if (!cancelled) {
        setVm(result);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [ports, args.learnerId, args.forms]);

  const start = React.useCallback(
    async (formId: string, sectionCode: ExamSectionCode) => {
      const repo = ports.examRunRepo;
      if (repo == null) {
        throw new EngineRepoError("examRunRepo is not wired");
      }
      return startExamSection(repo, {
        learnerId: args.learnerId,
        forms: args.forms,
        formId,
        sectionCode,
      });
    },
    [ports.examRunRepo, args.learnerId, args.forms],
  );

  return { vm, loading, start };
}
