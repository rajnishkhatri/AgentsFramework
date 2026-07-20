/**
 * Sprint B1 — coach_surface_vm (FR-1, FR-3, FR-6, FR-7; red-first).
 *
 * Pure T1 map: host-assembled chrome inputs → CoachSurfaceVM.
 * Failure paths first: absent pin / absent history must never invent
 * "of last 5" or a fake current-item line.
 */

import { describe, expect, it } from "vitest";
import {
  COACH_CHIP_SEEDS,
  toCoachSurfaceVM,
  type CoachSurfaceInputs,
} from "./coach_surface_vm";

const seeds = COACH_CHIP_SEEDS;

function inputs(over: Partial<CoachSurfaceInputs> = {}): CoachSurfaceInputs {
  return {
    mode: "pre_submit",
    pin: null,
    missesOnSkill: null,
    skillLabel: null,
    chipSeeds: seeds,
    ...over,
  };
}

describe("toCoachSurfaceVM — honest absent (FR-1, FR-3)", () => {
  it("omits current-item and history when pin and misses are absent", () => {
    const vm = toCoachSurfaceVM(inputs());
    expect(vm.currentItemLine).toBeNull();
    expect(vm.historyLine).toBeNull();
  });

  it("never emits fabricated 'of last 5' copy (FR-1)", () => {
    const withCount = toCoachSurfaceVM(
      inputs({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q4 · Commas" },
        missesOnSkill: 3,
        skillLabel: "Commas",
      }),
    );
    const absent = toCoachSurfaceVM(inputs());
    for (const vm of [withCount, absent]) {
      expect(JSON.stringify(vm)).not.toMatch(/of last 5/i);
      expect(vm.historyLine ?? "").not.toMatch(/of last 5/i);
    }
  });
});

describe("toCoachSurfaceVM — current item (FR-5 / FR-3)", () => {
  it("shows current-item line when pin is present", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q4 · Commas, non-essential" },
      }),
    );
    expect(vm.currentItemLine).toBe("Current item: Q4 · Commas, non-essential");
  });
});

describe("toCoachSurfaceVM — history (FR-6)", () => {
  it("shows skill-scoped history when missesOnSkill is known", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q4 · Commas" },
        missesOnSkill: 3,
        skillLabel: "Commas",
      }),
    );
    expect(vm.historyLine).toBe("Sees your history: 3 misses on Commas");
  });

  // Superseded 2026-07-20 (Phase-3 residual R2a): the old skillId fallback was
  // the VOICE-3 leak itself — unresolved display name now reads "this skill".
  it("falls back to 'this skill' when skillLabel is missing (never the raw id)", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q4" },
        missesOnSkill: 2,
        skillLabel: null,
      }),
    );
    expect(vm.historyLine).toBe("Sees your history: 2 misses on this skill");
  });

  it("omits history when missesOnSkill is null even if pin exists", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q4" },
        missesOnSkill: null,
      }),
    );
    expect(vm.historyLine).toBeNull();
  });
});

describe("toCoachSurfaceVM — D5a mode map (FR-7 / FR-26)", () => {
  // FR-26 (ADR-0037): the always-inert "Misconception summary" chip is dropped.
  // Only the two live modes remain. (G8: supersedes the prior 3-mode assertions —
  // the third chip never activated and added no learner value, M1/M7 register.)
  it("marks In-drill Socratic active for pre_submit (2 live modes only)", () => {
    const vm = toCoachSurfaceVM(inputs({ mode: "pre_submit" }));
    expect(vm.modes).toEqual([
      { id: "socratic", label: "In-drill Socratic", active: true },
      { id: "deep_dive", label: "Post-answer deep-dive", active: false },
    ]);
  });

  it("marks Post-answer deep-dive active for post_feedback (2 live modes only)", () => {
    const vm = toCoachSurfaceVM(inputs({ mode: "post_feedback" }));
    expect(vm.modes).toEqual([
      { id: "socratic", label: "In-drill Socratic", active: false },
      { id: "deep_dive", label: "Post-answer deep-dive", active: true },
    ]);
  });

  it("no longer exposes a Misconception summary mode (FR-26)", () => {
    for (const mode of ["pre_submit", "post_feedback"] as const) {
      const vm = toCoachSurfaceVM(inputs({ mode }));
      expect(vm.modes.find((m) => m.id === "misconception")).toBeUndefined();
      expect(vm.modes.map((m) => m.label)).not.toContain(
        "Misconception summary",
      );
    }
  });
});

describe("toCoachSurfaceVM — rail + chips", () => {
  it("exposes rail copy and chip seeds", () => {
    const vm = toCoachSurfaceVM(inputs());
    expect(vm.railTitle).toBe("Your Coach");
    expect(vm.railStatus).toMatch(/Adaptive/i);
    expect(vm.chips).toEqual([...seeds]);
  });
});

describe("CoachSurfacePin union — FR-4 exhaustiveness", () => {
  it("pin union — both branches handled (exhaustive)", () => {
    function labelOf(pin: import("./coach_surface_vm").CoachSurfacePin): string {
      switch (pin.kind) {
        case "item":
          return `item:${pin.questionId}`;
        case "lesson":
          return `lesson:${pin.skillId}`;
        default: {
          const _never: never = pin;
          return _never;
        }
      }
    }
    expect(
      labelOf({ kind: "item", questionId: "q1", skillId: "s-punc", label: "Q1" }),
    ).toBe("item:q1");
    expect(labelOf({ kind: "lesson", skillId: "s-punc", label: "Punctuation" })).toBe(
      "lesson:s-punc",
    );
  });

  it("lesson pin omits current-item line", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { kind: "lesson", skillId: "s-punc", label: "Punctuation" },
        missesOnSkill: 2,
        skillLabel: "Punctuation",
      }),
    );
    expect(vm.currentItemLine).toBeNull();
    expect(vm.historyLine).toBe("Sees your history: 2 misses on Punctuation");
  });
});

describe("toCoachSurfaceVM — VOICE-3 id hygiene (Phase-3 residual R2a)", () => {
  it("history line falls back to 'this skill', never the raw skill id", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { kind: "item", questionId: "q1", skillId: "s-punc", label: "Q1" },
        missesOnSkill: 2,
        skillLabel: null,
      }),
    );
    expect(vm.historyLine).toBe("Sees your history: 2 misses on this skill");
    expect(vm.historyLine).not.toContain("s-punc");
  });
});
