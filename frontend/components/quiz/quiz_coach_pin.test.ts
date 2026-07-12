import { describe, expect, it } from "vitest";
import { toQuizCoachPin } from "./quiz_coach_pin";

describe("toQuizCoachPin", () => {
  it("answering → pre_submit pin labeled with progress position", () => {
    expect(
      toQuizCoachPin({
        questionId: "q2",
        skillId: "s-org",
        position: 2,
        phase: "answering",
      }),
    ).toEqual({
      pin: {
        kind: "item",
        questionId: "q2",
        skillId: "s-org",
        label: "Q2 · s-org",
      },
      mode: "pre_submit",
    });
  });

  it("reviewing → post_feedback pin (sidebar Coach matches Ask-the-coach)", () => {
    expect(
      toQuizCoachPin({
        questionId: "q2",
        skillId: "s-punc",
        position: 2,
        phase: "reviewing",
      }),
    ).toEqual({
      pin: {
        kind: "item",
        questionId: "q2",
        skillId: "s-punc",
        label: "Q2 · s-punc",
      },
      mode: "post_feedback",
    });
  });
});
