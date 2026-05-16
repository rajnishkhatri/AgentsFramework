/**
 * Pure translator: BlackBoxEvent[] -> ReplayFrame[] for the Replay tab (S4.2.1).
 *
 * Each frame is a snapshot of the agent state AFTER the i-th event has been
 * applied: active agent, active model, latest parameter dict, last input, last
 * output, current step.  The scrubber renders these frames purely client-side
 * — there is no backend endpoint and NO graph re-execution.
 *
 * Architecture invariant ("Any -> Orchestration is FORBIDDEN", sprint board
 * §S4.2.1): this translator imports nothing from `lib/adapters/` or
 * `lib/composition`; the per-frame view is reconstructed exclusively from the
 * already-fetched event list.  See
 * `tests/architecture/test_replay_no_runtime_calls.test.ts`.
 *
 * Reachability invariant (covered by the property test): the frame at index
 * `i` equals the last frame produced by replaying events `[0..=i]`.  Adding
 * a new event type that needs accumulator state must respect this property.
 *
 * Rule T1: imports only from lib/wire/.
 */
import type { BlackBoxEvent } from "@/lib/wire/responses";

export interface ReplayFrame {
  /** Position in the chronologically-sorted event sequence, starting at 0. */
  index: number;
  /** Forwarded source event_id. */
  event_id: string;
  /** ISO timestamp of the source event, or null. */
  timestamp: string | null;
  /** Source event_type — exposed so the scrubber can colour the frame. */
  event_type: string;
  /** Most recent agent_id observed up to and including this event. */
  active_agent: string | null;
  /** Most recent model name observed. */
  active_model: string | null;
  /** Snapshot of the parameters dict mutated by parameter_changed events. */
  params: Readonly<Record<string, unknown>>;
  /** Most recent task_input or tool input as a printable string. */
  last_input: string | null;
  /** Most recent tool output or task completion result as a printable string. */
  last_output: string | null;
  /** Latest step index touched by step_planned / step_executed. */
  current_step: number | null;
}

export function eventsToReplayFrames(
  events: readonly BlackBoxEvent[],
): ReplayFrame[] {
  if (events.length === 0) return [];

  const sorted = [...events].sort(compareByTimestamp);

  let activeAgent: string | null = null;
  let activeModel: string | null = null;
  const params: Record<string, unknown> = {};
  let lastInput: string | null = null;
  let lastOutput: string | null = null;
  let currentStep: number | null = null;

  const frames: ReplayFrame[] = [];

  for (let i = 0; i < sorted.length; i += 1) {
    const event = sorted[i]!;
    const details = event.details ?? {};

    const detailsAgent = details["agent_id"];
    if (typeof detailsAgent === "string" && detailsAgent.length > 0) {
      activeAgent = detailsAgent;
    }

    const detailsModel = details["model"];
    if (typeof detailsModel === "string" && detailsModel.length > 0) {
      activeModel = detailsModel;
    }

    if (event.event_type === "task_started") {
      const taskInput = details["task_input"];
      if (typeof taskInput === "string") lastInput = taskInput;
    }

    if (event.event_type === "tool_called") {
      const input = details["input"];
      if (input !== undefined) lastInput = printable(input);
      const output = details["output"];
      if (output !== undefined) lastOutput = printable(output);
    }

    if (event.event_type === "step_executed") {
      const error = details["error"];
      if (error !== null && error !== undefined) {
        lastOutput = `error: ${printable(error)}`;
      }
    }

    if (event.event_type === "task_completed") {
      const status = details["status"];
      if (status !== undefined) {
        lastOutput = `task: ${printable(status)}`;
      }
    }

    if (event.event_type === "parameter_changed") {
      const name = details["parameter"];
      const value = details["new_value"];
      if (typeof name === "string" && value !== undefined) {
        params[name] = value;
      }
    }

    if (
      (event.event_type === "step_planned" ||
        event.event_type === "step_executed") &&
      typeof event.step === "number"
    ) {
      currentStep = event.step;
    }

    frames.push({
      index: i,
      event_id: event.event_id,
      timestamp: event.timestamp,
      event_type: event.event_type,
      active_agent: activeAgent,
      active_model: activeModel,
      params: { ...params },
      last_input: lastInput,
      last_output: lastOutput,
      current_step: currentStep,
    });
  }

  return frames;
}

function compareByTimestamp(a: BlackBoxEvent, b: BlackBoxEvent): number {
  const aT = a.timestamp ? Date.parse(a.timestamp) : 0;
  const bT = b.timestamp ? Date.parse(b.timestamp) : 0;
  return aT - bT;
}

function printable(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null) return "null";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
