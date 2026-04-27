/**
 * L1 tests for the UI-runtime event kernel.
 *
 * These are the narrowed shapes the UI runtime (CopilotKit hooks, useFrontendTool,
 * useComponent, useCoAgentStateRender) consumes after translation. They are
 * frontend-only and have no Python equivalent -- they sit at the boundary
 * between `translators/ag_ui_to_ui_runtime.ts` and the UI components.
 *
 * Per F-R7 / W5: every event keeps the `trace_id` forwarded from the wire so
 * cross-layer correlation survives the AG-UI -> UI-runtime hop.
 *
 * Failure paths first (Check 4).
 */

import { describe, expect, it } from "vitest";
import {
  ChatMessageDeltaEventSchema,
  RunCompletedEventSchema,
  RunErrorEventSchema,
  RunStartedEventSchema,
  StateRenderEventSchema,
  StepProgressEventSchema,
  ToolCallRendererRequestSchema,
  UIRuntimeEventSchema,
} from "./ui_runtime_events";
import type { UIRuntimeEvent } from "./ui_runtime_events";

const TRACE = "trace-001";

// ── trace_id presence (F-R7 / W5) ─────────────────────────────────────

describe("UI runtime event trace_id requirement [F-R7]", () => {
  it("rejects RunStartedEvent without trace_id", () => {
    const r = RunStartedEventSchema.safeParse({
      type: "run_started",
      run_id: "r1",
      thread_id: "t1",
    });
    expect(r.success).toBe(false);
  });

  it("rejects RunErrorEvent with empty trace_id", () => {
    const r = RunErrorEventSchema.safeParse({
      type: "run_error",
      trace_id: "",
      run_id: "r1",
      error_type: "wire_parse_error",
      message: "oops",
    });
    expect(r.success).toBe(false);
  });
});

// ── Chat message stream ───────────────────────────────────────────────

describe("ChatMessageDeltaEventSchema", () => {
  it("rejects when delta is empty", () => {
    const r = ChatMessageDeltaEventSchema.safeParse({
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "m1",
      delta: "",
    });
    expect(r.success).toBe(false);
  });

  it("accepts a valid streaming delta", () => {
    const v = ChatMessageDeltaEventSchema.parse({
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "m1",
      delta: "Hello, ",
    });
    expect(v.delta).toBe("Hello, ");
  });
});

// ── Run lifecycle ─────────────────────────────────────────────────────

describe("Run lifecycle events", () => {
  it("accepts RunStartedEvent", () => {
    const v = RunStartedEventSchema.parse({
      type: "run_started",
      trace_id: TRACE,
      run_id: "r1",
      thread_id: "t1",
    });
    expect(v.run_id).toBe("r1");
  });

  it("accepts RunCompletedEvent", () => {
    const v = RunCompletedEventSchema.parse({
      type: "run_completed",
      trace_id: TRACE,
      run_id: "r1",
      thread_id: "t1",
    });
    expect(v.type).toBe("run_completed");
  });

  it("requires error_type to be in the typed enum (X2 wire_parse_error)", () => {
    const r = RunErrorEventSchema.safeParse({
      type: "run_error",
      trace_id: TRACE,
      run_id: "r1",
      error_type: "made_up_kind",
      message: "boom",
    });
    expect(r.success).toBe(false);
  });

  it("accepts the documented error_type values", () => {
    for (const error_type of [
      "wire_parse_error",
      "auth_error",
      "authorization_error",
      "rate_limit_error",
      "server_error",
      "network_error",
      "cancelled",
    ] as const) {
      const v = RunErrorEventSchema.parse({
        type: "run_error",
        trace_id: TRACE,
        run_id: "r1",
        error_type,
        message: "oops",
      });
      expect(v.error_type).toBe(error_type);
    }
  });
});

// ── Step / state render (F6 step meter, F7 model badge) ───────────────

describe("StepProgressEvent (F6 step meter)", () => {
  it("rejects negative step number", () => {
    const r = StepProgressEventSchema.safeParse({
      type: "step_progress",
      trace_id: TRACE,
      step: -1,
      step_name: "react",
    });
    expect(r.success).toBe(false);
  });

  it("accepts non-negative step counters", () => {
    const v = StepProgressEventSchema.parse({
      type: "step_progress",
      trace_id: TRACE,
      step: 3,
      step_name: "react",
    });
    expect(v.step).toBe(3);
  });
});

describe("StateRenderEvent (CoAgent state)", () => {
  it("accepts a model badge state-render event", () => {
    const v = StateRenderEventSchema.parse({
      type: "state_render",
      trace_id: TRACE,
      key: "model",
      value: { name: "claude-3-5-sonnet", provider: "anthropic" },
    });
    expect(v.key).toBe("model");
  });
});

// ── Tool renderer request ─────────────────────────────────────────────

describe("ToolCallRendererRequest", () => {
  it("rejects when tool_call_id is missing", () => {
    const r = ToolCallRendererRequestSchema.safeParse({
      trace_id: TRACE,
      tool_name: "shell",
      input: {},
    });
    expect(r.success).toBe(false);
  });

  it("accepts an in-flight tool render request with no output yet", () => {
    const v = ToolCallRendererRequestSchema.parse({
      trace_id: TRACE,
      tool_call_id: "tc1",
      tool_name: "shell",
      input: { cmd: "ls" },
      status: "running",
      output: null,
    });
    expect(v.status).toBe("running");
    expect(v.output).toBeNull();
  });

  it("accepts a completed tool render with string output", () => {
    const v = ToolCallRendererRequestSchema.parse({
      trace_id: TRACE,
      tool_call_id: "tc1",
      tool_name: "shell",
      input: { cmd: "ls" },
      status: "completed",
      output: "file1\nfile2",
    });
    expect(v.status).toBe("completed");
  });
});

// ── UI runtime union ──────────────────────────────────────────────────

describe("UIRuntimeEventSchema (discriminated union)", () => {
  it("routes through every variant", () => {
    const samples: UIRuntimeEvent[] = [
      RunStartedEventSchema.parse({
        type: "run_started",
        trace_id: TRACE,
        run_id: "r1",
        thread_id: "t1",
      }),
      ChatMessageDeltaEventSchema.parse({
        type: "chat_message_delta",
        trace_id: TRACE,
        message_id: "m1",
        delta: "Hi",
      }),
      StepProgressEventSchema.parse({
        type: "step_progress",
        trace_id: TRACE,
        step: 1,
        step_name: "tool",
      }),
    ];
    for (const s of samples) {
      expect(UIRuntimeEventSchema.parse(s)).toBeTruthy();
    }
  });
});
