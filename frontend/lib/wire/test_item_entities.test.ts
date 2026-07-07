/**
 * L1 tests for the Phase-6 governed-plane wire entities (ADR-0015, FR-24.1).
 *
 * Failure paths first (TAP-4): every invalid-blueprint rejection is asserted
 * BEFORE the happy-path parse. `TestBlueprint` validation is the FR-24.1 gate —
 * a malformed blueprint must throw at parse, never silently clamp.
 */

import { describe, expect, it } from "vitest";
import { TestBlueprint, TestItem } from "./engine_entities";

function blueprint(over: Record<string, unknown> = {}) {
  return {
    id: "bp-english-mini",
    subject: "act-english",
    skill_mix: { "s-gram": 0.5, "s-punc": 0.5 },
    difficulty_dist: { "3": 1.0 },
    count: 10,
    minutes: 20,
    scale_band_table: [{ raw_min: 0, raw_max: 10, scale: 20 }],
    seed: 42,
    ...over,
  };
}

function item(over: Record<string, unknown> = {}) {
  return {
    id: "ti-gen-abc123",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "The committee <u>were</u> unanimous in its decision.",
    stem_md: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE" },
      { letter: "B", label: "was" },
      { letter: "C", label: "have been" },
      { letter: "D", label: "being" },
    ],
    answer_letter: "B",
    per_choice_rationale: {
      A: "'Committee' acts as a single unit here, so the plural verb clashes.",
      B: "'Committee' is singular in this sentence — 'was' agrees.",
      C: "Still plural, and shifts the tense needlessly.",
      D: "'being' leaves the sentence without a finite verb.",
    },
    why_correct_md: "A collective noun acting as one unit takes a **singular** verb.",
    why_tempted_md: "The plural people inside the committee make 'were' sound right.",
    rule_md: "Collective nouns are singular when the group acts as one.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "gpt-4o-mini@run-1",
    ...over,
  };
}

describe("TestBlueprint — failure paths first (FR-24.1)", () => {
  it("rejects skill_mix weights that do not sum to 1.0", () => {
    expect(() =>
      TestBlueprint.parse(blueprint({ skill_mix: { "s-gram": 0.3, "s-punc": 0.3 } })),
    ).toThrow();
  });

  it("rejects count <= 0", () => {
    expect(() => TestBlueprint.parse(blueprint({ count: 0 }))).toThrow();
  });

  it("rejects an empty scale_band_table", () => {
    expect(() => TestBlueprint.parse(blueprint({ scale_band_table: [] }))).toThrow();
  });

  it("rejects a missing seed", () => {
    const { seed: _seed, ...noSeed } = blueprint();
    expect(() => TestBlueprint.parse(noSeed)).toThrow();
  });
});

describe("TestBlueprint — valid parse", () => {
  it("accepts a well-formed blueprint (skill_mix sums to 1.0)", () => {
    const parsed = TestBlueprint.parse(blueprint());
    expect(parsed.count).toBe(10);
    expect(parsed.seed).toBe(42);
  });

  it("accepts skill_mix summing to 1.0 within float tolerance", () => {
    // three thirds — never exactly 1.0 in float
    const parsed = TestBlueprint.parse(
      blueprint({ skill_mix: { a: 1 / 3, b: 1 / 3, c: 1 / 3 } }),
    );
    expect(parsed.skill_mix).toBeDefined();
  });

  it("treats pass_criteria as optional (assembles without it)", () => {
    expect(() => TestBlueprint.parse(blueprint())).not.toThrow();
  });
});

describe("TestItem", () => {
  it("parses a reviewed item with four choices", () => {
    const parsed = TestItem.parse(item());
    expect(parsed.answer_letter).toBe("B");
    expect(parsed.choices).toHaveLength(4);
    expect(parsed.reviewed).toBe(true);
  });

  it("carries reviewed=false for an unpromoted seed row", () => {
    const parsed = TestItem.parse(item({ reviewed: false }));
    expect(parsed.reviewed).toBe(false);
  });
});

describe("TestItem — teaching fields (FR-C1, ADR-0021 schema extension)", () => {
  // Failure paths first (TAP-4): a bank row missing a teaching field must
  // fail at parse — the Feedback screen renders these (feedback_vm reads
  // per_choice_rationale + rule_md), so an ungated gap becomes blank feedback.
  it.each([
    "context_html",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
    "rule_md",
    "item_type",
  ] as const)("rejects a row missing %s", (field) => {
    const { [field]: _omitted, ...rest } = item() as Record<string, unknown>;
    expect(() => TestItem.parse(rest)).toThrow();
  });

  it("rejects an empty rule_md (blank feedback is the gap this closes)", () => {
    expect(() => TestItem.parse(item({ rule_md: "" }))).toThrow();
  });

  it("carries every teaching field through parse (lossless Question mapping)", () => {
    const parsed = TestItem.parse(item());
    expect(parsed.context_html).toContain("<u>");
    expect(parsed.per_choice_rationale["B"]).toContain("singular");
    expect(parsed.why_correct_md).toContain("singular");
    expect(parsed.why_tempted_md.length).toBeGreaterThan(0);
    expect(parsed.rule_md).toContain("Collective");
    expect(parsed.item_type).toBe("underlined-span-mc");
  });
});
