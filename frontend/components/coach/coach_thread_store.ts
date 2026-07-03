/**
 * coach_thread_store — the shared coach thread (Phase 4.3, FR-J3/J4).
 *
 * The iPad split (FR-J3) renders ONE coach thread in two mounts at once — the
 * quiz page's CoachPanel and the full Coach screen — and the thread must
 * survive the client-side navigation between them ("a message typed into the
 * panel SHALL appear in the full Coach screen's thread — one thread, not
 * two"). React state in either mount unmounts with it, so the transcript, the
 * LangGraph thread id, and the busy flag live in this module-level singleton
 * (the `quiz_session_store` precedent — plan §Architecture/OD-3), and every
 * consumer subscribes via `useSyncExternalStore`.
 *
 * FR-J4 (cross-surface independence) holds for free: the store is per-tab
 * (per JS heap) — two device surfaces are two heaps.
 *
 * Deliberately NOT an engine port and NOT persisted: a full page reload starts
 * a fresh thread (the durable-thread seam is the chat persistence plane, not
 * this carrier). State transitions are pure folds of `reduceRunView`; the
 * store owns no I/O — `use_coach.sendCoachAsk` drives the stream.
 */

import type { ChatTurn } from "@/components/chat/use_agent_run";
import {
  emptyRunView,
  reduceRunView,
} from "@/lib/translators/run_view_reducer";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

export interface CoachThreadState {
  /** Stable LangGraph thread id (checkpoint continuity); null until first ask. */
  readonly threadId: string | null;
  readonly turns: ReadonlyArray<ChatTurn>;
  /** A send is in flight (either mount may have started it). */
  readonly busy: boolean;
}

const EMPTY: CoachThreadState = { threadId: null, turns: [], busy: false };

let state: CoachThreadState = EMPTY;
const listeners = new Set<() => void>();

function emit(next: CoachThreadState): void {
  state = next;
  for (const notify of listeners) notify();
}

/** Current state — a stable object identity between mutations (uSES contract). */
export function coachThreadSnapshot(): CoachThreadState {
  return state;
}

/** Subscribe to mutations; returns the unsubscribe. */
export function subscribeCoachThread(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

/**
 * Open a new user turn on the shared thread: mints the thread id on the first
 * ask (lazy — no id until someone talks), appends the pending turn, and marks
 * the thread busy. Returns the ids the caller streams against.
 */
export function beginCoachTurn(user: string): {
  threadId: string;
  turnId: string;
} {
  const threadId = state.threadId ?? crypto.randomUUID();
  const turnId = crypto.randomUUID();
  emit({
    threadId,
    busy: true,
    turns: [...state.turns, { id: turnId, user, assistant: emptyRunView() }],
  });
  return { threadId, turnId };
}

/**
 * Fold one stream event into the owning turn. Unknown turn ids are a NO-OP —
 * a late event from an abandoned stream (e.g. after `resetCoachThread`) must
 * not resurrect a dead turn.
 */
export function applyCoachEvent(turnId: string, evt: UIRuntimeEvent): void {
  if (!state.turns.some((t) => t.id === turnId)) return;
  emit({
    ...state,
    turns: state.turns.map((t) =>
      t.id === turnId ? { ...t, assistant: reduceRunView(t.assistant, evt) } : t,
    ),
  });
}

/** Mark the in-flight send finished (terminal event already folded). */
export function endCoachTurn(): void {
  emit({ ...state, busy: false });
}

/** Drop the whole thread (tests + an explicit fresh-conversation affordance). */
export function resetCoachThread(): void {
  emit(EMPTY);
}
