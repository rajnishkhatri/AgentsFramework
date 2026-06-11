/**
 * run_phase tests (eval-UI F8). Pure (view) -> phase derivation.
 *
 * Failure paths first: an errored run must never read as `done`, and the
 * phase is derived from real event-fed view state, never timers
 * (Anti-Pattern: Determinism Theater).
 */

import { describe, expect, it } from "vitest";
import { emptyRunView, reduceRunView } from "./run_view_reducer";
import type { AssistantRunView } from "./run_view_reducer";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";
import { deriveRunPhase } from "./run_phase";

const TRACE = "trace-phase-1";

function started(): UIRuntimeEvent {
  return { type: "run_started", trace_id: TRACE, run_id: "r1", thread_id: "t1" };
}
function delta(text: string): UIRuntimeEvent {
  return { type: "chat_message_delta", trace_id: TRACE, message_id: "m1", delta: text };
}
function tool(status: "running" | "completed"): UIRuntimeEvent {
  return {
    type: "tool_render",
    trace_id: TRACE,
    request: {
      trace_id: TRACE,
      tool_call_id: "tc1",
      tool_name: "file_io",
      input: {},
      status,
      output: status === "completed" ? "ok" : null,
    },
  };
}

function view(...events: UIRuntimeEvent[]): AssistantRunView {
  return events.reduce(reduceRunView, emptyRunView());
}

describe("deriveRunPhase — failure paths first", () => {
  it("an errored run is 'error', never 'done'", () => {
    const v = view(started(), delta("partial"), {
      type: "run_error",
      trace_id: TRACE,
      run_id: "r1",
      error_type: "server_error",
      message: "boom",
    });
    expect(deriveRunPhase(v)).toBe("error");
  });

  it("a completed tool with no further activity does not regress to 'tool'", () => {
    const v = view(started(), tool("running"), tool("completed"), delta("Done."));
    expect(deriveRunPhase(v)).toBe("writing");
  });
});

describe("deriveRunPhase — progression", () => {
  it("no run_started yet → connecting", () => {
    expect(deriveRunPhase(emptyRunView())).toBe("connecting");
  });

  it("run started, no output yet → thinking", () => {
    expect(deriveRunPhase(view(started()))).toBe("thinking");
  });

  it("a running tool → tool", () => {
    expect(deriveRunPhase(view(started(), tool("running")))).toBe("tool");
  });

  it("text streaming after tools → writing", () => {
    expect(deriveRunPhase(view(started(), delta("Hello")))).toBe("writing");
  });

  it("run completed → done", () => {
    const v = view(started(), delta("answer"), {
      type: "run_completed",
      trace_id: TRACE,
      run_id: "r1",
      thread_id: "t1",
    });
    expect(deriveRunPhase(v)).toBe("done");
  });
});
