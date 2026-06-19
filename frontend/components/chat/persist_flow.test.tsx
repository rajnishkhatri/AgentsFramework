/**
 * Durable-persistence flow (plan §A3) — first-send auto-create + per-turn
 * persist, driven through the chat shell in jsdom (mirrors
 * resume_thread_flow.test.tsx's harness).
 *
 * Failure paths first (FD6/TAP-4): a rejecting create/persist must NEVER throw
 * into the live run — the chat keeps working and the answer still renders.
 */

import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ChatShell } from "@/app/chat-shell";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { ChatSidebarsState } from "./use_chat_sidebars";
import type { MemoryItem, RunCreateRequest } from "@/lib/wire/agent_protocol";
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
          type: "run_started",
          trace_id: "tr-persist",
          run_id: "r1",
          thread_id: req.thread_id,
        };
        yield {
          type: "chat_message_delta",
          trace_id: "tr-persist",
          message_id: "m1",
          delta: "the answer",
        };
        yield {
          type: "run_completed",
          trace_id: "tr-persist",
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

function fakeSidebars(
  overrides: Partial<ChatSidebarsState> = {},
): ChatSidebarsState {
  return {
    threads: [],
    memories: [] as ReadonlyArray<MemoryItem>,
    memoryEnabled: false,
    error: null,
    reloadThreads: vi.fn(async () => undefined),
    reloadMemories: vi.fn(async () => undefined),
    renameThread: vi.fn(async () => undefined),
    deleteThread: vi.fn(async () => undefined),
    addMemory: vi.fn(async () => undefined),
    deleteMemory: vi.fn(async () => undefined),
    suppressMemory: vi.fn(async () => undefined),
    setMemoryEnabled: vi.fn(),
    loadThreadTurns: vi.fn(async () => []),
    createThread: vi.fn(async () => undefined),
    persistTurn: vi.fn(async () => undefined),
    ...overrides,
  };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  HTMLElement.prototype.scrollIntoView ??= () => undefined;
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

function setValue(el: HTMLTextAreaElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype,
    "value",
  )?.set;
  setter?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

async function renderShell(
  runtime: AgentRuntimeClient,
  sidebars: ChatSidebarsState,
): Promise<void> {
  root.render(
    React.createElement(ChatShell, {
      userEmail: "t@example.com",
      runtime,
      sidebars,
    }),
  );
  await until(() => container.querySelector("textarea") !== null, "composer");
}

async function sendMessage(body: string): Promise<void> {
  const ta = container.querySelector(
    "textarea[aria-label='Compose message']",
  ) as HTMLTextAreaElement;
  setValue(ta, body);
  await tick();
  (
    container.querySelector("button[aria-label='Send']") as HTMLElement
  ).dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

describe("durable persistence flow", { timeout: 60_000 }, () => {
  it("a rejecting createThread does NOT break the live chat (failure path)", async () => {
    const { runtime } = scriptedRuntime();
    const sidebars = fakeSidebars({
      createThread: vi.fn(async () => {
        throw new Error("create boom");
      }),
    });
    await renderShell(runtime, sidebars);
    await sendMessage("hello there");
    // The answer still streams to completion despite the create failure.
    await until(
      () =>
        container.querySelector("[data-state='complete']") !== null,
      "completed run despite create failure",
    );
    expect(container.textContent).toContain("the answer");
  });

  it("auto-creates the thread once on the first send with the minted id + first line", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    const create = vi.fn(async () => undefined);
    const sidebars = fakeSidebars({ createThread: create });
    await renderShell(runtime, sidebars);
    await sendMessage("plan my trip");
    await until(
      () => container.querySelector("[data-state='complete']") !== null,
      "completed run",
    );
    expect(create).toHaveBeenCalledTimes(1);
    const [threadId, , firstMessage] = create.mock.calls[0] as unknown as [
      string,
      string,
      string,
    ];
    // The create id is the SAME id the run streamed under (resume continuity).
    expect(threadId).toBe(streamReqs[0]?.thread_id);
    expect(firstMessage).toBe("plan my trip");
  });

  it("does not re-create on a second send in the same chat", async () => {
    const { runtime } = scriptedRuntime();
    const create = vi.fn(async () => undefined);
    const sidebars = fakeSidebars({ createThread: create });
    await renderShell(runtime, sidebars);
    await sendMessage("first");
    await until(
      () =>
        container.querySelectorAll("[data-state='complete']").length === 1,
      "first run complete",
    );
    await sendMessage("second");
    await until(
      () =>
        container.querySelectorAll("[data-state='complete']").length === 2,
      "second run complete",
    );
    expect(create).toHaveBeenCalledTimes(1);
  });

  it("persists the completed turn with the final assistant text", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    const persist = vi.fn(async () => undefined);
    const sidebars = fakeSidebars({ persistTurn: persist });
    await renderShell(runtime, sidebars);
    await sendMessage("plan my trip");
    await until(
      () => persist.mock.calls.length === 1,
      "turn persisted",
    );
    const [threadId, turn] = persist.mock.calls[0] as unknown as [
      string,
      { user: string; assistant: string; turnId: string },
    ];
    expect(threadId).toBe(streamReqs[0]?.thread_id);
    expect(turn.user).toBe("plan my trip");
    expect(turn.assistant).toBe("the answer");
    expect(turn.turnId).toBeTruthy();
  });
});
