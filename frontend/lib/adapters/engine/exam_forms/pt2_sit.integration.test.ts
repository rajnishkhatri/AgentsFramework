/**
 * S-I3 / FR-P2-19, P2-7, P2-11/12 — PT2 sit on the server seam when
 * `_generated` exists: client form has no keys; finish grades server-side;
 * Math items map to the asset route; Science has a passage block.
 */

import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { examKeyPosture } from "@/components/exam/exam_key_posture";
import { assetRefToUrl, toExamItemVM } from "@/components/exam/exam_item_vm";
import { ExactLetterGrader } from "@/lib/adapters/engine/grader/exact_letter_grader";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { HttpEngineDb } from "@/lib/adapters/engine/db/http_engine_db";
import { DrizzleExamRunRepo } from "@/lib/adapters/engine/repos/drizzle_exam_run_repo";
import { EngineRepoError } from "@/lib/ports/engine/errors";
import { finishExamSectionServer } from "../exam_server_grade";
import { getExamFormDelivery } from "./index";

const PT2 = "act-practice-test-2";
const LEARNER = "learner-si3";
const NOW = new Date("2026-09-03T15:00:00.000Z");
const GENERATED_CLIENT = join(
  dirname(fileURLToPath(import.meta.url)),
  "_generated",
  `${PT2}.client.ts`,
);

const localOnly = existsSync(GENERATED_CLIENT);

describe.skipIf(!localOnly)("S-I3 PT2 server sit (FR-P2-19/7/11/12)", () => {
  it("loads PT2 without keys, server-grades English, maps Math image + Science passage", async () => {
    await import("./generated_official_form");
    const db = new InMemoryEngineDb();
    const repo = new DrizzleExamRunRepo({
      db,
      grader: new ExactLetterGrader(),
      now: () => NOW,
    });

    const forms = await repo.listClientForms({ learnerId: LEARNER });
    const pt2 = forms.find((f) => f.id === PT2);
    expect(pt2).toBeDefined();
    expect(pt2!.delivery).toBe("asset-served");
    expect(examKeyPosture(getExamFormDelivery(PT2))).toBe("server");
    expect(JSON.stringify(pt2)).not.toContain('"answer_letter"');

    const keys = await db.getExamFormKeys(PT2);
    expect(keys).not.toBeNull();

    const english = pt2!.sections.find((s) => s.code === "english")!;
    const first = english.questions[0]!;
    const keyLetter = keys!.keys[first.id]!.answer_letter;

    const run = await repo.startRun({ learnerId: LEARNER, formId: PT2 });
    await repo.beginSection({
      learnerId: LEARNER,
      runId: run.id,
      sectionCode: "english",
    });
    await repo.upsertItems({
      learnerId: LEARNER,
      items: [
        {
          run_id: run.id,
          section_code: "english",
          question_id: first.id,
          ordinal: 1,
          chosen_letter: keyLetter,
          correct: true,
          dwell_ms: 10,
          visits: 1,
          answer_changes: 0,
          first_answered_at: NOW.toISOString(),
          dwell_at_first_answer_ms: 10,
          flagged_in_section: false,
          bookmarked: false,
          updated_at: NOW.toISOString(),
        },
      ],
    });

    const finished = await finishExamSectionServer(
      db,
      new ExactLetterGrader(),
      LEARNER,
      run.id,
      "english",
      "submitted",
      { raw_correct: 99, raw_scored_total: 99, scale_score: 36 },
      1_000,
    );
    expect(finished.raw_correct).not.toBe(99);
    expect(finished.raw_correct).toBeGreaterThanOrEqual(1);
    expect(finished.raw_scored_total).toBeGreaterThan(0);
    const detail = await repo.getRunDetail({ learnerId: LEARNER, runId: run.id });
    expect(detail!.items.find((i) => i.question_id === first.id)?.correct).toBe(
      true,
    );

    const math = pt2!.sections.find((s) => s.code === "math")!;
    const imaged = math.questions.find((q) => q.image != null);
    expect(imaged).toBeDefined();
    const vm = toExamItemVM(imaged!);
    expect(vm.imageUrl).toBe(assetRefToUrl(imaged!.image!));

    const science = pt2!.sections.find((s) => s.code === "science")!;
    expect(science.passages.length).toBeGreaterThan(0);
    expect(science.passages[0]!.question_numbers.length).toBeGreaterThan(0);

    const http = new HttpEngineDb({ baseUrl: "", fetchImpl: () => {
      throw new Error("must not fetch");
    } });
    await expect(http.getExamFormKeys(PT2)).rejects.toBeInstanceOf(
      EngineRepoError,
    );
  });
});
