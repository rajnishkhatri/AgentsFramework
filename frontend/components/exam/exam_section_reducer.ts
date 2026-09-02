/**
 * Pure exam-section phase machine (W2-1 / FR-1, FR-13–24).
 *
 * Phases: directions → in_section → finished. Clock, dwell, and deadline
 * are driven by an injected `ExamClock` (B0-6). Dwell uses monotonic
 * deltas only — never wall-clock subtraction (spec §6).
 */

import type { ExamClock } from "./exam_clock";
import type {
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "@/lib/wire/exam_entities";

export const FIVE_MIN_MS = 5 * 60 * 1000;

export type ExamSectionPhase = "directions" | "in_section" | "finished";
export type ExamFinishStatus = "submitted" | "expired" | null;

export type NavigatorCell = {
  questionId: string;
  current: boolean;
  answered: boolean;
  flagged: boolean;
};

export type ExamSectionAction =
  | { type: "begin"; startedAt: string; deadlineAt: string }
  | { type: "tick" }
  | { type: "navigate"; questionId: string }
  | { type: "navigate_next" }
  | { type: "navigate_prev" }
  | { type: "answer"; letter: string }
  | { type: "clear" }
  | { type: "flag" }
  | { type: "submit" }
  | { type: "confirm_submit" }
  | { type: "cancel_submit" }
  | { type: "visibility"; hidden: boolean };

export type ExamSectionState = {
  phase: ExamSectionPhase;
  finishStatus: ExamFinishStatus;
  runId: string;
  sectionCode: ExamSectionCode;
  questionIds: readonly string[];
  currentIndex: number;
  items: Record<string, ExamRunItem>;
  startedAt: string | null;
  deadlineAt: string | null;
  remainingMs: number | null;
  fiveMinWarning: boolean;
  pendingBlankConfirm: number | null;
  hidden: boolean;
  visitStartedMono: number | null;
};

export function createExamSectionState(args: {
  questionIds: readonly string[];
  attempt: ExamSectionAttempt;
  items?: readonly ExamRunItem[];
  clock: ExamClock;
}): ExamSectionState {
  const { questionIds, attempt, clock } = args;
  const base: ExamSectionState = {
    phase: "directions",
    finishStatus: null,
    runId: attempt.run_id,
    sectionCode: attempt.section_code,
    questionIds,
    currentIndex: 0,
    items: buildItems(questionIds, attempt, args.items, clock),
    startedAt: attempt.started_at,
    deadlineAt: attempt.deadline_at,
    remainingMs: null,
    fiveMinWarning: false,
    pendingBlankConfirm: null,
    hidden: false,
    visitStartedMono: null,
  };

  if (attempt.status === "submitted" || attempt.status === "expired") {
    return {
      ...base,
      phase: "finished",
      finishStatus: attempt.status,
      remainingMs: remainingFrom(attempt.deadline_at, clock),
    };
  }

  if (attempt.status === "in_progress") {
    const remainingMs = remainingFrom(attempt.deadline_at, clock);
    if (remainingMs === 0) {
      return expire(base, clock);
    }
    return startVisit(
      withTiming({ ...base, phase: "in_section", remainingMs }, clock),
      clock,
      true,
    );
  }

  return base;
}

export function reduceExamSection(
  state: ExamSectionState,
  action: ExamSectionAction,
  clock: ExamClock,
): ExamSectionState {
  switch (action.type) {
    case "begin":
      return begin(state, action, clock);
    case "tick":
      return tick(state, clock);
    case "navigate":
      return navigateTo(state, action.questionId, clock);
    case "navigate_next":
      return navigateToIndex(state, state.currentIndex + 1, clock);
    case "navigate_prev":
      return navigateToIndex(state, state.currentIndex - 1, clock);
    case "answer":
      return answer(state, action.letter, clock);
    case "clear":
      return clearAnswer(state, clock);
    case "flag":
      return toggleFlag(state, clock);
    case "submit":
      return submit(state, clock);
    case "confirm_submit":
      return confirmSubmit(state, clock);
    case "cancel_submit":
      return cancelSubmit(state);
    case "visibility":
      return setVisibility(state, action.hidden, clock);
  }
}

export function navigatorCells(state: ExamSectionState): NavigatorCell[] {
  return state.questionIds.map((questionId, index) => {
    const item = state.items[questionId];
    return {
      questionId,
      current: index === state.currentIndex,
      answered: item?.chosen_letter != null,
      flagged: item?.flagged_in_section === true,
    };
  });
}

function begin(
  state: ExamSectionState,
  action: Extract<ExamSectionAction, { type: "begin" }>,
  clock: ExamClock,
): ExamSectionState {
  if (state.phase !== "directions") return state;
  const next = withTiming(
    {
      ...state,
      phase: "in_section",
      startedAt: action.startedAt,
      deadlineAt: action.deadlineAt,
    },
    clock,
  );
  if (next.remainingMs === 0) return expire(next, clock);
  return startVisit(next, clock, true);
}

function tick(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  if (state.phase !== "in_section") return state;
  const next = withTiming(state, clock);
  if (next.remainingMs === 0) return expire(next, clock);
  return next;
}

function navigateTo(
  state: ExamSectionState,
  questionId: string,
  clock: ExamClock,
): ExamSectionState {
  const index = state.questionIds.indexOf(questionId);
  if (index < 0) return state;
  return navigateToIndex(state, index, clock);
}

function navigateToIndex(
  state: ExamSectionState,
  index: number,
  clock: ExamClock,
): ExamSectionState {
  if (index < 0 || index >= state.questionIds.length) return state;
  if (index === state.currentIndex) return state;
  if (state.phase === "directions") return state;
  if (state.phase === "finished") {
    return { ...state, currentIndex: index };
  }
  const flushed = flushDwell(state, clock);
  return startVisit({ ...flushed, currentIndex: index }, clock, true);
}

function answer(
  state: ExamSectionState,
  letter: string,
  clock: ExamClock,
): ExamSectionState {
  if (!isWritable(state)) return state;
  const id = currentQuestionId(state);
  const item = id === undefined ? undefined : state.items[id];
  if (id === undefined || item == null || item.chosen_letter === letter) {
    return state;
  }
  const first = item.first_answered_at == null;
  const updated: ExamRunItem = {
    ...item,
    chosen_letter: letter,
    first_answered_at: first
      ? clock.now().toISOString()
      : item.first_answered_at,
    dwell_at_first_answer_ms: first
      ? item.dwell_ms + currentVisitDelta(state, clock)
      : item.dwell_at_first_answer_ms,
    answer_changes: first ? item.answer_changes : item.answer_changes + 1,
    updated_at: clock.now().toISOString(),
  };
  return {
    ...state,
    pendingBlankConfirm: null,
    items: { ...state.items, [id]: updated },
  };
}

function clearAnswer(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  if (!isWritable(state)) return state;
  const id = currentQuestionId(state);
  const item = id === undefined ? undefined : state.items[id];
  if (id === undefined || item == null || item.chosen_letter == null) {
    return state;
  }
  return {
    ...state,
    pendingBlankConfirm: null,
    items: {
      ...state.items,
      [id]: {
        ...item,
        chosen_letter: null,
        answer_changes: item.answer_changes + 1,
        updated_at: clock.now().toISOString(),
      },
    },
  };
}

function toggleFlag(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  if (!isWritable(state)) return state;
  const id = currentQuestionId(state);
  const item = id === undefined ? undefined : state.items[id];
  if (id === undefined || item == null) return state;
  return {
    ...state,
    items: {
      ...state.items,
      [id]: {
        ...item,
        flagged_in_section: !item.flagged_in_section,
        updated_at: clock.now().toISOString(),
      },
    },
  };
}

function submit(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  if (!isWritable(state)) return state;
  const blanks = unansweredCount(state);
  if (blanks > 0) {
    return { ...state, pendingBlankConfirm: blanks };
  }
  return finishSubmitted(state, clock);
}

function confirmSubmit(
  state: ExamSectionState,
  clock: ExamClock,
): ExamSectionState {
  if (!isWritable(state) || state.pendingBlankConfirm == null) return state;
  return finishSubmitted(state, clock);
}

function cancelSubmit(state: ExamSectionState): ExamSectionState {
  if (state.pendingBlankConfirm == null) return state;
  return { ...state, pendingBlankConfirm: null };
}

function setVisibility(
  state: ExamSectionState,
  hidden: boolean,
  clock: ExamClock,
): ExamSectionState {
  if (state.phase !== "in_section" || state.hidden === hidden) return state;
  if (hidden) {
    return { ...flushDwell(state, clock), hidden: true };
  }
  return startVisit({ ...state, hidden: false }, clock, false);
}

function expire(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  const flushed = flushDwell(state, clock);
  return {
    ...flushed,
    phase: "finished",
    finishStatus: "expired",
    remainingMs: 0,
    pendingBlankConfirm: null,
    visitStartedMono: null,
  };
}

function finishSubmitted(
  state: ExamSectionState,
  clock: ExamClock,
): ExamSectionState {
  const flushed = flushDwell(state, clock);
  return {
    ...flushed,
    phase: "finished",
    finishStatus: "submitted",
    remainingMs: remainingFrom(flushed.deadlineAt, clock),
    pendingBlankConfirm: null,
    visitStartedMono: null,
  };
}

function withTiming(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  const remainingMs = remainingFrom(state.deadlineAt, clock);
  const fiveMinWarning =
    state.fiveMinWarning ||
    (state.phase === "in_section" &&
      remainingMs != null &&
      remainingMs <= FIVE_MIN_MS);
  return { ...state, remainingMs, fiveMinWarning };
}

function flushDwell(state: ExamSectionState, clock: ExamClock): ExamSectionState {
  const delta = currentVisitDelta(state, clock);
  const id = currentQuestionId(state);
  const item = id === undefined ? undefined : state.items[id];
  if (id === undefined || item == null || delta === 0) {
    return { ...state, visitStartedMono: null };
  }
  return {
    ...state,
    visitStartedMono: null,
    items: {
      ...state.items,
      [id]: {
        ...item,
        dwell_ms: item.dwell_ms + delta,
        updated_at: clock.now().toISOString(),
      },
    },
  };
}

function startVisit(
  state: ExamSectionState,
  clock: ExamClock,
  incrementVisits: boolean,
): ExamSectionState {
  if (state.hidden) return { ...state, visitStartedMono: null };
  const id = currentQuestionId(state);
  const item = id === undefined ? undefined : state.items[id];
  if (id === undefined || item == null) {
    // G9: empty question list — no visit to start; keep the clock unarmed.
    return { ...state, visitStartedMono: null };
  }
  return {
    ...state,
    visitStartedMono: clock.monotonic(),
    items: incrementVisits
      ? {
          ...state.items,
          [id]: {
            ...item,
            visits: item.visits + 1,
            updated_at: clock.now().toISOString(),
          },
        }
      : state.items,
  };
}

function buildItems(
  questionIds: readonly string[],
  attempt: ExamSectionAttempt,
  existing: readonly ExamRunItem[] | undefined,
  clock: ExamClock,
): Record<string, ExamRunItem> {
  const byId = new Map((existing ?? []).map((item) => [item.question_id, item]));
  const stamp = clock.now().toISOString();
  const items: Record<string, ExamRunItem> = {};
  for (const [ordinal, id] of questionIds.entries()) {
    items[id] = byId.get(id) ?? {
      run_id: attempt.run_id,
      section_code: attempt.section_code,
      question_id: id,
      ordinal,
      chosen_letter: null,
      correct: null,
      dwell_ms: 0,
      visits: 0,
      answer_changes: 0,
      first_answered_at: null,
      dwell_at_first_answer_ms: null,
      flagged_in_section: false,
      bookmarked: false,
      updated_at: stamp,
    };
  }
  return items;
}

function remainingFrom(deadlineAt: string | null, clock: ExamClock): number | null {
  if (deadlineAt == null) return null;
  return Math.max(0, Date.parse(deadlineAt) - clock.now().getTime());
}

function currentVisitDelta(state: ExamSectionState, clock: ExamClock): number {
  if (state.visitStartedMono == null || state.hidden) return 0;
  return Math.max(0, clock.monotonic() - state.visitStartedMono);
}

function currentQuestionId(state: ExamSectionState): string | undefined {
  return state.questionIds[state.currentIndex];
}

function isWritable(state: ExamSectionState): boolean {
  return state.phase === "in_section" && state.finishStatus == null;
}

function unansweredCount(state: ExamSectionState): number {
  return state.questionIds.filter((id) => state.items[id]?.chosen_letter == null)
    .length;
}
