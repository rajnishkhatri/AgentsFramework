/**
 * resolve_hint_choice_letter — ADR-0031 moment router (Axis A).
 *
 * Pure T1: maps the learner's selected/answered letter + the item key to the
 * `choiceLetter` argument for `HintRepo.list` / `assembleCoachContext`.
 *
 *   no pick / invalid  → null  (Gen1 item-level ladder)
 *   correct letter     → null  (stay item-level; Gen2 has no key ladder)
 *   wrong letter A–D   → that letter (choice-conditional Gen2 ladder)
 */

export type HintChoiceLetter = "A" | "B" | "C" | "D";

/**
 * Which `choice_letter` to pass when loading a hint ladder or assembling
 * coach_context. Never invents a letter; returns null when the item-level
 * (null-letter) ladder is the honest default.
 */
export function resolveHintChoiceLetter(
  selected: string | null | undefined,
  answerLetter: string,
): HintChoiceLetter | null {
  if (
    selected !== "A" &&
    selected !== "B" &&
    selected !== "C" &&
    selected !== "D"
  ) {
    return null;
  }
  if (selected === answerLetter) return null;
  return selected;
}
