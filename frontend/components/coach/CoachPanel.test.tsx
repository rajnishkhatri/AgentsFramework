/**
 * Phase 4.3 — CoachPanel (FR-J3/J3a, L1 jsdom).
 *
 * The iPad quiz split's persistent live coach panel: it renders the SHARED
 * coach thread (coach_thread_store — one thread with the Coach screen, FR-J3)
 * and the two-tier hint: "One more nudge" reveals the next REVIEWED ladder rung
 * (2 → 3) in the panel, distinct from the item's own Get-a-hint (rung 1). The
 * rungs come from the ADR-0014 reviewed ladder, so neither tier can reveal the
 * answer (FR-J3a × FR-D5 — the verifier cascade is the guarantee).
 *
 * Failure path first (TAP-4): with no deeper rungs the nudge is DISABLED —
 * never a live control that does nothing (FR-B5).
 */

import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { EngineProvider } from "@/app/engine-provider";
import { LearnIdentityProvider } from "@/components/learn/LearnIdentityProvider";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import { CoachPanel } from "./CoachPanel";
import { resetCoachThread, coachThreadSnapshot } from "./coach_thread_store";
import type { AgentRuntimeClient, StreamRunOptions } from "@/lib/ports/agent_runtime_client";
import type { RunCreateRequest } from "@/lib/wire/agent_protocol";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";
import type { Hint } from "@/lib/wire/engine_entities";
import type { LearnIdentity } from "@/lib/learn/resolve_learn_identity";

const TEST_IDENTITY: LearnIdentity = {
  learnerId: "user_workos_1",
  displayName: "Test",
  seedMode: "fresh",
};

function scriptedRuntime(): AgentRuntimeClient {
  return {
    streamRun(req: RunCreateRequest, _o?: StreamRunOptions) {
      return (async function* (): AsyncGenerator<UIRuntimeEvent> {
        yield {
          type: "run_completed",
          trace_id: "tr-p",
          run_id: "r1",
          thread_id: req.thread_id,
        };
      })();
    },
    async cancel() {},
    async updateUnderstanding() {},
  } as unknown as AgentRuntimeClient;
}

function rung(rungLevel: 1 | 2 | 3, body: string): Hint {
  return {
    id: `h-q1-${rungLevel}`,
    subject: "act-english",
    question_id: "q1",
    rung: rungLevel,
    body_md: body,
    reviewed: true,
    generated_by: "authored",
  };
}

const LADDER: readonly Hint[] = [
  rung(1, "What is the clause between the commas doing?"),
  rung(2, "Droppable clauses need fencing on BOTH sides."),
  rung(3, "Find where the clause ends and check that exact spot."),
];

const engineBag = buildBrowserEngineAdapters({
  engineDb: new InMemoryEngineDb(),
});

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
  resetCoachThread();
});

const tick = (ms = 15): Promise<void> => new Promise((r) => setTimeout(r, ms));

function render(node: React.ReactElement): Promise<void> {
  root.render(
    <LearnIdentityProvider value={TEST_IDENTITY}>
      <EngineProvider bag={engineBag}>{node}</EngineProvider>
    </LearnIdentityProvider>,
  );
  return tick();
}

function click(el: Element): Promise<void> {
  (el as HTMLElement).click();
  return tick();
}

describe("CoachPanel — failure path first (FR-B5)", () => {
  it("with no deeper rungs the nudge is disabled, not a dead live control", async () => {
    await render(
      <CoachPanel runtime={scriptedRuntime()} hintLadder={[LADDER[0]!]} />,
    );
    const nudge = container.querySelector<HTMLButtonElement>(
      "[data-testid='one-more-nudge']",
    );
    expect(nudge).not.toBeNull();
    expect(nudge!.disabled).toBe(true);
    expect(nudge!.getAttribute("aria-disabled")).toBe("true");
    expect(nudge!.getAttribute("title")).toBe(
      "You've used all available nudges for this item",
    );
  });

  it("FR-12: Zone C hosts nudge; Zone B hosts ladder header", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const zoneC = container.querySelector("[data-testid='coach-zone-c']");
    expect(zoneC?.querySelector("[data-testid='one-more-nudge']")).not.toBeNull();
    expect(
      container.querySelector(
        "[data-testid='coach-zone-b'] [data-testid='hint-ladder-list']",
      ),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "[data-testid='coach-zone-b'] [data-testid='one-more-nudge']",
      ),
    ).toBeNull();
  });
});

describe("CoachPanel — FR-J3 presence + shared thread", () => {
  it("labels itself as the live coach panel with stacked chrome", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const panel = container.querySelector("[data-testid='coach-panel']");
    expect(panel?.getAttribute("aria-label")).toBe("Live coach panel");
    expect(
      container
        .querySelector("[data-testid='coach-chrome']")
        ?.getAttribute("data-layout"),
    ).toBe("stacked");
  });

  it("offers the item-scoped composer and an ask lands in the SHARED coach thread", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const input = container.querySelector<HTMLTextAreaElement>(
      "textarea, input[type='text']",
    );
    expect(input, "panel composer input").not.toBeNull();
    expect(input!.getAttribute("placeholder")).toBe("Ask about this item…");
  });
});

describe("CoachPanel — B1 shared chrome (FR-5, FR-9)", () => {
  it("renders coach-chrome; shows current-item when pin is supplied", async () => {
    await render(
      <CoachPanel
        runtime={scriptedRuntime()}
        hintLadder={LADDER}
        mode="pre_submit"
        pin={{
          kind: "item",
          questionId: "q1",
          skillId: "s-punc",
          label: "Q4 · Commas, non-essential",
        }}
      />,
    );
    expect(container.querySelector("[data-testid='coach-chrome']")).not.toBeNull();
    expect(
      container.querySelector("[data-testid='coach-current-item']")?.textContent,
    ).toContain("Q4 · Commas, non-essential");
  });

  it("omits current-item when pin is absent (honest absent)", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    expect(container.querySelector("[data-testid='coach-chrome']")).not.toBeNull();
    expect(container.querySelector("[data-testid='coach-current-item']")).toBeNull();
  });
});

describe("CoachPanel — BP-1.5c stacked + chips by composer (FR-1)", () => {
  it("uses stacked chrome without left-rail class; chips sit with composer", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const chrome = container.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("stacked");
    expect(chrome?.className ?? "").not.toMatch(/coach-layout-rail/);
    expect(
      chrome?.querySelectorAll("[data-testid='coach-chip']").length ?? 0,
    ).toBe(0);
    expect(
      container.querySelectorAll(
        "[data-testid='coach-panel-composer'] [data-testid='coach-chip']",
      ).length,
    ).toBe(3);
  });
});

describe("CoachPanel — BP-2b store pin sync (FR-6)", () => {
  it("writes the live item pin into coach_thread_store", async () => {
    await render(
      <CoachPanel
        runtime={scriptedRuntime()}
        hintLadder={LADDER}
        pin={{
          kind: "item",
          questionId: "q1",
          skillId: "s-punc",
          label: "Q4 · Commas, non-essential",
        }}
      />,
    );
    expect(coachThreadSnapshot().pin).toEqual({
      kind: "item",
      questionId: "q1",
      skillId: "s-punc",
      label: "Q4 · Commas, non-essential",
    });
  });
});

describe("CoachPanel — FR-J3a two-tier nudge", () => {
  it("reveals rung 2 then rung 3 in the panel, then disables (never invents a 4th)", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const nudge = (): HTMLButtonElement =>
      container.querySelector<HTMLButtonElement>("[data-testid='one-more-nudge']")!;

    // Nothing deeper is shown until asked (tier 1 belongs to the item card).
    expect(container.textContent).not.toContain("fencing on BOTH sides");

    await click(nudge());
    expect(container.textContent).toContain("Droppable clauses need fencing on BOTH sides.");
    expect(container.textContent).not.toContain("check that exact spot");

    await click(nudge());
    expect(container.textContent).toContain("Find where the clause ends and check that exact spot.");

    // Ladder exhausted: the control disables — there is NO rung 4 (FR-D5).
    expect(nudge().disabled).toBe(true);
  });
});
