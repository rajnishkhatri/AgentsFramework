/**
 * greeting_vm — FR-9/FR-10/FR-11 (C1). Failure/edge rows first (TAP-4).
 */

import { describe, expect, it } from "vitest";
import { toGreetingVM } from "./greeting_vm";

/** Build a nowISO whose *local* wall-clock is the given hour:minute on 2026-07-10. */
function localISO(hour: number, minute = 0): string {
  return new Date(2026, 6, 10, hour, minute, 0, 0).toISOString();
}

describe("toGreetingVM — time-of-day boundaries (FR-9)", () => {
  it.each([
    [5, 0, "Good morning"],
    [11, 59, "Good morning"],
    [12, 0, "Good afternoon"],
    [17, 59, "Good afternoon"],
    [18, 0, "Good evening"],
    [4, 59, "Good evening"],
  ] as const)(
    "time_of_day_boundaries %i:%i → %s",
    (hour, minute, greeting) => {
      const vm = toGreetingVM(localISO(hour, minute), "maya");
      expect(vm.headline.startsWith(greeting)).toBe(true);
    },
  );
});

describe("toGreetingVM — subline + display name (FR-10/FR-9)", () => {
  it("subline_uses_intl_datetime — weekday + month + day", () => {
    const vm = toGreetingVM(localISO(14, 0), "Maya");
    // Locale-agnostic: must contain a weekday word and a day-of-month digit.
    expect(vm.subline).toMatch(
      /\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b/,
    );
    expect(vm.subline).toMatch(
      /\b(January|February|March|April|May|June|July|August|September|October|November|December)\b/,
    );
    expect(vm.subline).toMatch(/\b\d{1,2}\b/);
  });

  it("title_case_id_maya_becomes_Maya", () => {
    // Pre-fix: titleCaseId("maya") → "Maya". Post-fix (FR-11): caller
    // supplies displayName; no learner_id guess. Keep oracle as display name.
    const vm = toGreetingVM(localISO(14, 0), "Maya");
    expect(vm.headline).toBe("Good afternoon, Maya");
  });
});

describe("toGreetingVM — C1-fix honesty (FR-11/FR-12)", () => {
  it("no_display_name_omits_name_from_headline", () => {
    const vm = toGreetingVM(localISO(14, 0));
    expect(vm.headline).toBe("Good afternoon");
    expect(vm.headline).not.toContain(",");
  });

  it("non_latin_display_name_passthrough", () => {
    const vm = toGreetingVM(localISO(14, 0), "美夜");
    expect(vm.headline).toBe("Good afternoon, 美夜");
  });

  it.each([
    [4, 59, "Good evening"],
    [5, 0, "Good morning"],
    [11, 59, "Good morning"],
    [12, 0, "Good afternoon"],
    [17, 59, "Good afternoon"],
    [18, 0, "Good evening"],
  ] as const)(
    "time_of_day_boundaries_%i%i → bare %s (no name)",
    (hour, minute, greeting) => {
      const vm = toGreetingVM(localISO(hour, minute));
      expect(vm.headline).toBe(greeting);
    },
  );
});
