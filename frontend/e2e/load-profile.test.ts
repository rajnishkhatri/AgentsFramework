/**
 * Gate for the live-testing profile loader (e2e/load-profile.ts).
 *
 * The headline guard is the PRECEDENCE rule (12-factor / config-research):
 * an explicit env value must always beat the profile — getting this wrong means
 * a `BASE_URL=...` on the command line is silently ignored and the run hits the
 * wrong target. Pure, no network, no Playwright.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyTestProfile } from "./load-profile";

const KEYS = [
  "BASE_URL",
  "E2E_AUTHENTICATED",
  "TEST_PROFILE",
  "STRESS_PHASE",
  "STRESS_LIMIT",
  "MOCK_MIDDLEWARE",
];

let saved: Record<string, string | undefined>;

beforeEach(() => {
  saved = {};
  for (const k of KEYS) {
    saved[k] = process.env[k];
    delete process.env[k];
  }
  vi.spyOn(console, "log").mockImplementation(() => {});
});

afterEach(() => {
  for (const k of KEYS) {
    if (saved[k] === undefined) delete process.env[k];
    else process.env[k] = saved[k];
  }
  vi.restoreAllMocks();
});

describe("applyTestProfile", () => {
  it("applies the stress profile to unset vars", () => {
    process.env.TEST_PROFILE = "stress";
    const name = applyTestProfile();
    expect(name).toBe("stress");
    expect(process.env.BASE_URL).toContain("stress---agent-frontend");
    expect(process.env.E2E_AUTHENTICATED).toBe("1");
  });

  it("does NOT clobber an explicit env value (precedence: explicit > profile)", () => {
    process.env.TEST_PROFILE = "stress";
    process.env.BASE_URL = "https://override.example.com";
    applyTestProfile();
    expect(process.env.BASE_URL).toBe("https://override.example.com");
  });

  it("a blank profile value leaves an explicit value intact", () => {
    process.env.TEST_PROFILE = "stress";
    process.env.STRESS_PHASE = "reflexion";
    applyTestProfile();
    expect(process.env.STRESS_PHASE).toBe("reflexion");
  });

  it("throws fail-fast on an unknown profile name", () => {
    process.env.TEST_PROFILE = "does-not-exist";
    expect(() => applyTestProfile()).toThrow(/not found/);
  });

  it("falls back to the default profile when TEST_PROFILE is unset", () => {
    const name = applyTestProfile();
    expect(name).toBe("local");
    expect(process.env.BASE_URL).toBe("http://localhost:3000");
  });
});
