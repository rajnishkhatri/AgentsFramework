/**
 * CV5-1 regression: the generated `_generated/` loader must resolve its directory
 * across BOTH runtimes. The original code used only `import.meta.url`, which
 * resolves to the source dir under node/vitest but to `.next/server/…` inside
 * Next's server bundle — so registration silently no-op'd in a real Next server
 * (caught only by manual validation, never by vitest). `firstExistingDir` makes
 * the fallback explicit and unit-testable with an injected `exists`.
 */

import { describe, expect, it } from "vitest";

import { firstExistingDir } from "./generated_official_form";

const MODULE_REL = "/build/.next/server/chunks/_generated"; // Next bundle (absent)
const CWD_REL = "/app/frontend/lib/adapters/engine/exam_forms/_generated"; // real

describe("firstExistingDir (CV5-1 — _generated/ resolution)", () => {
  it("falls back to the cwd-relative candidate when the module-relative one is absent (the Next-server case)", () => {
    const exists = (p: string): boolean => p === CWD_REL;
    expect(firstExistingDir([MODULE_REL, CWD_REL], exists)).toBe(CWD_REL);
  });

  it("prefers the module-relative candidate when it exists (the node/vitest case)", () => {
    expect(firstExistingDir([MODULE_REL, CWD_REL], () => true)).toBe(
      MODULE_REL,
    );
  });

  it("returns the first candidate when none exist → caller loads null (CI / fresh checkout, §6)", () => {
    const dir = firstExistingDir([MODULE_REL, CWD_REL], () => false);
    expect(dir).toBe(MODULE_REL);
    // The caller's `existsSync(join(dir, '<form>.client.ts'))` is then false,
    // so tryLoadGeneratedOfficialForm returns null — never a fabricated form.
  });
});
