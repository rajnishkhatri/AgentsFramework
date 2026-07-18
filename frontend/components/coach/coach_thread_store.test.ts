/**
 * Phase 4.3 — coach_thread_store (FR-J3/J4, L1 deterministic).
 *
 * The iPad split renders the SAME coach thread in two places at once (the quiz
 * page's CoachPanel and the full Coach screen), and the thread must survive the
 * client-side route change between them. React state in either mount dies with
 * it, so the thread lives in this module-level store (the `quiz_session_store`
 * precedent — plan §Architecture/OD-3) and every consumer is a subscriber.
 *
 * Failure path first (TAP-4): an event for an unknown turn id must be a no-op
 * (a late stream event after reset must not resurrect a dead turn).
 */

import { afterEach, describe, expect, it } from "vitest";
import {
  applyCoachEvent,
  beginCoachTurn,
  coachThreadSnapshot,
  endCoachTurn,
  resetCoachThread,
  setCoachChoiceLetter,
  setCoachPin,
  subscribeCoachThread,
} from "./coach_thread_store";

afterEach(() => {
  resetCoachThread();
});

describe("coach_thread_store — failure paths first", () => {
  it("an event for an unknown turn id is a no-op (late event after reset)", () => {
    const { turnId } = beginCoachTurn("why is B right?");
    resetCoachThread();
    applyCoachEvent(turnId, {
      type: "chat_message_delta",
      trace_id: "tr-1",
      message_id: "m1",
      delta: "ghost",
    });
    expect(coachThreadSnapshot().turns).toEqual([]);
  });

  it("reset drops the thread id so the next turn mints a fresh one", () => {
    const first = beginCoachTurn("q1");
    resetCoachThread();
    const second = beginCoachTurn("q2");
    expect(second.threadId).not.toBe(first.threadId);
  });
});

describe("coach_thread_store — one shared thread (FR-J3)", () => {
  it("consecutive turns ride the SAME thread id (one thread, not two)", () => {
    const a = beginCoachTurn("panel ask");
    endCoachTurn();
    const b = beginCoachTurn("coach-screen ask");
    expect(b.threadId).toBe(a.threadId);
    expect(coachThreadSnapshot().turns.map((t) => t.user)).toEqual([
      "panel ask",
      "coach-screen ask",
    ]);
  });

  it("folds streamed events into the owning turn's assistant view", () => {
    const { turnId } = beginCoachTurn("ask");
    applyCoachEvent(turnId, {
      type: "run_started",
      trace_id: "tr-9",
      run_id: "r1",
      thread_id: "t",
    });
    applyCoachEvent(turnId, {
      type: "chat_message_delta",
      trace_id: "tr-9",
      message_id: "m1",
      delta: "Look at the clause…",
    });
    const [turn] = coachThreadSnapshot().turns;
    expect(turn!.assistant.status).toBe("streaming");
    expect(
      turn!.assistant.segments.map((s) => (s.kind === "text" ? s.text : "")).join(""),
    ).toContain("Look at the clause");
  });

  it("notifies every subscriber on each mutation; snapshot identity is stable between them", () => {
    let panelSaw = 0;
    let screenSaw = 0;
    const un1 = subscribeCoachThread(() => (panelSaw += 1));
    const un2 = subscribeCoachThread(() => (screenSaw += 1));
    const before = coachThreadSnapshot();
    beginCoachTurn("ask");
    expect(panelSaw).toBe(1);
    expect(screenSaw).toBe(1);
    // A new snapshot object per mutation (useSyncExternalStore change detection)…
    expect(coachThreadSnapshot()).not.toBe(before);
    // …but stable identity while nothing mutates.
    expect(coachThreadSnapshot()).toBe(coachThreadSnapshot());
    un1();
    un2();
    endCoachTurn();
    expect(panelSaw).toBe(1); // unsubscribed — no further notifications
  });

  it("busy tracks the in-flight turn", () => {
    expect(coachThreadSnapshot().busy).toBe(false);
    beginCoachTurn("ask");
    expect(coachThreadSnapshot().busy).toBe(true);
    endCoachTurn();
    expect(coachThreadSnapshot().busy).toBe(false);
  });
});

describe("coach_thread_store — surface pin (BP-2a / C1, C1a)", () => {
  it("cold open has pin null (honest absent)", () => {
    expect(coachThreadSnapshot().pin).toBeNull();
    expect(coachThreadSnapshot().choiceLetter).toBeNull();
  });

  it("setCoachChoiceLetter stores a wrong letter without clearing the thread (ADR-0035)", () => {
    setCoachPin({
      kind: "item",
      questionId: "q1",
      skillId: "s-punc",
      label: "Q1 · Commas",
    });
    beginCoachTurn("why A?");
    endCoachTurn();
    setCoachChoiceLetter("A");
    expect(coachThreadSnapshot().choiceLetter).toBe("A");
    expect(coachThreadSnapshot().turns).toHaveLength(1);
    setCoachPin(null);
    expect(coachThreadSnapshot().choiceLetter).toBeNull();
  });

  it("setCoachPin writes the pin; reset clears pin with the thread", () => {
    setCoachPin({
      kind: "item",
      questionId: "q1",
      skillId: "s-punc",
      label: "Q4 · Commas",
    });
    expect(coachThreadSnapshot().pin).toEqual({
      kind: "item",
      questionId: "q1",
      skillId: "s-punc",
      label: "Q4 · Commas",
    });
    beginCoachTurn("ask");
    resetCoachThread();
    expect(coachThreadSnapshot().pin).toBeNull();
    expect(coachThreadSnapshot().mode).toBe("pre_submit");
    expect(coachThreadSnapshot().turns).toEqual([]);
  });

  it("setCoachPin(null) clears pin without dropping the transcript", () => {
    setCoachPin({
      kind: "item",
      questionId: "q1",
      skillId: "s-punc",
      label: "Q4 · Commas",
    });
    beginCoachTurn("ask");
    endCoachTurn();
    setCoachPin(null);
    expect(coachThreadSnapshot().pin).toBeNull();
    expect(coachThreadSnapshot().mode).toBe("pre_submit");
    expect(coachThreadSnapshot().turns).toHaveLength(1);
  });

  it("stores advisory mode with the pin (Feedback→Coach post_feedback)", () => {
    setCoachPin(
      {
        kind: "item",
        questionId: "q1",
        skillId: "s-punc",
        label: "Q4 · Commas",
      },
      "post_feedback",
    );
    expect(coachThreadSnapshot().mode).toBe("post_feedback");
    setCoachPin(
      {
        kind: "item",
        questionId: "q1",
        skillId: "s-punc",
        label: "Q4 · Commas",
      },
      "pre_submit",
    );
    expect(coachThreadSnapshot().mode).toBe("pre_submit");
  });

  it("notifies subscribers when the pin changes", () => {
    let saw = 0;
    const un = subscribeCoachThread(() => (saw += 1));
    setCoachPin({
      kind: "item",
      questionId: "q2",
      skillId: "s-agr",
      label: "Q2 · Agreement",
    });
    expect(saw).toBe(1);
    un();
  });

  it("questionId change clears transcript + threadId (new item = fresh coach thread)", () => {
    setCoachPin({
      kind: "item",
      questionId: "q2",
      skillId: "s-org",
      label: "Q2 · s-org",
    });
    const { threadId } = beginCoachTurn("Explain the rule simply");
    endCoachTurn();
    expect(coachThreadSnapshot().turns).toHaveLength(1);
    expect(coachThreadSnapshot().threadId).toBe(threadId);

    setCoachPin(
      {
        kind: "item",
        questionId: "q3",
        skillId: "s-gram",
        label: "Q3 · s-gram",
      },
      "post_feedback",
    );
    const snap = coachThreadSnapshot();
    expect(snap.pin?.kind).toBe("item");
    if (snap.pin?.kind === "item") {
      expect(snap.pin.questionId).toBe("q3");
    }
    expect(snap.mode).toBe("post_feedback");
    expect(snap.turns).toEqual([]);
    expect(snap.threadId).toBeNull();
    expect(snap.busy).toBe(false);
  });

  it("same questionId pin update keeps transcript and threadId (FR-J3)", () => {
    setCoachPin({
      kind: "item",
      questionId: "q2",
      skillId: "s-org",
      label: "Q2 · s-org",
    });
    const { threadId } = beginCoachTurn("why B?");
    endCoachTurn();
    setCoachPin(
      {
        kind: "item",
        questionId: "q2",
        skillId: "s-org",
        label: "Q2 · Organization",
      },
      "post_feedback",
    );
    expect(coachThreadSnapshot().threadId).toBe(threadId);
    expect(coachThreadSnapshot().turns).toHaveLength(1);
    expect(coachThreadSnapshot().pin?.label).toBe("Q2 · Organization");
  });

  it("FR-1: lesson pin overwrites a stale item pin", () => {
    setCoachPin({
      kind: "item",
      questionId: "q-stale",
      skillId: "s-gram",
      label: "Q9 · Usage",
    });
    beginCoachTurn("stale ask");
    endCoachTurn();
    setCoachPin(
      { kind: "lesson", skillId: "s-punc", label: "Punctuation" },
      "pre_submit",
    );
    const snap = coachThreadSnapshot();
    expect(snap.pin).toEqual({
      kind: "lesson",
      skillId: "s-punc",
      label: "Punctuation",
    });
    expect(snap.pin).not.toHaveProperty("questionId");
    expect(snap.mode).toBe("pre_submit");
    // Item→lesson is an identity change → fresh thread.
    expect(snap.turns).toEqual([]);
    expect(snap.threadId).toBeNull();
  });

  it("FR-6b: lesson→lesson same skill does not spuriously reset", () => {
    setCoachPin(
      { kind: "lesson", skillId: "s-punc", label: "Punctuation" },
      "pre_submit",
    );
    const { threadId } = beginCoachTurn("help with commas");
    endCoachTurn();
    setCoachPin(
      { kind: "lesson", skillId: "s-punc", label: "Punctuation" },
      "pre_submit",
    );
    expect(coachThreadSnapshot().threadId).toBe(threadId);
    expect(coachThreadSnapshot().turns).toHaveLength(1);
  });
});
