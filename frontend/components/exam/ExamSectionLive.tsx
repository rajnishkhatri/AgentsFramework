/**
 * ExamSectionLive — wires useExamSection to runner / finished review (S-D2).
 */

"use client";

import * as React from "react";
import type { ExamRunRepo } from "@/lib/ports/engine/exam_run_repo";
import type {
  ExamQuestion,
  ExamRunItem,
  ExamSection,
  ExamSectionAttempt,
} from "@/lib/wire/exam_entities";
import { toQuizItemVM } from "@/lib/translators/quiz_item_vm";
import { createExamClock } from "./exam_clock";
import { navigatorCells } from "./exam_section_reducer";
import { useExamSection } from "./use_exam_section";
import { ExamRunnerView } from "./ExamRunnerView";
import { ExamReviewView } from "./ExamReviewView";
import {
  buildExamReview,
  type ExamReviewFilter,
} from "./exam_review";

export interface ExamSectionLiveProps {
  readonly repo: ExamRunRepo;
  readonly learnerId: string;
  readonly runId: string;
  readonly section: ExamSection;
  readonly attempt: ExamSectionAttempt;
  readonly items: readonly ExamRunItem[];
  readonly questions: readonly ExamQuestion[];
}

function browserBeacon(): boolean {
  // G9: no exam beacon route exists yet. Returning false keeps the
  // localStorage mirror + retry ladder (FR-36); do not pretend a 404 flushed.
  return false;
}

export function ExamSectionLive(props: ExamSectionLiveProps): React.JSX.Element {
  const clock = React.useMemo(() => createExamClock(), []);
  const storage = React.useMemo<Pick<Storage, "getItem" | "setItem" | "removeItem">>(
    () =>
      typeof window === "undefined"
        ? {
            getItem: () => null,
            setItem: () => undefined,
            removeItem: () => undefined,
          }
        : window.localStorage,
    [],
  );
  const { state, notSaved, dispatch } = useExamSection({
    clock,
    repo: props.repo,
    learnerId: props.learnerId,
    runId: props.runId,
    sectionCode: props.section.code,
    questionIds: props.questions.map((q) => q.id),
    attempt: props.attempt,
    items: props.items,
    storage,
    sendBeacon: browserBeacon,
  });

  React.useEffect(() => {
    if (state.phase !== "in_section") return;
    const id = window.setInterval(() => {
      void dispatch({ type: "tick" });
    }, 1000);
    void dispatch({ type: "tick" });
    return () => window.clearInterval(id);
  }, [state.phase, dispatch]);

  const [filter, setFilter] = React.useState<ExamReviewFilter>("all");
  const [bookmarks, setBookmarks] = React.useState<ReadonlyMap<string, boolean>>(
    () => new Map(props.items.map((i) => [i.question_id, i.bookmarked])),
  );

  const currentId = state.questionIds[state.currentIndex];
  const currentQuestion = props.questions.find((q) => q.id === currentId);
  const currentItem = currentId == null ? undefined : state.items[currentId];

  if (state.phase === "finished") {
    const mergedItems = props.questions.map((q, index) => {
      const live = state.items[q.id];
      const stored = props.items.find((i) => i.question_id === q.id);
      const base = live ?? stored;
      if (base == null) return null;
      return {
        ...base,
        ordinal: base.ordinal || index,
        bookmarked: bookmarks.get(q.id) ?? base.bookmarked,
      };
    }).filter((row): row is ExamRunItem => row != null);
    const review = buildExamReview(props.questions, mergedItems, filter);
    return (
      <ExamReviewView
        title={props.section.title}
        items={review.items}
        filter={filter}
        onFilter={setFilter}
        onToggleBookmark={(questionId, bookmarked) => {
          setBookmarks((prev) => new Map(prev).set(questionId, bookmarked));
          void props.repo.setBookmark({
            learnerId: props.learnerId,
            runId: props.runId,
            sectionCode: props.section.code,
            questionId,
            bookmarked,
          });
        }}
      />
    );
  }

  if (state.phase !== "in_section" || currentQuestion == null) {
    return (
      <div data-testid="exam-section-loading" className="p-6 text-sm text-muted">
        Loading section…
      </div>
    );
  }

  const answeredCount = state.questionIds.filter(
    (id) => state.items[id]?.chosen_letter != null,
  ).length;

  return (
    <ExamRunnerView
      vm={toQuizItemVM(currentQuestion)}
      selectedLetter={currentItem?.chosen_letter ?? null}
      flagged={currentItem?.flagged_in_section === true}
      index={state.currentIndex}
      count={state.questionIds.length}
      answeredCount={answeredCount}
      remainingMs={state.remainingMs ?? 0}
      fiveMinWarning={state.fiveMinWarning}
      sectionLabel={props.section.title}
      cells={navigatorCells(state)}
      pendingBlankConfirm={state.pendingBlankConfirm}
      notSaved={notSaved}
      onSelect={(letter) => {
        void dispatch({ type: "answer", letter });
      }}
      onClear={() => {
        void dispatch({ type: "clear" });
      }}
      onFlag={() => {
        void dispatch({ type: "flag" });
      }}
      onPrev={() => {
        void dispatch({ type: "navigate_prev" });
      }}
      onNext={() => {
        void dispatch({ type: "navigate_next" });
      }}
      onJump={(questionId) => {
        void dispatch({ type: "navigate", questionId });
      }}
      onSubmit={() => {
        void dispatch({ type: "submit" });
      }}
      onConfirmSubmit={() => {
        void dispatch({ type: "confirm_submit" });
      }}
      onCancelSubmit={() => {
        void dispatch({ type: "cancel_submit" });
      }}
    />
  );
}
