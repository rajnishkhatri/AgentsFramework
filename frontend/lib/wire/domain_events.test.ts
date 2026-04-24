/**
 * L1 tests for canonical domain events (mirrors Python
 * `agent_ui_adapter/wire/domain_events.py`). Every event carries `trace_id`
 * and is `extra: 'forbid'` / immutable in the producer (we don't enforce
 * `Object.freeze` on parse, but the schema rejects extra fields).
 *
 * Failure paths first (rejection tests precede acceptance tests).
 */

import { describe, expect, it } from "vitest";
import {
  DomainEventSchema,
  LLMMessageEndedSchema,
  LLMMessageStartedSchema,
  LLMTokenEmittedSchema,
  RunFinishedDomainSchema,
  RunStartedDomainSchema,
  StateMutatedSchema,
  ToolCallEndedSchema,
  ToolCallStartedSchema,
  ToolResultReceivedSchema,
} from "./domain_events";
import type { DomainEvent } from "./domain_events";

const TRACE = "trace-001";
const TS = "2026-04-24T00:00:00.000Z";

// ── trace_id presence (W5: every event extends BaseEvent with trace_id) ─

describe("Domain event trace_id requirement [W5]", () => {
  it("rejects LLMTokenEmitted without trace_id", () => {
    const r = LLMTokenEmittedSchema.safeParse({ message_id: "m1", delta: "x" });
    expect(r.success).toBe(false);
  });

  it("rejects RunStartedDomain with empty trace_id", () => {
    const r = RunStartedDomainSchema.safeParse({
      trace_id: "",
      run_id: "r1",
      thread_id: "t1",
    });
    expect(r.success).toBe(false);
  });
});

// ── extra='forbid' parity ─────────────────────────────────────────────

describe("Domain events forbid extra fields", () => {
  it("rejects unknown fields on ToolCallStarted", () => {
    const r = ToolCallStartedSchema.safeParse({
      trace_id: TRACE,
      tool_call_id: "tc1",
      tool_name: "shell",
      args_json: "{}",
      surprise: 1,
    });
    expect(r.success).toBe(false);
  });
});

// ── individual acceptance ─────────────────────────────────────────────

describe("LLM lifecycle events", () => {
  it("accepts LLMMessageStarted", () => {
    const v = LLMMessageStartedSchema.parse({ trace_id: TRACE, message_id: "m1" });
    expect(v.message_id).toBe("m1");
  });

  it("accepts LLMTokenEmitted with delta", () => {
    const v = LLMTokenEmittedSchema.parse({
      trace_id: TRACE,
      message_id: "m1",
      delta: "Hello",
    });
    expect(v.delta).toBe("Hello");
  });

  it("accepts LLMMessageEnded", () => {
    const v = LLMMessageEndedSchema.parse({ trace_id: TRACE, message_id: "m1" });
    expect(v.message_id).toBe("m1");
  });
});

describe("Tool lifecycle events", () => {
  it("accepts ToolCallStarted with stringified args", () => {
    const v = ToolCallStartedSchema.parse({
      trace_id: TRACE,
      tool_call_id: "tc1",
      tool_name: "shell",
      args_json: '{"cmd":"ls"}',
    });
    expect(v.tool_name).toBe("shell");
  });

  it("accepts ToolCallEnded", () => {
    const v = ToolCallEndedSchema.parse({ trace_id: TRACE, tool_call_id: "tc1" });
    expect(v.tool_call_id).toBe("tc1");
  });

  it("accepts ToolResultReceived", () => {
    const v = ToolResultReceivedSchema.parse({
      trace_id: TRACE,
      tool_call_id: "tc1",
      result: "ok",
    });
    expect(v.result).toBe("ok");
  });
});

describe("Run lifecycle events", () => {
  it("accepts RunStartedDomain", () => {
    const v = RunStartedDomainSchema.parse({
      trace_id: TRACE,
      run_id: "r1",
      thread_id: "t1",
    });
    expect(v.run_id).toBe("r1");
  });

  it("accepts RunFinishedDomain with no error", () => {
    const v = RunFinishedDomainSchema.parse({
      trace_id: TRACE,
      run_id: "r1",
      thread_id: "t1",
    });
    expect(v.error).toBeNull();
  });

  it("accepts RunFinishedDomain with error message", () => {
    const v = RunFinishedDomainSchema.parse({
      trace_id: TRACE,
      run_id: "r1",
      thread_id: "t1",
      error: "boom",
    });
    expect(v.error).toBe("boom");
  });
});

describe("StateMutated", () => {
  it("accepts a snapshot-only mutation", () => {
    const v = StateMutatedSchema.parse({
      trace_id: TRACE,
      timestamp: TS,
      snapshot: { foo: "bar" },
    });
    expect(v.snapshot).toEqual({ foo: "bar" });
    expect(v.delta).toBeNull();
  });

  it("accepts a delta-only mutation (JSON Patch)", () => {
    const v = StateMutatedSchema.parse({
      trace_id: TRACE,
      delta: [{ op: "add", path: "/foo", value: "bar" }],
    });
    expect(v.delta).toHaveLength(1);
  });
});

// ── DomainEvent union (T3 zero-or-many) ────────────────────────────────

describe("DomainEventSchema (variant routing)", () => {
  it("parses every variant via the union", () => {
    const samples: DomainEvent[] = [
      LLMTokenEmittedSchema.parse({ trace_id: TRACE, message_id: "m1", delta: "x" }),
      ToolCallEndedSchema.parse({ trace_id: TRACE, tool_call_id: "tc1" }),
      RunStartedDomainSchema.parse({ trace_id: TRACE, run_id: "r1", thread_id: "t1" }),
    ];
    for (const s of samples) {
      expect(DomainEventSchema.parse(s)).toBeTruthy();
    }
  });

  it("rejects an event missing trace_id at the union level", () => {
    const r = DomainEventSchema.safeParse({ message_id: "m1", delta: "x" });
    expect(r.success).toBe(false);
  });
});
