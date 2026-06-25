/**
 * Benchmark-shaped corpus for the extensive model A/B sweep.
 *
 * Regenerate: `.venv/bin/python scripts/build_model_ab_corpus.py`
 *   → frontend/e2e/fixtures/model_ab_corpus.json
 *
 * Each row carries a `prompt` (single-shot, GAIA/memory) OR a `turns` array
 * (multi-turn τ²-shaped), plus a `family` and a `difficulty`. The spec is a
 * driver + capture; the JSON keys here are NOT asserted per-case (T3 is
 * non-deterministic — aggregate scoring is the analyzer's job).
 *
 * `isReasoningEligible` is the SINGLE place the Opus/Pro eligibility rule lives
 * (plan §1.3 / §2.0): the driver, the cost estimator, and the analyzer all
 * import this one predicate so they cannot drift.
 */
import corpus from "./model_ab_corpus.json" with { type: "json" };

export type ModelAbFamily = "general" | "multi-turn" | "memory" | "stress";

export type ModelAbDifficulty = "L1" | "L2" | "L3";

export type ModelAbCase = {
  case: string;
  // Regex-conforming id (GJ-AB{GENL,MULT,MEMO}-NN) the gj: thread bridge requires;
  // the descriptive `case` is for humans / the report.
  gj_id: string;
  family: ModelAbFamily;
  difficulty: ModelAbDifficulty;
  trace_id: string;
  session_id: string;
  // exactly one of prompt / turns is present per row (single-shot vs multi-turn)
  prompt?: string;
  turns?: string[];
  rationale?: string;
  // optional expectation hooks the analyzer's --judge pass scores against
  want_answer?: string;
  want_policy?: string;
};

export const MODEL_AB_CORPUS: ModelAbCase[] = corpus as ModelAbCase[];

/**
 * The ONE eligibility predicate (plan §1.3 / §2.0). A row is Opus/Pro-eligible
 * iff its `difficulty ∈ {L2,L3}` OR its `family ∈ {stress, multi-turn}`. The
 * reasoning arms NEVER run on routine L1 general cases — that is the cost-control
 * core. Driver, cost estimator and analyzer import THIS function so the rule
 * cannot drift between them.
 */
export function isReasoningEligible(c: ModelAbCase): boolean {
  return (
    c.difficulty === "L2" ||
    c.difficulty === "L3" ||
    c.family === "stress" ||
    c.family === "multi-turn"
  );
}

/**
 * Load (and optionally filter) the corpus.
 *   MODEL_AB_FAMILY=general        — one family
 *   MODEL_AB_CASE_FILTER=GEN-L1-…  — one case by id
 *   MODEL_AB_LIMIT=4               — cap (applied AFTER the family filter)
 *   reasoningEligibleOnly=true     — drop non-eligible rows (the Opus/Pro arms)
 */
export function loadCases(opts?: {
  family?: string;
  caseFilter?: string;
  limit?: number;
  reasoningEligibleOnly?: boolean;
}): ModelAbCase[] {
  let rows = MODEL_AB_CORPUS;
  if (opts?.family) {
    rows = rows.filter((c) => c.family === opts.family);
  }
  if (opts?.caseFilter) {
    rows = rows.filter((c) => c.case === opts.caseFilter);
  }
  if (opts?.reasoningEligibleOnly) {
    rows = rows.filter(isReasoningEligible);
  }
  if (opts?.limit && opts.limit > 0) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}

/** One case per family — the smoke subset (confirm carriers + screenshots). */
export function smokeCases(): ModelAbCase[] {
  const seen = new Set<string>();
  const out: ModelAbCase[] = [];
  for (const c of MODEL_AB_CORPUS) {
    if (!seen.has(c.family)) {
      seen.add(c.family);
      out.push(c);
    }
  }
  return out;
}
