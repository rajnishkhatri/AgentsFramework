/**
 * Click-to-resume round trip — interactive jsdom test of the FULL UI flow
 * through the ChatShell (no Playwright, no network): click a past thread in
 * the sidebar → its persisted history replays into the chat view → a new
 * `send` continues THAT thread's checkpoint server-side.
 *
 * The sidebars seam is injected (`loadThreadTurns` returns scripted replay
 * turns) and the runtime is a scripted `AgentRuntimeClient` that records the
 * `thread_id` of every `streamRun` request. The continuation guarantee — the
 * next message reuses the resumed thread id, not a fresh uuid — is the load-
 * bearing assertion (it is what makes resume actually resume, not restart).
 *
 * Failure path first (TAP-4): a thread whose fetch fails (loadThreadTurns
 * resolves []) clears the view to empty rather than corrupting it, and a
 * subsequent send still binds to the selected thread id.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { ChatShell } from "@/app/chat-shell";
import { threadMessagesToTurns } from "./use_chat_sidebars";
import type { ChatSidebarsState } from "./use_chat_sidebars";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { MemoryItem, ThreadState } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

const RESUMED_ID = "thread-trip-7";

function fakeThread(id: string, title: string): ThreadState {
  return {
    thread_id: id,
    user_id: "u",
    title,
    messages: [],
    created_at: "2026-06-17T00:00:00Z",
    updated_at: "2026-06-17T00:00:00Z",
    archived_at: null,
  };
}

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
          trace_id: "tr-resume",
          run_id: "r1",
          thread_id: req.thread_id,
        };
        yield {
          type: "chat_message_delta",
          trace_id: "tr-resume",
          message_id: "m1",
          delta: "ok",
        };
        yield {
          type: "run_completed",
          trace_id: "tr-resume",
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
    threads: [fakeThread(RESUMED_ID, "Plan my trip")],
    memories: [] as ReadonlyArray<MemoryItem>,
    memoryEnabled: false,
    error: null,
    reloadThreads: vi.fn(async () => undefined),
    reloadMemories: vi.fn(async () => undefined),
    renameThread: vi.fn(async () => undefined),
    deleteThread: vi.fn(async () => undefined),
    addMemory: vi.fn(async () => undefined),
    deleteMemory: vi.fn(async () => undefined),
    setMemoryEnabled: vi.fn(),
    loadThreadTurns: vi.fn(async () => []),
    ...overrides,
  };
}

// ── jsdom driving helpers (mirrors understanding_edit_flow.test.tsx) ────

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

function byTestId(id: string): HTMLElement | null {
  return container.querySelector(`[data-testid='${id}']`);
}

function click(el: HTMLElement): void {
  el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
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
  await until(() => byTestId("thread-sidebar") !== null, "sidebar");
}

async function sendMessage(body: string): Promise<void> {
  const ta = container.querySelector(
    "textarea[aria-label='Compose message']",
  ) as HTMLTextAreaElement;
  setValue(ta, body);
  await tick();
  click(container.querySelector("button[aria-label='Send']") as HTMLElement);
}

// ── tests ───────────────────────────────────────────────────────────────

describe("click-to-resume round trip", { timeout: 60_000 }, () => {
  it("a failed thread fetch leaves the view empty but still binds the thread id for the next send", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    // loadThreadTurns resolves [] (the fetch failed / thread empty).
    const sidebars = fakeSidebars({ loadThreadTurns: vi.fn(async () => []) });
    await renderShell(runtime, sidebars);

    click(byTestId(`thread-row-${RESUMED_ID}`)!);
    await tick(30);
    // No replayed bubbles — view collapses back to the empty state.
    expect(container.textContent).toContain("What can I help you with?");

    await sendMessage("continue here");
    await until(() => streamReqs.length === 1, "stream request");
    // The new run continues the RESUMED thread id, not a fresh uuid.
    expect(streamReqs[0]?.thread_id).toBe(RESUMED_ID);
  });

  it("replays the selected thread's history, then continues its checkpoint on the next send", async () => {
    const { runtime, streamReqs } = scriptedRuntime();
    const replay = threadMessagesToTurns([
      { role: "user", content: "plan a 3-day trip to Kyoto" },
      { role: "assistant", content: "Day 1: Fushimi Inari…" },
    ]);
    const sidebars = fakeSidebars({
      loadThreadTurns: vi.fn(async () => replay),
    });
    await renderShell(runtime, sidebars);

    click(byTestId(`thread-row-${RESUMED_ID}`)!);
    // The replayed transcript appears in the chat view.
    await until(
      () => container.textContent?.includes("Fushimi Inari…") ?? false,
      "replayed assistant line",
    );
    expect(container.textContent).toContain("plan a 3-day trip to Kyoto");

    // The replayed assistant turn is COMPLETE (frozen history), never a live
    // run: its terminal marker is present, no streaming animation.
    expect(byTestId("terminal-marker")).toBeTruthy();

    // A follow-up message continues the resumed checkpoint.
    await sendMessage("add a day 4");
    await until(() => streamReqs.length === 1, "stream request");
    expect(streamReqs[0]?.thread_id).toBe(RESUMED_ID);
    // …and appends to the replayed history rather than replacing it.
    expect(container.textContent).toContain("plan a 3-day trip to Kyoto");
    expect(container.textContent).toContain("add a day 4");
  });

  it("marks the selected thread row as active (aria-current=page)", async () => {
    const { runtime } = scriptedRuntime();
    const sidebars = fakeSidebars();
    await renderShell(runtime, sidebars);

    click(byTestId(`thread-row-${RESUMED_ID}`)!);
    await until(
      () =>
        byTestId(`thread-row-${RESUMED_ID}`)?.getAttribute("aria-current") ===
        "page",
      "active row",
    );
  });
});
