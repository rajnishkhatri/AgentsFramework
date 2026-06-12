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
