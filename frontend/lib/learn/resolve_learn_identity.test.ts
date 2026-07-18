/**
 * FR-1 / FR-2 / FR-5 — resolveLearnIdentity (eng-coach-workos-learner-identity).
 */

import { describe, expect, it } from "vitest";
import { DEV_LEARNER_ID } from "@/lib/adapters/engine/_dev_seed";
import { resolveLearnIdentity } from "./resolve_learn_identity";

describe("resolveLearnIdentity", () => {
  it("FR-1: refuses to invent Garvit when bypass is off and user is null", () => {
    expect(() =>
      resolveLearnIdentity({ bypass: false, user: null }),
    ).toThrow(/learn identity|WorkOS|signed.?in/i);
    try {
      resolveLearnIdentity({ bypass: false, user: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      expect(msg).not.toMatch(/Garvit/);
    }
  });

  it("FR-2: bypass → demo Garvit identity + demo seedMode", () => {
    const id = resolveLearnIdentity({
      bypass: true,
      user: { id: "user_should_be_ignored", firstName: "Other" },
    });
    expect(id).toEqual({
      learnerId: DEV_LEARNER_ID,
      displayName: "Garvit",
      seedMode: "demo",
    });
  });

  it("FR-5: displayName prefers non-empty firstName", () => {
    const id = resolveLearnIdentity({
      bypass: false,
      user: {
        id: "user_workos_1",
        firstName: "Rajnish",
        email: "rajnish@example.com",
      },
    });
    expect(id).toEqual({
      learnerId: "user_workos_1",
      displayName: "Rajnish",
      seedMode: "fresh",
    });
    expect(id.displayName).not.toBe("Garvit");
  });

  it("FR-5: falls back to email local-part when firstName empty", () => {
    const id = resolveLearnIdentity({
      bypass: false,
      user: { id: "user_2", firstName: "  ", email: "maya.k@school.edu" },
    });
    expect(id.displayName).toBe("maya.k");
    expect(id.seedMode).toBe("fresh");
    expect(id.learnerId).toBe("user_2");
  });

  it("FR-5: falls back to Learner when firstName and email absent", () => {
    const id = resolveLearnIdentity({
      bypass: false,
      user: { id: "user_3", firstName: null, email: null },
    });
    expect(id).toEqual({
      learnerId: "user_3",
      displayName: "Learner",
      seedMode: "fresh",
    });
  });
});
