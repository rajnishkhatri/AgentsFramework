/**
 * BP-1.5b — CoachWorkspace (FR-2, FR-3; red-first structure).
 *
 * Standalone coach composition: Back / Wrap-up header, rail vs strip body,
 * chips in the chat column (not in chrome). Repo convention: static markup +
 * JSDOM; click via createRoot.
 */

import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoachWorkspace } from "./CoachWorkspace";
import {
  COACH_CHIP_SEEDS,
  toCoachSurfaceVM,
} from "@/lib/translators/coach_surface_vm";

function vm() {
  return toCoachSurfaceVM({
    mode: "pre_submit",
    pin: null,
    missesOnSkill: null,
    skillLabel: null,
    chipSeeds: COACH_CHIP_SEEDS,
  });
}

function staticDoc(
  props: React.ComponentProps<typeof CoachWorkspace>,
): Document {
  const html = renderToStaticMarkup(
    React.createElement(CoachWorkspace, props),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

const base = {
  vm: vm(),
  turns: [] as const,
  busy: false,
  onAsk: () => {},
  onRetry: () => {},
  onBack: () => {},
  onWrapUp: () => {},
};

describe("CoachWorkspace — header actions (FR-2)", () => {
  it("renders Back and Wrap up session controls", () => {
    const doc = staticDoc({ ...base, layout: "rail" });
    expect(doc.querySelector("[data-testid='coach-back']")?.textContent).toContain(
      "Back",
    );
    expect(
      doc.querySelector("[data-testid='coach-wrap-up']")?.textContent,
    ).toContain("Wrap up session");
  });
});

describe("CoachWorkspace — desktop rail (FR-3)", () => {
  it("rail layout: chrome without chips; chips live in chat column", () => {
    const doc = staticDoc({ ...base, layout: "rail" });
    const root = doc.querySelector("[data-testid='coach-workspace']");
    expect(root?.getAttribute("data-layout")).toBe("rail");
    expect(doc.querySelector("[data-testid='coach-context-column']")).toBeTruthy();
    expect(doc.querySelector("[data-testid='coach-chat-column']")).toBeTruthy();
    const chrome = doc.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("rail");
    expect(chrome?.className ?? "").toMatch(/coach-layout-rail/);
    // Chips only in chat column (chrome showChips=false)
    const chromeChips = chrome?.querySelectorAll("[data-testid='coach-chip']") ?? [];
    expect(chromeChips.length).toBe(0);
    expect(
      doc.querySelectorAll(
        "[data-testid='coach-chat-column'] [data-testid='coach-chip']",
      ).length,
    ).toBe(3);
  });
});

describe("CoachWorkspace — iPad strip (FR-1)", () => {
  it("strip layout: no left-rail column class; centered body", () => {
    const doc = staticDoc({ ...base, layout: "strip" });
    const root = doc.querySelector("[data-testid='coach-workspace']");
    expect(root?.getAttribute("data-layout")).toBe("strip");
    const chrome = doc.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("strip");
    expect(chrome?.className ?? "").not.toMatch(/coach-layout-rail/);
    expect(doc.querySelector("[data-testid='coach-chat-column']")).toBeTruthy();
  });
});

describe("CoachWorkspace — header clicks", () => {
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

  it("Back and Wrap up invoke handlers", async () => {
    const onBack = vi.fn();
    const onWrapUp = vi.fn();
    root.render(
      React.createElement(CoachWorkspace, {
        ...base,
        layout: "rail",
        onBack,
        onWrapUp,
      }),
    );
    await tick();
    container.querySelector<HTMLButtonElement>("[data-testid='coach-back']")!.click();
    container
      .querySelector<HTMLButtonElement>("[data-testid='coach-wrap-up']")!
      .click();
    await tick();
    expect(onBack).toHaveBeenCalledTimes(1);
    expect(onWrapUp).toHaveBeenCalledTimes(1);
  });
});
