/**
 * Phase 0.5 — coach_message_vm (FR-F1..F5, L2 contract, TAP-2 table-driven).
 *
 * Pure map: AssistantRunView (from run_view_reducer) → CoachMessage for the
 * coach bubble. Reuses the chat run-lifecycle reducer so the coach inherits the
 * terminal-state safety (FR-F4) for free (plan §Coach reuse).
 *
 * The named failure rows run FIRST (plan §Phase 0.5): a STREAMING view → a
 * pending coach bubble (typing indicator, FR-F3), and an ERROR-terminal view →
 * a recoverable error message with a retry affordance, NOT a permanent spinner
 * (FR-F4).
 */

import { describe, expect, it } from "vitest";
import { toCoachMessage } from "./coach_message_vm";
import { emptyRunView, type AssistantRunView } from "./run_view_reducer";

function view(over: Partial<AssistantRunView> = {}): AssistantRunView {
  return { ...emptyRunView(), ...over };
}

describe("toCoachMessage — streaming + error terminal (failure paths first, FR-F3/F4)", () => {
  it("streaming view → pending bubble (typing indicator), not error", () => {
    const msg = toCoachMessage(view({ status: "streaming" }));
    expect(msg.status).toBe("streaming");
    expect(msg.pending).toBe(true);
    expect(msg.error).toBe(false);
  });

  it("error-terminal view → recoverable error with retry, not a permanent spinner (FR-F4)", () => {
    const msg = toCoachMessage(
      view({ status: "error", errorMessage: "stream dropped" }),
    );
    expect(msg.status).toBe("error");
    expect(msg.pending).toBe(false); // spinner cleared
    expect(msg.error).toBe(true);
    expect(msg.canRetry).toBe(true);
    expect(msg.markdown).toContain("stream dropped");
  });

  it("partial reply then error keeps a separator so prose and error don't glue (FR-F4)", () => {
    const msg = toCoachMessage(
      view({
        status: "error",
        segments: [{ kind: "text", text: "Use a semicolon." }],
        errorMessage: "stream dropped",
      }),
    );
    // The salvaged prose and the error must not run together
    // ("…semicolon.stream dropped"); a blank line separates them.
    expect(msg.markdown).not.toContain("semicolon.stream");
    expect(msg.markdown).toBe("Use a semicolon.\n\nstream dropped");
  });
});

describe("toCoachMessage — happy path (FR-F3/F5)", () => {
  it("flattens text segments into the coach bubble markdown", () => {
    const msg = toCoachMessage(
      view({
        status: "complete",
        segments: [
          { kind: "text", text: "Think about " },
          { kind: "text", text: "the comma rule." },
        ],
      }),
    );
    expect(msg.markdown).toBe("Think about the comma rule.");
    expect(msg.role).toBe("coach");
    expect(msg.pending).toBe(false);
    expect(msg.error).toBe(false);
  });

  it("a streaming view with partial tokens still shows them (progressive render, FR-F3)", () => {
    const msg = toCoachMessage(
      view({ status: "streaming", segments: [{ kind: "text", text: "Well, " }] }),
    );
    expect(msg.markdown).toBe("Well, ");
    expect(msg.pending).toBe(true);
  });

  it("ignores non-text (tool) segments — the coach bubble is prose only", () => {
    const msg = toCoachMessage(
      view({
        status: "complete",
        segments: [
          { kind: "text", text: "Answer: " },
          // A real tool segment on the path — must be dropped, not stringified,
          // so the filter is actually exercised (not a tautology of two texts).
          {
            kind: "tool",
            request: {
              trace_id: "t1",
              tool_call_id: "tc_1",
              tool_name: "shell",
              input: {},
              status: "completed",
              output: null,
            },
          },
          { kind: "text", text: "use a semicolon." },
        ],
      }),
    );
    expect(msg.markdown).toBe("Answer: use a semicolon.");
  });

  it("carries traceId through when present (F-R7)", () => {
    const msg = toCoachMessage(view({ status: "complete", traceId: "abc123" }));
    expect(msg.traceId).toBe("abc123");
  });
});
