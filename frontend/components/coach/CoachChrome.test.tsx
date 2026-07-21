/**
 * Sprint B1 — CoachChrome (FR-2, FR-4, FR-5, FR-8; red-first).
 *
 * Presentational leaf for shared coach workspace chrome. Structure via
 * renderToStaticMarkup + JSDOM; chip click via createRoot (repo convention:
 * no @testing-library/react).
 */

import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoachChrome } from "./CoachChrome";
import {
  COACH_CHIP_SEEDS,
  toCoachSurfaceVM,
  type CoachSurfaceInputs,
} from "@/lib/translators/coach_surface_vm";

function vm(over: Partial<CoachSurfaceInputs> = {}) {
  return toCoachSurfaceVM({
    mode: "pre_submit",
    pin: null,
    missesOnSkill: null,
    skillLabel: null,
    chipSeeds: COACH_CHIP_SEEDS,
    ...over,
  });
}

function staticDoc(
  props: React.ComponentProps<typeof CoachChrome>,
): Document {
  const html = renderToStaticMarkup(React.createElement(CoachChrome, props));
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("CoachChrome — structure (FR-4)", () => {
  it("renders rail, modes, and chips with stable testids", () => {
    const doc = staticDoc({ vm: vm(), busy: false, onAsk: () => {} });
    expect(doc.querySelector("[data-testid='coach-chrome']")).toBeTruthy();
    expect(doc.querySelector("[data-testid='coach-rail']")?.textContent).toContain(
      "Your Coach",
    );
    expect(doc.querySelector("[data-testid='coach-modes']")).toBeTruthy();
    expect(doc.querySelectorAll("[data-testid='coach-chip']").length).toBe(3);
  });

  it("omits current-item and history when absent (FR-1, FR-3)", () => {
    const doc = staticDoc({ vm: vm(), busy: false, onAsk: () => {} });
    expect(doc.querySelector("[data-testid='coach-current-item']")).toBeNull();
    expect(doc.querySelector("[data-testid='coach-history']")).toBeNull();
  });

  it("FR-21: mode + chip rows never scroll horizontally (they wrap)", () => {
    const doc = staticDoc({ vm: vm(), busy: false, onAsk: () => {} });
    for (const id of ["coach-modes", "coach-chips"]) {
      const el = doc.querySelector(`[data-testid='${id}']`);
      expect(el, id).toBeTruthy();
      expect(el?.className ?? "", `${id} must not overflow-x`).not.toMatch(
        /overflow-x-(auto|scroll)/,
      );
      expect(el?.className ?? "", `${id} must wrap`).toContain("flex-wrap");
    }
  });

  it("shows current-item and history when present (FR-5, FR-6)", () => {
    const doc = staticDoc({
      vm: vm({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q4 · Commas" },
        missesOnSkill: 3,
        skillLabel: "Commas",
      }),
      busy: false,
      onAsk: () => {},
    });
    expect(
      doc.querySelector("[data-testid='coach-current-item']")?.textContent,
    ).toContain("Q4 · Commas");
    expect(
      doc.querySelector("[data-testid='coach-history']")?.textContent,
    ).toContain("3 misses on Commas");
  });
});

describe("CoachChrome — display-only modes (FR-2)", () => {
  it("mode labels are not buttons that change mode", () => {
    const doc = staticDoc({ vm: vm(), busy: false, onAsk: () => {} });
    const modes = doc.querySelector("[data-testid='coach-modes']");
    expect(modes?.querySelector("button")).toBeNull();
    const active = modes?.querySelector("[data-active='true']");
    expect(active?.textContent).toContain("In-drill Socratic");
  });
});

describe("CoachChrome — layout variants (BP-1.5a / FR-1, FR-3)", () => {
  it('layout="rail" marks a left-rail region and can omit chips', () => {
    const doc = staticDoc({
      vm: vm(),
      busy: false,
      onAsk: () => {},
      layout: "rail",
      showChips: false,
    });
    const chrome = doc.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("rail");
    expect(doc.querySelector("[data-testid='coach-rail']")).toBeTruthy();
    expect(doc.querySelectorAll("[data-testid='coach-chip']").length).toBe(0);
  });

  it('layout="strip" marks header-strip (no left-rail column class)', () => {
    const doc = staticDoc({
      vm: vm(),
      busy: false,
      onAsk: () => {},
      layout: "strip",
      showChips: false,
    });
    const chrome = doc.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("strip");
    expect(chrome?.className ?? "").not.toMatch(/coach-layout-rail/);
    expect(doc.querySelectorAll("[data-testid='coach-chip']").length).toBe(0);
  });

  it('layout="stacked" keeps chrome without left-rail column class', () => {
    const doc = staticDoc({
      vm: vm(),
      busy: false,
      onAsk: () => {},
      layout: "stacked",
    });
    const chrome = doc.querySelector("[data-testid='coach-chrome']");
    expect(chrome?.getAttribute("data-layout")).toBe("stacked");
    expect(chrome?.className ?? "").not.toMatch(/coach-layout-rail/);
    expect(doc.querySelectorAll("[data-testid='coach-chip']").length).toBe(3);
  });

  it("defaults to stacked with chips when layout/showChips omitted (B1 compat)", () => {
    const doc = staticDoc({ vm: vm(), busy: false, onAsk: () => {} });
    expect(
      doc.querySelector("[data-testid='coach-chrome']")?.getAttribute("data-layout"),
    ).toBe("stacked");
    expect(doc.querySelectorAll("[data-testid='coach-chip']").length).toBe(3);
  });
});

describe("CoachChrome — chips → onAsk (FR-8)", () => {
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

  it("clicking a chip calls onAsk with the seed once when not busy", async () => {
    const onAsk = vi.fn();
    root.render(
      React.createElement(CoachChrome, { vm: vm(), busy: false, onAsk }),
    );
    await tick();
    const chip = container.querySelector<HTMLButtonElement>(
      "[data-testid='coach-chip']",
    );
    expect(chip).not.toBeNull();
    chip!.click();
    await tick();
    expect(onAsk).toHaveBeenCalledTimes(1);
    expect(onAsk).toHaveBeenCalledWith("Explain the rule simply");
  });

  it("chips are disabled while busy", async () => {
    const onAsk = vi.fn();
    root.render(
      React.createElement(CoachChrome, { vm: vm(), busy: true, onAsk }),
    );
    await tick();
    const chips = container.querySelectorAll<HTMLButtonElement>(
      "[data-testid='coach-chip']",
    );
    expect(chips.length).toBe(3);
    for (const c of chips) {
      expect(c.disabled).toBe(true);
      c.click();
    }
    await tick();
    expect(onAsk).not.toHaveBeenCalled();
  });
});
