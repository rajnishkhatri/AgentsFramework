/**
 * 1B-10 — the coach client stamps `agent_id` on the run body.
 *
 * The middleware selects the governed coach graph on body
 * `agent_id === "subject-coach-english"` (ADR-0007/0012 shadow wiring);
 * the ratified design puts the id in the CLIENT body (not the BFF route —
 * see app/api/coach/run/stream/route.test.ts). Without it every /learn/coach
 * turn is silently served by the DEFAULT graph and Phase-1 shadow traces
 * never accumulate.
 *
 * Failure path first (TAP-4): plain chat (`useAgentRun` without the option)
 * must send NO agent_id — the coach id leaking into chat would flip every
 * chat turn onto the least-privilege coach graph.
 */

import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { SUBJECT_COACH_AGENT_ID, useCoach } from "./use_coach";
import { useAgentRun } from "@/components/chat/use_agent_run";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

function scriptedRuntime(): {
  runtime: AgentRuntimeClient;
  streamReqs: RunCreateRequest[];
} {
  const streamReqs: RunCreateRequest[] = [];
  const runtime: AgentRuntimeClient = {
    streamRun(req: RunCreateRequest, _options?: StreamRunOptions) {
      streamReqs.push(req);
      return (async function* (): AsyncGenerator<UIRuntimeEvent> {
        yield {
          type: "run_completed",
          trace_id: "tr-coach",
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

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  root.unmount();
  container.remove();
});

const tick = (ms = 15): Promise<void> => new Promise((r) => setTimeout(r, ms));

async function until(cond: () => boolean, label: string): Promise<void> {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    if (cond()) return;
    await tick();
  }
  throw new Error(`timeout waiting for: ${label}`);
}

function CoachProbe({ runtime }: { runtime: AgentRuntimeClient }) {
  const { ask } = useCoach(runtime);
  return React.createElement(
    "button",
    { onClick: () => void ask("why is B right?") },
    "ask",
  );
}

function ChatProbe({ runtime }: { runtime: AgentRuntimeClient }) {
  const { send } = useAgentRun(runtime);
  return React.createElement(
    "button",
    { onClick: () => void send("plain chat turn") },
    "send",
  );
}

async function clickProbe(): Promise<void> {
  await until(() => container.querySelector("button") !== null, "probe button");
  (container.querySelector("button") as HTMLElement).click();
}

describe("coach agent_id stamping — failure path first", () => {
  it("plain chat sends NO agent_id (coach graph never captures chat)", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    root.render(React.createElement(ChatProbe, { runtime }));
    await clickProbe();
    await until(() => streamReqs.length === 1, "chat streamRun call");
    expect(streamReqs[0]).not.toHaveProperty("agent_id");
  });

  it("a coach ask carries agent_id=subject-coach-english on the run body", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    root.render(React.createElement(CoachProbe, { runtime }));
    await clickProbe();
    await until(() => streamReqs.length === 1, "coach streamRun call");
    expect(streamReqs[0]?.agent_id).toBe(SUBJECT_COACH_AGENT_ID);
    expect(SUBJECT_COACH_AGENT_ID).toBe("subject-coach-english");
  });
});
