/**
 * W2-5 — use_exam_section orchestration (FR-5).
 * Lifecycle + not-saved surfacing against an in-memory ExamRunRepo fake.
 * Reducer owns the local clock; the write buffer owns durability only.
 */

import { describe, expect, it } from "vitest";
import type { ExamClock } from "./exam_clock";
import type { ExamRunRepo } from "@/lib/ports/engine/exam_run_repo";
import { EngineRepoError } from "@/lib/ports/engine/errors";
import type {
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "@/lib/wire/exam_entities";
import type {
  ExamWriteBeacon,
  ExamWriteScheduler,
  ExamWriteStorage,
} from "./exam_write_buffer";
import {
  NOT_SAVED,
  createExamSectionSession,
} from "./use_exam_section";

const QUESTION_ONE = ["q-1"] as const;
const QUESTION_TWO = ["q-1", "q-2"] as const;
const SECTION_MS = 18 * 60_000;
const LEARNER = "learner-1";
const RUN = "run-1";
const SECTION: ExamSectionCode = "english";

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

function memoryStorage(): ExamWriteStorage {
  const map = new Map<string, string>();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => {
      map.set(key, value);
    },
    removeItem: (key) => {
      map.delete(key);
    },
  };
}

function manualScheduler() {
  let nextId = 1;
  const tasks = new Map<number, { fn: () => void; ms: number }>();
  return {
    scheduler: {
      schedule(fn: () => void, ms: number) {
        const id = nextId++;
        tasks.set(id, { fn, ms });
        return id;
      },
      cancel(id: number) {
        tasks.delete(id);
      },
    } satisfies ExamWriteScheduler,
    runNext() {
      const id = tasks.keys().next().value;
      if (id === undefined) return;
      const task = tasks.get(id);
      tasks.delete(id);
      task?.fn();
    },
  };
}

function unused(): never {
  throw new Error("ExamRunRepo method not used by use_exam_section");
}

function attempt(over: Partial<ExamSectionAttempt> = {}): ExamSectionAttempt {
  return {
    run_id: RUN,
    section_code: SECTION,
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

function fakeRepo(clock: ExamClock) {
  const stored = new Map<string, ExamRunItem>();
  const finishCalls: Array<{
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
  }> = [];
  let current = attempt();
  let rejectUpserts = 0;

  const repo: ExamRunRepo = {
    startRun: unused,
    async beginSection({ learnerId, runId, sectionCode }) {
      if (learnerId !== LEARNER) {
        throw new EngineRepoError("wrong learner");
      }
      if (current.status === "in_progress") {
        return current;
      }
      const startedAt = clock.now().toISOString();
      current = attempt({
        run_id: runId,
        section_code: sectionCode,
        status: "in_progress",
        started_at: startedAt,
        deadline_at: new Date(clock.now().getTime() + SECTION_MS).toISOString(),
      });
      return current;
    },
    upsertItem: unused,
    async upsertItems({ items }) {
      if (rejectUpserts > 0) {
        rejectUpserts -= 1;
        throw new EngineRepoError("offline");
      }
      for (const row of items) {
        stored.set(row.question_id, { ...row });
      }
    },
    async finishSection(args) {
      finishCalls.push({ ...args });
      current = {
        ...current,
        status: "submitted",
        finished_at: clock.now().toISOString(),
      };
      return current;
    },
    getRun: unused,
    getRunDetail: unused,
    listRunsByLearner: unused,
    listRunEntries: unused,
    async listItems() {
      return [...stored.values()];
    },
    listItemsByLearner: unused,
    setBookmark: unused,
    listClientForms: unused,
    getClientForm: unused,
  };

  return {
    repo,
    finishCalls,
    stored,
    offline(n = 1) {
      rejectUpserts = n;
    },
  };
}

function harness(over: { questionIds?: readonly string[] } = {}) {
  const clock = fakeClock();
  const ports = fakeRepo(clock.clock);
  const beacons: ExamRunItem[][] = [];
  const sendBeacon: ExamWriteBeacon = (items) => {
    beacons.push(items.map((row) => ({ ...row })));
    return true;
  };
  const sched = manualScheduler();
  const session = createExamSectionSession({
    clock: clock.clock,
    repo: ports.repo,
    learnerId: LEARNER,
    runId: RUN,
    sectionCode: SECTION,
    questionIds: over.questionIds ?? QUESTION_ONE,
    attempt: attempt(),
    storage: memoryStorage(),
    sendBeacon,
    scheduler: sched.scheduler,
  });
  return { session, clock, ports, beacons, sched };
}

describe("FR-5 — use_exam_section lifecycle + not-saved", () => {
  it("offline buffer flushes; failed flush ⇒ not-saved state", async () => {
    const { session, ports } = harness();
    await session.begin();
    expect(session.state().phase).toBe("in_section");

    ports.offline(2);
    await session.dispatch({ type: "answer", letter: "A" });
    await session.dispatch({ type: "submit" });

    expect(session.saveNotice()).toBe(NOT_SAVED);
    expect(session.saveNotice()).toBe("not saved");
    expect(session.notSaved()).toBe(true);
    expect(ports.finishCalls).toHaveLength(0);
    expect(session.state().phase).toBe("in_section");
    expect(session.state().items["q-1"]?.chosen_letter).toBe("A");
  });

  it("keeps the section on the local clock while the BFF is unreachable", async () => {
    const { session, clock, ports } = harness();
    await session.begin();
    const remainingAtBegin = session.state().remainingMs;
    expect(remainingAtBegin).toBe(SECTION_MS);

    ports.offline(8);
    clock.advance(60_000);
    await session.dispatch({ type: "tick" });

    expect(session.state().phase).toBe("in_section");
    expect(session.state().remainingMs).toBe(SECTION_MS - 60_000);
    expect(ports.finishCalls).toHaveLength(0);
  });

  it("flushes on reconnect and then allows finishSection", async () => {
    const { session, ports } = harness();
    await session.begin();
    ports.offline(1);
    await session.dispatch({ type: "answer", letter: "A" });
    await session.dispatch({ type: "submit" });
    expect(ports.finishCalls).toHaveLength(0);
    expect(session.saveNotice()).toBe(NOT_SAVED);

    await session.reconnect();
    expect(session.notSaved()).toBe(false);
    expect(ports.stored.get("q-1")?.chosen_letter).toBe("A");

    await session.dispatch({ type: "submit" });
    expect(ports.finishCalls).toEqual([
      { learnerId: LEARNER, runId: RUN, sectionCode: SECTION },
    ]);
    expect(session.state().phase).toBe("finished");
    expect(session.state().finishStatus).toBe("submitted");
    expect(session.saveNotice()).toBeNull();
  });

  it("flushNow on navigate; unflushed nav surfaces not saved and does not finish", async () => {
    const { session, ports } = harness({ questionIds: QUESTION_TWO });
    await session.begin();
    await session.dispatch({ type: "answer", letter: "A" });
    expect(ports.stored.get("q-1")?.chosen_letter).toBeUndefined();

    await session.dispatch({ type: "navigate_next" });
    expect(ports.stored.get("q-1")?.chosen_letter).toBe("A");
    expect(session.state().currentIndex).toBe(1);
    expect(session.saveNotice()).toBeNull();
    expect(ports.finishCalls).toHaveLength(0);
  });

  it("pagehide → onPageHide and visibilitychange=hidden → onVisibilityHidden", async () => {
    const { session, beacons, ports } = harness();
    await session.begin();
    ports.offline(4);
    await session.dispatch({ type: "answer", letter: "B" });
    expect(beacons).toHaveLength(0);

    const host = new EventTarget();
    let hidden = false;
    const detach = session.attachLifecycle(host, { hidden: () => hidden });

    host.dispatchEvent(new Event("pagehide"));
    expect(beacons.length).toBeGreaterThanOrEqual(1);

    hidden = true;
    host.dispatchEvent(new Event("visibilitychange"));
    expect(beacons.length).toBeGreaterThanOrEqual(2);

    expect(ports.finishCalls).toHaveLength(0);
    expect(session.state().phase).toBe("in_section");
    detach();
  });

  it("online event reconnects and flushes the buffer", async () => {
    const { session, ports } = harness();
    await session.begin();
    ports.offline(1);
    await session.dispatch({ type: "answer", letter: "C" });
    await session.dispatch({ type: "submit" });
    expect(ports.stored.size).toBe(0);

    const host = new EventTarget();
    session.attachLifecycle(host, { hidden: () => false });
    host.dispatchEvent(new Event("online"));
    await session.pending();

    expect(ports.stored.get("q-1")?.chosen_letter).toBe("C");
    expect(session.notSaved()).toBe(false);
  });
});
