/**
 * Phase B reject corpus — recall → reject → re-run cases for the GCP E2E harness.
 *
 * Memories are CRUD-seeded under identity.owner (same pattern as memory-multisession
 * A1/A3 crud-seed) so recalled keys join the owner memory panel in eval disclosure.
 * Scoring is the offline analyzer (`scripts/analyze_memory_traces.py --phase reject`).
 *
 * Regenerate JSON manually or edit `phaseb_reject_corpus.json` in place.
 */
import corpus from "./phaseb_reject_corpus.json" with { type: "json" };

export type SeedMemory = {
  key: string;
  text: string;
  type: string;
  salience?: number | null;
};

export type PhasebRejectCase = {
  case: string;
  mem_id: string;
  /** `"owner"` — real WorkOS identity; suppress carrier matched key-only in analyzer. */
  user_id: string;
  seed_memory: SeedMemory[];
  query: string;
  /** Substrings that must never appear in MEMORY_RECALLED carrier details (C5). */
  seed_snippets: string[];
  expect_min_recall_run1: number;
  rationale: string;
};

export const PHASEB_REJECT_CORPUS: PhasebRejectCase[] = corpus as PhasebRejectCase[];

export function filterPhasebCases(opts: {
  caseFilter?: string;
  limit?: number;
}): PhasebRejectCase[] {
  let rows = PHASEB_REJECT_CORPUS;
  if (opts.caseFilter) {
    rows = rows.filter(
      (c) => c.case === opts.caseFilter || c.mem_id === opts.caseFilter,
    );
  }
  if (opts.limit !== undefined) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}

/** One case per distinct seed pattern — smoke the carrier + disclosure path. */
export function smokePhasebCases(): PhasebRejectCase[] {
  return PHASEB_REJECT_CORPUS.slice(0, 1);
}
