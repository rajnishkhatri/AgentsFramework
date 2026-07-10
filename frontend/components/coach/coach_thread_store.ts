/**
 * coach_thread_store — the shared coach thread (Phase 4.3, FR-J3/J4 + BP-2 pin).
 *
 * The iPad split (FR-J3) renders ONE coach thread in two mounts at once — the
 * quiz page's CoachPanel and the full Coach screen — and the thread must
 * survive the client-side navigation between them ("a message typed into the
 * panel SHALL appear in the full Coach screen's thread — one thread, not
 * two"). React state in either mount unmounts with it, so the transcript, the
 * LangGraph thread id, the busy flag, and the UI pin (C1) live in this
 * module-level singleton (the `quiz_session_store` precedent — plan
 * §Architecture/OD-3), and every consumer subscribes via `useSyncExternalStore`.
 *
 * FR-J4 (cross-surface independence) holds for free: the store is per-tab
 * (per JS heap) — two device surfaces are two heaps.
 *
 * Pin (C1/C1a): `{questionId, skillId, label}` only — full Question loads at
 * ask time. Advisory `mode` is a sibling field (not on the pin schema) so
 * Feedback→Coach can show post_feedback chrome/wire without bloating C1a.
 * `resetCoachThread` clears pin + mode with the transcript.
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
import type { CoachMode } from "@/lib/translators/coach_context_sanitizer";
import type { CoachSurfacePin } from "@/lib/translators/coach_surface_vm";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

export interface CoachThreadState {
  /** Stable LangGraph thread id (checkpoint continuity); null until first ask. */
  readonly threadId: string | null;
  readonly turns: ReadonlyArray<ChatTurn>;
  /** A send is in flight (either mount may have started it). */
  readonly busy: boolean;
  /**
   * UI pin for current-item / history chrome + B3 wire assembly (C1).
   * null = honest absent (cold open / reset).
   */
  readonly pin: CoachSurfacePin | null;
  /**
   * Advisory coach mode for chrome + client wire (ADR-0012 — BFF overwrites).
   * Cleared to `pre_submit` when pin is null / on reset.
   */
  readonly mode: CoachMode;
}

const EMPTY: CoachThreadState = {
  threadId: null,
  turns: [],
  busy: false,
  pin: null,
  mode: "pre_submit",
};

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
 * Set or clear the UI pin (Feedback Ask-the-coach / quiz panel live item).
 * Optional `mode` is advisory for chrome + wire (default `pre_submit`);
 * clearing the pin resets mode. Does not touch transcript or thread id.
 */
export function setCoachPin(
  pin: CoachSurfacePin | null,
  mode: CoachMode = "pre_submit",
): void {
  const nextMode: CoachMode = pin == null ? "pre_submit" : mode;
  if (
    pin != null &&
    state.pin != null &&
    pin.questionId === state.pin.questionId &&
    pin.skillId === state.pin.skillId &&
    pin.label === state.pin.label &&
    state.mode === nextMode
  ) {
    return;
  }
  if (pin == null && state.pin == null && state.mode === nextMode) return;
  emit({ ...state, pin, mode: nextMode });
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
    ...state,
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

/** Drop the whole thread + pin (tests + an explicit fresh-conversation affordance). */
export function resetCoachThread(): void {
  emit(EMPTY);
}
