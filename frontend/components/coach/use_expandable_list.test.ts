/**
 * use_expandable_list — FR-3/4/7/13/14 (Direction 2b / Q-C5).
 *
 * Pure fold is node-testable; the hook wraps it.
 */

import { describe, expect, it } from "vitest";
import {
  deriveExpandedIds,
  reduceExpandableList,
  type ExpandableListState,
} from "./use_expandable_list";

describe("deriveExpandedIds — conversation (autoCollapseOnComplete)", () => {
  it("FR-13: newest completed expanded; prior non-error collapsed", () => {
    const ids = deriveExpandedIds({
      ids: ["a", "b", "c"],
      manual: new Map(),
      forceExpandedIds: new Set(),
      autoCollapseOnComplete: true,
    });
    expect(ids.has("c")).toBe(true);
    expect(ids.has("a")).toBe(false);
    expect(ids.has("b")).toBe(false);
  });

  it("FR-3: forceExpanded (streaming) always expanded; prior collapse", () => {
    const ids = deriveExpandedIds({
      ids: ["a", "b"],
      manual: new Map(),
      forceExpandedIds: new Set(["b"]),
      autoCollapseOnComplete: true,
    });
    expect(ids.has("b")).toBe(true);
    expect(ids.has("a")).toBe(false);
  });

  it("FR-4: error in forceExpanded stays open with newest", () => {
    const ids = deriveExpandedIds({
      ids: ["a", "b"],
      manual: new Map(),
      forceExpandedIds: new Set(["a"]),
      autoCollapseOnComplete: true,
    });
    expect(ids.has("a")).toBe(true);
    expect(ids.has("b")).toBe(true);
  });

  it("manual override wins over newest/default when not forced", () => {
    const ids = deriveExpandedIds({
      ids: ["a", "b"],
      manual: new Map([
        ["a", true],
        ["b", false],
      ]),
      forceExpandedIds: new Set(),
      autoCollapseOnComplete: true,
    });
    expect(ids.has("a")).toBe(true);
    expect(ids.has("b")).toBe(false);
  });

  it("force-expand beats manual collapse", () => {
    const ids = deriveExpandedIds({
      ids: ["a", "b"],
      manual: new Map([
        ["a", false],
        ["b", false],
      ]),
      forceExpandedIds: new Set(["a", "b"]),
      autoCollapseOnComplete: true,
    });
    expect(ids.has("a")).toBe(true);
    expect(ids.has("b")).toBe(true);
  });

  it("empty ids → empty set", () => {
    expect(
      deriveExpandedIds({
        ids: [],
        manual: new Map(),
        forceExpandedIds: new Set(),
        autoCollapseOnComplete: true,
      }).size,
    ).toBe(0);
  });
});

describe("deriveExpandedIds — ladder (autoExpandNewest)", () => {
  it("FR-14: new id auto-expands; others retain prior expanded state", () => {
    // Prior: a expanded via manual; b collapsed. New c appears → c expands; a stays.
    const ids = deriveExpandedIds({
      ids: ["a", "b", "c"],
      manual: new Map([["a", true]]),
      forceExpandedIds: new Set(),
      autoExpandNewest: true,
      previousIds: ["a", "b"],
    });
    expect(ids.has("c")).toBe(true);
    expect(ids.has("a")).toBe(true);
    expect(ids.has("b")).toBe(false);
  });

  it("ladder with no prior: only newest open by default", () => {
    const ids = deriveExpandedIds({
      ids: ["a", "b"],
      manual: new Map(),
      forceExpandedIds: new Set(),
      autoExpandNewest: true,
      previousIds: [],
    });
    expect(ids.has("b")).toBe(true);
    expect(ids.has("a")).toBe(false);
  });
});

describe("reduceExpandableList — toggle ignored when forced", () => {
  it("stores manual override when not forced", () => {
    let state: ExpandableListState = { manual: new Map(), seenIds: ["a", "b"] };
    const expanded = deriveExpandedIds({
      ids: ["a", "b"],
      manual: state.manual,
      forceExpandedIds: new Set(),
      autoCollapseOnComplete: true,
    });
    expect(expanded.has("a")).toBe(false);
    state = reduceExpandableList(state, { type: "toggle", id: "a" }, {
      ids: ["a", "b"],
      forceExpandedIds: new Set(),
      autoCollapseOnComplete: true,
    });
    expect(state.manual.get("a")).toBe(true);
  });

  it("FR-3/4: toggle is a no-op for forceExpanded ids", () => {
    let state: ExpandableListState = { manual: new Map(), seenIds: ["a"] };
    state = reduceExpandableList(state, { type: "toggle", id: "a" }, {
      ids: ["a"],
      forceExpandedIds: new Set(["a"]),
      autoCollapseOnComplete: true,
    });
    expect(state.manual.has("a")).toBe(false);
  });
});
