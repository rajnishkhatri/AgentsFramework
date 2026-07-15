/**
 * FR-7 — browserEngineAdapters seedMode latch (fresh vs demo).
 */

import { afterEach, describe, expect, it } from "vitest";
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
