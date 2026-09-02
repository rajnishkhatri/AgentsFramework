/**
 * W2-4 — exam write buffer (FR-5, FR-36).
 * R2 full ladder: debounce + localStorage mirror + pagehide/sendBeacon +
 * backoff retry + block-finalize-while-unflushed. Client side of
 * mergeExamDwell. Does not grade.
 */

import { describe, expect, it } from "vitest";
import type { ExamClock } from "./exam_clock";
import type { ExamRunItem } from "@/lib/wire/exam_entities";
import {
  FLUSH_BACKOFF_MS,
  FLUSH_DEBOUNCE_MS,
  createExamWriteBuffer,
  examWriteBufferStorageKey,
  type ExamWriteBeacon,
  type ExamWriteFlush,
  type ExamWriteScheduler,
  type ExamWriteStorage,
} from "./exam_write_buffer";

function item(over: Partial<ExamRunItem> = {}): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: "q-1",
    ordinal: 1,
    chosen_letter: "A",
    correct: null,
    dwell_ms: 100,
    visits: 1,
    answer_changes: 0,
    first_answered_at: "2026-09-02T12:00:01.000Z",
    dwell_at_first_answer_ms: 80,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: "2026-09-02T12:00:02.000Z",
    ...over,
  };
}

function fakeClock(startIso = "2026-09-02T12:00:00.000Z"): ExamClock {
  let wall = Date.parse(startIso);
  let mono = 10_000;
  return {
    now: () => new Date(wall),
    monotonic: () => mono,
  };
}

function memoryStorage(): ExamWriteStorage & { snapshot(): Map<string, string> } {
  const map = new Map<string, string>();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => {
      map.set(key, value);
    },
    removeItem: (key) => {
      map.delete(key);
    },
    snapshot: () => new Map(map),
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
    delays(): number[] {
      return [...tasks.values()].map((t) => t.ms);
    },
    runNext() {
      const id = tasks.keys().next().value;
      if (id === undefined) return;
      const task = tasks.get(id);
      tasks.delete(id);
      task?.fn();
    },
  };
}

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

function harness(over: {
  flush?: ExamWriteFlush;
  sendBeacon?: ExamWriteBeacon;
  storage?: ExamWriteStorage;
} = {}) {
  const calls: ExamRunItem[][] = [];
  let rejectNext = 0;
  const flush: ExamWriteFlush =
    over.flush ??
    (async ({ items }) => {
      calls.push(items.map((row) => ({ ...row })));
      if (rejectNext > 0) {
        rejectNext -= 1;
        throw new Error("offline");
      }
    });
  const beacons: ExamRunItem[][] = [];
  const sendBeacon: ExamWriteBeacon =
    over.sendBeacon ??
    ((items) => {
      beacons.push(items.map((row) => ({ ...row })));
      return true;
    });
  const storage = over.storage ?? memoryStorage();
  const sched = manualScheduler();
  const buffer = createExamWriteBuffer({
    clock: fakeClock(),
    learnerId: "learner-1",
    runId: "run-1",
    sectionCode: "english",
    flush,
    storage,
    sendBeacon,
    scheduler: sched.scheduler,
  });
  return {
    buffer,
    calls,
    beacons,
    storage,
    sched,
    offline(n = 1) {
      rejectNext = n;
    },
  };
}

describe("exam_write_buffer (FR-5 / FR-36)", () => {
  it("offline-flush: buffers while unreachable, then flushes on reconnect", async () => {
    const h = harness();
    h.offline(1);
    h.buffer.enqueue(item());
    expect(h.buffer.hasUnflushed()).toBe(true);
    expect(h.calls).toHaveLength(0);
    expect(h.sched.delays()).toEqual([FLUSH_DEBOUNCE_MS]);

    h.sched.runNext();
    await settle();
    expect(h.calls).toHaveLength(1);
    expect(h.buffer.hasUnflushed()).toBe(true);
    expect(h.sched.delays()).toEqual([FLUSH_BACKOFF_MS[0]]);

    h.sched.runNext();
    await settle();
    expect(h.calls).toHaveLength(2);
    expect(h.calls[1]?.[0]?.question_id).toBe("q-1");
    expect(h.buffer.hasUnflushed()).toBe(false);
    expect(h.buffer.notSaved()).toBe(false);
  });

  it("failed-flush→not-saved: submit flush that still fails never looks saved", async () => {
    const h = harness();
    h.offline(1);
    h.buffer.enqueue(item({ question_id: "q-2", ordinal: 2 }));
    const ok = await h.buffer.flushNow();
    expect(ok).toBe(false);
    expect(h.buffer.notSaved()).toBe(true);
    expect(h.buffer.hasUnflushed()).toBe(true);
    expect(h.buffer.canFinalize()).toBe(false);
    expect(h.buffer.gateFinalize()).toEqual({
      allowed: false,
      reason: "unflushed",
    });
  });

  it("localStorage-restore: a new buffer reloads the mirrored unflushed items", () => {
    const storage = memoryStorage();
    const first = harness({ storage });
    first.buffer.enqueue(
      item({
        question_id: "q-3",
        ordinal: 3,
        chosen_letter: "C",
        dwell_ms: 400,
      }),
    );
    const key = examWriteBufferStorageKey({
      learnerId: "learner-1",
      runId: "run-1",
      sectionCode: "english",
    });
    expect(storage.getItem(key)).not.toBeNull();

    const second = harness({ storage });
    const restored = second.buffer.peek();
    expect(restored).toHaveLength(1);
    expect(restored[0]?.question_id).toBe("q-3");
    expect(restored[0]?.chosen_letter).toBe("C");
    expect(restored[0]?.dwell_ms).toBe(400);
    expect(second.buffer.hasUnflushed()).toBe(true);
    expect(second.buffer.canFinalize()).toBe(false);
  });

  it("pagehide-beacon: pagehide and visibility=hidden flush via sendBeacon", () => {
    const h = harness();
    h.buffer.enqueue(item({ question_id: "q-4", ordinal: 4, chosen_letter: "D" }));
    expect(h.beacons).toHaveLength(0);
    h.buffer.onPageHide();
    expect(h.beacons).toHaveLength(1);
    expect(h.beacons[0]?.[0]?.question_id).toBe("q-4");
    h.buffer.onVisibilityHidden();
    expect(h.beacons).toHaveLength(2);
    expect(h.buffer.hasUnflushed()).toBe(true);
  });

  it("block scored finalize while unflushed (FR-36)", async () => {
    const h = harness();
    h.buffer.enqueue(item());
    expect(h.buffer.canFinalize()).toBe(false);
    expect(h.buffer.gateFinalize()).toEqual({
      allowed: false,
      reason: "unflushed",
    });

    const ok = await h.buffer.flushNow();
    expect(ok).toBe(true);
    expect(h.buffer.hasUnflushed()).toBe(false);
    expect(h.buffer.canFinalize()).toBe(true);
    expect(h.buffer.gateFinalize()).toEqual({ allowed: true });
    expect(h.storage.getItem(
      examWriteBufferStorageKey({
        learnerId: "learner-1",
        runId: "run-1",
        sectionCode: "english",
      }),
    )).toBeNull();
  });

  it("coalesces same-question writes with mergeExamDwell (R6 client)", async () => {
    const h = harness();
    h.buffer.enqueue(item({ dwell_ms: 100, visits: 1, answer_changes: 0 }));
    h.buffer.enqueue(
      item({
        dwell_ms: 250,
        visits: 3,
        answer_changes: 2,
        chosen_letter: "B",
        first_answered_at: "2026-09-02T12:00:08.000Z",
        dwell_at_first_answer_ms: 400,
        updated_at: "2026-09-02T12:00:09.000Z",
      }),
    );
    const ok = await h.buffer.flushNow();
    expect(ok).toBe(true);
    expect(h.calls).toHaveLength(1);
    const flushed = h.calls[0]?.[0];
    expect(flushed?.dwell_ms).toBe(250);
    expect(flushed?.visits).toBe(3);
    expect(flushed?.answer_changes).toBe(2);
    expect(flushed?.chosen_letter).toBe("B");
    expect(flushed?.first_answered_at).toBe("2026-09-02T12:00:01.000Z");
    expect(flushed?.dwell_at_first_answer_ms).toBe(80);
    expect(flushed?.correct).toBeNull();
  });
});
