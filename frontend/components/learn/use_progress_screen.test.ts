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
