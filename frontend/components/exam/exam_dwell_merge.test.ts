/**
 * FR-39 — one shared monotonic-max dwell merge (client + server).
 * dwell max, visits/changes max, first-answer keep-first.
 */

import { describe, expect, it } from "vitest";
import { mergeExamDwell } from "./exam_dwell_merge";
import type { ExamRunItem } from "@/lib/wire/exam_entities";

function item(over: Partial<ExamRunItem> = {}): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: "q-1",
    ordinal: 1,
    chosen_letter: "A",
    correct: null,
    dwell_ms: 100,
    visits: 1,
    answer_changes: 0,
    first_answered_at: "2026-09-02T00:00:01.000Z",
    dwell_at_first_answer_ms: 80,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: "2026-09-02T00:00:02.000Z",
    ...over,
  };
}

describe("mergeExamDwell (FR-39)", () => {
  it("takes max dwell / visits / answer_changes", () => {
    const merged = mergeExamDwell(
      item({ dwell_ms: 100, visits: 1, answer_changes: 0 }),
      item({
        dwell_ms: 250,
        visits: 3,
        answer_changes: 2,
        chosen_letter: "B",
        updated_at: "2026-09-02T00:00:09.000Z",
      }),
    );
    expect(merged.dwell_ms).toBe(250);
    expect(merged.visits).toBe(3);
    expect(merged.answer_changes).toBe(2);
    expect(merged.chosen_letter).toBe("B");
  });

  it("keep-first on first-answer fields (never overwrite a recorded first)", () => {
    const merged = mergeExamDwell(
      item({
        first_answered_at: "2026-09-02T00:00:01.000Z",
        dwell_at_first_answer_ms: 80,
      }),
      item({
        first_answered_at: "2026-09-02T00:00:08.000Z",
        dwell_at_first_answer_ms: 400,
        chosen_letter: "C",
      }),
    );
    expect(merged.first_answered_at).toBe("2026-09-02T00:00:01.000Z");
    expect(merged.dwell_at_first_answer_ms).toBe(80);
  });

  it("fills first-answer from incoming when stored is empty", () => {
    const merged = mergeExamDwell(
      item({ first_answered_at: null, dwell_at_first_answer_ms: null }),
      item({
        first_answered_at: "2026-09-02T00:00:08.000Z",
        dwell_at_first_answer_ms: 400,
      }),
    );
    expect(merged.first_answered_at).toBe("2026-09-02T00:00:08.000Z");
    expect(merged.dwell_at_first_answer_ms).toBe(400);
  });
});
