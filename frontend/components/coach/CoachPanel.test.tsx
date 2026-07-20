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
    choice_letter: null,
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

  // FR-23 (ADR-0037): supersedes the old FR-12 "Zone C hosts nudge" — the pinned
  // bar (coach-zone-c) is composer-only; the "One more nudge" control moves into
  // the single scroll body (coach-zone-b) alongside the ladder. (G8: the prior
  // assertion pinned a control the new single-scroll layout deliberately relocates.)
  it("FR-23: pinned bar is composer-only; nudge + ladder live in the scroll body", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const zoneC = container.querySelector("[data-testid='coach-zone-c']");
    // nudge NOT in the pinned bar anymore
    expect(zoneC?.querySelector("[data-testid='one-more-nudge']")).toBeNull();
    // nudge + ladder BOTH in the scroll body
    expect(
      container.querySelector(
        "[data-testid='coach-zone-b'] [data-testid='one-more-nudge']",
      ),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "[data-testid='coach-zone-b'] [data-testid='hint-ladder-list']",
      ),
    ).not.toBeNull();
    // pinned bar still hosts the composer
    expect(
      zoneC?.querySelector("[data-testid='coach-panel-composer']"),
    ).not.toBeNull();
  });

  // FR-24 mechanism (ADR-0037 / M3): the coach composer is slimmed to reclaim
  // transcript height — no "+" attach button, no model picker. (The ≥50% height
  // floor itself is a computed-layout assertion covered live/e2e; this guards the
  // mechanism that makes it reachable.)
  it("FR-24: coach composer has no attach or model-picker (slim bar)", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const bar = container.querySelector("[data-testid='coach-zone-c']");
    expect(bar).not.toBeNull();
    expect(
      bar!.querySelector("[data-testid='model-picker-trigger']"),
      "coach composer must not show the model picker",
    ).toBeNull();
    expect(
      bar!.querySelector("[aria-label='Add attachment']"),
      "coach composer must not show the '+' attach button",
    ).toBeNull();
    // the send control stays
    expect(bar!.querySelector("[aria-label='Send']")).not.toBeNull();
  });

  // FR-24/25 (ADR-0037, tightened by FR-27/M8): the coach column is a single-scroll
  // body with ONLY the composer pinned — there is no fixed top header zone anymore.
  // Zone B is the ONLY vertical scroll region and takes the flex remainder (grows
  // with the conversation); the composer is shrink-0 so it never scrolls. (G8: the
  // prior assertion required a shrink-0 `coach-zone-a` fixed header — M8 unpins that
  // header into the scroll body, so a fixed Zone A no longer exists; the height it
  // used to steal now belongs to Zone B. Absolute heights are computed layout —
  // asserted live/e2e; this guards the class contract that produces it.)
  it("FR-24/25/27: Zone B is the single flex-1 scroll region; only the composer is shrink-0", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const zoneB = container.querySelector("[data-testid='coach-zone-b']");
    const zoneC = container.querySelector("[data-testid='coach-zone-c']");
    // Zone B: the one growing scroll region.
    expect(zoneB?.className).toMatch(/flex-1/);
    expect(zoneB?.className).toMatch(/min-h-0/);
    expect(zoneB?.className).toMatch(/overflow-y-auto/);
    // Composer: the sole fixed region; never scrolls.
    expect(zoneC?.className).toMatch(/shrink-0/);
    expect(zoneC?.className ?? "").not.toMatch(/overflow-y-(auto|scroll)/);
    // FR-27: there is NO fixed top header zone — the identity header scrolls in Zone B.
    expect(
      container.querySelector("[data-testid='coach-zone-a']"),
      "coach-zone-a (fixed header) must be gone — header now scrolls in the body",
    ).toBeNull();
  });

  // FR-27 (M8): the coach identity header (title/status/current-item/history + mode
  // chips = CoachChrome) is unpinned — it lives at the TOP of the scroll body
  // (coach-zone-b), so it scrolls away with the transcript instead of eating a
  // fixed ~187px. The dismiss control stays reachable, riding with the header.
  it("FR-27: CoachChrome + dismiss live in the scroll body, not a fixed header", async () => {
    let dismissed = false;
    await render(
      <CoachPanel
        runtime={scriptedRuntime()}
        hintLadder={LADDER}
        onDismiss={() => {
          dismissed = true;
        }}
      />,
    );
    const zoneB = container.querySelector("[data-testid='coach-zone-b']");
    // The identity chrome is a descendant of the scroll body.
    expect(
      zoneB?.querySelector("[data-testid='coach-chrome']"),
      "CoachChrome must scroll inside Zone B",
    ).not.toBeNull();
    // The dismiss control rides with it (still reachable).
    const dismiss = zoneB?.querySelector<HTMLButtonElement>(
      "[data-testid='coach-panel-dismiss']",
    );
    expect(dismiss, "dismiss control must remain in the scroll body").not.toBeNull();
    dismiss!.click();
    await tick();
    expect(dismissed).toBe(true);
  });

  // FR-21 (ADR-0037): no descendant of the coach panel may declare a horizontal
  // scroll axis. jsdom can't compute real overflow, so we assert the className
  // contract that produces it — the single guard that keeps the "scroll within
  // scroll" from regressing. (Live overflow is asserted by the e2e FR-21 test.)
  it("FR-21: no coach-panel descendant declares overflow-x auto/scroll", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const panel = container.querySelector("[data-testid='coach-panel']");
    expect(panel).not.toBeNull();
    const offenders = Array.from(panel!.querySelectorAll<HTMLElement>("*"))
      .filter((el) => /overflow-x-(auto|scroll)/.test(el.className ?? ""))
      .map((el) => el.getAttribute("data-testid") ?? el.className);
    expect(offenders, `horizontal-scroll offenders: ${offenders.join(", ")}`).toEqual(
      [],
    );
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

describe("CoachPanel — stacked chrome + chips in scroll body (FR-22)", () => {
  // FR-22 (ADR-0037): quick-action chips move OUT of the pinned composer bar into
  // the single scroll body, so they scroll with the transcript and never form a
  // horizontal-scroll strip. (G8: supersedes the prior "chips by composer" pin.)
  it("uses stacked chrome; chips live in the scroll body, not the pinned bar", async () => {
    await render(<CoachPanel runtime={scriptedRuntime()} hintLadder={LADDER} />);
    const chrome = container.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("stacked");
    expect(chrome?.className ?? "").not.toMatch(/coach-layout-rail/);
    // chrome (Zone A header) still carries no chips
    expect(
      chrome?.querySelectorAll("[data-testid='coach-chip']").length ?? 0,
    ).toBe(0);
    // chips are in the scroll body (Zone B), NOT in the pinned composer bar
    expect(
      container.querySelectorAll(
        "[data-testid='coach-zone-b'] [data-testid='coach-chip']",
      ).length,
    ).toBe(3);
    expect(
      container.querySelectorAll(
        "[data-testid='coach-zone-c'] [data-testid='coach-chip']",
      ).length,
    ).toBe(0);
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

describe("CoachPanel — commit-first retires quiz-pin ladder (FR-2)", () => {
  it("flag ON: idle copy present; no nudge / hint-ladder in quiz context", async () => {
    await render(
      <CoachPanel
        runtime={scriptedRuntime()}
        hintLadder={LADDER}
        mode="pre_submit"
        commitFirstCoach
      />,
    );
    expect(container.textContent).toContain(
      "Commit to a choice — coaching starts from what you pick",
    );
    expect(container.querySelector("[data-testid='one-more-nudge']")).toBeNull();
    expect(container.querySelector("[data-testid='hint-ladder-list']")).toBeNull();
  });

  it("T19/V10: wrong-pick suppresses the generic CONVERSATION opener bubble", async () => {
    await render(
      <CoachPanel
        runtime={scriptedRuntime()}
        hintLadder={LADDER}
        mode="pre_submit"
        commitFirstCoach
        coachedLoop={{
          wrongLetters: ["B"],
          activeLetter: "B",
          rungsRevealed: { B: 1 },
          exhausted: false,
          rungCap: 3,
        }}
      />,
    );
    expect(container.querySelector("[data-testid='coach-opener']")).toBeNull();
    expect(container.textContent).not.toContain(
      "You're in the coaching loop for that pick",
    );
    expect(
      container.querySelector("[data-testid='quiz-pick-echo']")?.textContent,
    ).toBe("I chose B.");
  });
});
