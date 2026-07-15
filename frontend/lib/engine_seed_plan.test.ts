/**
 * FR-1..3 — planEngineSeed pure decision helper (the NODE_ENV test-seam
 * resolution, tasks §"Design-risk resolution"). Table-driven; no env flip.
 *
 * Truth table (validated against the existing non-prod branch in
 * composition_engine_browser.ts:241-255):
 *   (isProd=true,  "fresh")     → "fresh-pack"   (FR-3: the only prod seed path)
 *   (isProd=true,  "demo")      → "none"         (FR-1: prod non-fresh → empty)
 *   (isProd=true,  undefined)   → "none"         (FR-1: undecidable → empty, AP-6)
 *   (isProd=false, "fresh")     → "fresh-pack"
 *   (isProd=false, "demo")      → "demo-corpus"
 *   (isProd=false, undefined)   → "demo-corpus"  (latch defaults to demo in dev)
 */

import { describe, expect, it } from "vitest";
import { planEngineSeed } from "@/lib/engine_seed_plan";
import type { SeedMode } from "@/lib/learn/resolve_learn_identity";

describe("planEngineSeed (FR-1..3)", () => {
  it.each<[boolean, SeedMode | undefined, string]>([
    // FR-1 failure path FIRST: prod non-fresh seeds nothing.
    [true, "demo", "none"],
    [true, undefined, "none"],
    // FR-3: prod fresh is the only positive prod seed path.
    [true, "fresh", "fresh-pack"],
    // Non-prod parity (unchanged behavior).
    [false, "fresh", "fresh-pack"],
    [false, "demo", "demo-corpus"],
    [false, undefined, "demo-corpus"],
  ])("planEngineSeed(isProd=%s, seedMode=%s) → %s", (isProd, seedMode, expected) => {
    expect(planEngineSeed({ isProd, seedMode })).toBe(expected);
  });
});
