/**
 * Phase 2.2 — Coach orchestration (FR-F2/F3/F4/F6, L1 deterministic).
 *
 * The coach is NOT an engine port (plan OD-3 / design §7): it rides the chat
 * `AgentRuntimeClient` via `useAgentRun`, and each streaming assistant turn
 * (`AssistantRunView`) is projected to a coach bubble by `toCoachMessage`
 * (Phase 0.5). `useCoach` is that composition; the React-free mapping
 * `coachTurnsFromChat` is exported so it is testable in node without React
 * (the analogue of `consumeRunStream`).
 *
 * Failure path first (TAP-4 / FR-F4): a turn whose stream ended in `run_error`
 * must map to a coach bubble that is `error + canRetry`, NOT a stuck spinner.
 */

import { describe, expect, it } from "vitest";
import { coachTurnsFromChat } from "./use_coach";
import type { ChatTurn } from "@/components/chat/use_agent_run";
import type { AssistantRunView } from "@/lib/translators/run_view_reducer";

function view(over: Partial<AssistantRunView> = {}): AssistantRunView {
  return {
    status: "complete",
    segments: [{ kind: "text", text: "Think about the subject–verb link." }],
    traceId: "tr-1",
    errorMessage: null,
    ...over,
  } as AssistantRunView;
}

function turn(over: Partial<ChatTurn> = {}): ChatTurn {
  return { id: "t1", user: "why is B right?", assistant: view(), ...over };
}

describe("coachTurnsFromChat — failure path first (FR-F4)", () => {
  it("an errored stream maps to error + canRetry, never a pending spinner", () => {
    const turns = [
      turn({
        assistant: view({
          status: "error",
          segments: [],
          errorMessage: "stream dropped",
        }),
      }),
    ];
    const [ct] = coachTurnsFromChat(turns);
    expect(ct!.coach.error).toBe(true);
    expect(ct!.coach.canRetry).toBe(true);
    expect(ct!.coach.pending).toBe(false);
    expect(ct!.coach.markdown).toContain("stream dropped");
  });
});

describe("coachTurnsFromChat — happy + streaming", () => {
  it("carries the user ask and projects the assistant view to a coach bubble", () => {
    const [ct] = coachTurnsFromChat([turn()]);
    expect(ct!.id).toBe("t1");
    expect(ct!.user).toBe("why is B right?");
    expect(ct!.coach.role).toBe("coach");
    expect(ct!.coach.markdown).toContain("subject–verb");
    expect(ct!.coach.error).toBe(false);
  });

  it("a still-streaming turn is pending (typing indicator, FR-F3)", () => {
    const [ct] = coachTurnsFromChat([
      turn({ assistant: view({ status: "streaming" }) }),
    ]);
    expect(ct!.coach.pending).toBe(true);
    expect(ct!.coach.error).toBe(false);
  });

  it("forwards trace_id verbatim (F-R7) and preserves turn order", () => {
    const turns = [
      turn({ id: "a", assistant: view({ traceId: "tr-a" }) }),
      turn({ id: "b", assistant: view({ traceId: "tr-b" }) }),
    ];
    const mapped = coachTurnsFromChat(turns);
    expect(mapped.map((m) => m.id)).toEqual(["a", "b"]);
    expect(mapped[0]!.coach.traceId).toBe("tr-a");
    expect(mapped[1]!.coach.traceId).toBe("tr-b");
  });

  it("empty transcript maps to empty", () => {
    expect(coachTurnsFromChat([])).toEqual([]);
  });
});
