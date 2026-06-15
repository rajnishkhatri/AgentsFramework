/**
 * Planning-stress corpus for the T3 tiered-loops stress run.
 *
 * Regenerate: `python scripts/build_planning_stress_corpus.py`
 *   → frontend/e2e/fixtures/planning_stress_corpus.json
 *
 * Each row carries a prompt plus the per-phase EXPECTATION the trace-analysis
 * half (scripts/analyze_planning_traces.py) scores against. The spec is a
 * driver + capture; the JSON keys here are NOT asserted per-case in the spec
 * (T3 is non-deterministic — see the determinism note in the e2e-stress plan §3).
 */
import corpus from "./planning_stress_corpus.json" with { type: "json" };

export type StressPhase = "depth" | "replan" | "reflexion" | "escalation";

export type PlanningStressCase = {
  case: string;
  prompt: string;
  phase: StressPhase;
  rationale: string;
  trace_id: string;
  session_id: string;
  // per-phase expectations (only the relevant ones are present per row)
  want_depth?: string;
  want_replan?: boolean;
  want_reflexion?: boolean;
  want_terminates_at_budget?: boolean;
  want_escalation?: "reflect" | "done";
};

export const PLANNING_STRESS_CORPUS: PlanningStressCase[] =
  corpus as PlanningStressCase[];

/**
 * Filter cases by single-case id, phase, and limit.
 *   STRESS_CASE_FILTER=STRESS-DEPTH-010  — one case
 *   STRESS_PHASE=reflexion               — one phase
 *   STRESS_LIMIT=4                        — cap (applied AFTER phase filter)
 */
export function filterCases(opts?: {
  caseFilter?: string;
  phase?: string;
  limit?: number;
}): PlanningStressCase[] {
  let rows = PLANNING_STRESS_CORPUS;
  if (opts?.phase) {
    rows = rows.filter((c) => c.phase === opts.phase);
  }
  if (opts?.caseFilter) {
    rows = rows.filter((c) => c.case === opts.caseFilter);
  }
  if (opts?.limit && opts.limit > 0) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}

/** One case per phase — the smoke subset (confirm carriers + screenshots). */
export function smokeCases(): PlanningStressCase[] {
  const seen = new Set<string>();
  const out: PlanningStressCase[] = [];
  for (const c of PLANNING_STRESS_CORPUS) {
    if (!seen.has(c.phase)) {
      seen.add(c.phase);
      out.push(c);
    }
  }
  return out;
}
