// B1: 'use client' — exam home reads the engine bag and starts a run.
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { listExamForms } from "@/lib/adapters/engine/exam_forms";
import { ExamHomeView } from "@/components/exam/ExamHomeView";
import { useExamHome } from "@/components/exam/use_exam_home";

export default function ExamHomePage(): React.JSX.Element {
  const { learnerId } = useLearnIdentity();
  const router = useRouter();
  const searchParams = useSearchParams();
  const forms = React.useMemo(() => listExamForms(), []);
  const { vm, loading, start } = useExamHome({ learnerId, forms });

  if (loading || vm == null) {
    return (
      <div data-testid="exam-home-loading" className="p-6 text-sm text-muted">
        Loading exam…
      </div>
    );
  }

  return (
    <ExamHomeView
      vm={vm}
      onStart={(formId, sectionCode) => {
        void start(formId, sectionCode).then(({ runId }) => {
          const qs = searchParams?.toString();
          const suffix = qs ? `?${qs}` : "";
          router.push(`/learn/exam/${runId}/${sectionCode}${suffix}`);
        });
      }}
    />
  );
}
