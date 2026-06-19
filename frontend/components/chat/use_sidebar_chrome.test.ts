/**
 * use_sidebar_chrome — pure persistence-helper tests (jsdom project, but these
 * exercise only the framework-free read/write helpers via an injected storage,
 * mirroring how use_chat_sidebars tests its pure fetch functions).
 *
 * Failure paths first (FD6): a throwing / absent storage must never crash the
 * read or the write — the panel falls back to "expanded" and the persist is a
 * silent no-op. The collapse toggle is a cosmetic preference, not data; losing
 * it must degrade gracefully, never surface an error.
 */

import { describe, expect, it, vi } from "vitest";
import {
  COLLAPSED_STORAGE_KEY,
  readCollapsed,
  writeCollapsed,
} from "./use_sidebar_chrome";

/** A throwing storage (e.g. Safari private mode quota / SSR-less window). */
const throwingStorage: Pick<Storage, "getItem" | "setItem"> = {
  getItem() {
    throw new Error("storage blocked");
  },
  setItem() {
    throw new Error("storage blocked");
  },
};

function memoryStorage(seed: Record<string, string> = {}): Pick<
  Storage,
  "getItem" | "setItem"
> {
  const map = new Map(Object.entries(seed));
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => void map.set(k, v),
  };
}

describe("readCollapsed — failure paths first", () => {
  it("defaults to false (expanded) when storage is null", () => {
    expect(readCollapsed(null)).toBe(false);
  });

  it("defaults to false when getItem throws (private-mode / blocked)", () => {
    expect(readCollapsed(throwingStorage)).toBe(false);
  });

  it("defaults to false when no value has been stored yet", () => {
    expect(readCollapsed(memoryStorage())).toBe(false);
  });

  it("reads true only for the exact persisted '1' sentinel", () => {
    expect(readCollapsed(memoryStorage({ [COLLAPSED_STORAGE_KEY]: "1" }))).toBe(
      true,
    );
    expect(
      readCollapsed(memoryStorage({ [COLLAPSED_STORAGE_KEY]: "true" })),
    ).toBe(false);
  });
});

describe("writeCollapsed — failure paths first", () => {
  it("is a silent no-op when storage is null", () => {
    expect(() => writeCollapsed(null, true)).not.toThrow();
  });

  it("swallows a throwing setItem (never surfaces a preference error)", () => {
    expect(() => writeCollapsed(throwingStorage, true)).not.toThrow();
  });

  it("round-trips: writeCollapsed(true) then readCollapsed === true", () => {
    const s = memoryStorage();
    writeCollapsed(s, true);
    expect(readCollapsed(s)).toBe(true);
    writeCollapsed(s, false);
    expect(readCollapsed(s)).toBe(false);
  });

  it("persists under the namespaced key", () => {
    const setItem = vi.fn();
    writeCollapsed({ getItem: () => null, setItem }, true);
    expect(setItem).toHaveBeenCalledWith(COLLAPSED_STORAGE_KEY, "1");
  });
});
