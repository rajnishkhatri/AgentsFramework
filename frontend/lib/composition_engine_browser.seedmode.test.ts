/**
 * FR-7 — browserEngineAdapters seedMode latch (fresh vs demo).
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  resetBrowserEngineSingleton,
  setBrowserEngineSeedMode,
  browserEngineAdapters,
} from "@/lib/composition_engine_browser";
import {
  DEV_LEARNER_ID,
  DEV_SKILL_STATES,
} from "@/lib/adapters/engine/_dev_seed";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";

afterEach(() => {
  resetBrowserEngineSingleton();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("browserEngineAdapters seedMode (FR-2 / FR-7)", () => {
  it("fresh path has zero DEV_SKILL_STATES rows for Garvit", async () => {
    setBrowserEngineSeedMode("fresh");
    const bag = browserEngineAdapters();
    const states = await bag.learnerRead.listSkillState(
      DEFAULT_SUBJECT,
      DEV_LEARNER_ID,
    );
    expect(states).toEqual([]);
    const skills = await bag.skillTaxonomy.list(DEFAULT_SUBJECT);
    expect(skills.length).toBeGreaterThan(0);
  });

  it("demo path retains Garvit mastery rows", async () => {
    setBrowserEngineSeedMode("demo");
    const bag = browserEngineAdapters();
    const states = await bag.learnerRead.listSkillState(
      DEFAULT_SUBJECT,
      DEV_LEARNER_ID,
    );
    expect(states.length).toBe(DEV_SKILL_STATES.length);
  });
});

// D7 prod-branch: NODE_ENV=production reaches the `isProd` read in
// browserEngineAdapters() at runtime under Vitest (this config does NOT inline
// NODE_ENV via a Vite `define`; the Next production bundle does — which is why
// planEngineSeed is extracted as a pure L1-tested helper regardless).
describe("browserEngineAdapters prod seed boundary (D7 / FR-1,3,4,5)", () => {
  it("prod + non-fresh (demo) seeds NOTHING — empty bag, no Garvit corpus (FR-1)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    setBrowserEngineSeedMode("demo");
    const bag = browserEngineAdapters();
    // Empty substrate: no skills, no reviewed bank items, no Garvit mastery.
    expect(await bag.skillTaxonomy.list(DEFAULT_SUBJECT)).toEqual([]);
    expect(await bag.testItemRepo.listReviewed(DEFAULT_SUBJECT)).toEqual([]);
    expect(
      await bag.learnerRead.listSkillState(DEFAULT_SUBJECT, DEV_LEARNER_ID),
    ).toEqual([]);
  });

  it("prod + unset seed mode also seeds nothing (FR-1 undecidable→empty)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    // No setBrowserEngineSeedMode → latch is the "demo" default (reset in
    // afterEach). Prod branch keys strictly on "fresh", so this is empty.
    const bag = browserEngineAdapters();
    expect(await bag.skillTaxonomy.list(DEFAULT_SUBJECT)).toEqual([]);
    expect(await bag.testItemRepo.listReviewed(DEFAULT_SUBJECT)).toEqual([]);
  });

  it("prod + fresh seeds the reviewed bank + taxonomy corpus (FR-3)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    setBrowserEngineSeedMode("fresh");
    const bag = browserEngineAdapters();
    expect((await bag.skillTaxonomy.list(DEFAULT_SUBJECT)).length).toBeGreaterThan(0);
    expect(
      (await bag.testItemRepo.listReviewed(DEFAULT_SUBJECT)).length,
    ).toBeGreaterThan(0);
  });

  it("prod + fresh leaves the progress slate empty (FR-4)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    setBrowserEngineSeedMode("fresh");
    const bag = browserEngineAdapters();
    // Content, not history: no Garvit mastery rows on a fresh prod seed.
    expect(
      await bag.learnerRead.listSkillState(DEFAULT_SUBJECT, DEV_LEARNER_ID),
    ).toEqual([]);
  });

  it("prod ignores the __PREACT_E2E_SEED__ override (FR-5)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    // Inject an override on window; a prod build must never read it, so with
    // seedMode=demo the bag stays empty (override would otherwise seed skills).
    vi.stubGlobal("window", {
      __PREACT_E2E_SEED__: {
        skills: [{ id: "x", subject: DEFAULT_SUBJECT, name: "leak", parentId: null }],
        questions: [],
        skillStates: [],
      },
      location: { search: "" },
    });
    setBrowserEngineSeedMode("demo");
    const bag = browserEngineAdapters();
    expect(await bag.skillTaxonomy.list(DEFAULT_SUBJECT)).toEqual([]);
  });
});
