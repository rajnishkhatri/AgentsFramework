/**
 * L1 tests for loadSkillDetail (E1a FR-3/17/18/19).
 */

import { describe, expect, it } from "vitest";
import { buildEngineAdapters } from "@/lib/composition_engine";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { seedLessonContent } from "@/lib/adapters/engine/_lesson_seed";
import { seedDevCorpus } from "@/lib/adapters/engine/_dev_seed";
import { loadSkillDetail } from "./use_skill_detail";

describe("loadSkillDetail — E1a FR-3/18/19", () => {
  it("FR-19: valid skill with seed renders ok", async () => {
    const db = new InMemoryEngineDb();
    seedDevCorpus(db);
    seedLessonContent(db);
    const ports = buildEngineAdapters({ env: {}, engineDb: db });
    const result = await loadSkillDetail(ports, {
      subject: "act-english",
      learnerId: "maya",
      skillId: "s-punc",
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(result.status).toBe("ok");
    if (result.status === "ok") {
      expect(result.vm.empty).toBe(false);
      expect(result.vm.main.length).toBeGreaterThan(0);
    }
  });

  it("FR-19: unknown skillId → not_found (404-equiv)", async () => {
    const db = new InMemoryEngineDb();
    seedDevCorpus(db);
    const ports = buildEngineAdapters({ env: {}, engineDb: db });
    const result = await loadSkillDetail(ports, {
      subject: "act-english",
      learnerId: "maya",
      skillId: "s-nope",
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(result.status).toBe("not_found");
  });

  it("FR-3/18: known skill with no reviewed tutorial → honest empty", async () => {
    const db = new InMemoryEngineDb();
    seedDevCorpus(db);
    // no seedLessonContent
    const ports = buildEngineAdapters({ env: {}, engineDb: db });
    const result = await loadSkillDetail(ports, {
      subject: "act-english",
      learnerId: "maya",
      skillId: "s-punc",
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(result.status).toBe("empty");
    if (result.status === "empty") {
      expect(result.vm.empty).toBe(true);
      expect(result.vm.main).toEqual([]);
    }
  });
});
