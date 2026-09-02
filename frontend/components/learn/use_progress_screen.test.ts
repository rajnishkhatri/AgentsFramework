/**
 * L1 tests for loadProgressScreen (Epic F FR-8 loader side).
 */

import { describe, expect, it, vi } from "vitest";
import { buildEngineAdapters } from "@/lib/composition_engine";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { seedDevCorpus, DEV_LEARNER_ID } from "@/lib/adapters/engine/_dev_seed";
import {
  loadProgressScreen,
  computeProgressSinceISO,
} from "./use_progress_screen";

describe("loadProgressScreen — FR-8 range filter", () => {
  it("30d passes sinceISO to listByLearner", async () => {
    const db = new InMemoryEngineDb();
    seedDevCorpus(db);
    const ports = buildEngineAdapters({ env: {}, engineDb: db });
    const listSpy = vi.spyOn(ports.sessionRepo, "listByLearner");
    const nowISO = "2026-07-13T12:00:00.000Z";
    await loadProgressScreen(ports, {
      subject: "act-english",
      learnerId: DEV_LEARNER_ID,
      range: "30d",
      nowISO,
    });
    expect(listSpy).toHaveBeenCalledWith("act-english", DEV_LEARNER_ID, {
      sinceISO: computeProgressSinceISO(nowISO, 30),
    });
  });

  it("Exam performance panel is sourced only from ExamAnalytics (FR-34)", async () => {
    const db = new InMemoryEngineDb();
    seedDevCorpus(db);
    const ports = buildEngineAdapters({ env: {}, engineDb: db });
    const repo = ports.examRunRepo;
    expect(repo, "W1-7 must wire examRunRepo").toBeDefined();
    const { TEST01_ENGLISH_FORM } = await import(
      "@/lib/adapters/engine/exam_forms/test01_english"
    );
    const q0 = TEST01_ENGLISH_FORM.sections[0]?.questions[0];
    expect(q0).toBeDefined();
    const run = await repo!.startRun({
      learnerId: DEV_LEARNER_ID,
      formId: TEST01_ENGLISH_FORM.id,
    });
    await repo!.beginSection({
      learnerId: DEV_LEARNER_ID,
      runId: run.id,
      sectionCode: "english",
    });
    await repo!.upsertItems({
      learnerId: DEV_LEARNER_ID,
      items: [
        {
          run_id: run.id,
          section_code: "english",
          question_id: q0!.id,
          ordinal: 0,
          chosen_letter: q0!.answer_letter,
          correct: null,
          dwell_ms: 1000,
          visits: 1,
          answer_changes: 0,
          first_answered_at: "2026-09-02T12:00:01.000Z",
          dwell_at_first_answer_ms: 800,
          flagged_in_section: false,
          bookmarked: false,
          updated_at: "2026-09-02T12:00:02.000Z",
        },
      ],
    });
    await repo!.finishSection({
      learnerId: DEV_LEARNER_ID,
      runId: run.id,
      sectionCode: "english",
    });
    const beforeBuckets = (
      await loadProgressScreen(ports, {
        subject: "act-english",
        learnerId: DEV_LEARNER_ID,
        range: "all",
        nowISO: "2026-07-13T12:00:00.000Z",
      })
    ).buckets;
    const vm = await loadProgressScreen(ports, {
      subject: "act-english",
      learnerId: DEV_LEARNER_ID,
      range: "all",
      nowISO: "2026-07-13T12:00:00.000Z",
    });
    expect(vm.examPerformance).toBeTruthy();
    expect(vm.examPerformance?.scope.learner_id).toBe(DEV_LEARNER_ID);
    expect(vm.examPerformance?.scope.run_id).toBeNull();
    expect(vm.buckets.map((b) => b.skillId)).toEqual(
      beforeBuckets.map((b) => b.skillId),
    );
    expect(vm.buckets.every((b) => !("facets" in b))).toBe(true);
  });

  it("all-time omits sinceISO", async () => {
    const db = new InMemoryEngineDb();
    seedDevCorpus(db);
    const ports = buildEngineAdapters({ env: {}, engineDb: db });
    const listSpy = vi.spyOn(ports.sessionRepo, "listByLearner");
    await loadProgressScreen(ports, {
      subject: "act-english",
      learnerId: DEV_LEARNER_ID,
      range: "all",
      nowISO: "2026-07-13T12:00:00.000Z",
    });
    expect(listSpy).toHaveBeenCalledWith("act-english", DEV_LEARNER_ID);
  });
});
