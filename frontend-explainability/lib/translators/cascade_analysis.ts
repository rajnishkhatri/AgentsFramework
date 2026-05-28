/**
 * Pure translator: BlackBoxEvent[] -> CascadeReport for the Cascade tab (S4.1.1).
 *
 * Brainstorm §2b layout: surface the ROOT_CAUSE of a failure, the IMMEDIATE
 * EFFECT it produced, the PROPAGATION chain across subsequent steps, the
 * SYSTEM RESPONSE (workflow termination, retry, etc.), and a PLAN_VS_ACTUAL
 * grid that contrasts the planned step actions with what actually happened.
 *
 * Detection rule:
 *   1. Walk causation_id chains where present (`details.causation_id` points
 *      at an `event_id`).  Any event whose causation chain reaches an
 *      `error_occurred` event is a propagation child.
 *   2. Fall back to the step-number heuristic: any `step_planned` /
 *      `step_executed` / `error_occurred` event whose `step` is strictly
 *      greater than the root cause's step (and whose timestamp is later) is
 *      considered downstream.
 *
 * Rule T1: imports only from lib/wire/.  No I/O, no React, no localStorage,
 * no fetch, no document, no window.
 */
import type { BlackBoxEvent } from "@/lib/wire/responses";

export type ImmediateEffectKind =
  | "step_skipped"
  | "step_retried"
  | "workflow_terminated"
  | "no_observable_effect";

export interface RootCause {
  event_id: string;
  step: number | null;
  error_message: string;
  timestamp: string | null;
  model: string | null;
}

export interface ImmediateEffect {
  event_id: string;
  step: number | null;
  kind: ImmediateEffectKind;
  description: string;
}

export interface PropagationFrame {
  event_id: string;
  step: number | null;
  kind: ImmediateEffectKind;
  description: string;
}

export type SystemResponse =
  | "workflow_terminated_no_recovery"
  | "workflow_completed_after_error"
  | "workflow_in_progress"
  | "no_response_observed";

export type PlanStatus = "ok" | "error" | "skipped" | "missing";

export interface PlanVsActualRow {
  step: number;
  planned: string;
  actual: string;
  status: PlanStatus;
}

export interface CascadeReport {
  has_errors: boolean;
  root_cause: RootCause | null;
  immediate_effect: ImmediateEffect | null;
  propagation: PropagationFrame[];
  system_response: SystemResponse | null;
  plan_vs_actual: PlanVsActualRow[];
}

const EMPTY_REPORT: CascadeReport = {
  has_errors: false,
  root_cause: null,
  immediate_effect: null,
  propagation: [],
  system_response: null,
  plan_vs_actual: [],
};

export function analyzeCascade(
  events: readonly BlackBoxEvent[],
): CascadeReport {
  if (events.length === 0) return { ...EMPTY_REPORT };

  const sorted = [...events].sort(compareByTimestamp);
  const errors = sorted.filter((e) => e.event_type === "error_occurred");

  if (errors.length === 0) {
    return {
      ...EMPTY_REPORT,
      plan_vs_actual: derivePlanVsActual(sorted, null),
    };
  }

  const rootEvent = errors[0]!;
  const rootCause = toRootCause(rootEvent);

  const downstream = collectDownstream(sorted, rootEvent);
  const propagation = downstream.map(classifyDownstream);
  const immediateEffect = propagation.length > 0 ? propagation[0]! : null;

  const systemResponse = deriveSystemResponse(sorted);

  return {
    has_errors: true,
    root_cause: rootCause,
    immediate_effect: immediateEffect,
    propagation,
    system_response: systemResponse,
    plan_vs_actual: derivePlanVsActual(sorted, rootEvent),
  };
}

function compareByTimestamp(a: BlackBoxEvent, b: BlackBoxEvent): number {
  const aT = a.timestamp ? Date.parse(a.timestamp) : 0;
  const bT = b.timestamp ? Date.parse(b.timestamp) : 0;
  return aT - bT;
}

function toRootCause(event: BlackBoxEvent): RootCause {
  const details = event.details ?? {};
  const error =
    typeof details["error"] === "string" ? (details["error"] as string) : "";
  const model =
    typeof details["model"] === "string" ? (details["model"] as string) : null;
  return {
    event_id: event.event_id,
    step: event.step,
    error_message: error,
    timestamp: event.timestamp,
    model,
  };
}

function collectDownstream(
  sorted: readonly BlackBoxEvent[],
  rootEvent: BlackBoxEvent,
): BlackBoxEvent[] {
  // Phase 1: collect every event whose causation chain hits the root error.
  const causationChildren = new Set<string>();
  causationChildren.add(rootEvent.event_id);
  // Iterate until no new ids are added (events are already in chronological
  // order; a single sweep is enough but a fixpoint loop is safe and tiny).
  let added = true;
  while (added) {
    added = false;
    for (const event of sorted) {
      if (causationChildren.has(event.event_id)) continue;
      const cid = event.details?.["causation_id"];
      if (typeof cid === "string" && causationChildren.has(cid)) {
        causationChildren.add(event.event_id);
        added = true;
      }
    }
  }

  // Phase 2: heuristic — any event after the root with a strictly greater
  // step number, when neither the root nor the candidate exposed an explicit
  // causation chain.
  const rootIndex = sorted.indexOf(rootEvent);
  const rootStep = rootEvent.step;

  const downstream: BlackBoxEvent[] = [];
  for (let i = rootIndex + 1; i < sorted.length; i += 1) {
    const candidate = sorted[i]!;
    if (causationChildren.has(candidate.event_id)) {
      downstream.push(candidate);
      continue;
    }
    const cid = candidate.details?.["causation_id"];
    // If the event explicitly cites a different cause, it is NOT downstream
    // of this root by the heuristic.
    if (typeof cid === "string") continue;

    if (rootStep === null || candidate.step === null) continue;
    if (candidate.step > rootStep) {
      downstream.push(candidate);
    }
  }

  return downstream;
}

function classifyDownstream(event: BlackBoxEvent): PropagationFrame {
  const details = event.details ?? {};
  const planned =
    typeof details["planned_action"] === "string"
      ? (details["planned_action"] as string)
      : null;

  let kind: ImmediateEffectKind = "no_observable_effect";
  let description = event.event_type;

  if (event.event_type === "step_planned") {
    if (planned === "skip" || planned === "skipped") {
      kind = "step_skipped";
      description = `Step ${event.step ?? "?"} planned as skip`;
    } else if (planned === "retry" || planned === "retried") {
      kind = "step_retried";
      description = `Step ${event.step ?? "?"} planned as retry`;
    } else {
      kind = "no_observable_effect";
      description = `Step ${event.step ?? "?"} replanned`;
    }
  } else if (event.event_type === "step_executed") {
    if (details["error"]) {
      kind = "no_observable_effect";
      description = `Step ${event.step ?? "?"} executed with error`;
    } else {
      kind = "no_observable_effect";
      description = `Step ${event.step ?? "?"} executed`;
    }
  } else if (event.event_type === "error_occurred") {
    kind = "no_observable_effect";
    description = `Cascading error at step ${event.step ?? "?"}`;
  }

  return {
    event_id: event.event_id,
    step: event.step,
    kind,
    description,
  };
}

function deriveSystemResponse(
  sorted: readonly BlackBoxEvent[],
): SystemResponse {
  const completed = sorted.find((e) => e.event_type === "task_completed");
  if (completed) return "workflow_completed_after_error";
  const lastEvent = sorted[sorted.length - 1];
  if (
    lastEvent &&
    (lastEvent.event_type === "error_occurred" ||
      lastEvent.event_type === "step_planned" ||
      lastEvent.event_type === "step_executed")
  ) {
    return "workflow_terminated_no_recovery";
  }
  return "no_response_observed";
}

function derivePlanVsActual(
  sorted: readonly BlackBoxEvent[],
  rootEvent: BlackBoxEvent | null,
): PlanVsActualRow[] {
  // Build a per-step view: latest planned action + actual outcome.
  const planByStep = new Map<number, string>();
  const statusByStep = new Map<number, PlanStatus>();
  const actualByStep = new Map<number, string>();

  for (const event of sorted) {
    const step = event.step;
    if (step === null) continue;
    const details = event.details ?? {};

    if (event.event_type === "step_planned") {
      const planned =
        typeof details["planned_action"] === "string"
          ? (details["planned_action"] as string)
          : "(unspecified)";
      // The most recent plan wins (replans overwrite).
      planByStep.set(step, planned);
      if (!statusByStep.has(step)) {
        statusByStep.set(step, "missing");
      }
      if (planned === "skip" || planned === "skipped") {
        statusByStep.set(step, "skipped");
        actualByStep.set(step, "skipped");
      }
    } else if (event.event_type === "step_executed") {
      if (details["error"]) {
        statusByStep.set(step, "error");
        actualByStep.set(
          step,
          typeof details["error"] === "string"
            ? `error: ${details["error"] as string}`
            : "error",
        );
      } else {
        statusByStep.set(step, "ok");
        actualByStep.set(step, "executed");
      }
    } else if (event.event_type === "error_occurred") {
      statusByStep.set(step, "error");
      actualByStep.set(
        step,
        typeof details["error"] === "string"
          ? `error: ${details["error"] as string}`
          : "error",
      );
    }
  }

  // Promote the root cause's step to "error" status even if no
  // step_planned/step_executed mentioned it.
  if (rootEvent !== null && rootEvent.step !== null) {
    statusByStep.set(rootEvent.step, "error");
    if (!actualByStep.has(rootEvent.step)) {
      const err = rootEvent.details?.["error"];
      actualByStep.set(
        rootEvent.step,
        typeof err === "string" ? `error: ${err}` : "error",
      );
    }
  }

  const steps = Array.from(planByStep.keys()).sort((a, b) => a - b);
  return steps.map((step) => ({
    step,
    planned: planByStep.get(step) ?? "(unspecified)",
    actual: actualByStep.get(step) ?? "(no outcome)",
    status: statusByStep.get(step) ?? "missing",
  }));
}
