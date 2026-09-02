/**
 * Exam write buffer — R2 full ladder (W2-4 / FR-5, FR-36).
 *
 * Debounced item upserts, localStorage mirror, pagehide/sendBeacon,
 * backoff retry, and a finalize gate that stays closed while anything
 * is unflushed. Queued rows merge via mergeExamDwell (FR-39 client).
 * Does not grade.
 */

import type { ExamRunRepo } from "@/lib/ports/engine/exam_run_repo";
import { ExamRunItem, type ExamSectionCode } from "@/lib/wire/exam_entities";
import type { ExamClock } from "./exam_clock";
import { mergeExamDwell } from "./exam_dwell_merge";

export const FLUSH_DEBOUNCE_MS = 300;
export const FLUSH_BACKOFF_MS = [1000, 2000, 4000] as const;

export type ExamWriteFlush = ExamRunRepo["upsertItems"];
export type ExamWriteBeacon = (items: readonly ExamRunItem[]) => boolean;
export type ExamWriteStorage = Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;
export type ExamWriteScheduler = {
  schedule: (fn: () => void, delayMs: number) => number;
  cancel: (id: number) => void;
};

export type FinalizeGate =
  | { allowed: true }
  | { allowed: false; reason: "unflushed" };

export type ExamWriteBuffer = {
  enqueue(item: ExamRunItem): void;
  flushNow(): Promise<boolean>;
  onPageHide(): void;
  onVisibilityHidden(): void;
  hasUnflushed(): boolean;
  notSaved(): boolean;
  canFinalize(): boolean;
  gateFinalize(): FinalizeGate;
  peek(): readonly ExamRunItem[];
  dispose(): void;
};

export function examWriteBufferStorageKey(args: {
  learnerId: string;
  runId: string;
  sectionCode: ExamSectionCode;
}): string {
  return `exam-write-buffer:${args.learnerId}:${args.runId}:${args.sectionCode}`;
}

function defaultScheduler(): ExamWriteScheduler {
  const handles = new Map<number, ReturnType<typeof setTimeout>>();
  let nextId = 1;
  return {
    schedule(fn, delayMs) {
      const id = nextId++;
      handles.set(id, globalThis.setTimeout(fn, delayMs));
      return id;
    },
    cancel(id) {
      const handle = handles.get(id);
      if (handle !== undefined) {
        globalThis.clearTimeout(handle);
        handles.delete(id);
      }
    },
  };
}

type StoredEnvelope = {
  learnerId: string;
  runId: string;
  sectionCode: ExamSectionCode;
  mirrored_at: string;
  items: ExamRunItem[];
};

export function createExamWriteBuffer(deps: {
  clock: ExamClock;
  learnerId: string;
  runId: string;
  sectionCode: ExamSectionCode;
  flush: ExamWriteFlush;
  storage: ExamWriteStorage;
  sendBeacon: ExamWriteBeacon;
  scheduler?: ExamWriteScheduler;
  debounceMs?: number;
  backoffMs?: readonly number[];
}): ExamWriteBuffer {
  const scheduler = deps.scheduler ?? defaultScheduler();
  const debounceMs = deps.debounceMs ?? FLUSH_DEBOUNCE_MS;
  const backoffMs = deps.backoffMs ?? FLUSH_BACKOFF_MS;
  const pending = new Map<string, ExamRunItem>();
  const key = examWriteBufferStorageKey(deps);
  let timer: number | null = null;
  let failCount = 0;
  let notSavedFlag = false;
  let inFlight: Promise<void> | null = null;

  loadFromStorage();
  if (pending.size > 0) {
    armDebounce();
  }

  function snapshot(): ExamRunItem[] {
    return [...pending.values()];
  }

  function loadFromStorage(): void {
    let raw: string | null;
    try {
      raw = deps.storage.getItem(key);
    } catch {
      // G9: localStorage read failed (private mode / SecurityError).
      return;
    }
    if (raw == null) return;
    const items = parseEnvelope(raw, deps);
    if (items === null) {
      try {
        deps.storage.removeItem(key);
      } catch {
        // G9: cannot clear a corrupt key (quota / SecurityError).
      }
      return;
    }
    for (const row of items) {
      pending.set(row.question_id, row);
    }
  }

  function persist(): void {
    if (pending.size === 0) {
      try {
        deps.storage.removeItem(key);
      } catch {
        // G9: localStorage remove failed (private mode). Memory is empty.
      }
      return;
    }
    const envelope: StoredEnvelope = {
      learnerId: deps.learnerId,
      runId: deps.runId,
      sectionCode: deps.sectionCode,
      mirrored_at: deps.clock.now().toISOString(),
      items: snapshot(),
    };
    try {
      deps.storage.setItem(key, JSON.stringify(envelope));
    } catch {
      // G9: localStorage write failed (quota / private mode). Keep the
      // in-memory queue; a reload may lose the debounce window (FR-21).
    }
  }

  function cancelTimer(): void {
    if (timer !== null) {
      scheduler.cancel(timer);
      timer = null;
    }
  }

  function armDebounce(): void {
    cancelTimer();
    timer = scheduler.schedule(() => {
      timer = null;
      void runFlush();
    }, debounceMs);
  }

  function armBackoff(): void {
    cancelTimer();
    const idx = Math.min(Math.max(failCount - 1, 0), backoffMs.length - 1);
    const delay = backoffMs[idx];
    if (delay === undefined) {
      throw new Error("exam write-buffer backoff table is empty");
    }
    timer = scheduler.schedule(() => {
      timer = null;
      void runFlush();
    }, delay);
  }

  async function doFlush(): Promise<void> {
    if (pending.size === 0) return;
    const items = snapshot();
    try {
      await deps.flush({ learnerId: deps.learnerId, items });
      for (const row of items) {
        const current = pending.get(row.question_id);
        if (
          current !== undefined &&
          current.updated_at === row.updated_at &&
          current.dwell_ms === row.dwell_ms
        ) {
          pending.delete(row.question_id);
        }
      }
      failCount = 0;
      notSavedFlag = false;
      persist();
    } catch {
      // G9: BFF upsert failed (offline / 5xx / network). Keep the queue,
      // retry with backoff, never report a silent success (FR-5).
      failCount += 1;
      armBackoff();
    }
  }

  async function runFlush(): Promise<void> {
    if (inFlight !== null) {
      await inFlight;
      return;
    }
    if (pending.size === 0) return;
    inFlight = doFlush();
    try {
      await inFlight;
    } finally {
      inFlight = null;
    }
  }

  function beaconFlush(): void {
    if (pending.size === 0) return;
    try {
      deps.sendBeacon(snapshot());
    } catch {
      // G9: sendBeacon missing or threw. Keep queue + localStorage so
      // the next load can restore (FR-36). Do not mark flushed.
    }
  }

  return {
    enqueue(next: ExamRunItem) {
      const existing = pending.get(next.question_id);
      pending.set(
        next.question_id,
        existing === undefined ? next : mergeExamDwell(existing, next),
      );
      persist();
      armDebounce();
    },
    async flushNow() {
      cancelTimer();
      await runFlush();
      if (pending.size > 0) {
        notSavedFlag = true;
        return false;
      }
      return true;
    },
    onPageHide: beaconFlush,
    onVisibilityHidden: beaconFlush,
    hasUnflushed: () => pending.size > 0,
    notSaved: () => notSavedFlag,
    canFinalize: () => pending.size === 0,
    gateFinalize: () =>
      pending.size === 0
        ? { allowed: true }
        : { allowed: false, reason: "unflushed" },
    peek: () => snapshot(),
    dispose() {
      cancelTimer();
    },
  };
}

function parseEnvelope(
  raw: string,
  expected: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
  },
): ExamRunItem[] | null {
  try {
    const data: unknown = JSON.parse(raw);
    if (data === null || typeof data !== "object") return null;
    const rec = data as Record<string, unknown>;
    if (
      rec.learnerId !== expected.learnerId ||
      rec.runId !== expected.runId ||
      rec.sectionCode !== expected.sectionCode ||
      !Array.isArray(rec.items)
    ) {
      return null;
    }
    const items: ExamRunItem[] = [];
    for (const row of rec.items) {
      const parsed = ExamRunItem.safeParse(row);
      if (!parsed.success) return null;
      items.push(parsed.data);
    }
    return items;
  } catch {
    // G9: corrupt JSON — empty buffer, never invent items (AP-6).
    return null;
  }
}
