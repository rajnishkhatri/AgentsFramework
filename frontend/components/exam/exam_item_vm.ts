/**
 * Exam-local item VM (C-1 / FR-P2-10/11).
 *
 * Maps ExamQuestion → view fields. imageUrl is a string mapping from
 * AssetRef — no fetch. Kept exam-local so the shared quiz_item_vm and
 * its isolation guard stay untouched.
 */

import type { AssetRef, ExamQuestion } from "@/lib/wire/exam_entities";

export type ExamChoiceVM = {
  readonly letter: string;
  readonly label: string;
};

export type ExamItemVM = {
  readonly stem: string;
  readonly contextHtml: string;
  readonly choices: readonly ExamChoiceVM[];
  readonly imageUrl: string | null;
  readonly passageLabel: string | null;
};

/** String mapping only (C-1). WT-B serves the bytes. */
export function assetRefToUrl(ref: AssetRef): string {
  return `/api/engine/asset/${ref.form_id}/${ref.key}`;
}

export function toExamItemVM(question: ExamQuestion): ExamItemVM {
  return {
    stem: question.stem,
    contextHtml: question.context_html,
    choices: question.choices.map((c) => ({
      letter: c.letter,
      label: c.label,
    })),
    imageUrl: question.image == null ? null : assetRefToUrl(question.image),
    passageLabel: question.passage,
  };
}
