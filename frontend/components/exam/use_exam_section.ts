/**
 * use_exam_section — WT-2 orchestration (W2-5 / FR-5).
 *
 * Wires the pure reducer (local clock) to the write buffer (durability)
 * against an injected ExamRunRepo. Tests use createExamSectionSession plus
 * an in-memory port fake; the React hook is a thin window-lifecycle binding.
 * Does not grade and does not own the FR-29 review VM (S-D2).
 */

"use client"; // B1: pagehide / visibilitychange / online + useSyncExternalStore

import * as React from "react";
import type { ExamRunRepo } from "@/lib/ports/engine/exam_run_repo";
import type { ExamRunItem, ExamSectionAttempt, ExamSectionCode } from "@/lib/wire/exam_entities";
import type { ExamClock } from "./exam_clock";
import {
  createExamSectionState,
  reduceExamSection,
  type ExamSectionAction,
  type ExamSectionState,
} from "./exam_section_reducer";
import {
  createExamWriteBuffer,
  type ExamWriteBeacon,
  type ExamWriteScheduler,
  type ExamWriteStorage,
} from "./exam_write_buffer";

export const NOT_SAVED = "not saved";

export type ExamLifecycleTarget = {
  addEventListener(type: string, listener: EventListener): void;
  removeEventListener(type: string, listener: EventListener): void;
};

export type ExamVisibility = {
  hidden: () => boolean;
};

export type ExamSectionSessionDeps = {
  clock: ExamClock;
  repo: ExamRunRepo;
  learnerId: string;
  runId: string;
  sectionCode: ExamSectionCode;
  questionIds: readonly string[];
  attempt: ExamSectionAttempt;
  items?: readonly ExamRunItem[];
  storage: ExamWriteStorage;
  sendBeacon: ExamWriteBeacon;
  scheduler?: ExamWriteScheduler;
};

export type ExamSectionSnapshot = {
  state: ExamSectionState;
  saveNotice: string | null;
  notSaved: boolean;
};

export type ExamSectionSession = {
  state(): ExamSectionState;
  saveNotice(): string | null;
  notSaved(): boolean;
  snapshot(): ExamSectionSnapshot;
  begin(): Promise<void>;
  dispatch(action: ExamSectionAction): Promise<void>;
  reconnect(): Promise<void>;
  attachLifecycle(
    target: ExamLifecycleTarget,
    visibility?: ExamVisibility,
  ): () => void;
  subscribe(listener: () => void): () => void;
  pending(): Promise<void>;
  dispose(): void;
};

function defaultHidden(): boolean {
  return (
    typeof document !== "undefined" && document.visibilityState === "hidden"
  );
}

function isNavigate(action: ExamSectionAction): boolean {
  return (
    action.type === "navigate" ||
    action.type === "navigate_next" ||
    action.type === "navigate_prev"
  );
}

function isLearnerFinish(action: ExamSectionAction): boolean {
  return action.type === "submit" || action.type === "confirm_submit";
}

export function createExamSectionSession(
  deps: ExamSectionSessionDeps,
): ExamSectionSession {
  const buffer = createExamWriteBuffer({
    clock: deps.clock,
    learnerId: deps.learnerId,
    runId: deps.runId,
    sectionCode: deps.sectionCode,
    flush: (args) => deps.repo.upsertItems(args),
    storage: deps.storage,
    sendBeacon: deps.sendBeacon,
    ...(deps.scheduler === undefined ? {} : { scheduler: deps.scheduler }),
  });

  let state = createExamSectionState({
    questionIds: deps.questionIds,
    attempt: deps.attempt,
    clock: deps.clock,
    ...(deps.items === undefined ? {} : { items: deps.items }),
  });
  let saveNotice: string | null = null;
  let cached: ExamSectionSnapshot = makeSnapshot();
  const listeners = new Set<() => void>();
  let tail: Promise<void> = Promise.resolve();

  function makeSnapshot(): ExamSectionSnapshot {
    return {
      state,
      saveNotice,
      notSaved: saveNotice === NOT_SAVED || buffer.notSaved(),
    };
  }

  function notify(): void {
    cached = makeSnapshot();
    for (const listener of listeners) {
      listener();
    }
  }

  function enqueueDirty(prev: ExamSectionState, next: ExamSectionState): void {
    for (const id of next.questionIds) {
      const before = prev.items[id];
      const after = next.items[id];
      if (after !== undefined && after !== before) {
        buffer.enqueue(after);
      }
    }
  }

  function surfaceNotSaved(): void {
    saveNotice = NOT_SAVED;
    notify();
  }

  async function persistNow(): Promise<boolean> {
    const ok = await buffer.flushNow();
    if (!ok || !buffer.gateFinalize().allowed || buffer.notSaved()) {
      surfaceNotSaved();
      return false;
    }
    saveNotice = null;
    notify();
    return true;
  }

  async function finishOnServer(): Promise<boolean> {
    try {
      await deps.repo.finishSection({
        learnerId: deps.learnerId,
        runId: deps.runId,
        sectionCode: deps.sectionCode,
      });
      return true;
    } catch {
      // G9: finishSection failed (offline / 5xx). Items may already be
      // durable; never report scored-complete (FR-5 / FR-36).
      surfaceNotSaved();
      return false;
    }
  }

  function launch(op: () => Promise<void>): Promise<void> {
    const run = tail.then(op, op);
    tail = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  async function begin(): Promise<void> {
    const attempt = await deps.repo.beginSection({
      learnerId: deps.learnerId,
      runId: deps.runId,
      sectionCode: deps.sectionCode,
    });
    if (attempt.started_at == null || attempt.deadline_at == null) {
      // G9 / AP-6: server timestamps missing — do not invent a deadline.
      throw new Error("beginSection returned no started_at/deadline_at");
    }
    const prev = state;
    state = reduceExamSection(
      state,
      {
        type: "begin",
        startedAt: attempt.started_at,
        deadlineAt: attempt.deadline_at,
      },
      deps.clock,
    );
    enqueueDirty(prev, state);
    notify();
  }

  async function reconnect(): Promise<void> {
    await persistNow();
  }

  async function dispatch(action: ExamSectionAction): Promise<void> {
    const next = reduceExamSection(state, action, deps.clock);
    const finishing =
      next.phase === "finished" && state.phase !== "finished";

    if (finishing && isLearnerFinish(action)) {
      enqueueDirty(state, next);
      if (!(await persistNow())) return;
      if (!(await finishOnServer())) return;
      state = next;
      saveNotice = null;
      notify();
      return;
    }

    enqueueDirty(state, next);
    state = next;
    notify();

    if (finishing) {
      if (await persistNow()) {
        await finishOnServer();
      }
      return;
    }

    if (isNavigate(action) || isLearnerFinish(action)) {
      await persistNow();
    }
  }

  function applyHidden(): void {
    const prev = state;
    state = reduceExamSection(
      state,
      { type: "visibility", hidden: true },
      deps.clock,
    );
    enqueueDirty(prev, state);
    notify();
  }

  function handlePageHide(): void {
    if (!state.hidden) applyHidden();
    buffer.onPageHide();
  }

  function handleVisibilityHidden(): void {
    applyHidden();
    buffer.onVisibilityHidden();
  }

  function handleVisibilityVisible(): void {
    const prev = state;
    state = reduceExamSection(
      state,
      { type: "visibility", hidden: false },
      deps.clock,
    );
    enqueueDirty(prev, state);
    notify();
  }

  return {
    state: () => state,
    saveNotice: () => saveNotice,
    notSaved: () => saveNotice === NOT_SAVED || buffer.notSaved(),
    snapshot: () => cached,
    begin: () => launch(begin),
    dispatch: (action) => launch(() => dispatch(action)),
    reconnect: () => launch(reconnect),
    attachLifecycle(target, visibility) {
      const hidden = visibility?.hidden ?? defaultHidden;
      const onPageHide = () => {
        handlePageHide();
      };
      const onVisibility = () => {
        if (hidden()) handleVisibilityHidden();
        else handleVisibilityVisible();
      };
      const onOnline = () => {
        void launch(reconnect);
      };
      target.addEventListener("pagehide", onPageHide);
      target.addEventListener("visibilitychange", onVisibility);
      target.addEventListener("online", onOnline);
      return () => {
        target.removeEventListener("pagehide", onPageHide);
        target.removeEventListener("visibilitychange", onVisibility);
        target.removeEventListener("online", onOnline);
      };
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    pending: () => tail,
    dispose() {
      buffer.dispose();
      listeners.clear();
    },
  };
}

export function useExamSection(deps: ExamSectionSessionDeps): {
  state: ExamSectionState;
  saveNotice: string | null;
  notSaved: boolean;
  begin: () => Promise<void>;
  dispatch: (action: ExamSectionAction) => Promise<void>;
  reconnect: () => Promise<void>;
} {
  const sessionRef = React.useRef<ExamSectionSession | null>(null);
  if (sessionRef.current === null) {
    sessionRef.current = createExamSectionSession(deps);
  }
  const session = sessionRef.current;
  React.useEffect(() => {
    const detach = session.attachLifecycle(window);
    return () => {
      detach();
      session.dispose();
    };
  }, [session]);
  const snap = React.useSyncExternalStore(
    session.subscribe,
    session.snapshot,
    session.snapshot,
  );
  return {
    state: snap.state,
    saveNotice: snap.saveNotice,
    notSaved: snap.notSaved,
    begin: session.begin,
    dispatch: session.dispatch,
    reconnect: session.reconnect,
  };
}
