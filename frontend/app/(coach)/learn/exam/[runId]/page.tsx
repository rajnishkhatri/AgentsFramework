// B1: 'use client' — run results read the engine bag + form registry.
"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { getExamForm } from "@/lib/adapters/engine/exam_forms";
import { ExamResultsView } from "@/components/exam/ExamResultsView";
import { useExamRunResults } from "@/components/exam/use_exam_run";

export default function ExamRunPage(): React.JSX.Element {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const { learnerId } = useLearnIdentity();
  const { vm, loading } = useExamRunResults({
    learnerId,
    runId,
    getForm: getExamForm,
  });

  if (loading || vm == null) {
    return (
      <div data-testid="exam-results-loading" className="p-6 text-sm text-muted">
        Loading results…
      </div>
    );
  }

  return (
    <ExamResultsView
      formTitle={vm.form.title}
      composite={vm.run.composite}
      analytics={vm.analytics}
      homeHref="/learn/exam"
      sections={vm.form.sections.map((section) => ({
        code: section.code,
        title: section.title,
        attempt:
          vm.attempts.find((a) => a.section_code === section.code) ?? null,
        href: `/learn/exam/${runId}/${section.code}`,
      }))}
    />
  );
}
