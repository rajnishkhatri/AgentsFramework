/**
 * shell_layout_store — Home/Progress LS + panel dismiss (FR-9/19).
 * Pin / content-screen auto-collapse removed (Q-C3 / Direction 2b).
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  getShellLayoutSnapshot,
  resetShellLayoutStore,
  setPanelDismissed,
  setSidebarCollapsed,
  toggleSidebarCollapsed,
  SIDEBAR_STORAGE_KEY,
  PANEL_DISMISSED_KEY,
} from "./shell_layout_store";

/** Minimal in-memory Storage for node vitest (no jsdom required). */
function memoryStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear() {
      map.clear();
    },
    getItem(key: string) {
      return map.has(key) ? map.get(key)! : null;
    },
    setItem(key: string, value: string) {
      map.set(key, value);
    },
    removeItem(key: string) {
      map.delete(key);
    },
    key(index: number) {
      return [...map.keys()][index] ?? null;
    },
  };
}

beforeEach(() => {
  const local = memoryStorage();
  const session = memoryStorage();
  Object.defineProperty(globalThis, "localStorage", {
    value: local,
    configurable: true,
    writable: true,
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    value: session,
    configurable: true,
    writable: true,
  });
  resetShellLayoutStore();
});

afterEach(() => {
  resetShellLayoutStore();
});

describe("shell_layout_store — Home/Progress persistence (FR-9)", () => {
  it("defaults to expanded sidebar; no pin field", () => {
    const s = getShellLayoutSnapshot();
    expect(s.sidebarCollapsed).toBe(false);
    expect(s.panelDismissed).toBe(false);
    expect("sidebarUserPinned" in s).toBe(false);
  });

  it("persists sidebar preference to localStorage", () => {
    setSidebarCollapsed(true);
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe("collapsed");
    setSidebarCollapsed(false);
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe("expanded");
  });

  it("hydrates sidebarCollapsed from localStorage on reset", () => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, "collapsed");
    resetShellLayoutStore();
    expect(getShellLayoutSnapshot().sidebarCollapsed).toBe(true);
  });

  it("toggle expands/collapses without session pin key", () => {
    toggleSidebarCollapsed();
    expect(getShellLayoutSnapshot().sidebarCollapsed).toBe(true);
    expect(sessionStorage.getItem("preact.shell.sidebarPinned")).toBeNull();
    toggleSidebarCollapsed();
    expect(getShellLayoutSnapshot().sidebarCollapsed).toBe(false);
    expect(sessionStorage.getItem("preact.shell.sidebarPinned")).toBeNull();
  });

  it("does not export pin / content-screen auto-collapse APIs", async () => {
    const mod = await import("./shell_layout_store");
    expect("pinSidebarExpanded" in mod).toBe(false);
    expect("applyContentScreenAutoCollapse" in mod).toBe(false);
    expect("SIDEBAR_PIN_KEY" in mod).toBe(false);
  });
});

describe("shell_layout_store — panel dismiss (FR-19)", () => {
  it("persists panelDismissed in sessionStorage", () => {
    setPanelDismissed(true);
    expect(getShellLayoutSnapshot().panelDismissed).toBe(true);
    expect(sessionStorage.getItem(PANEL_DISMISSED_KEY)).toBe("1");
    setPanelDismissed(false);
    expect(sessionStorage.getItem(PANEL_DISMISSED_KEY)).toBeNull();
  });
});
