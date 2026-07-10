/**
 * L1 tests for the seeded test-form assembler (Phase 6, ADR-0015, FR-26/27).
 *
 * Failure path FIRST (TAP-4): a bank that cannot satisfy the blueprint fails
 * closed with the named short stratum, asserted BEFORE any happy path. Then the
 * determinism contract: byte-identical 10x for a fixed seed, wrong-seed differs,
 * and the independent reviewed filter (FR-27.1 at the assembler layer).
 */

import { describe, expect, it } from "vitest";
import {
  assembleTestForm,
  ShortStratumError,
} from "./assemble_test_form";
import type { TestBlueprint, TestItem } from "../../../wire/engine_entities";

function item(id: string, over: Partial<TestItem> = {}): TestItem {
  return {
    id,
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: `passage <u>${id}</u>`,
    stem_md: `stem ${id}`,
    choices: [
      { letter: "A", label: "a", is_no_change: true },
      { letter: "B", label: "b", is_no_change: false },
      { letter: "C", label: "c", is_no_change: false },
      { letter: "D", label: "d", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "a…", B: "b…", C: "c…", D: "d…" },
    why_correct_md: "why-correct",
    why_tempted_md: "why-tempted",
    rule_md: "rule",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "gpt-4o-mini@run-1",
    ...over,
  };
}

// A bank of 10 reviewed gram items + 10 reviewed punc items, all difficulty 3.
function bank(): TestItem[] {
  const rows: TestItem[] = [];
  for (let i = 0; i < 10; i++) rows.push(item(`gram-${i}`, { skill_id: "s-gram" }));
  for (let i = 0; i < 10; i++) rows.push(item(`punc-${i}`, { skill_id: "s-punc" }));
  return rows;
}

function blueprint(over: Partial<TestBlueprint> = {}): TestBlueprint {
  return {
    id: "bp-mix",
    subject: "act-english",
    skill_mix: { "s-gram": 0.5, "s-punc": 0.5 },
    difficulty_dist: { "3": 1.0 },
    count: 6,
    minutes: 12,
    scale_band_table: [{ raw_min: 0, raw_max: 6, scale: 20 }],
    seed: 42,
    ...over,
  };
}

describe("assembleTestForm — fail closed first (FR-26.1)", () => {
  it("throws ShortStratumError naming the short skill when the bank is thin", () => {
    // blueprint wants 3 gram + 3 punc; provide only 1 gram.
    const thin = [item("gram-only", { skill_id: "s-gram" })];
    expect(() => assembleTestForm(blueprint(), thin)).toThrow(ShortStratumError);
  });

  it("names the short stratum in the error", () => {
    // Enough gram (sorted first, so it clears), zero punc → punc is the short
    // stratum the deterministic scan reports.
    const gramOnly = Array.from({ length: 10 }, (_, i) =>
      item(`gram-${i}`, { skill_id: "s-gram" }),
    );
    try {
      assembleTestForm(blueprint(), gramOnly);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(String(err)).toContain("s-punc");
    }
  });

  it("never draws a reviewed=false item (FR-27.1 assembler-layer filter)", () => {
    // Enough reviewed to satisfy, plus an unreviewed decoy that must be ignored.
    const rows = [
      ...bank(),
      item("gram-bad", { skill_id: "s-gram", reviewed: false }),
    ];
    const form = assembleTestForm(blueprint(), rows);
    expect(form.items.every((i) => i.reviewed === true)).toBe(true);
    expect(form.items.some((i) => i.id === "gram-bad")).toBe(false);
  });
});

describe("assembleTestForm — determinism (FR-26.2/26.3)", () => {
  it("emits a byte-identical form across 10 runs for a fixed seed", () => {
    const forms = Array.from({ length: 10 }, () =>
      assembleTestForm(blueprint(), bank()),
    );
    const first = JSON.stringify(forms[0]);
    for (const f of forms) expect(JSON.stringify(f)).toBe(first);
  });

  it("is insensitive to input bank order (internal sort by id)", () => {
    const a = assembleTestForm(blueprint(), bank());
    const shuffled = [...bank()].reverse();
    const b = assembleTestForm(blueprint(), shuffled);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });

  it("produces a different form for a different seed", () => {
    const a = assembleTestForm(blueprint({ seed: 42 }), bank());
    const b = assembleTestForm(blueprint({ seed: 43 }), bank());
    expect(JSON.stringify(a)).not.toBe(JSON.stringify(b));
  });

  it("draws the blueprint count, honoring the skill mix", () => {
    const form = assembleTestForm(blueprint(), bank());
    expect(form.items).toHaveLength(6);
    const gram = form.items.filter((i) => i.skill_id === "s-gram").length;
    const punc = form.items.filter((i) => i.skill_id === "s-punc").length;
    expect(gram).toBe(3);
    expect(punc).toBe(3);
  });

  it("never repeats an item within a form", () => {
    const form = assembleTestForm(blueprint(), bank());
    const ids = form.items.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
