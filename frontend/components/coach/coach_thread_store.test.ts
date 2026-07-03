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
