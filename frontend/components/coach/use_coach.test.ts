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

import { afterEach, describe, expect, it } from "vitest";
import { coachTurnsFromChat, sendCoachAsk, SUBJECT_COACH_AGENT_ID } from "./use_coach";
import {
  coachThreadSnapshot,
  resetCoachThread,
  setCoachPin,
} from "./coach_thread_store";
import type { ChatTurn } from "@/components/chat/use_agent_run";
import type { AssistantRunView } from "@/lib/translators/run_view_reducer";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

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

// ─── Phase 4.3: the shared coach thread (FR-J3/J4) ─────────────────────────

function scriptedRuntime(reply = "Watch the clause boundary."): {
  runtime: AgentRuntimeClient;
  streamReqs: RunCreateRequest[];
} {
  const streamReqs: RunCreateRequest[] = [];
  const runtime: AgentRuntimeClient = {
    streamRun(req: RunCreateRequest, _options?: StreamRunOptions) {
      streamReqs.push(req);
      return (async function* (): AsyncGenerator<UIRuntimeEvent> {
        yield {
          type: "run_started",
          trace_id: "tr-1",
          run_id: "r1",
          thread_id: req.thread_id,
        };
        yield { type: "chat_message_delta", trace_id: "tr-1", message_id: "m1", delta: reply };
        yield {
          type: "run_completed",
          trace_id: "tr-1",
          run_id: "r1",
          thread_id: req.thread_id,
        };
      })();
    },
    async cancel() {
      /* unused */
    },
    async updateUnderstanding() {
      /* unused */
    },
  };
  return { runtime, streamReqs };
}

describe("sendCoachAsk — the store-backed send (FR-J3 shared thread)", () => {
  afterEach(() => {
    resetCoachThread();
  });

  it("a panel ask and a coach-screen ask land in ONE thread (same thread_id on the wire)", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    // Two independent call sites (the iPad panel and the Coach screen) share
    // the module store — neither holds the thread in React state.
    await sendCoachAsk(runtime, "panel: why not C?");
    await sendCoachAsk(runtime, "screen: what rule is this?");

    expect(streamReqs).toHaveLength(2);
    expect(streamReqs[1]!.thread_id).toBe(streamReqs[0]!.thread_id);
    const { turns } = coachThreadSnapshot();
    expect(turns.map((t) => t.user)).toEqual([
      "panel: why not C?",
      "screen: what rule is this?",
    ]);
    expect(turns.every((t) => t.assistant.status === "complete")).toBe(true);
  });

  it("stamps the coach agent_id on every run body (governed graph selection)", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    await sendCoachAsk(runtime, "why is B right?");
    expect(streamReqs[0]!.agent_id).toBe(SUBJECT_COACH_AGENT_ID);
  });

  it("a synchronously-throwing runtime yields a terminal error turn, never a stuck spinner (FR-F4)", async () => {
    const runtime = {
      streamRun(): AsyncIterable<UIRuntimeEvent> {
        throw new Error("composition not wired");
      },
      async cancel() {},
      async updateUnderstanding() {},
    } as unknown as AgentRuntimeClient;

    await sendCoachAsk(runtime, "hello?");
    const snap = coachThreadSnapshot();
    expect(snap.busy).toBe(false);
    expect(snap.turns[0]!.assistant.status).toBe("error");
  });
});

describe("sendCoachAsk — coach_context when pinned (BP-3b / FR-10)", () => {
  afterEach(() => {
    resetCoachThread();
  });

  it("omits coach_context when pin is null (messages-only)", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    await sendCoachAsk(runtime, "plain ask");
    expect(streamReqs[0]!.input).not.toHaveProperty("coach_context");
  });

  it("attaches assembled coach_context when pin + ports load a question", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    setCoachPin(
      {
        questionId: "q1",
        skillId: "s-punc",
        label: "Q4 · Commas",
      },
      "post_feedback",
    );
    const question = {
      id: "q1",
      subject: "act-english",
      skill_id: "s-punc",
      difficulty: 3,
      context_html: "x",
      stem: "stem",
      choices: [{ letter: "A", label: "a", is_no_change: false }],
      answer_letter: "A",
      per_choice_rationale: { A: "ok" },
      why_correct_md: "",
      why_tempted_md: "",
      rule_md: "rule",
      item_type: "underlined-span-mc" as const,
      misconception: null,
      reviewed: true,
      generated_by: "test",
    };
    const ports = {
      questionRepo: {
        async get(id: string) {
          return id === "q1" ? question : null;
        },
      },
      attemptRepo: {
        async misses() {
          return [
            {
              id: "a1",
              subject: "act-english",
              session_id: "s1",
              question_id: "q1",
              chosen_letter: "B",
              correct: false,
              elapsed_ms: 1000,
              used_hint: false,
              created_at: "2026-01-01T00:00:00Z",
            },
          ];
        },
      },
      learnerReadRepo: {
        async listSkillState() {
          return [
            {
              subject: "act-english",
              skill_id: "s-punc",
              learner_id: "maya",
              mastery: 0.5,
              last_seen: null,
              fsrs_stability: 0,
              fsrs_difficulty: 0,
              due_at: "2026-01-01T00:00:00Z",
              fsrs_card: null,
            },
          ];
        },
      },
    };

    await sendCoachAsk(runtime, "why B?", {
      ports: ports as never,
      learnerId: "maya",
      subject: "act-english",
    });

    const input = streamReqs[0]!.input as {
      coach_context?: {
        question_id: string;
        skill_id: string;
        mode: string;
        misses_aggregate?: { missed: number; window?: number };
        mastery_snapshot?: Record<string, number>;
      };
    };
    expect(input.coach_context).toMatchObject({
      question_id: "q1",
      skill_id: "s-punc",
      mode: "post_feedback",
    });
    expect(input.coach_context!.misses_aggregate).toEqual({
      skill_id: "s-punc",
      missed: 1,
    });
    expect(input.coach_context!.misses_aggregate).not.toHaveProperty("window");
    expect(input.coach_context!.mastery_snapshot).toEqual({ "s-punc": 50 });
  });
});
