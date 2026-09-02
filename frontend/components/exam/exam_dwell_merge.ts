/**
 * FR-39 / R6 — the single monotonic-max dwell merge both the client
 * write-buffer and the server upsert import. Do not fork this algorithm.
 *
 * - dwell_ms / visits / answer_changes → max
 * - first_answered_at / dwell_at_first_answer_ms → keep-first
 * - chosen_letter / flagged / bookmarked / updated_at → incoming wins
 *   (last writer by caller-supplied updated_at; this fn does not compare clocks)
 */

import type { ExamRunItem } from "@/lib/wire/exam_entities";

export function mergeExamDwell(
  stored: ExamRunItem,
  incoming: ExamRunItem,
): ExamRunItem {
  return {
    ...incoming,
    dwell_ms: Math.max(stored.dwell_ms, incoming.dwell_ms),
    visits: Math.max(stored.visits, incoming.visits),
    answer_changes: Math.max(stored.answer_changes, incoming.answer_changes),
    first_answered_at: stored.first_answered_at ?? incoming.first_answered_at,
    dwell_at_first_answer_ms:
      stored.dwell_at_first_answer_ms ?? incoming.dwell_at_first_answer_ms,
  };
}
