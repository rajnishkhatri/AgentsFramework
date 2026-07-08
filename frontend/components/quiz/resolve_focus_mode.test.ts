/**
 * resolve_focus_mode — FR-6 (S2): the pure decision behind the Quiz page's
 * `?focus=` handling. Node-testable, no React (the F-R1 split: the page is thin
 * glue that fetches skills and forwards this result to `openSession`).
 *
 * Failure/edge paths first (spec §6): a null param and an UNKNOWN skill id must
 * both fall back to adaptive with NO focus — a bad/absent param never errors and
 * never opens a drill on a nonexistent skill.
 */

import { describe, expect, it } from "vitest";
import { resolveFocusMode } from "./resolve_focus_mode";

const KNOWN = ["s-punc", "s-gram", "s-conc"];

describe("resolveFocusMode — FR-6 fallback paths (edge first)", () => {
  it("null focus → adaptive, no focus", () => {
    expect(resolveFocusMode(null, KNOWN)).toEqual({ mode: "adaptive" });
  });

  it("unknown skill id → adaptive, no focus (never a drill on a ghost skill)", () => {
    expect(resolveFocusMode("s-does-not-exist", KNOWN)).toEqual({ mode: "adaptive" });
  });

  it("empty string → adaptive, no focus", () => {
    expect(resolveFocusMode("", KNOWN)).toEqual({ mode: "adaptive" });
  });
});

describe("resolveFocusMode — FR-6 known skill opens a drill", () => {
  it("a known skill id → drill focused on that skill", () => {
    expect(resolveFocusMode("s-punc", KNOWN)).toEqual({
      mode: "drill",
      focus: "s-punc",
    });
  });

  it("resolves against the provided id set, not a hardcoded list", () => {
    expect(resolveFocusMode("s-only", ["s-only"])).toEqual({
      mode: "drill",
      focus: "s-only",
    });
    // The same id is unknown when the set does not contain it.
    expect(resolveFocusMode("s-only", [])).toEqual({ mode: "adaptive" });
  });
});
