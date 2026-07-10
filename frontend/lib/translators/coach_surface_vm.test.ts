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
        pin: { questionId: "q1", skillId: "s-punc", label: "Q4 · Commas" },
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
        pin: { questionId: "q1", skillId: "s-punc", label: "Q4 · Commas, non-essential" },
      }),
    );
    expect(vm.currentItemLine).toBe("Current item: Q4 · Commas, non-essential");
  });
});

describe("toCoachSurfaceVM — history (FR-6)", () => {
  it("shows skill-scoped history when missesOnSkill is known", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { questionId: "q1", skillId: "s-punc", label: "Q4 · Commas" },
        missesOnSkill: 3,
        skillLabel: "Commas",
      }),
    );
    expect(vm.historyLine).toBe("Sees your history: 3 misses on Commas");
  });

  it("falls back to skillId when skillLabel is missing", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { questionId: "q1", skillId: "s-punc", label: "Q4" },
        missesOnSkill: 2,
        skillLabel: null,
      }),
    );
    expect(vm.historyLine).toBe("Sees your history: 2 misses on s-punc");
  });

  it("omits history when missesOnSkill is null even if pin exists", () => {
    const vm = toCoachSurfaceVM(
      inputs({
        pin: { questionId: "q1", skillId: "s-punc", label: "Q4" },
        missesOnSkill: null,
      }),
    );
    expect(vm.historyLine).toBeNull();
  });
});

describe("toCoachSurfaceVM — D5a mode map (FR-7)", () => {
  it("marks In-drill Socratic active for pre_submit", () => {
    const vm = toCoachSurfaceVM(inputs({ mode: "pre_submit" }));
    expect(vm.modes).toEqual([
      { id: "socratic", label: "In-drill Socratic", active: true },
      { id: "deep_dive", label: "Post-answer deep-dive", active: false },
      { id: "misconception", label: "Misconception summary", active: false },
    ]);
  });

  it("marks Post-answer deep-dive active for post_feedback", () => {
    const vm = toCoachSurfaceVM(inputs({ mode: "post_feedback" }));
    expect(vm.modes).toEqual([
      { id: "socratic", label: "In-drill Socratic", active: false },
      { id: "deep_dive", label: "Post-answer deep-dive", active: true },
      { id: "misconception", label: "Misconception summary", active: false },
    ]);
  });

  it("never activates Misconception summary in B1", () => {
    for (const mode of ["pre_submit", "post_feedback"] as const) {
      const vm = toCoachSurfaceVM(inputs({ mode }));
      const mis = vm.modes.find((m) => m.id === "misconception");
      expect(mis?.active).toBe(false);
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
