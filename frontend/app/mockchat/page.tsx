/**
 * THROWAWAY dev-only preview route (not committed). Mounts ChatShell with a
 * mock runtime + mock sidebars so a fully populated conversation renders
 * without a backend — for visual comparison against the design showcase.
 * Delete after previewing.
 */
"use client";

import * as React from "react";
import { ChatShell } from "../chat-shell";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

const TRACE = "mock-trace-0001";

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// Scripted event sequence mirroring the All Surfaces design conversation:
// recall → understanding card → tool (running→complete) → streamed answer → done.
async function* scriptedRun(
  req: RunCreateRequest,
): AsyncIterable<UIRuntimeEvent> {
  const run_id = "mock-run-1";
  const thread_id = req.thread_id;
  yield { type: "run_started", trace_id: TRACE, run_id, thread_id };
  await sleep(150);

  yield {
    type: "memory_recalled",
    trace_id: TRACE,
    count: 3,
    keys: ["mem-a", "mem-b", "mem-c"],
  };
  await sleep(200);

  yield {
    type: "task_understanding",
    trace_id: TRACE,
    restated_intent:
      "Design a durable cross-session recall improvement, measured against the eval suite.",
    success_conditions: [
      "Recall@5 improves on the held-out set",
      "No regression in latency budget",
    ],
    confidence: 0.82,
    source: "generated",
  };
  await sleep(300);

  // Tool: running → completed
  const toolBase = {
    trace_id: TRACE,
    tool_call_id: "tc-1",
    tool_name: "search_memory",
    input: { query: "memory recall across sessions" },
  } as const;
  yield {
    type: "tool_render",
    trace_id: TRACE,
    request: { ...toolBase, status: "running", output: null },
  };
  await sleep(700);
  yield {
    type: "tool_render",
    trace_id: TRACE,
    request: {
      ...toolBase,
      status: "completed",
      output: "3 matches · 98ms",
    },
  };
  await sleep(250);

  // Streamed answer
  const answer = [
    "Here's a focused five-step plan:\n\n",
    "1. **Embed on write** — store turn summaries as vectors, not raw text.\n",
    "2. **Hybrid recall** — combine semantic + recency scoring.\n",
    "3. **Dedup** near-duplicate memories before write.\n",
    "4. **Decay** stale facts so recall stays sharp.\n",
    "5. **Gate** on the Recall@5 eval before shipping.\n",
  ];
  for (const delta of answer) {
    yield {
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "msg-1",
      delta,
    };
    await sleep(120);
  }
  await sleep(150);

  yield { type: "run_completed", trace_id: TRACE, run_id, thread_id };
}

const mockRuntime: AgentRuntimeClient = {
  streamRun(req: RunCreateRequest, _opts?: StreamRunOptions) {
    return scriptedRun(req);
  },
  async cancel() {},
  async updateUnderstanding() {},
};

const now = new Date().toISOString();
const mockThreads = [
  { thread_id: "t1", user_id: "u", title: "Improve memory recall", messages: [], created_at: now, updated_at: now, archived_at: null },
  { thread_id: "t2", user_id: "u", title: "Planning-stress eval triage", messages: [], created_at: now, updated_at: now, archived_at: null },
  { thread_id: "t3", user_id: "u", title: "Native-wrap UI redesign", messages: [], created_at: now, updated_at: now, archived_at: null },
  { thread_id: "t4", user_id: "u", title: "GoalJudge rubric draft", messages: [], created_at: now, updated_at: now, archived_at: null },
  { thread_id: "t5", user_id: "u", title: "pgvector index tuning", messages: [], created_at: now, updated_at: now, archived_at: null },
];

const mockSidebars = {
  threads: mockThreads,
  memories: [],
  memoryEnabled: true,
  error: null,
  async reloadThreads() {},
  async reloadMemories() {},
  async renameThread() {},
  async deleteThread() {},
  async addMemory() {},
  async deleteMemory() {},
  async suppressMemory() {},
  setMemoryEnabled() {},
  async loadThreadTurns() { return []; },
  async createThread() {},
  async persistTurn() {},
} as unknown as NonNullable<React.ComponentProps<typeof ChatShell>["sidebars"]>;

export default function MockChatPage(): React.JSX.Element {
  // Auto-send the design prompt once mounted so a populated turn renders.
  React.useEffect(() => {
    const t = setTimeout(() => {
      const ta = document.querySelector<HTMLTextAreaElement>(
        'textarea[aria-label="Compose message"]',
      );
      const btn = document.querySelector<HTMLButtonElement>(
        'button[aria-label="Send"]',
      );
      if (ta && btn) {
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          "value",
        )?.set;
        setter?.call(
          ta,
          "Improve memory recall across sessions — give me a concrete plan.",
        );
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        setTimeout(() => btn.click(), 50);
      }
    }, 400);
    return () => clearTimeout(t);
  }, []);

  return (
    <ChatShell
      userEmail="rajnish@studio.dev"
      runtime={mockRuntime}
      sidebars={mockSidebars}
    />
  );
}
