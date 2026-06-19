/**
 * recalledItems (Phase B B2) — pure join of a turn's recalled KEYS against the
 * owner's loaded memory panel. Content never rides the recall wire event; this
 * join is how the eval view gets type+content for a recalled key.
 */

import { describe, expect, it } from "vitest";
import { recalledItems } from "./chat-shell";
import type { MemoryItem } from "@/lib/wire/agent_protocol";

function item(key: string, content: string): MemoryItem {
  return { key, type: "semantic", content, salience: null };
}

describe("recalledItems", () => {
  it("returns [] when no keys were recalled", () => {
    expect(recalledItems([], [item("k1", "x")])).toEqual([]);
  });

  it("resolves keys to panel items, preserving recall order", () => {
    const memories = [item("k1", "metric"), item("k2", "Berlin"), item("k3", "z")];
    const out = recalledItems(["k2", "k1"], memories);
    expect(out.map((m) => m.key)).toEqual(["k2", "k1"]);
    expect(out.map((m) => m.content)).toEqual(["Berlin", "metric"]);
  });

  it("drops a recalled key with no matching panel item (no contentless row)", () => {
    // A key the panel hasn't loaded (privacy: the event carries no content) is
    // simply not shown rather than rendered empty.
    const out = recalledItems(["k1", "missing"], [item("k1", "metric")]);
    expect(out.map((m) => m.key)).toEqual(["k1"]);
  });
});
