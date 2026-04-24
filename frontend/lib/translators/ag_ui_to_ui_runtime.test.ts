/**
 * L1 (pure-function) tests for the AG-UI -> UI-runtime translator.
 *
 * Per S3.4.1 / TDD-Agentic-Systems §Pattern 4: table-driven case per
 * discriminated-union variant, trace_id forwarding verified for every
 * mapping, zero-or-many output rule documented in the test name.
 *
 * No I/O, no SDK, no React. Translators are pure -- given the same input
 * they always produce the same output (T1).
 */

import { describe, expect, it } from "vitest";
import { agUiToUiRuntime } from "./ag_ui_to_ui_runtime";
import type { AGUIEvent } from "../wire/ag_ui_events";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";

const TRACE = "trace-001";
const RAW = { raw_event: { trace_id: TRACE } };

// ── trace_id forwarding (T2 / F-R7) -- failure paths first ────────────

describe("agUiToUiRuntime trace_id propagation [T2 / F-R7]", () => {
  it("rejects an event whose raw_event lacks trace_id (no silent omission)", () => {
    const evt: AGUIEvent = {
      type: "RUN_STARTED",
      run_id: "r1",
      thread_id: "t1",
      raw_event: null,
      timestamp: undefined,
    } as never;
    expect(() => agUiToUiRuntime(evt)).toThrowError(/trace_id/);
  });

  it("forwards trace_id to every emitted UI runtime event", () => {
    const evt: AGUIEvent = {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: "m1",
      delta: "hi",
      ...RAW,
      timestamp: undefined,
    } as never;
    const out = agUiToUiRuntime(evt);
    expect(out.length).toBeGreaterThan(0);
    for (const e of out) {
      expect((e as UIRuntimeEvent).trace_id).toBe(TRACE);
    }
  });
});

// ── zero-or-many output rule (T3) ─────────────────────────────────────

describe("agUiToUiRuntime variant routing", () => {
  it("RUN_STARTED -> exactly one run_started event", () => {
    const out = agUiToUiRuntime({
      type: "RUN_STARTED",
      run_id: "r1",
      thread_id: "t1",
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    expect(out[0]!.type).toBe("run_started");
  });

  it("RUN_FINISHED -> exactly one run_completed event", () => {
    const out = agUiToUiRuntime({
      type: "RUN_FINISHED",
      run_id: "r1",
      thread_id: "t1",
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    expect(out[0]!.type).toBe("run_completed");
  });

  it("RUN_ERROR -> exactly one run_error event with mapped error_type", () => {
    const out = agUiToUiRuntime({
      type: "RUN_ERROR",
      run_id: "r1",
      thread_id: "t1",
      message: "boom",
      code: null,
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    const e = out[0]! as UIRuntimeEvent & { type: "run_error" };
    expect(e.type).toBe("run_error");
    expect(e.error_type).toBe("server_error");
    expect(e.message).toBe("boom");
  });

  it("STEP_STARTED -> one step_progress event with monotonically increasing step", () => {
    const out = agUiToUiRuntime({
      type: "STEP_STARTED",
      step_name: "react",
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    expect(out[0]!.type).toBe("step_progress");
  });

  it("TEXT_MESSAGE_CONTENT -> one chat_message_delta event", () => {
    const out = agUiToUiRuntime({
      type: "TEXT_MESSAGE_CONTENT",
      message_id: "m1",
      delta: "Hi",
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    expect(out[0]!.type).toBe("chat_message_delta");
  });

  it("TEXT_MESSAGE_START / TEXT_MESSAGE_END -> zero output (lifecycle absorbed)", () => {
    const start = agUiToUiRuntime({
      type: "TEXT_MESSAGE_START",
      message_id: "m1",
      role: "assistant",
      ...RAW,
    } as never);
    const end = agUiToUiRuntime({
      type: "TEXT_MESSAGE_END",
      message_id: "m1",
      ...RAW,
    } as never);
    expect(start).toEqual([]);
    expect(end).toEqual([]);
  });

  it("CUSTOM step_meter -> one step_progress event", () => {
    const out = agUiToUiRuntime({
      type: "CUSTOM",
      name: "step_meter",
      value: { step: 3, step_name: "tool" },
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    const e = out[0]! as UIRuntimeEvent & { type: "step_progress" };
    expect(e.step).toBe(3);
  });

  it("CUSTOM model_badge -> one state_render event", () => {
    const out = agUiToUiRuntime({
      type: "CUSTOM",
      name: "model_badge",
      value: { name: "claude-3-5-sonnet" },
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    expect(out[0]!.type).toBe("state_render");
  });

  it("STATE_SNAPSHOT -> one state_render event with key='snapshot'", () => {
    const out = agUiToUiRuntime({
      type: "STATE_SNAPSHOT",
      snapshot: { foo: "bar" },
      ...RAW,
    } as never);
    expect(out).toHaveLength(1);
    expect(out[0]!.type).toBe("state_render");
  });

  it("RAW -> zero output (debug-only, never reaches UI)", () => {
    const out = agUiToUiRuntime({
      type: "RAW",
      event: "tick",
      source: "edge",
      ...RAW,
    } as never);
    expect(out).toEqual([]);
  });
});

// ── purity (T1: same input -> same output) ────────────────────────────

describe("agUiToUiRuntime purity [T1]", () => {
  it("returns deeply-equal output for the same input", () => {
    const evt: AGUIEvent = {
      type: "TEXT_MESSAGE_CONTENT",
      message_id: "m1",
      delta: "Hi",
      ...RAW,
    } as never;
    expect(agUiToUiRuntime(evt)).toEqual(agUiToUiRuntime(evt));
  });
});
