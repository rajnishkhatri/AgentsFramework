/**
 * B-2 — EngineDb getExamFormForClient / getExamFormKeys (FR-P2-7).
 *
 * Client payload is ClientExamForm.strict() (no answer-bearing fields).
 * Keys are server-only: HttpEngineDb throws without fetching.
 */

import { describe, expect, it, vi } from "vitest";

import { ANSWER_BEARING_FIELDS } from "@/components/exam/exam_key_posture";
import { ClientExamForm } from "../../../wire/exam_entities";
import { EngineRepoError } from "../../../ports/engine/errors";
import { InMemoryEngineDb } from "./in_memory_engine_db";
import { HttpEngineDb } from "./http_engine_db";
import { getExamForm } from "../exam_forms";

const LEARNER = "learner-1";

describe("getExamFormForClient (B-2 / FR-P2-7)", () => {
  it("returns a ClientExamForm.strict() payload with no answer-bearing fields", async () => {
    const db = new InMemoryEngineDb();
    const payload = await db.getExamFormForClient(LEARNER, "test01-english");
    expect(payload).not.toBeNull();
    const parsed = ClientExamForm.safeParse(payload);
    expect(parsed.success, parsed.success ? "" : String(parsed.error)).toBe(
      true,
    );
    const raw = JSON.stringify(payload);
    for (const field of ANSWER_BEARING_FIELDS) {
      expect(raw).not.toContain(`"${field}"`);
    }
    expect(payload!.id).toBe(getExamForm("test01-english").id);
    expect(payload!.delivery).toBe("client-bundled");
  });

  it("returns null when the form is not loadable", async () => {
    const db = new InMemoryEngineDb();
    expect(await db.getExamFormForClient(LEARNER, "no-such-form")).toBeNull();
    expect(
      await db.getExamFormForClient(LEARNER, "fake-official-form"),
    ).toBeNull();
  });
});

describe("getExamFormKeys (B-2 / FR-P2-7)", () => {
  it("returns keys for a client-bundled form on the in-memory seam", async () => {
    const db = new InMemoryEngineDb();
    const keys = await db.getExamFormKeys("test01-english");
    expect(keys).not.toBeNull();
    const first = getExamForm("test01-english").sections[0]!.questions[0]!;
    expect(keys!.form_id).toBe("test01-english");
    expect(keys!.keys[first.id]?.answer_letter).toBe(first.answer_letter);
  });

  it("HttpEngineDb.getExamFormKeys throws server-only without fetching", async () => {
    const fetchImpl = vi.fn();
    const db = new HttpEngineDb({ baseUrl: "", fetchImpl });
    await expect(db.getExamFormKeys("test01-english")).rejects.toSatisfy(
      (err: unknown) =>
        err instanceof EngineRepoError && err.message === "server-only method",
    );
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
