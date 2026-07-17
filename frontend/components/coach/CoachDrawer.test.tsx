/**
 * CoachDrawer — FR-2 Escape + focus restore (jsdom).
 */

import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CoachDrawer } from "./CoachDrawer";

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

const tick = (ms = 20): Promise<void> => new Promise((r) => setTimeout(r, ms));

describe("CoachDrawer", () => {
  it("Escape calls onClose; focus returns to restore target on close", async () => {
    const onClose = vi.fn();
    const pill = document.createElement("button");
    pill.textContent = "Coach";
    document.body.appendChild(pill);
    const restoreRef = { current: pill };

    root.render(
      <CoachDrawer open onClose={onClose} restoreFocusRef={restoreRef}>
        <div>panel</div>
      </CoachDrawer>,
    );
    await tick(50);
    expect(container.querySelector("[data-testid='coach-drawer']")).not.toBeNull();
    // Effect attaches Escape listener after paint — wait for close focus.
    await tick(30);

    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    expect(onClose).toHaveBeenCalled();

    root.render(
      <CoachDrawer open={false} onClose={onClose} restoreFocusRef={restoreRef}>
        <div>panel</div>
      </CoachDrawer>,
    );
    await tick(250);
    expect(document.activeElement).toBe(pill);
    pill.remove();
  });

  it("scrim click closes", async () => {
    const onClose = vi.fn();
    root.render(
      <CoachDrawer open onClose={onClose}>
        <div>panel</div>
      </CoachDrawer>,
    );
    await tick();
    container
      .querySelector<HTMLButtonElement>("[data-testid='coach-drawer-scrim']")
      ?.click();
    expect(onClose).toHaveBeenCalled();
  });

  it("root is position:absolute (scoped to host — must not cover the sidebar rail)", async () => {
    // FR-B1: learners must still reach Home / Progress while the drawer is open.
    // fixed inset-0 covered the left rail; absolute keeps the overlay in <main>.
    root.render(
      <CoachDrawer open onClose={() => undefined}>
        <div>panel</div>
      </CoachDrawer>,
    );
    await tick();
    const rootEl = container.querySelector<HTMLElement>(
      "[data-testid='coach-drawer-root']",
    );
    expect(rootEl).not.toBeNull();
    expect(rootEl!.className).toMatch(/\babsolute\b/);
    expect(rootEl!.className).not.toMatch(/\bfixed\b/);
  });
});
