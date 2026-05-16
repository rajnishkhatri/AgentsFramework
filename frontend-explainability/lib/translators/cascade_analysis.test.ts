/**
 * Cascade analysis translator tests (S4.1.1).
 *
 * Failure-paths-first per AGENTS.md TAP-4: empty input and "no errors" return
 * the empty-state CascadeReport BEFORE any happy-path row is asserted. The
 * translator is a pure function: rule T1 (no I/O / React / fetch / document).
 */
import { describe, it, expect } from "vitest";
import { analyzeCascade } from "./cascade_analysis";
import type { BlackBoxEvent } from "@/lib/wire/responses";

const ORIGIN = "2026-04-26T08:00:00.000Z";

function ts(offsetMs: number): string {
  return new Date(Date.parse(ORIGIN) + offsetMs).toISOString();
}

function evt(
  overrides: Partial<BlackBoxEvent> & Pick<BlackBoxEvent, "event_type"> & {
    event_id: string;
  },
): BlackBoxEvent {
  return {
    workflow_id: "wf-test",
    timestamp: ts(0),
    step: null,
    details: {},
    integrity_hash: "h",
    ...overrides,
  };
}

describe("analyzeCascade — failure / empty paths first", () => {
  it("returns the empty-state CascadeReport for empty input", () => {
    const report = analyzeCascade([]);
    expect(report.has_errors).toBe(false);
    expect(report.root_cause).toBeNull();
    expect(report.immediate_effect).toBeNull();
    expect(report.propagation).toEqual([]);
    expect(report.system_response).toBeNull();
    expect(report.plan_vs_actual).toEqual([]);
  });

  it("returns the empty-state CascadeReport when there are no errors", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "e0",
        event_type: "task_started",
        timestamp: ts(0),
        details: { task_input: "hi" },
      }),
      evt({
        event_id: "e1",
        event_type: "step_planned",
        step: 0,
        timestamp: ts(10),
      }),
      evt({
        event_id: "e2",
        event_type: "step_executed",
        step: 0,
        timestamp: ts(20),
        details: { error: null },
      }),
      evt({
        event_id: "e3",
        event_type: "task_completed",
        timestamp: ts(30),
      }),
    ];
    const report = analyzeCascade(events);
    expect(report.has_errors).toBe(false);
    expect(report.root_cause).toBeNull();
    expect(report.propagation).toEqual([]);
  });
});

describe("analyzeCascade — error in step 2 cascades to skip in step 3", () => {
  it("identifies root cause, immediate effect, propagation, and system response", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "p1",
        event_type: "step_planned",
        step: 1,
        timestamp: ts(10),
        details: { planned_action: "tool_then_model" },
      }),
      evt({
        event_id: "p2",
        event_type: "step_planned",
        step: 2,
        timestamp: ts(15),
        details: { planned_action: "tool_then_model" },
      }),
      evt({
        event_id: "p3",
        event_type: "step_planned",
        step: 3,
        timestamp: ts(20),
        details: { planned_action: "tool_then_model" },
      }),
      evt({
        event_id: "x1",
        event_type: "step_executed",
        step: 1,
        timestamp: ts(25),
        details: { error: null, model: "gpt-4o" },
      }),
      evt({
        event_id: "err",
        event_type: "error_occurred",
        step: 2,
        timestamp: ts(30),
        details: { error: "ConnectionRefused", model: "gpt-4o" },
      }),
      evt({
        event_id: "ev",
        event_type: "step_planned",
        step: 3,
        timestamp: ts(40),
        details: {
          planned_action: "skip",
          reason: "previous step errored",
        },
      }),
    ];
    const report = analyzeCascade(events);
    expect(report.has_errors).toBe(true);
    expect(report.root_cause).not.toBeNull();
    expect(report.root_cause?.event_id).toBe("err");
    expect(report.root_cause?.step).toBe(2);
    expect(report.root_cause?.error_message).toBe("ConnectionRefused");
    expect(report.immediate_effect).not.toBeNull();
    expect(report.immediate_effect?.kind).toBe("step_skipped");
    expect(report.immediate_effect?.step).toBe(3);
    expect(report.propagation.length).toBeGreaterThan(0);
    expect(report.propagation[0]?.kind).toBe("step_skipped");
    expect(report.system_response).toBe("workflow_terminated_no_recovery");

    const planVsActual = report.plan_vs_actual;
    const planned1 = planVsActual.find((row) => row.step === 1);
    expect(planned1?.planned).toBe("tool_then_model");
    expect(planned1?.status).toBe("ok");
    const planned2 = planVsActual.find((row) => row.step === 2);
    expect(planned2?.status).toBe("error");
    const planned3 = planVsActual.find((row) => row.step === 3);
    expect(planned3?.status).toBe("skipped");
  });
});

describe("analyzeCascade — error with no downstream effects", () => {
  it("populates root_cause but leaves propagation empty", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "p1",
        event_type: "step_planned",
        step: 1,
        timestamp: ts(10),
        details: { planned_action: "tool_then_model" },
      }),
      evt({
        event_id: "err",
        event_type: "error_occurred",
        step: 1,
        timestamp: ts(20),
        details: { error: "Timeout" },
      }),
      evt({
        event_id: "done",
        event_type: "task_completed",
        timestamp: ts(30),
      }),
    ];
    const report = analyzeCascade(events);
    expect(report.has_errors).toBe(true);
    expect(report.root_cause?.event_id).toBe("err");
    expect(report.propagation).toEqual([]);
    expect(report.immediate_effect).toBeNull();
    expect(report.system_response).toBe("workflow_completed_after_error");
  });
});

describe("analyzeCascade — purity", () => {
  it("does not mutate the input events array", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "b",
        event_type: "task_completed",
        timestamp: ts(20),
      }),
      evt({
        event_id: "a",
        event_type: "task_started",
        timestamp: ts(0),
      }),
    ];
    const before = events.map((e) => e.event_id);
    analyzeCascade(events);
    expect(events.map((e) => e.event_id)).toEqual(before);
  });
});

describe("analyzeCascade — causation_id chain", () => {
  it("prefers explicit causation_id chains over the step-number heuristic", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "root-error",
        event_type: "error_occurred",
        step: 0,
        timestamp: ts(10),
        details: { error: "boom" },
      }),
      evt({
        event_id: "child-skip",
        event_type: "step_planned",
        step: 99, // out-of-step-order, only causation_id links it
        timestamp: ts(20),
        details: {
          causation_id: "root-error",
          planned_action: "skip",
          reason: "parent failed",
        },
      }),
    ];
    const report = analyzeCascade(events);
    expect(report.has_errors).toBe(true);
    expect(report.propagation.map((p) => p.event_id)).toContain("child-skip");
  });
});
