/**
 * run_view_reducer tests (eval-UI F1, plan §3-F1 / §8.7).
 *
 * Failure paths first (TAP-4): error terminal state, events after a
 * terminal event, unknown-shape tolerance -- before the happy path.
 *
 * The reducer is the per-assistant-message view state behind the F1 port
 * wiring: {status, segments[], step, traceId} derived purely from
 * UIRuntimeEvents (F-R1: no run-lifecycle logic in components).
 */

import { describe, expect, it } from "vitest";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";
import {
  emptyRunView,
  reduceRunView,
  type AssistantRunView,
} from "./run_view_reducer";

const TRACE = "trace-rv-1";

function started(): UIRuntimeEvent {
  return {
    type: "run_started",
    trace_id: TRACE,
    run_id: "r1",
    thread_id: "t1",
  };
}

function delta(text: string): UIRuntimeEvent {
  return {
    type: "chat_message_delta",
    trace_id: TRACE,
    message_id: "m1",
    delta: text,
  };
}

function toolRender(
  id: string,
  status: "running" | "completed" | "errored",
  output: string | null = null,
): UIRuntimeEvent {
  return {
    type: "tool_render",
    trace_id: TRACE,
    request: {
      trace_id: TRACE,
      tool_call_id: id,
      tool_name: "file_io",
      input: { path: "/tmp/x" },
      status,
      output,
    },
  };
}

function completed(): UIRuntimeEvent {
  return {
    type: "run_completed",
    trace_id: TRACE,
    run_id: "r1",
    thread_id: "t1",
  };
}

function errored(message = "boom"): UIRuntimeEvent {
  return {
    type: "run_error",
    trace_id: TRACE,
    run_id: "r1",
    error_type: "server_error",
    message,
  };
}

function reduceAll(events: UIRuntimeEvent[]): AssistantRunView {
  return events.reduce(reduceRunView, emptyRunView());
}

describe("run_view_reducer — failure paths first", () => {
  it("run_error flips status to error and records the message", () => {
    const view = reduceAll([started(), delta("partial"), errored("backend 500")]);
    expect(view.status).toBe("error");
    expect(view.errorMessage).toBe("backend 500");
    // Partial output is preserved as evidence -- never wiped.
    expect(view.segments).toEqual([{ kind: "text", text: "partial" }]);
  });

  it("ignores events arriving after a terminal run_completed (frozen view)", () => {
    const view = reduceAll([started(), delta("answer"), completed(), delta("late")]);
    expect(view.status).toBe("complete");
    expect(view.segments).toEqual([{ kind: "text", text: "answer" }]);
  });

  it("ignores events arriving after a terminal run_error (frozen view)", () => {
    const view = reduceAll([started(), errored(), delta("late")]);
    expect(view.status).toBe("error");
    expect(view.segments).toEqual([]);
  });

  it("a stream with no terminal event leaves status streaming (caller surfaces it)", () => {
    const view = reduceAll([started(), delta("text")]);
    expect(view.status).toBe("streaming");
  });

  it("a malformed state_render payload is tolerated and changes nothing", () => {
    const before = reduceAll([started(), delta("x")]);
    const after = reduceRunView(before, {
      type: "state_render",
      trace_id: TRACE,
      key: "delta",
      value: "garbage",
    });
    expect(after).toBe(before);
  });

  it("a /todos state_render delta populates the checklist without touching segments (F9)", () => {
    const before = reduceAll([started(), delta("x")]);
    const after = reduceRunView(before, {
      type: "state_render",
      trace_id: TRACE,
      key: "delta",
      value: [
        {
          op: "replace",
          path: "/todos",
          value: [
            { id: "t1", content: "read file", status: "completed" },
            { id: "t2", content: "write file", status: "pending" },
          ],
        },
      ],
    });
    expect(after.segments).toEqual(before.segments);
    expect(after.todos?.total).toBe(2);
    expect(after.todos?.done).toBe(1);
  });
});

describe("run_view_reducer — trajectory assembly", () => {
  it("starts empty and streaming with no identity", () => {
    const view = emptyRunView();
    expect(view.status).toBe("streaming");
    expect(view.segments).toEqual([]);
    expect(view.traceId).toBeNull();
    expect(view.runId).toBeNull();
  });

  it("run_started captures forwarded trace/run/thread ids (F-R7: never generated)", () => {
    const view = reduceAll([started()]);
    expect(view.traceId).toBe(TRACE);
    expect(view.runId).toBe("r1");
    expect(view.threadId).toBe("t1");
  });

  it("consecutive text deltas merge into one text segment", () => {
    const view = reduceAll([started(), delta("Hel"), delta("lo")]);
    expect(view.segments).toEqual([{ kind: "text", text: "Hello" }]);
  });

  it("segments interleave in trajectory order: text → tool → text", () => {
    const view = reduceAll([
      started(),
      delta("Reading file… "),
      toolRender("tc1", "running"),
      delta("Done."),
    ]);
    expect(view.segments.map((s) => s.kind)).toEqual(["text", "tool", "text"]);
  });

  it("a tool_render update replaces the existing segment in place (no duplicate card)", () => {
    const view = reduceAll([
      started(),
      toolRender("tc1", "running"),
      delta("between"),
      toolRender("tc1", "completed", "42"),
    ]);
    expect(view.segments.map((s) => s.kind)).toEqual(["tool", "text"]);
    const tool = view.segments[0];
    if (tool?.kind !== "tool") throw new Error("expected tool segment");
    expect(tool.request.status).toBe("completed");
    expect(tool.request.output).toBe("42");
  });

  it("two distinct tool calls produce two segments in call order", () => {
    const view = reduceAll([
      started(),
      toolRender("tc1", "running"),
      toolRender("tc2", "running"),
      toolRender("tc1", "completed", "a"),
    ]);
    const ids = view.segments.map((s) =>
      s.kind === "tool" ? s.request.tool_call_id : "",
    );
    expect(ids).toEqual(["tc1", "tc2"]);
  });

  it("a /selected_model state delta populates the model badge (F5)", () => {
    const view = reduceAll([started()]);
    const after = reduceRunView(view, {
      type: "state_render",
      trace_id: TRACE,
      key: "delta",
      value: [{ op: "replace", path: "/selected_model", value: "haiku-tier" }],
    });
    expect(after.modelBadge).toBe("haiku-tier");
  });

  it("a malformed /selected_model value is ignored (failure path)", () => {
    const view = reduceAll([started()]);
    const after = reduceRunView(view, {
      type: "state_render",
      trace_id: TRACE,
      key: "delta",
      value: [{ op: "replace", path: "/selected_model", value: 42 }],
    });
    expect(after.modelBadge).toBeNull();
  });

  it("step_progress updates the step meter view", () => {
    const view = reduceAll([
      started(),
      { type: "step_progress", trace_id: TRACE, step: 2, step_name: "evaluation" },
    ]);
    expect(view.step).toEqual({ count: 2, name: "evaluation" });
  });

  it("run_completed flips status to complete and keeps the trajectory", () => {
    const view = reduceAll([
      started(),
      delta("answer"),
      toolRender("tc1", "completed", "ok"),
      completed(),
    ]);
    expect(view.status).toBe("complete");
    expect(view.segments).toHaveLength(2);
  });

  it("never mutates the prior view (pure reducer)", () => {
    const v0 = reduceAll([started()]);
    const frozen = JSON.parse(JSON.stringify(v0));
    reduceRunView(v0, delta("x"));
    expect(v0).toEqual(frozen);
  });
});

describe("run_view_reducer — reasoning recap (F10 Tier-2)", () => {
  it("emptyRunView carries no reasoning", () => {
    expect(emptyRunView().reasoning).toBeNull();
  });

  it("reasoning_summary populates view.reasoning without touching segments", () => {
    const before = reduceAll([started(), delta("answer")]);
    const after = reduceRunView(before, {
      type: "reasoning_summary",
      trace_id: TRACE,
      text: "Did A then B because C.",
    });
    expect(after.reasoning).toBe("Did A then B because C.");
    expect(after.segments).toEqual(before.segments);
  });

  it("reasoning arriving before run_completed survives the terminal freeze", () => {
    const view = reduceAll([
      started(),
      delta("answer"),
      { type: "reasoning_summary", trace_id: TRACE, text: "recap" },
      completed(),
    ]);
    expect(view.status).toBe("complete");
    expect(view.reasoning).toBe("recap");
  });
});

describe("run_view_reducer — task understanding card (Phase 3)", () => {
  const artifact = {
    type: "task_understanding" as const,
    trace_id: TRACE,
    restated_intent: "Create the file and verify it.",
    success_conditions: ["file exists", "contents verified"],
    confidence: 0.8,
    source: "generated" as const,
  };

  it("emptyRunView carries no understanding", () => {
    expect(emptyRunView().understanding).toBeNull();
  });

  it("task_understanding populates view.understanding without touching segments", () => {
    const before = reduceAll([started(), delta("streaming answer")]);
    const after = reduceRunView(before, artifact);
    expect(after.understanding).toMatchObject({
      restated_intent: "Create the file and verify it.",
      success_conditions: ["file exists", "contents verified"],
      source: "generated",
    });
    expect(after.segments).toEqual(before.segments);
  });

  it("a later artifact (user edit) replaces the card content", () => {
    const v = reduceAll([
      started(),
      artifact,
      { ...artifact, success_conditions: ["file exists"], source: "user_edited" as const },
    ]);
    expect(v.understanding?.source).toBe("user_edited");
    expect(v.understanding?.success_conditions).toEqual(["file exists"]);
  });

  it("understanding survives the terminal freeze", () => {
    const v = reduceAll([started(), artifact, completed()]);
    expect(v.status).toBe("complete");
    expect(v.understanding?.restated_intent).toBe("Create the file and verify it.");
  });
});
