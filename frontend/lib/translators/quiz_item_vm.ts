/**
 * quiz_item_vm — Question → QuizItemVM (FR-D2/A6) + the submit gate (FR-D4/D2a).
 *
 * Pure T1 map for the quiz item column: the context sentence carrying the
 * underlined span (FR-A6, passed through as HTML the renderer styles), the stem,
 * and the choice rows (choice A is "NO CHANGE", FR-D2).
 *
 * FR-D5 NON-REVEAL is enforced structurally: the VM deliberately OMITS
 * `answer_letter` and `per_choice_rationale`. The pre-answer screen renders only
 * this VM, so the correct answer cannot leak into the pre-answer DOM even by
 * accident. Grading + rationale come from the Grader / feedback_vm AFTER submit.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type { Question } from "../wire/engine_entities";

export interface ChoiceVM {
  readonly letter: string;
  readonly label: string;
  readonly isNoChange: boolean;
}

export interface QuizItemVM {
  readonly questionId: string;
  readonly skillId: string;
  /** Context sentence HTML carrying the underlined span (FR-A6). */
  readonly contextHtml: string;
  readonly stem: string;
  readonly choices: ReadonlyArray<ChoiceVM>;
  /**
   * Q-7: joined skill display name; `null` if the join failed (FR-Q7-1).
   * Derived in this translator — the view renders blindly (F-R1).
   */
  readonly skillName: string | null;
  /**
   * Q-7: `Skill.accent_var` (a CSS custom-property name); `null` if the join
   * failed (FR-Q7-1).
   */
  readonly accentVar: string | null;
  // NOTE: no answerLetter / rationale here — FR-D5 non-reveal (see file header).
}

/** Minimal skill row the Q-7 join needs (name + accent). */
export type SkillChipSource = {
  readonly name: string;
  readonly accent_var: string;
};

export function toQuizItemVM(
  question: Question,
  skillsById?: ReadonlyMap<string, SkillChipSource>,
): QuizItemVM {
  const skill = skillsById?.get(question.skill_id);
  return {
    questionId: question.id,
    skillId: question.skill_id,
    contextHtml: question.context_html,
    stem: question.stem,
    choices: question.choices.map((c) => ({
      letter: c.letter,
      label: c.label,
      isNoChange: c.is_no_change,
    })),
    skillName: skill?.name ?? null,
    accentVar: skill?.accent_var ?? null,
  };
}

/**
 * The submit gate (FR-D4/D2a): submit is enabled only when a non-empty letter is
 * selected. Pure — a component styles the button off this boolean, never off its
 * own logic (F-R1).
 */
export function canSubmit(selectedLetter: string | null): boolean {
  return selectedLetter != null && selectedLetter !== "";
}
