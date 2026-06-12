/**
 * fallback_answer tests (eval-UI F11, decision D-C).
 *
 * The empty answer slot IS the bug under test (GJ-F-008/GJ-012 root
 * cause): a completed run must NEVER leave the answer empty. Failure
 * paths first.
 */

import { describe, expect, it } from "vitest";
import { emptyRunView, reduceRunView } from "./run_view_reducer";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";
import { synthesizeFallbackAnswer } from "./fallback_answer";

const TRACE = "trace-fb-1";

function started(): UIRuntimeEvent {
  return { type: "run_started", trace_id: TRACE, run_id: "r1", thread_id: "t1" };
}
function completed(): UIRuntimeEvent {
  return { type: "run_completed", trace_id: TRACE, run_id: "r1", thread_id: "t1" };
}
function delta(text: string): UIRuntimeEvent {
  return { type: "chat_message_delta", trace_id: TRACE, message_id: "m1", delta: text };
}
function tool(name: string, input: Record<string, unknown>): UIRuntimeEvent {
  return {
    type: "tool_render",
    trace_id: TRACE,
    request: {
      trace_id: TRACE,
      tool_call_id: `tc-${name}`,
      tool_name: name,
      input,
      status: "completed",
      output: "ok",
    },
  };
}

function viewOf(...events: UIRuntimeEvent[]) {
  return events.reduce(reduceRunView, emptyRunView());
}

describe("synthesizeFallbackAnswer — failure paths first", () => {
  it("a completed run with NO text and NO tools still gets a non-empty answer", () => {
    const fallback = synthesizeFallbackAnswer(viewOf(started(), completed()));
    expect(fallback).toBeTruthy();
    expect(fallback!.length).toBeGreaterThan(0);
  });

  it("whitespace-only text does not count as an answer", () => {
    const fallback = synthesizeFallbackAnswer(
      viewOf(started(), delta("   \n"), completed()),
    );
    expect(fallback).toBeTruthy();
  });

  it("an errored run yields no fallback (the error slot owns that state)", () => {
    const fallback = synthesizeFallbackAnswer(
      viewOf(started(), {
        type: "run_error",
        trace_id: TRACE,
        run_id: "r1",
        error_type: "server_error",
        message: "boom",
      }),
    );
    expect(fallback).toBeNull();
  });

  it("a still-streaming run yields no fallback", () => {
    expect(synthesizeFallbackAnswer(viewOf(started()))).toBeNull();
  });
});

describe("synthesizeFallbackAnswer — recap synthesis", () => {
  it("a real text answer suppresses the fallback", () => {
    const fallback = synthesizeFallbackAnswer(
      viewOf(started(), delta("Here is the answer."), completed()),
    );
    expect(fallback).toBeNull();
  });

  it("a tool-only run recaps the trajectory deterministically", () => {
    const fallback = synthesizeFallbackAnswer(
      viewOf(
        started(),
        tool("file_io", { operation: "write", path: "/workspace/f3.txt" }),
        tool("shell", { command: "ls /workspace" }),
        completed(),
      ),
    );
    expect(fallback).toBe(
      "Completed 2 steps: writing /workspace/f3.txt, running `ls /workspace`.",
    );
  });

  it("a single step is phrased singular", () => {
    const fallback = synthesizeFallbackAnswer(
      viewOf(started(), tool("web_search", { query: "Austin weather" }), completed()),
    );
    expect(fallback).toBe("Completed 1 step: searching “Austin weather”.");
  });
});
