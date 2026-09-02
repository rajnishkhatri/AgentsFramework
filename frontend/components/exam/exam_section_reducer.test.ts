/**
 * W2-1 — exam section reducer (FR-1, FR-13–24).
 * Deadline→expired + writes refused; navigator states; dwell pause/sum;
 * first-answer fields immutable. Injected clock (B0-6).
 */

import { describe, expect, it } from "vitest";
import type { ExamClock } from "./exam_clock";
import {
  FIVE_MIN_MS,
  createExamSectionState,
  navigatorCells,
  reduceExamSection,
  type ExamSectionState,
} from "./exam_section_reducer";
import type { ExamRunItem, ExamSectionAttempt } from "@/lib/wire/exam_entities";

function itemOf(state: ExamSectionState, id: string): ExamRunItem {
  const item = state.items[id];
  if (item === undefined) {
    throw new Error(`missing item ${id}`);
  }
  return item;
}

const QUESTION_IDS = ["q-1", "q-2", "q-3"] as const;
const SECTION_MS = 18 * 60_000;

function fakeClock(startIso = "2026-09-02T12:00:00.000Z") {
  let wall = Date.parse(startIso);
  let mono = 10_000;
  return {
    clock: {
      now: () => new Date(wall),
      monotonic: () => mono,
    } satisfies ExamClock,
    advance(ms: number) {
      wall += ms;
      mono += ms;
    },
  };
}

function attempt(over: Partial<ExamSectionAttempt> = {}): ExamSectionAttempt {
  return {
    run_id: "run-1",
    section_code: "english",
    status: "not_started",
    started_at: null,
    finished_at: null,
    deadline_at: null,
    raw_correct: null,
    raw_scored_total: null,
    scale_score: null,
    time_remaining_ms_at_submit: null,
    ...over,
  };
}

function fresh(clock = fakeClock()) {
  const state = createExamSectionState({
    questionIds: QUESTION_IDS,
    attempt: attempt(),
    clock: clock.clock,
  });
  return { state, clock };
}

function beginAt(clock: ReturnType<typeof fakeClock>) {
  const startedAt = clock.clock.now().toISOString();
  const deadlineAt = new Date(
    clock.clock.now().getTime() + SECTION_MS,
  ).toISOString();
  return { type: "begin" as const, startedAt, deadlineAt };
}

function inSection() {
  const { state, clock } = fresh();
  return {
    state: reduceExamSection(state, beginAt(clock), clock.clock),
    clock,
  };
}

describe("FR-13 — directions until explicit Begin", () => {
  it("opens a not-started section on directions and does not start the clock", () => {
    const { state } = fresh();
    expect(state.phase).toBe("directions");
    expect(state.startedAt).toBeNull();
    expect(state.deadlineAt).toBeNull();
    expect(state.remainingMs).toBeNull();
    expect(itemOf(state, "q-1").visits).toBe(0);
  });

  it("Begin moves to in_section and records the server deadline", () => {
    const { state, clock } = fresh();
    const action = beginAt(clock);
    const next = reduceExamSection(state, action, clock.clock);
    expect(next.phase).toBe("in_section");
    expect(next.startedAt).toBe(action.startedAt);
    expect(next.deadlineAt).toBe(action.deadlineAt);
    expect(next.remainingMs).toBe(SECTION_MS);
    expect(next.currentIndex).toBe(0);
    expect(itemOf(next, "q-1").visits).toBe(1);
  });
});

describe("FR-1 / FR-16 — deadline → expired, writes refused", () => {
  it("deadline passed on load ⇒ expired, writes refused", () => {
    const clock = fakeClock("2026-09-02T12:20:00.000Z");
    const state = createExamSectionState({
      questionIds: QUESTION_IDS,
      attempt: attempt({
        status: "in_progress",
        started_at: "2026-09-02T12:00:00.000Z",
        deadline_at: "2026-09-02T12:18:00.000Z",
      }),
      clock: clock.clock,
    });
    expect(state.phase).toBe("finished");
    expect(state.finishStatus).toBe("expired");
    const answered = reduceExamSection(
      state,
      { type: "answer", letter: "A" },
      clock.clock,
    );
    expect(answered).toBe(state);
    expect(itemOf(answered, "q-1").chosen_letter).toBeNull();
  });

  it("tick at zero auto-submits expired and refuses further writes", () => {
    const { state, clock } = inSection();
    clock.advance(SECTION_MS);
    const expired = reduceExamSection(state, { type: "tick" }, clock.clock);
    expect(expired.phase).toBe("finished");
    expect(expired.finishStatus).toBe("expired");
    expect(expired.remainingMs).toBe(0);
    const flagged = reduceExamSection(expired, { type: "flag" }, clock.clock);
    expect(itemOf(flagged, "q-1").flagged_in_section).toBe(false);
    expect(flagged).toBe(expired);
  });
});

describe("FR-14 / FR-15 — countdown and 5-minute warning", () => {
  it("remainingMs is deadline_at − now (wall-clock)", () => {
    const { state, clock } = inSection();
    clock.advance(3 * 60_000);
    const ticked = reduceExamSection(state, { type: "tick" }, clock.clock);
    expect(ticked.remainingMs).toBe(SECTION_MS - 3 * 60_000);
    expect(ticked.fiveMinWarning).toBe(false);
  });

  it("shows the 5-minute warning once when remaining ≤ 5 min", () => {
    const { state, clock } = inSection();
    clock.advance(SECTION_MS - FIVE_MIN_MS);
    const warned = reduceExamSection(state, { type: "tick" }, clock.clock);
    expect(warned.fiveMinWarning).toBe(true);
    expect(warned.remainingMs).toBe(FIVE_MIN_MS);
    clock.advance(30_000);
    const still = reduceExamSection(warned, { type: "tick" }, clock.clock);
    expect(still.fiveMinWarning).toBe(true);
  });
});

describe("FR-17 / FR-18 — nav, answer, clear; submit-with-blanks confirms", () => {
  it("navigates by id / next / prev, answers, changes, and clears", () => {
    const { state, clock } = inSection();
    const answered = reduceExamSection(
      state,
      { type: "answer", letter: "B" },
      clock.clock,
    );
    expect(itemOf(answered, "q-1").chosen_letter).toBe("B");
    const jumped = reduceExamSection(
      answered,
      { type: "navigate", questionId: "q-3" },
      clock.clock,
    );
    expect(jumped.currentIndex).toBe(2);
    const prev = reduceExamSection(jumped, { type: "navigate_prev" }, clock.clock);
    expect(prev.currentIndex).toBe(1);
    const next = reduceExamSection(prev, { type: "navigate_next" }, clock.clock);
    expect(next.currentIndex).toBe(2);
    const clearedHome = reduceExamSection(
      next,
      { type: "navigate", questionId: "q-1" },
      clock.clock,
    );
    const cleared = reduceExamSection(clearedHome, { type: "clear" }, clock.clock);
    expect(itemOf(cleared, "q-1").chosen_letter).toBeNull();
  });

  it("submit with blanks requires confirmation; confirm finishes submitted", () => {
    const { state, clock } = inSection();
    const withOne = reduceExamSection(
      state,
      { type: "answer", letter: "A" },
      clock.clock,
    );
    const warned = reduceExamSection(withOne, { type: "submit" }, clock.clock);
    expect(warned.phase).toBe("in_section");
    expect(warned.pendingBlankConfirm).toBe(2);
    const cancelled = reduceExamSection(
      warned,
      { type: "cancel_submit" },
      clock.clock,
    );
    expect(cancelled.pendingBlankConfirm).toBeNull();
    expect(cancelled.phase).toBe("in_section");
    const again = reduceExamSection(cancelled, { type: "submit" }, clock.clock);
    const done = reduceExamSection(again, { type: "confirm_submit" }, clock.clock);
    expect(done.phase).toBe("finished");
    expect(done.finishStatus).toBe("submitted");
    expect(itemOf(done, "q-2").chosen_letter).toBeNull();
    expect(itemOf(done, "q-3").chosen_letter).toBeNull();
  });
});

describe("FR-19 / FR-21 / FR-22 — dwell pause, sum, visits", () => {
  it("accumulates dwell, pauses on visibilitychange, sums visits", () => {
    const { state, clock } = inSection();
    clock.advance(400);
    const hidden = reduceExamSection(
      state,
      { type: "visibility", hidden: true },
      clock.clock,
    );
    expect(itemOf(hidden, "q-1").dwell_ms).toBe(400);
    clock.advance(5_000);
    const stillHidden = reduceExamSection(hidden, { type: "tick" }, clock.clock);
    expect(itemOf(stillHidden, "q-1").dwell_ms).toBe(400);
    const shown = reduceExamSection(
      stillHidden,
      { type: "visibility", hidden: false },
      clock.clock,
    );
    clock.advance(250);
    const away = reduceExamSection(
      shown,
      { type: "navigate", questionId: "q-2" },
      clock.clock,
    );
    expect(itemOf(away, "q-1").dwell_ms).toBe(650);
    expect(itemOf(away, "q-1").visits).toBe(1);
    expect(itemOf(away, "q-2").visits).toBe(1);
    clock.advance(100);
    const back = reduceExamSection(
      away,
      { type: "navigate", questionId: "q-1" },
      clock.clock,
    );
    expect(itemOf(back, "q-1").visits).toBe(2);
    clock.advance(50);
    const flushed = reduceExamSection(
      back,
      { type: "navigate", questionId: "q-2" },
      clock.clock,
    );
    expect(itemOf(flushed, "q-1").dwell_ms).toBe(700);
  });
});

describe("FR-20 — first-answer fields immutable", () => {
  it("records first_answered_at + dwell_at_first_answer_ms; later changes increment", () => {
    const { state, clock } = inSection();
    clock.advance(120);
    const first = reduceExamSection(
      state,
      { type: "answer", letter: "A" },
      clock.clock,
    );
    expect(itemOf(first, "q-1").first_answered_at).toBe(
      "2026-09-02T12:00:00.120Z",
    );
    expect(itemOf(first, "q-1").dwell_at_first_answer_ms).toBe(120);
    expect(itemOf(first, "q-1").answer_changes).toBe(0);
    clock.advance(80);
    const changed = reduceExamSection(
      first,
      { type: "answer", letter: "C" },
      clock.clock,
    );
    expect(itemOf(changed, "q-1").chosen_letter).toBe("C");
    expect(itemOf(changed, "q-1").answer_changes).toBe(1);
    expect(itemOf(changed, "q-1").first_answered_at).toBe(
      "2026-09-02T12:00:00.120Z",
    );
    expect(itemOf(changed, "q-1").dwell_at_first_answer_ms).toBe(120);
  });
});

describe("FR-23 / FR-24 — flag + navigator; flags freeze on finish", () => {
  it("toggles mark-for-review and exposes distinct navigator states", () => {
    const { state, clock } = inSection();
    const answered = reduceExamSection(
      state,
      { type: "answer", letter: "D" },
      clock.clock,
    );
    const flagged = reduceExamSection(answered, { type: "flag" }, clock.clock);
    expect(itemOf(flagged, "q-1").flagged_in_section).toBe(true);
    const cells = navigatorCells(flagged);
    expect(cells).toEqual([
      {
        questionId: "q-1",
        current: true,
        answered: true,
        flagged: true,
      },
      {
        questionId: "q-2",
        current: false,
        answered: false,
        flagged: false,
      },
      {
        questionId: "q-3",
        current: false,
        answered: false,
        flagged: false,
      },
    ]);
  });

  it("keeps flagged_in_section immutable after submit", () => {
    const { state, clock } = inSection();
    const a = reduceExamSection(state, { type: "answer", letter: "A" }, clock.clock);
    const b = reduceExamSection(
      a,
      { type: "navigate", questionId: "q-2" },
      clock.clock,
    );
    const c = reduceExamSection(b, { type: "answer", letter: "B" }, clock.clock);
    const d = reduceExamSection(
      c,
      { type: "navigate", questionId: "q-3" },
      clock.clock,
    );
    const e = reduceExamSection(d, { type: "answer", letter: "C" }, clock.clock);
    const f = reduceExamSection(e, { type: "flag" }, clock.clock);
    const done = reduceExamSection(f, { type: "submit" }, clock.clock);
    expect(done.phase).toBe("finished");
    expect(done.finishStatus).toBe("submitted");
    expect(itemOf(done, "q-3").flagged_in_section).toBe(true);
    const toggled = reduceExamSection(done, { type: "flag" }, clock.clock);
    expect(itemOf(toggled, "q-3").flagged_in_section).toBe(true);
    expect(toggled).toBe(done);
  });
});
