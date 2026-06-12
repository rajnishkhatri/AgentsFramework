/**
 * consumeRunStream tests (eval-UI F1).
 *
 * The React-free consumption loop: streams events into dispatch and
 * guarantees a terminal dispatch when the iterable throws (failure path
 * first per TAP-4). Hook rendering itself is covered by the chat-shell
 * SSR tests + T1 Playwright specs.
 */

import { describe, expect, it } from "vitest";
import { consumeRunStream } from "./use_agent_run";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

const COMPLETED: UIRuntimeEvent = {
  type: "run_completed",
  trace_id: "tr1",
  run_id: "r1",
  thread_id: "t1",
};

describe("consumeRunStream — failure path first", () => {
  it("dispatches a synthetic terminal run_error when the iterable throws", async () => {
    const stream = (async function* (): AsyncGenerator<UIRuntimeEvent> {
      yield {
        type: "run_started",
        trace_id: "tr1",
        run_id: "r1",
        thread_id: "t1",
      };
      throw new Error("iterator blew up");
    })();
    const seen: UIRuntimeEvent[] = [];
    await consumeRunStream(stream, (e) => seen.push(e));
    expect(seen).toHaveLength(2);
    expect(seen[1]).toMatchObject({
      type: "run_error",
      error_type: "network_error",
    });
  });

  it("dispatches every event in order on the happy path", async () => {
    const stream = (async function* (): AsyncGenerator<UIRuntimeEvent> {
      yield { type: "run_started", trace_id: "tr1", run_id: "r1", thread_id: "t1" };
      yield {
        type: "chat_message_delta",
        trace_id: "tr1",
        message_id: "m1",
        delta: "hi",
      };
      yield COMPLETED;
    })();
    const seen: UIRuntimeEvent[] = [];
    await consumeRunStream(stream, (e) => seen.push(e));
    expect(seen.map((e) => e.type)).toEqual([
      "run_started",
      "chat_message_delta",
      "run_completed",
    ]);
  });
});

// ── Phase 4: edit-and-resume orchestration (React-free) ──────────────

import {
  performUnderstandingEdit,
  resumeRunStream,
} from "./use_agent_run";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";

function runtimeWith(overrides: Partial<AgentRuntimeClient>): AgentRuntimeClient {
  return {
    streamRun: () =>
      (async function* (): AsyncGenerator<UIRuntimeEvent> {
        yield COMPLETED;
      })(),
    cancel: async () => undefined,
    updateUnderstanding: async () => undefined,
    ...overrides,
  };
}

const EDIT = {
  restated_intent: "Only compare the options.",
  success_conditions: ["compares options", "grounded in task"],
};

describe("performUnderstandingEdit — failure path first", () => {
  it("propagates a rejected POST and never opens the resume stream", async () => {
    let streamed = 0;
    const runtime = runtimeWith({
      updateUnderstanding: async () => {
        throw new Error("understanding edit rejected (409): run already completed");
      },
      streamRun: () => {
        streamed += 1;
        return (async function* (): AsyncGenerator<UIRuntimeEvent> {
          yield COMPLETED;
        })();
      },
    });
    await expect(
      performUnderstandingEdit({
        runtime,
        threadId: "t1",
        traceId: "tr1",
        edit: EDIT,
        dispatch: () => undefined,
      }),
    ).rejects.toThrow(/already completed/);
    expect(streamed).toBe(0);
  });

  it("POSTs the trace-echoed edit, then resumes with the _resume sentinel", async () => {
    const posts: Array<[string, unknown]> = [];
    const streamReqs: Array<unknown> = [];
    const order: string[] = [];
    const runtime = runtimeWith({
      updateUnderstanding: async (threadId, req) => {
        posts.push([threadId, req]);
        order.push("post");
      },
      streamRun: (req) => {
        streamReqs.push(req);
        order.push("resume");
        return (async function* (): AsyncGenerator<UIRuntimeEvent> {
          yield COMPLETED;
        })();
      },
    });
    const seen: UIRuntimeEvent[] = [];
    await performUnderstandingEdit({
      runtime,
      threadId: "t1",
      traceId: "tr1",
      edit: EDIT,
      dispatch: (e) => seen.push(e),
      onEditAccepted: () => order.push("accepted"),
    });
    expect(posts).toEqual([
      ["t1", { trace_id: "tr1", ...EDIT }],
    ]);
    expect(streamReqs).toEqual([
      { thread_id: "t1", input: { _resume: true } },
    ]);
    // POST → pause cleared → resume stream, strictly in that order.
    expect(order).toEqual(["post", "accepted", "resume"]);
    expect(seen.map((e) => e.type)).toEqual(["run_completed"]);
  });
});

describe("resumeRunStream", () => {
  it("re-invokes the stream with only the _resume sentinel as input", async () => {
    const streamReqs: Array<unknown> = [];
    const runtime = runtimeWith({
      streamRun: (req) => {
        streamReqs.push(req);
        return (async function* (): AsyncGenerator<UIRuntimeEvent> {
          yield COMPLETED;
        })();
      },
    });
    await resumeRunStream({
      runtime,
      threadId: "t9",
      dispatch: () => undefined,
    });
    expect(streamReqs).toEqual([
      { thread_id: "t9", input: { _resume: true } },
    ]);
  });
});
