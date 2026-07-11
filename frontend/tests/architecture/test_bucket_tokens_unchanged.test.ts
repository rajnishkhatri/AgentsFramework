/**
 * D2 FR-7 — CSS token identifiers stay `--color-bucket-*` (not design-spec
 * shorthand `--b-<key>`). NO-CHANGE invariant: expected GREEN on pre-D2 and
 * post-D2 trees. G8: regression guard, not a seen-red new-behavior gate.
 */

import { describe, expect, it } from "vitest";
import { DEV_SKILLS } from "@/lib/adapters/engine/_dev_seed";

describe("D2 FR-7 — bucket accent_var tokens unchanged", () => {
  it("every DEV_SKILLS row uses --color-bucket-* (not --b-*)", () => {
    expect(DEV_SKILLS.length).toBe(6);
    for (const skill of DEV_SKILLS) {
      expect(
        skill.accent_var,
        `${skill.id} accent_var must stay --color-bucket-*`,
      ).toMatch(/^--color-bucket-/);
      expect(skill.accent_var.startsWith("--b-")).toBe(false);
    }
  });
});
