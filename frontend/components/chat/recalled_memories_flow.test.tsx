/**
 * Recalled-memories eval/reject round trip (Phase B B2) — interactive jsdom
 * test of the FULL path through the live ChatShell (no Playwright, no network):
 * a run whose stream carries a `memory_recalled` event with KEYS, rendered in
 * eval mode, surfaces the per-turn "memories recalled here" disclosure listing
 * the joined items (key → panel content); clicking Reject soft-suppresses the
 * memory globally via the injected sidebars seam.
 *
 * The recall wire event carries keys only (never content — privacy invariant);
 * the eval view JOINS those keys against the owner's loaded memory panel
 * (injected `sidebars.memories`) to show content. The Reject button calls
 * `sidebars.suppressMemory(key, true)`.
 *
 * Failure paths first (TAP-4): WITHOUT eval mode the disclosure never renders
 * (prod chat stays clean), and a recalled key with no matching panel item is
 * not shown (no contentless row).
 *
 * Hooks: recalled-memories, recalled-memory-{key}, reject-memory-{key}.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { ChatShell } from "@/app/chat-shell";
import type { ChatSidebarsState } from "./use_chat_sidebars";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { MemoryItem, RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

const TRACE = "tr-recalled";

function runtimeEmitting(events: UIRuntimeEvent[]): AgentRuntimeClient {
  return {
    streamRun(_req: RunCreateRequest, _options?: StreamRunOptions) {
      return (async function* (): AsyncGenerator<UIRuntimeEvent> {
        for (const evt of events) yield evt;
      })();
    },
    async cancel() {
      /* unused */
    },
    async updateUnderstanding() {
      /* unused */
    },
  };
}

function recallRun(keys: string[]): UIRuntimeEvent[] {
  return [
    { type: "run_started", trace_id: TRACE, run_id: "r1", thread_id: "t1" },
    { type: "memory_recalled", trace_id: TRACE, count: keys.length, keys },
    {
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "m1",
      delta: "You prefer metric units.",
    },
    { type: "run_completed", trace_id: TRACE, run_id: "r1", thread_id: "t1" },
  ];
}

function memItem(key: string, content: string): MemoryItem {
  return { key, type: "semantic", content, salience: null };
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

// ── jsdom driving helpers (mirrors recall_indicator_flow.test.tsx) ──────

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

function click(el: HTMLElement): void {
  el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

function byTestId(id: string): HTMLElement | null {
  return container.querySelector(`[data-testid='${id}']`);
}

async function renderAndSend(
  runtime: AgentRuntimeClient,
  sidebars: ChatSidebarsState,
  evalCase: string | null,
): Promise<void> {
  root.render(
    React.createElement(ChatShell, {
      userEmail: "t@example.com",
      runtime,
      sidebars,
      evalCase,
    }),
  );
  await until(
    () =>
      container.querySelector("textarea[aria-label='Compose message']") !== null,
    "composer",
  );
  const ta = container.querySelector(
    "textarea[aria-label='Compose message']",
  ) as HTMLTextAreaElement;
  setValue(ta, "what units do I prefer?");
  await tick();
  click(container.querySelector("button[aria-label='Send']") as HTMLElement);
  await until(
    () => container.querySelector("[data-state='complete']") !== null,
    "run complete",
  );
}

// ── tests ───────────────────────────────────────────────────────────────

describe("recalled-memories eval/reject round trip", { timeout: 60_000 }, () => {
  it("WITHOUT eval mode the disclosure never renders (prod stays clean)", async () => {
    const sidebars = fakeSidebars({
      memories: [memItem("k1", "prefers metric units")],
    });
    await renderAndSend(runtimeEmitting(recallRun(["k1"])), sidebars, null);
    expect(byTestId("recalled-memories")).toBeNull();
  });

  it("in eval mode, lists the recalled items joined from the memory panel", async () => {
    const sidebars = fakeSidebars({
      memories: [
        memItem("k1", "prefers metric units"),
        memItem("k2", "lives in Berlin"),
        memItem("k3", "unrelated fact"),
      ],
    });
    await renderAndSend(
      runtimeEmitting(recallRun(["k1", "k2"])),
      sidebars,
      "EVAL-1",
    );
    await until(() => byTestId("recalled-memories") !== null, "disclosure");
    expect(byTestId("recalled-memory-k1")?.textContent).toContain(
      "prefers metric units",
    );
    expect(byTestId("recalled-memory-k2")?.textContent).toContain(
      "lives in Berlin",
    );
    // A memory that was NOT recalled this turn is not listed.
    expect(byTestId("recalled-memory-k3")).toBeNull();
  });

  it("a recalled key with no matching panel item is not shown (no contentless row)", async () => {
    const sidebars = fakeSidebars({
      memories: [memItem("k1", "prefers metric units")],
    });
    await renderAndSend(
      runtimeEmitting(recallRun(["k1", "k-missing"])),
      sidebars,
      "EVAL-1",
    );
    await until(() => byTestId("recalled-memories") !== null, "disclosure");
    expect(byTestId("recalled-memory-k1")).toBeTruthy();
    expect(byTestId("recalled-memory-k-missing")).toBeNull();
  });

  it("Reject soft-suppresses the memory via the sidebars seam", async () => {
    const suppress = vi.fn(async () => undefined);
    const sidebars = fakeSidebars({
      memories: [memItem("k1", "prefers metric units")],
      suppressMemory: suppress,
    });
    await renderAndSend(runtimeEmitting(recallRun(["k1"])), sidebars, "EVAL-1");
    await until(() => byTestId("reject-memory-k1") !== null, "reject button");
    click(byTestId("reject-memory-k1") as HTMLElement);
    await until(() => suppress.mock.calls.length === 1, "suppress called");
    expect(suppress).toHaveBeenCalledWith("k1", true);
  });
});
