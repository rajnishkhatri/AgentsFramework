/**
 * L1 tests for AG-UI events (mirrors Python `agent_ui_adapter/wire/ag_ui_events.py`).
 *
 * The 17 AG-UI native events form a Zod discriminated union on `type` (W3).
 * Per plan §4.3 Option B, `trace_id` rides in `raw_event.trace_id`. Failure
 * paths first (Check 4).
 */

import { describe, expect, it } from "vitest";
import {
  AGUI_PINNED_VERSION,
  AGUIEventSchema,
  CustomSchema,
  EventTypeSchema,
  MessagesSnapshotSchema,
  RawSchema,
  RunErrorSchema,
  RunFinishedSchema,
  RunStartedSchema,
  StateDeltaSchema,
  StateSnapshotSchema,
  StepFinishedSchema,
  StepStartedSchema,
  TextMessageContentSchema,
  TextMessageEndSchema,
  TextMessageStartSchema,
  ToolCallArgsSchema,
  ToolCallEndSchema,
  ToolCallStartSchema,
  ToolResultSchema,
} from "./ag_ui_events";

// ── Pinned version invariant ──────────────────────────────────────────

describe("AGUI_PINNED_VERSION", () => {
  it("matches the Python ag_ui_events.AGUI_PINNED_VERSION constant", () => {
    expect(AGUI_PINNED_VERSION).toBe("0.1.18");
  });
});

// ── EventType enum (17 native types) ──────────────────────────────────

describe("EventTypeSchema", () => {
  it("includes exactly the 17 native AG-UI event types", () => {
    const expected = [
      "RUN_STARTED",
      "RUN_FINISHED",
      "RUN_ERROR",
      "STEP_STARTED",
      "STEP_FINISHED",
      "TEXT_MESSAGE_START",
      "TEXT_MESSAGE_CONTENT",
      "TEXT_MESSAGE_END",
      "TOOL_CALL_START",
      "TOOL_CALL_ARGS",
      "TOOL_CALL_END",
      "TOOL_RESULT",
      "STATE_SNAPSHOT",
      "STATE_DELTA",
      "MESSAGES_SNAPSHOT",
      "RAW",
      "CUSTOM",
    ];
    for (const t of expected) {
      expect(EventTypeSchema.parse(t)).toBe(t);
    }
    expect(() => EventTypeSchema.parse("UNKNOWN_EVENT")).toThrow();
  });
});

// ── Discriminated union (W3) ──────────────────────────────────────────

describe("AGUIEventSchema discriminated union [W3]", () => {
  it("rejects an event with an unknown discriminator", () => {
    const r = AGUIEventSchema.safeParse({ type: "BOGUS", run_id: "r1", thread_id: "t1" });
    expect(r.success).toBe(false);
  });

  it("rejects RunStarted missing run_id", () => {
    const r = AGUIEventSchema.safeParse({ type: "RUN_STARTED", thread_id: "t1" });
    expect(r.success).toBe(false);
  });

  it("routes RUN_STARTED to RunStarted shape", () => {
    const evt = AGUIEventSchema.parse({
      type: "RUN_STARTED",
      run_id: "r1",
      thread_id: "t1",
      raw_event: { trace_id: "trace-001" },
    });
    expect(evt.type).toBe("RUN_STARTED");
  });

  it("routes TOOL_CALL_START to ToolCallStart with optional parent_message_id", () => {
    const evt = AGUIEventSchema.parse({
      type: "TOOL_CALL_START",
      tool_call_id: "tc1",
      tool_call_name: "shell",
      raw_event: { trace_id: "trace-001" },
    });
    expect(evt.type).toBe("TOOL_CALL_START");
  });

  it("routes CUSTOM to Custom with arbitrary payload", () => {
    const evt = AGUIEventSchema.parse({
      type: "CUSTOM",
      name: "step_meter",
      value: { step: 3 },
    });
    expect(evt.type).toBe("CUSTOM");
  });
});

// ── trace_id transport via raw_event (Plan §4.3 Option B) ─────────────

describe("trace_id rides in raw_event [§4.3 Option B / W5]", () => {
  it("accepts events with raw_event.trace_id present", () => {
    const evt = RunStartedSchema.parse({
      type: "RUN_STARTED",
      run_id: "r1",
      thread_id: "t1",
      raw_event: { trace_id: "trace-001" },
    });
    expect(evt.raw_event?.trace_id).toBe("trace-001");
  });

  it("accepts events without raw_event (raw_event is optional like Python)", () => {
    // Python: raw_event: dict | None = None. Some emitters may omit it
    // (e.g. Custom events synthesized client-side); the SSE client and
    // translator are responsible for synthesizing trace_id when missing.
    const evt = RunFinishedSchema.parse({
      type: "RUN_FINISHED",
      run_id: "r1",
      thread_id: "t1",
    });
    expect(evt.raw_event).toBeNull();
  });
});

// ── Per-variant smoke tests (one per shape; W3 enforcement) ───────────

describe("Per-variant minimal acceptance", () => {
  const RAW = { raw_event: { trace_id: "trace-001" } };

  it.each([
    ["RUN_STARTED", RunStartedSchema, { run_id: "r1", thread_id: "t1" }],
    ["RUN_FINISHED", RunFinishedSchema, { run_id: "r1", thread_id: "t1" }],
    [
      "RUN_ERROR",
      RunErrorSchema,
      { run_id: "r1", thread_id: "t1", message: "boom" },
    ],
    ["STEP_STARTED", StepStartedSchema, { step_name: "react" }],
    ["STEP_FINISHED", StepFinishedSchema, { step_name: "react" }],
    [
      "TEXT_MESSAGE_START",
      TextMessageStartSchema,
      { message_id: "m1", role: "assistant" },
    ],
    [
      "TEXT_MESSAGE_CONTENT",
      TextMessageContentSchema,
      { message_id: "m1", delta: "Hi" },
    ],
    ["TEXT_MESSAGE_END", TextMessageEndSchema, { message_id: "m1" }],
    [
      "TOOL_CALL_START",
      ToolCallStartSchema,
      { tool_call_id: "tc1", tool_call_name: "shell" },
    ],
    ["TOOL_CALL_ARGS", ToolCallArgsSchema, { tool_call_id: "tc1", delta: "x" }],
    ["TOOL_CALL_END", ToolCallEndSchema, { tool_call_id: "tc1" }],
    [
      "TOOL_RESULT",
      ToolResultSchema,
      { tool_call_id: "tc1", content: "ok", role: "tool" },
    ],
    ["STATE_SNAPSHOT", StateSnapshotSchema, { snapshot: { foo: "bar" } }],
    ["STATE_DELTA", StateDeltaSchema, { delta: [{ op: "add" }] }],
    [
      "MESSAGES_SNAPSHOT",
      MessagesSnapshotSchema,
      { messages: [{ role: "user", content: "hi" }] },
    ],
    ["RAW", RawSchema, { event: "tick", source: "edge" }],
    ["CUSTOM", CustomSchema, { name: "step_meter", value: { step: 3 } }],
  ])("accepts %s", (typeStr, schema, payload) => {
    const v = (schema as any).parse({ type: typeStr, ...payload, ...RAW });
    expect(v.type).toBe(typeStr);
  });
});
