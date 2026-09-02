// B1: 'use client' — section sitting is a live timed client surface.
"use client";

import * as React from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useEngine } from "@/app/engine-provider";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";
import { getExamForm } from "@/lib/adapters/engine/exam_forms";
import {
  ExamSectionCode,
  type ExamSectionAttempt,
} from "@/lib/wire/exam_entities";
import { ExamDirectionsView } from "@/components/exam/ExamDirectionsView";
import { ExamSectionLive } from "@/components/exam/ExamSectionLive";
import { ExamReviewView } from "@/components/exam/ExamReviewView";
import {
  buildExamReview,
  type ExamReviewFilter,
} from "@/components/exam/exam_review";

function resolveDurationMs(param: string | null, fullMs: number): number {
  if (process.env.NODE_ENV === "production") return fullMs;
  if (param == null) return fullMs;
  const parsed = Number(param);
  if (!Number.isFinite(parsed) || parsed <= 0) return fullMs;
  return parsed;
}

export default function ExamSectionPage(): React.JSX.Element {
  const params = useParams<{ runId: string; section: string }>();
  const searchParams = useSearchParams();
  const { learnerId } = useLearnIdentity();
  const ports = useEngine();
  const parsed = ExamSectionCode.safeParse(params.section);
  const [attempt, setAttempt] = React.useState<ExamSectionAttempt | null>(null);
  const [items, setItems] = React.useState<
    Awaited<ReturnType<NonNullable<typeof ports.examRunRepo>["listItems"]>>
  >([]);
  const [formId, setFormId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<ExamReviewFilter>("all");
  const [ready, setReady] = React.useState(false);
  const sectionCode = parsed.success ? parsed.data : null;

  React.useEffect(() => {
    const repo = ports.examRunRepo;
    if (repo == null || sectionCode == null) {
      setReady(true);
      setError("not-found");
      return;
    }
    let cancelled = false;
    void repo
      .getRunDetail({ learnerId, runId: params.runId })
      .then((detail) => {
        if (cancelled) return;
        if (detail == null) {
          setError("not-found");
          setReady(true);
          return;
        }
        setFormId(detail.run.form_id);
        setItems(detail.items.filter((i) => i.section_code === sectionCode));
        const row = detail.attempts.find((a) => a.section_code === sectionCode);
        setAttempt(
          row ?? {
            run_id: params.runId,
            section_code: sectionCode,
            status: "not_started",
            started_at: null,
            finished_at: null,
            deadline_at: null,
            raw_correct: null,
            raw_scored_total: null,
            scale_score: null,
            time_remaining_ms_at_submit: null,
          },
        );
        setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ports.examRunRepo, learnerId, params.runId, sectionCode]);

  if (!ready) {
    return (
      <div data-testid="exam-section-loading" className="p-6 text-sm text-muted">
        Loading section…
      </div>
    );
  }

  if (!parsed.success || error === "not-found" || formId == null || attempt == null) {
    return (
      <div data-testid="exam-section-missing" className="p-6 text-sm text-muted">
        Section not found.
      </div>
    );
  }

  const form = getExamForm(formId);
  const section = form.sections.find((s) => s.code === parsed.data);
  const repo = ports.examRunRepo;
  if (section == null || repo == null) {
    return (
      <div data-testid="exam-section-missing" className="p-6 text-sm text-muted">
        Section not found.
      </div>
    );
  }

  const fullMs = section.minutes * 60_000;
  const durMs = resolveDurationMs(searchParams?.get("dur") ?? null, fullMs);

  if (attempt.status === "not_started") {
    return (
      <ExamDirectionsView
        title={section.title}
        directions={section.directions}
        minutes={section.minutes}
        onBegin={() => {
          void repo
            .beginSection({
              learnerId,
              runId: params.runId,
              sectionCode: section.code,
            })
            .then((begun) => {
              const deadlineAt =
                durMs === fullMs
                  ? begun.deadline_at
                  : new Date(Date.now() + durMs).toISOString();
              setAttempt({ ...begun, deadline_at: deadlineAt });
            });
        }}
      />
    );
  }

  if (attempt.status === "submitted" || attempt.status === "expired") {
    const review = buildExamReview(section.questions, items, filter);
    return (
      <ExamReviewView
        title={section.title}
        items={review.items}
        filter={filter}
        onFilter={setFilter}
        onToggleBookmark={(questionId, bookmarked) => {
          void repo.setBookmark({
            learnerId,
            runId: params.runId,
            sectionCode: section.code,
            questionId,
            bookmarked,
          });
          setItems((prev) =>
            prev.map((row) =>
              row.question_id === questionId ? { ...row, bookmarked } : row,
            ),
          );
        }}
      />
    );
  }

  return (
    <ExamSectionLive
      key={`${attempt.started_at}-${attempt.deadline_at}`}
      repo={repo}
      learnerId={learnerId}
      runId={params.runId}
      section={section}
      attempt={attempt}
      items={items}
      questions={section.questions}
    />
  );
}
