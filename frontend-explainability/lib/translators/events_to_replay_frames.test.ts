/**
 * Replay frames translator tests (S4.2.1).
 *
 * Failure-paths-first: empty input and a single-event workflow are asserted
 * BEFORE any happy-path multi-step sequence.  Property test verifies the
 * "frame at index i is reachable from frame 0 by replaying events [0..i]"
 * invariant.
 *
 * Rule T1: the translator imports only from lib/wire/.  No I/O.
 */
import { describe, it, expect } from "vitest";
import { eventsToReplayFrames } from "./events_to_replay_frames";
import type { BlackBoxEvent } from "@/lib/wire/responses";

const ORIGIN = "2026-04-26T08:00:00.000Z";
function ts(offsetMs: number): string {
  return new Date(Date.parse(ORIGIN) + offsetMs).toISOString();
}
function evt(
  o: Partial<BlackBoxEvent> & Pick<BlackBoxEvent, "event_type"> & {
    event_id: string;
  },
): BlackBoxEvent {
  return {
    workflow_id: "wf-test",
    timestamp: ts(0),
    step: null,
    details: {},
    integrity_hash: "h",
    ...o,
  };
}

describe("eventsToReplayFrames — failure / empty paths", () => {
  it("returns [] for empty input", () => {
    expect(eventsToReplayFrames([])).toEqual([]);
  });

  it("returns a single frame for a single event", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "e0",
        event_type: "task_started",
        timestamp: ts(0),
        details: { task_input: "hi", agent_id: "cli-agent" },
      }),
    ];
    const frames = eventsToReplayFrames(events);
    expect(frames).toHaveLength(1);
    expect(frames[0]?.index).toBe(0);
    expect(frames[0]?.event_id).toBe("e0");
    expect(frames[0]?.active_agent).toBe("cli-agent");
    expect(frames[0]?.last_input).toBe("hi");
  });

  it("never drops a step (length(frames) === length(events))", () => {
    const events: BlackBoxEvent[] = [
      evt({ event_id: "a", event_type: "task_started", timestamp: ts(0) }),
      evt({
        event_id: "b",
        event_type: "step_planned",
        step: 0,
        timestamp: ts(1),
      }),
      evt({
        event_id: "c",
        event_type: "step_executed",
        step: 0,
        timestamp: ts(2),
      }),
      evt({ event_id: "d", event_type: "task_completed", timestamp: ts(3) }),
    ];
    expect(eventsToReplayFrames(events)).toHaveLength(events.length);
  });
});

describe("eventsToReplayFrames — happy path", () => {
  const events: BlackBoxEvent[] = [
    evt({
      event_id: "start",
      event_type: "task_started",
      timestamp: ts(0),
      details: { task_input: "What is 2+2?", agent_id: "cli-agent" },
    }),
    evt({
      event_id: "model",
      event_type: "model_selected",
      timestamp: ts(10),
      details: { model: "gpt-4o", agent_id: "cli-agent" },
    }),
    evt({
      event_id: "param",
      event_type: "parameter_changed",
      timestamp: ts(20),
      details: {
        parameter: "temperature",
        old_value: 0.0,
        new_value: 0.3,
      },
    }),
    evt({
      event_id: "plan0",
      event_type: "step_planned",
      step: 0,
      timestamp: ts(30),
      details: { agent_id: "cli-agent", planned_action: "tool_then_model" },
    }),
    evt({
      event_id: "tool0",
      event_type: "tool_called",
      step: 0,
      timestamp: ts(40),
      details: {
        tool_name: "shell",
        input: { cmd: "echo 4" },
        output: { stdout: "4" },
      },
    }),
    evt({
      event_id: "exec0",
      event_type: "step_executed",
      step: 0,
      timestamp: ts(50),
      details: { model: "gpt-4o", error: null, latency_ms: 200 },
    }),
    evt({
      event_id: "done",
      event_type: "task_completed",
      timestamp: ts(60),
      details: { status: "success" },
    }),
  ];

  it("produces one frame per event with monotonically increasing index", () => {
    const frames = eventsToReplayFrames(events);
    expect(frames).toHaveLength(events.length);
    frames.forEach((frame, idx) => {
      expect(frame.index).toBe(idx);
      expect(frame.event_id).toBe(events[idx]!.event_id);
    });
  });

  it("snapshots the active model and agent as they appear", () => {
    const frames = eventsToReplayFrames(events);
    expect(frames[0]?.active_model).toBeNull();
    expect(frames[1]?.active_model).toBe("gpt-4o");
    expect(frames[1]?.active_agent).toBe("cli-agent");
    expect(frames[2]?.active_model).toBe("gpt-4o");
  });

  it("snapshots parameter changes into params", () => {
    const frames = eventsToReplayFrames(events);
    expect(frames[1]?.params).toEqual({});
    expect(frames[2]?.params).toEqual({ temperature: 0.3 });
    expect(frames[3]?.params).toEqual({ temperature: 0.3 });
  });

  it("tracks last_input and last_output as tools and tasks fire", () => {
    const frames = eventsToReplayFrames(events);
    expect(frames[0]?.last_input).toBe("What is 2+2?");
    const toolFrame = frames[4]!;
    expect(toolFrame.last_input).toContain("4");
    expect(toolFrame.last_output).toContain("4");
  });

  it("tracks the current_step from step_planned/step_executed", () => {
    const frames = eventsToReplayFrames(events);
    expect(frames[0]?.current_step).toBeNull();
    expect(frames[3]?.current_step).toBe(0);
    expect(frames[5]?.current_step).toBe(0);
  });
});

describe("eventsToReplayFrames — reachability invariant (property test)", () => {
  it("frame[i] equals replay of events[0..=i]", () => {
    const events: BlackBoxEvent[] = [
      evt({
        event_id: "a",
        event_type: "task_started",
        timestamp: ts(0),
        details: { task_input: "x" },
      }),
      evt({
        event_id: "b",
        event_type: "model_selected",
        timestamp: ts(10),
        details: { model: "m1" },
      }),
      evt({
        event_id: "c",
        event_type: "parameter_changed",
        timestamp: ts(20),
        details: { parameter: "t", old_value: 0, new_value: 1 },
      }),
      evt({
        event_id: "d",
        event_type: "step_planned",
        step: 0,
        timestamp: ts(30),
      }),
    ];
    const full = eventsToReplayFrames(events);
    for (let i = 0; i < events.length; i += 1) {
      const partial = eventsToReplayFrames(events.slice(0, i + 1));
      expect(partial.at(-1)).toEqual(full[i]);
    }
  });
});

describe("eventsToReplayFrames — purity", () => {
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
    eventsToReplayFrames(events);
    expect(events.map((e) => e.event_id)).toEqual(before);
  });
});
