/**
 * Pure translator: BlackBoxEvent -> TimelineFrame for the trace timeline view.
 *
 * Rule T1: this file imports only from lib/wire/. No I/O, no React, no
 *          localStorage / fetch / document / window.
 * Rule T2 (analogue): the source `event_id` is forwarded to the frame `id`.
 * Rule T4: every EventType has a deterministic colour and label; tests cover
 *          all nine variants.
 */
import type { BlackBoxEvent } from "@/lib/wire/responses";

export type TimelineKind =
  | "task"
  | "step"
  | "tool"
  | "model"
  | "error"
  | "guardrail"
  | "param";

export interface TimelineFrame {
  /** Forwarded source event_id (rule T2 spirit). */
  id: string;
  /** Parent timeline frame id, or null for top-level frames. */
  parentId: string | null;
  /** Short human label (free-text, drawn under the bar). */
  label: string;
  /** Milliseconds from the timeline origin (workflow start). */
  startMs: number;
  /** Bar duration in milliseconds. Always >= 0. */
  durationMs: number;
  /** A semantic colour token consumed by the chart layer. */
  color: TimelineColor;
  /** Discriminator for the detail panel. */
  kind: TimelineKind;
  /** Step index when the source event carried one, otherwise null. */
  step: number | null;
  /** Pass-through of the source `details` dict for the side panel. */
  details: Readonly<Record<string, unknown>>;
}

export type TimelineColor =
  | "neutral"
  | "primary"
  | "info"
  | "success"
  | "warning"
  | "danger";

interface EventTypeMeta {
  kind: TimelineKind;
  color: TimelineColor;
  label: (event: BlackBoxEvent) => string;
}

/**
 * Static table mapping every `EventType` from
 * `services/governance/black_box.py` to its visual presentation.  Adding a new
 * EventType server-side requires a new row here AND a new test row.
 */
const EVENT_TYPE_TABLE: Record<string, EventTypeMeta> = {
  task_started: {
    kind: "task",
    color: "primary",
    label: (e) => `Task started: ${truncate(e.details["task_input"])}`,
  },
  step_planned: {
    kind: "step",
    color: "info",
    label: (e) => `Step ${stepLabel(e)} planned`,
  },
  step_executed: {
    kind: "step",
    color: "neutral",
    label: (e) => `Step ${stepLabel(e)} executed`,
  },
  tool_called: {
    kind: "tool",
    color: "info",
    label: (e) =>
      `Tool: ${truncate(e.details["tool_name"]) ?? "(unknown)"}`,
  },
  model_selected: {
    kind: "model",
    color: "info",
    label: (e) => `Model: ${truncate(e.details["model"]) ?? "(unset)"}`,
  },
  error_occurred: {
    kind: "error",
    color: "danger",
    label: (e) => `Error: ${truncate(e.details["error"]) ?? "(unknown)"}`,
  },
  guardrail_checked: {
    kind: "guardrail",
    color: "neutral",
    label: (e) =>
      `Guardrail: ${truncate(e.details["guardrail"]) ?? "check"}`,
  },
  parameter_changed: {
    kind: "param",
    color: "warning",
    label: (e) =>
      `Param: ${truncate(e.details["parameter"]) ?? "(unset)"}`,
  },
  task_completed: {
    kind: "task",
    color: "success",
    label: () => "Task completed",
  },
};

const FALLBACK_META: EventTypeMeta = {
  kind: "step",
  color: "neutral",
  label: (e) => e.event_type,
};

/** Convert an array of events into ordered timeline frames. */
export function eventsToTimeline(events: readonly BlackBoxEvent[]): TimelineFrame[] {
  if (events.length === 0) return [];

  const sorted = [...events].sort(compareEvents);
  const originMs = sorted[0]!.timestamp ? Date.parse(sorted[0]!.timestamp) : 0;

  const frames: TimelineFrame[] = sorted.map((event, index) => {
    const meta = EVENT_TYPE_TABLE[event.event_type] ?? FALLBACK_META;
    const next = sorted[index + 1];
    const startMs = event.timestamp ? Date.parse(event.timestamp) - originMs : 0;
    const endMs =
      next && next.timestamp
        ? Date.parse(next.timestamp) - originMs
        : startMs;
    const durationMs = Math.max(0, endMs - startMs);

    return {
      id: event.event_id,
      parentId: null,
      label: meta.label(event),
      startMs: Number.isFinite(startMs) ? startMs : 0,
      durationMs: Number.isFinite(durationMs) ? durationMs : 0,
      color: applyOverrides(meta.color, event),
      kind: meta.kind,
      step: event.step,
      details: event.details,
    };
  });

  // Wire children to their nearest preceding `task_started` frame so the
  // waterfall renders one band per task. Only `task_started` opens a new
  // parent band; `task_completed` belongs to the band it closes.
  let currentTaskId: string | null = null;
  for (let i = 0; i < frames.length; i += 1) {
    const frame = frames[i]!;
    const sourceType = sorted[i]!.event_type;
    if (sourceType === "task_started") {
      currentTaskId = frame.id;
      frame.parentId = null;
    } else {
      frame.parentId = currentTaskId;
    }
  }
  return frames;
}

function compareEvents(a: BlackBoxEvent, b: BlackBoxEvent): number {
  const aTs = a.timestamp ? Date.parse(a.timestamp) : 0;
  const bTs = b.timestamp ? Date.parse(b.timestamp) : 0;
  return aTs - bTs;
}

function stepLabel(event: BlackBoxEvent): string {
  if (typeof event.step === "number") return String(event.step);
  return "?";
}

function truncate(value: unknown, max = 60): string | null {
  if (typeof value !== "string") return null;
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

/**
 * Colour overrides that the static table cannot express:
 *  - guardrail with `accepted=false` is a danger band, not neutral.
 *  - step_executed with a non-null `error` field is a danger band.
 */
function applyOverrides(color: TimelineColor, event: BlackBoxEvent): TimelineColor {
  if (event.event_type === "guardrail_checked") {
    return event.details["accepted"] === false ? "danger" : "success";
  }
  if (event.event_type === "step_executed" && event.details["error"]) {
    return "danger";
  }
  return color;
}
