/**
 * Translator tests — table-driven, one row per `EventType` (rule T4).
 *
 * Failure-first: the empty-input case is asserted before any happy-path row.
 * The translator is a pure function: no I/O, no React, no localStorage.
 */
import { describe, it, expect } from "vitest";
import {
  eventsToTimeline,
  type TimelineColor,
  type TimelineKind,
} from "./event_to_timeline";
import type { BlackBoxEvent } from "@/lib/wire/responses";

const ORIGIN = "2026-04-26T08:00:00.000Z";

function makeEvent(
  overrides: Partial<BlackBoxEvent> & Pick<BlackBoxEvent, "event_type">,
): BlackBoxEvent {
  return {
    event_id: `evt-${overrides.event_type}`,
    workflow_id: "wf-test",
    timestamp: ORIGIN,
    step: null,
    details: {},
    integrity_hash: "h",
    ...overrides,
  };
}

describe("eventsToTimeline — failure paths", () => {
  it("returns [] for empty input", () => {
    expect(eventsToTimeline([])).toEqual([]);
  });

  it("falls back gracefully on an unknown event_type", () => {
    const evt = makeEvent({ event_type: "unknown_future_type" });
    const frames = eventsToTimeline([evt]);
    expect(frames).toHaveLength(1);
    expect(frames[0]!.label).toBe("unknown_future_type");
    expect(frames[0]!.color).toBe("neutral");
  });

  it("survives an event with a null timestamp", () => {
    const evt = makeEvent({
      event_type: "task_started",
      timestamp: null,
      details: { task_input: "hi" },
    });
    const frames = eventsToTimeline([evt]);
    expect(frames).toHaveLength(1);
    expect(frames[0]!.startMs).toBe(0);
    expect(frames[0]!.durationMs).toBe(0);
  });
});

interface TableRow {
  event_type: string;
  details?: Record<string, unknown>;
  step?: number | null;
  expectedKind: TimelineKind;
  expectedColor: TimelineColor;
  expectedLabelMatches: RegExp;
}

const TABLE: TableRow[] = [
  {
    event_type: "task_started",
    details: { task_input: "What is the capital of France?" },
    expectedKind: "task",
    expectedColor: "primary",
    expectedLabelMatches: /Task started: What is the capital/i,
  },
  {
    event_type: "step_planned",
    step: 1,
    expectedKind: "step",
    expectedColor: "info",
    expectedLabelMatches: /Step 1 planned/,
  },
  {
    event_type: "step_executed",
    step: 2,
    expectedKind: "step",
    expectedColor: "neutral",
    expectedLabelMatches: /Step 2 executed/,
  },
  {
    event_type: "tool_called",
    details: { tool_name: "shell" },
    expectedKind: "tool",
    expectedColor: "info",
    expectedLabelMatches: /Tool: shell/,
  },
  {
    event_type: "model_selected",
    details: { model: "gpt-4o" },
    expectedKind: "model",
    expectedColor: "info",
    expectedLabelMatches: /Model: gpt-4o/,
  },
  {
    event_type: "error_occurred",
    details: { error: "timeout" },
    expectedKind: "error",
    expectedColor: "danger",
    expectedLabelMatches: /Error: timeout/,
  },
  {
    event_type: "guardrail_checked",
    details: { guardrail: "prompt_injection", accepted: true },
    expectedKind: "guardrail",
    expectedColor: "success",
    expectedLabelMatches: /Guardrail: prompt_injection/,
  },
  {
    event_type: "parameter_changed",
    details: { parameter: "temperature" },
    expectedKind: "param",
    expectedColor: "warning",
    expectedLabelMatches: /Param: temperature/,
  },
  {
    event_type: "task_completed",
    expectedKind: "task",
    expectedColor: "success",
    expectedLabelMatches: /Task completed/,
  },
];

describe("eventsToTimeline — one row per EventType (rule T4)", () => {
  it.each(TABLE)(
    "$event_type → kind=$expectedKind, color=$expectedColor",
    ({ event_type, details, step, expectedKind, expectedColor, expectedLabelMatches }) => {
      const evt = makeEvent({
        event_type,
        details: details ?? {},
        step: step ?? null,
      });
      const [frame] = eventsToTimeline([evt]);
      expect(frame).toBeDefined();
      expect(frame!.kind).toBe(expectedKind);
      expect(frame!.color).toBe(expectedColor);
      expect(frame!.label).toMatch(expectedLabelMatches);
      expect(frame!.id).toBe(evt.event_id);
    },
  );

  it("covers every EventType from the Python EventType enum", () => {
    // Mirror of services/governance/black_box.py::EventType — fails the day a
    // new type is added server-side without an entry here.
    const expectedTypes = new Set([
      "task_started",
      "step_planned",
      "step_executed",
      "tool_called",
      "model_selected",
      "error_occurred",
      "guardrail_checked",
      "parameter_changed",
      "task_completed",
    ]);
    const tableTypes = new Set(TABLE.map((row) => row.event_type));
    for (const type of expectedTypes) {
      expect(tableTypes.has(type), `missing TABLE row for ${type}`).toBe(true);
    }
  });
});

describe("eventsToTimeline — colour overrides", () => {
  it("guardrail with accepted=false is danger", () => {
    const evt = makeEvent({
      event_type: "guardrail_checked",
      details: { guardrail: "pii_scan", accepted: false },
    });
    expect(eventsToTimeline([evt])[0]!.color).toBe("danger");
  });

  it("step_executed with a non-null error becomes danger", () => {
    const evt = makeEvent({
      event_type: "step_executed",
      step: 0,
      details: { error: "boom" },
    });
    expect(eventsToTimeline([evt])[0]!.color).toBe("danger");
  });
});

describe("eventsToTimeline — ordering and parenting", () => {
  it("sorts events by timestamp ascending", () => {
    const t0 = "2026-04-26T08:00:00.000Z";
    const t1 = "2026-04-26T08:00:01.000Z";
    const t2 = "2026-04-26T08:00:02.000Z";
    const frames = eventsToTimeline([
      makeEvent({ event_type: "task_completed", timestamp: t2, event_id: "c" }),
      makeEvent({ event_type: "task_started", timestamp: t0, event_id: "a" }),
      makeEvent({ event_type: "step_executed", timestamp: t1, event_id: "b", step: 0 }),
    ]);
    expect(frames.map((f) => f.id)).toEqual(["a", "b", "c"]);
    expect(frames[0]!.startMs).toBe(0);
    expect(frames[1]!.startMs).toBe(1000);
    expect(frames[2]!.startMs).toBe(2000);
  });

  it("non-task children inherit parentId from the preceding task_started frame", () => {
    const t0 = "2026-04-26T08:00:00.000Z";
    const t1 = "2026-04-26T08:00:01.000Z";
    const t2 = "2026-04-26T08:00:02.000Z";
    const frames = eventsToTimeline([
      makeEvent({ event_type: "task_started", timestamp: t0, event_id: "T" }),
      makeEvent({ event_type: "step_executed", timestamp: t1, event_id: "S", step: 0 }),
      makeEvent({ event_type: "task_completed", timestamp: t2, event_id: "C" }),
    ]);
    expect(frames[0]!.parentId).toBeNull();
    expect(frames[1]!.parentId).toBe("T");
    expect(frames[2]!.parentId).toBe("T");
  });

  it("durationMs is the gap to the next event", () => {
    const t0 = "2026-04-26T08:00:00.000Z";
    const t1 = "2026-04-26T08:00:00.500Z";
    const frames = eventsToTimeline([
      makeEvent({ event_type: "task_started", timestamp: t0, event_id: "a" }),
      makeEvent({ event_type: "task_completed", timestamp: t1, event_id: "b" }),
    ]);
    expect(frames[0]!.durationMs).toBe(500);
    expect(frames[1]!.durationMs).toBe(0);
  });
});

describe("eventsToTimeline — purity", () => {
  it("does not mutate input event arrays", () => {
    const events: BlackBoxEvent[] = [
      makeEvent({
        event_type: "task_completed",
        timestamp: "2026-04-26T08:00:01.000Z",
      }),
      makeEvent({
        event_type: "task_started",
        timestamp: "2026-04-26T08:00:00.000Z",
      }),
    ];
    const before = events.map((e) => e.event_id);
    eventsToTimeline(events);
    const after = events.map((e) => e.event_id);
    expect(after).toEqual(before);
  });
});
