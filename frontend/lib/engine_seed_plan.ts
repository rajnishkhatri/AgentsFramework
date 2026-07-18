/**
 * Pure seed-plan decision for the browser engine bag (D7 / FR-1..3).
 *
 * Extracted from the `browserEngineAdapters()` seed branch so the prod-path
 * FR-1..5 requirements are L1-deterministic without an `NODE_ENV` flip (Next
 * inlines `process.env.NODE_ENV` at build, so the branch cannot be toggled in a
 * unit test — tasks §"Design-risk resolution"). The caller computes
 * `isProd = process.env.NODE_ENV === "production"` once and delegates the choice
 * here. This is a pure decision function pulled out of an existing branch — not
 * a new abstraction (no new dep/service/node), so no ADR (noted in decisions.md).
 *
 * The e2e-seed override (`__PREACT_E2E_SEED__`) is NOT decided here: it is a
 * runtime `window` read gated to `NODE_ENV !== "production"` and stays upstream
 * of this helper (FR-5 — never reachable in a prod build).
 */

import type { SeedMode } from "./learn/resolve_learn_identity";

/** The seed pack the caller must apply to a fresh `InMemoryEngineDb`. */
export type EngineSeedPlan =
  /** Empty engine bag; seed nothing (prod non-fresh — FR-1, AP-6 undecidable→empty). */
  | "none"
  /** Reviewed web corpus: taxonomy + bank + hints + lessons, `questionSource:"bank"` (FR-3). */
  | "fresh-pack"
  /** Full Garvit demo corpus + bank + hints + lessons (dev / bypass only). */
  | "demo-corpus";

/**
 * Decide the seed pack from the build kind and the resolved seed mode.
 *
 * FR-1 (failure path): in a production build, anything other than `"fresh"`
 * (`"demo"`, unset/undecidable) → `"none"` (empty bag, never the Garvit corpus
 * or a partial pack). FR-3: prod `"fresh"` is the single positive prod seed
 * path. Non-prod preserves the prior dev behavior (fresh-pack / demo-corpus).
 */
export function planEngineSeed(args: {
  readonly isProd: boolean;
  readonly seedMode: SeedMode | undefined;
}): EngineSeedPlan {
  if (args.isProd) {
    // FR-1: the prod branch keys strictly on `"fresh"`. demo/unset → empty.
    return args.seedMode === "fresh" ? "fresh-pack" : "none";
  }
  // Non-prod (unchanged): fresh → taxonomy-only pack; everything else → demo.
  return args.seedMode === "fresh" ? "fresh-pack" : "demo-corpus";
}
