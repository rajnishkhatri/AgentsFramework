/**
 * L1 tests for the AG-UI tool-event aggregator.
 *
 * Tool-event aggregation is stateful at the *call site* (a chain of TOOL_*
 * events for the same tool_call_id collapses into one renderer request),
 * but the translator itself is a pure (state, event) -> state' function.
 * This is exactly the property tested by Pattern 1 / Pattern 4.
 */

import { describe, expect, it } from "vitest";
import {
  emptyToolAggregatorState,
  reduceToolEvent,
  type ToolAggregatorState,
} from "./tool_event_to_renderer_request";
import type { AGUIEvent } from "../wire/ag_ui_events";

const TRACE = "trace-001";
const RAW = { raw_event: { trace_id: TRACE } };

describe("reduceToolEvent (pure aggregator) [T1, T2]", () => {
  it("rejects events without trace_id", () => {
    const evt = {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      raw_event: null,
    } as unknown as AGUIEvent;
    expect(() => reduceToolEvent(emptyToolAggregatorState(), evt)).toThrowError(
      /trace_id/,
    );
  });

  it("TOOL_CALL_START registers a 'running' renderer request with empty input", () => {
    const next = reduceToolEvent(emptyToolAggregatorState(), {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      parent_message_id: null,
      ...RAW,
    } as never);
    expect(next.renderers).toHaveLength(1);
    const req = next.renderers[0]!;
    expect(req.tool_call_id).toBe("tc1");
    expect(req.tool_name).toBe("shell");
    expect(req.status).toBe("running");
    expect(req.input).toEqual({});
    expect(req.output).toBeNull();
    expect(req.trace_id).toBe(TRACE);
  });

  it("accumulates TOOL_CALL_ARGS deltas into a JSON-parseable input dict", () => {
    let state = emptyToolAggregatorState();
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      parent_message_id: null,
      ...RAW,
    } as never);
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_ARGS",
      tool_call_id: "tc1",
      delta: '{"cmd"',
      ...RAW,
    } as never);
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_ARGS",
      tool_call_id: "tc1",
      delta: ':"ls"}',
      ...RAW,
    } as never);
    expect(state.renderers[0]!.input).toEqual({ cmd: "ls" });
  });

  it("TOOL_RESULT transitions the renderer to status='completed'", () => {
    let state = emptyToolAggregatorState();
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      parent_message_id: null,
      ...RAW,
    } as never);
    state = reduceToolEvent(state, {
      type: "TOOL_RESULT",
      tool_call_id: "tc1",
      content: "file1\nfile2",
      role: "tool",
      ...RAW,
    } as never);
    expect(state.renderers[0]!.status).toBe("completed");
    expect(state.renderers[0]!.output).toBe("file1\nfile2");
  });

  it("TOOL_CALL_END alone keeps the renderer 'running' until TOOL_RESULT arrives", () => {
    let state = emptyToolAggregatorState();
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      parent_message_id: null,
      ...RAW,
    } as never);
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_END",
      tool_call_id: "tc1",
      ...RAW,
    } as never);
    expect(state.renderers[0]!.status).toBe("running");
  });

  it("ignores non-tool AG-UI events without changing state (T3 zero output)", () => {
    const initial = emptyToolAggregatorState();
    const next = reduceToolEvent(initial, {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: "m1",
      delta: "Hi",
      ...RAW,
    } as never);
    expect(next).toEqual(initial);
  });

  it("is pure -- the input state is never mutated", () => {
    const before = emptyToolAggregatorState();
    const snapshot = JSON.stringify(before);
    reduceToolEvent(before, {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      parent_message_id: null,
      ...RAW,
    } as never);
    expect(JSON.stringify(before)).toBe(snapshot);
  });

  it("trace_id forwards onto every renderer request [T2 / F-R7]", () => {
    let state: ToolAggregatorState = emptyToolAggregatorState();
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      parent_message_id: null,
      ...RAW,
    } as never);
    state = reduceToolEvent(state, {
      type: "TOOL_CALL_START",
      tool_call_id: "tc2",
      tool_call_name: "file_io",
      parent_message_id: null,
      ...RAW,
    } as never);
    for (const r of state.renderers) {
      expect(r.trace_id).toBe(TRACE);
    }
  });
});
