/**
 * quiz_coach_pin — pure map from the live Quiz item → coach_thread_store pin.
 *
 * Phase-3 residual R2b (VOICE-3): the pin label is learner-facing (Current-item
 * line + coach opener), so it must carry the skill DISPLAY name, never the raw
 * `s-*` id; an unresolved name degrades to the bare position (honest omission,
 * AP-6) — never a fabricated or internal label.
 */

import { describe, expect, it } from "vitest";
import { toQuizCoachPin } from "./quiz_coach_pin";

describe("toQuizCoachPin", () => {
  it("labels with the skill display name, never the raw skill id (R2b)", () => {
    const { pin, mode } = toQuizCoachPin({
      questionId: "q2",
      skillId: "s-org",
      skillName: "Organization",
      position: 2,
      phase: "answering",
    });
    expect(pin).toEqual({
      kind: "item",
      questionId: "q2",
      skillId: "s-org",
      label: "Q2 · Organization",
    });
    expect(mode).toBe("pre_submit");
    expect(pin.label).not.toContain("s-org");
  });

  it("unresolved skill name → bare position label (honest omission, AP-6)", () => {
    const { pin } = toQuizCoachPin({
      questionId: "q2",
      skillId: "s-punc",
      skillName: null,
      position: 2,
      phase: "answering",
    });
    expect(pin.label).toBe("Q2");
    expect(pin.label).not.toContain("s-punc");
  });

  it("reviewing → post_feedback mode (sidebar Coach matches Ask-the-coach)", () => {
    const { mode } = toQuizCoachPin({
      questionId: "q2",
      skillId: "s-punc",
      skillName: "Punctuation",
      position: 2,
      phase: "reviewing",
    });
    expect(mode).toBe("post_feedback");
  });
});
