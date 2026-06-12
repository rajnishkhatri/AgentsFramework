/**
 * Phase 4 soft-gate edit round trip — interactive jsdom test of the FULL
 * UI flow through the ChatShell's injected-runtime seam (no Playwright,
 * no network): send → card renders mid-stream → Edit pauses (abort) →
 * Save POSTs through the port → resume folds into the SAME turn.
 *
 * This is the headless twin of the T2 browser spec
 * (`e2e/integration/understanding-edit-roundtrip.spec.ts`): the runtime
 * here is a scripted `AgentRuntimeClient` whose first stream stays open
 * until aborted, exactly like a paused middleware run.
 *
 * Failure path first (TAP-4): a rejected edit POST keeps the run paused
 * and never opens the resume stream.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { ChatShell } from "@/app/chat-shell";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "@/lib/ports/agent_runtime_client";
import type {
  RunCreateRequest,
  TaskUnderstandingEditRequest,
} from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

const TRACE = "tr-edit-flow";

function initialEvents(threadId: string): UIRuntimeEvent[] {
  return [
    { type: "run_started", trace_id: TRACE, run_id: "r1", thread_id: threadId },
    {
      type: "task_understanding",
      trace_id: TRACE,
      restated_intent: "Create the file and verify it.",
      success_conditions: ["file exists", "contents verified"],
      confidence: 0.85,
      source: "generated",
    },
  ];
}

function resumedEvents(threadId: string): UIRuntimeEvent[] {
  return [
    { type: "run_started", trace_id: TRACE, run_id: "r2", thread_id: threadId },
    {
      type: "task_understanding",
      trace_id: TRACE,
      restated_intent: "Only verify the file.",
      success_conditions: ["file exists", "verification ran"],
      confidence: 0.85,
      source: "user_edited",
    },
    {
      type: "chat_message_delta",
      trace_id: TRACE,
      message_id: "m1",
      delta: "Verified the file as corrected.",
    },
    { type: "run_completed", trace_id: TRACE, run_id: "r2", thread_id: threadId },
  ];
}

/** Yields the initial leg, then stays open until the pause aborts it. */
async function* openUntilAborted(
  events: UIRuntimeEvent[],
  signal: AbortSignal | undefined,
): AsyncGenerator<UIRuntimeEvent> {
  for (const evt of events) yield evt;
  await new Promise<never>((_resolve, reject) => {
    const abort = (): void => reject(new Error("stream aborted (pause)"));
    if (signal?.aborted) abort();
    signal?.addEventListener("abort", abort);
  });
}

function scriptedRuntime(opts?: { rejectEdit?: string }): {
  runtime: AgentRuntimeClient;
  edits: Array<[string, TaskUnderstandingEditRequest]>;
  streamReqs: RunCreateRequest[];
} {
  const edits: Array<[string, TaskUnderstandingEditRequest]> = [];
  const streamReqs: RunCreateRequest[] = [];
  const runtime: AgentRuntimeClient = {
    streamRun(req: RunCreateRequest, options?: StreamRunOptions) {
      streamReqs.push(req);
      if (req.input["_resume"] === true) {
        return (async function* (): AsyncGenerator<UIRuntimeEvent> {
          for (const evt of resumedEvents(req.thread_id)) yield evt;
        })();
      }
      return openUntilAborted(initialEvents(req.thread_id), options?.signal);
    },
    async cancel() {
      /* not used here */
    },
    async updateUnderstanding(threadId, req) {
      if (opts?.rejectEdit) throw new Error(opts.rejectEdit);
      edits.push([threadId, req]);
    },
  };
  return { runtime, edits, streamReqs };
}

// ── jsdom driving helpers ─────────────────────────────────────────────

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  // jsdom has no scrollIntoView; the shell calls it on every turn update.
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

// Generous budget: the full vitest suite runs files in parallel forks, so
// renders that take milliseconds standalone can take seconds under load.
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

function setValue(
  el: HTMLInputElement | HTMLTextAreaElement,
  value: string,
): void {
  const proto =
    el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  setter?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

async function renderShellAndSend(runtime: AgentRuntimeClient): Promise<void> {
  root.render(
    React.createElement(ChatShell, { userEmail: "t@example.com", runtime }),
  );
  await until(
    () => container.querySelector("textarea[aria-label='Compose message']") !== null,
    "composer",
  );
  const ta = container.querySelector(
    "textarea[aria-label='Compose message']",
  ) as HTMLTextAreaElement;
  setValue(ta, "create the file and verify it");
  await tick();
  click(container.querySelector("button[aria-label='Send']") as HTMLElement);
  await until(() => byTestId("task-understanding-card") !== null, "card");
  await until(() => byTestId("understanding-edit") !== null, "edit affordance");
}

// ── tests ─────────────────────────────────────────────────────────────

describe("understanding edit round trip — failure path first", { timeout: 60_000 }, () => {
  it("a rejected edit POST shows the error, stays paused, never resumes", async () => {
    const { runtime, streamReqs } = scriptedRuntime({
      rejectEdit: "understanding edit rejected (409): run already completed",
    });
    await renderShellAndSend(runtime);

    click(byTestId("understanding-edit")!);
    await until(() => byTestId("understanding-save") !== null, "edit form");
    click(byTestId("understanding-save")!);

    await until(() => byTestId("understanding-edit-error") !== null, "edit error");
    expect(byTestId("understanding-edit-error")!.textContent).toContain(
      "already completed",
    );
    // Still in edit mode; no resume stream was opened.
    expect(byTestId("understanding-save")).not.toBeNull();
    expect(streamReqs).toHaveLength(1);
    // The turn never flipped to error: the pause swallow kept it streaming.
    expect(
      byTestId("assistant-message")?.getAttribute("data-state"),
    ).toBe("streaming");
  });

  it("pause → edit → save resumes the SAME turn with the edited artifact", async () => {
    const { runtime, edits, streamReqs } = scriptedRuntime();
    await renderShellAndSend(runtime);

    // The Phase 3 display state, mid-stream and editable.
    const card = byTestId("task-understanding-card")!;
    expect(card.getAttribute("data-source")).toBe("generated");

    click(byTestId("understanding-edit")!);
    await until(() => byTestId("understanding-intent-input") !== null, "form");

    setValue(
      byTestId("understanding-intent-input") as HTMLTextAreaElement,
      "Only verify the file.",
    );
    setValue(
      byTestId("understanding-condition-input-1") as HTMLInputElement,
      "verification ran",
    );
    await tick();
    click(byTestId("understanding-save")!);

    // The resumed stream completes the same (single) turn.
    await until(
      () =>
        byTestId("assistant-message")?.getAttribute("data-state") === "complete",
      "resume completes",
    );
    // The fresh user_edited artifact supersedes the draft form via a
    // passive effect — wait for edit mode to exit before content checks.
    await until(
      () =>
        byTestId("task-understanding-card")?.getAttribute("data-editing") !==
        "true",
      "edit mode exits",
    );

    // Edit POST carried the trace echo + drafts, before the resume leg.
    expect(edits).toHaveLength(1);
    const [threadId, editReq] = edits[0]!;
    expect(threadId.length).toBeGreaterThan(0);
    expect(editReq).toEqual({
      trace_id: TRACE,
      restated_intent: "Only verify the file.",
      success_conditions: ["file exists", "verification ran"],
    });
    expect(streamReqs).toHaveLength(2);
    expect(streamReqs[1]).toEqual({
      thread_id: threadId,
      input: { _resume: true },
    });

    // Card now shows the user_edited artifact from the resumed stream.
    const finalCard = byTestId("task-understanding-card")!;
    expect(finalCard.getAttribute("data-source")).toBe("user_edited");
    expect(finalCard.textContent).toContain("Only verify the file.");
    expect(finalCard.textContent).toContain("verification ran");
    // And the answer landed in the same assistant message.
    expect(byTestId("assistant-message")!.textContent).toContain(
      "Verified the file as corrected.",
    );
    expect(container.querySelectorAll("[data-testid='assistant-message']")).toHaveLength(1);
  });

  it("cancel resumes unchanged: no POST, original artifact stands", async () => {
    const { runtime, edits, streamReqs } = scriptedRuntime();
    await renderShellAndSend(runtime);

    click(byTestId("understanding-edit")!);
    await until(() => byTestId("understanding-cancel-edit") !== null, "form");
    click(byTestId("understanding-cancel-edit")!);

    await until(
      () =>
        byTestId("assistant-message")?.getAttribute("data-state") === "complete",
      "resume completes",
    );
    expect(edits).toHaveLength(0);
    expect(streamReqs).toHaveLength(2);
    expect(streamReqs[1]?.input).toEqual({ _resume: true });
  });
});
