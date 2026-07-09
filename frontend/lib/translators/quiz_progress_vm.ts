/**
 * quiz_progress_vm — (gradedTotal, phase, targetCount) → QuizProgressVM (S4).
 *
 * Pure T1 map for the "Question N of M" progress bar. The number spine already
 * exists (S3): `targetCount` = QuizSession.target_count (nullable; null = endless),
 * `gradedTotal` = the reducer's SessionTally.total (graded-so-far). This map owns
 * all the counting/clamp math so the QuizProgress component stays presentational
 * (F-R1): the component renders this VM and holds no logic.
 *
 * Numerator convention (§2.2 Q1): 1-based "which question you're ON". While
 * answering, N = gradedTotal + 1 (you're on the next one); while reviewing, N =
 * gradedTotal (the item you JUST graded); loading/done carry the last N so the
 * counter never flickers to 0/1 (FR-6). Floored at 1 so the first render is 1.
 *
 * Denominator (§2.2 Q2/Q4): `total` is the number to DISPLAY after "of", or null
 * when there is nothing honest to show — endless (targetCount null, FR-1) OR
 * over-run past the target (position > targetCount, FR-2). The BAR geometry is
 * separate: `bounded`/`fraction` keep the bar full on over-run even though the
 * counter drops "of M".
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

/** The Quiz screen's phase tag (mirrors quiz_screen_reducer's phases; taken as a
 *  plain string union so this translator imports nothing React-adjacent). */
export type QuizProgressPhase = "loading" | "answering" | "reviewing" | "done";

export interface QuizProgressVM {
  /** 1-based index of the question the learner is on (answering) or just did (reviewing). */
  readonly position: number;
  /** Denominator to DISPLAY after "of", or null when endless OR over-run. */
  readonly total: number | null;
  /** Bar fill 0..1: clamp(position / targetCount, 0, 1); 0 when endless. */
  readonly fraction: number;
  /** targetCount != null — determinate vs indeterminate bar. */
  readonly bounded: boolean;
}

const clamp01 = (n: number): number => Math.min(1, Math.max(0, n));

export function toQuizProgressVM(
  gradedTotal: number,
  phase: QuizProgressPhase,
  targetCount: number | null,
): QuizProgressVM {
  // FR-3/FR-4/§0: answering → the one you're on; reviewing/loading/done → the
  // one you just did (carries). Floor at 1 so a fresh session reads "1", not "0".
  const position = Math.max(
    1,
    phase === "answering" ? gradedTotal + 1 : gradedTotal,
  );

  const bounded = targetCount != null; // FR-1
  const fraction = bounded ? clamp01(position / targetCount) : 0; // FR-5 (clamp → FR-2)
  // FR-1/FR-2/§2.2 Q4: show the denominator only while at/under the target; drop
  // it when endless or over-run (the fixed target stops being meaningful past M).
  const total = bounded && position <= targetCount ? targetCount : null;

  return { position, total, fraction, bounded };
}
