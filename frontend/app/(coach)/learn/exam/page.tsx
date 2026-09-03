// B1: 'use client' — exam home reads the engine bag and starts a run.
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEngine } from "@/app/engine-provider";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { ExamHomeView } from "@/components/exam/ExamHomeView";
import { useExamHome } from "@/components/exam/use_exam_home";
import type { ClientExamForm } from "@/lib/wire/exam_entities";

export default function ExamHomePage(): React.JSX.Element {
  const { learnerId } = useLearnIdentity();
  const router = useRouter();
  const searchParams = useSearchParams();
  const ports = useEngine();
  const [forms, setForms] = React.useState<readonly ClientExamForm[] | null>(
    null,
  );

  React.useEffect(() => {
    const repo = ports.examRunRepo;
    if (repo == null) {
      setForms([]);
      return;
    }
    let cancelled = false;
    void repo.listClientForms({ learnerId }).then((loaded) => {
      if (!cancelled) setForms(loaded);
    });
    return () => {
      cancelled = true;
    };
  }, [ports.examRunRepo, learnerId]);

  const { vm, loading, start } = useExamHome({
    learnerId,
    forms: forms ?? [],
  });

  if (forms == null || loading || vm == null) {
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
