/**
 * Deterministic image-necessary rule (ADR-0042 / spec §4.1).
 * Converter and fixture use this; the renderer consumes the resulting
 * `ExamQuestion.image` and does not re-derive fidelity.
 */

export type ImageRuleFidelity = "ok" | "math-notation" | "low" | (string & {});

export type ImageRuleQuestion = {
  readonly text_fidelity: ImageRuleFidelity;
};

export type ImageRulePassage = {
  readonly is_figure: boolean;
} | null | undefined;

/**
 * A question needs an official image iff its source text is lossy
 * (`math-notation` or `low`) or it sits on a figure passage.
 */
export function needsImage(
  q: ImageRuleQuestion,
  passage?: ImageRulePassage,
): boolean {
  return (
    q.text_fidelity === "math-notation" ||
    q.text_fidelity === "low" ||
    passage?.is_figure === true
  );
}
