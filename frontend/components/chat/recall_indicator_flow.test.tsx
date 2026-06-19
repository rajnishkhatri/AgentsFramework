/**
 * Recall-indicator round trip — interactive jsdom test of the FULL path
 * (no Playwright, no network): a run whose stream carries a `memory_recalled`
 * event renders the transparent-recall indicator above that turn with the
 * recalled count. Count only, never content (privacy invariant).
 *
 * This closes the last UI-behavior gap of the memory layer: previously the
 * indicator was mounted but fed a literal 0. Here the count flows backend →
 * Custom 'memory_recalled' → ag_ui translator → run_view_reducer.recalledCount
 * → RecallIndicator, proven end to end through the live ChatShell.
 *
 * Failure path first (TAP-4): a run with NO memory_recalled event (or count 0)
 * renders no indicator — it must never add noise to a memory-off run.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { ChatShell } from "@/app/chat-shell";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type { RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

const TRACE = "tr-recall";

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

function baseRun(extra: UIRuntimeEvent[]): UIRuntimeEvent[] {
  return [
    { type: "run_started", trace_id: TRACE, run_id: "r1", thread_id: "t1" },
    ...extra,
    {
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "m1",
      delta: "Here is your answer.",
    },
    { type: "run_completed", trace_id: TRACE, run_id: "r1", thread_id: "t1" },
  ];
}

// ── jsdom driving helpers (mirrors resume_thread_flow.test.tsx) ─────────

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

async function renderAndSend(runtime: AgentRuntimeClient): Promise<void> {
  root.render(
    React.createElement(ChatShell, { userEmail: "t@example.com", runtime }),
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

describe("recall indicator round trip", { timeout: 60_000 }, () => {
  it("a run with no memory_recalled event shows no indicator (failure path first)", async () => {
    await renderAndSend(runtimeEmitting(baseRun([])));
    expect(container.querySelector("[data-testid='recall-indicator']")).toBeNull();
  });

  it("count 0 shows no indicator (memory-off / no-hit run stays quiet)", async () => {
    await renderAndSend(
      runtimeEmitting(
        baseRun([{ type: "memory_recalled", trace_id: TRACE, count: 0, keys: [] }]),
      ),
    );
    expect(container.querySelector("[data-testid='recall-indicator']")).toBeNull();
  });

  it("a positive count renders the transparent-recall indicator", async () => {
    await renderAndSend(
      runtimeEmitting(
        baseRun([{ type: "memory_recalled", trace_id: TRACE, count: 2, keys: [] }]),
      ),
    );
    const indicator = container.querySelector(
      "[data-testid='recall-indicator']",
    );
    expect(indicator).toBeTruthy();
    expect(indicator?.textContent).toContain("Recalled 2 memories about you");
    // The indicator never carries memory content — only the count.
    expect(indicator?.textContent).not.toContain("what units do I prefer?");
  });
});
