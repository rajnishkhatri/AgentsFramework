/**
 * GoalJudge registry cases exported from case_registry.py.
 *
 * Regenerate: `python scripts/export_goaljudge_registry_json.py`
 */
import registry from "./goaljudge_registry.json" with { type: "json" };

export type GoalJudgeRegistryCase = {
  id: string;
  prompt: string;
  target_code: string;
  target_axes: {
    goal_met?: boolean;
    graceful_failure?: boolean;
    partial_fraction?: number;
  };
  stratum: string;
  domain: string;
  expected_feasibility: string;
  provenance: string;
  trace_id: string;
  session_id: string;
};

export const GOALJUDGE_REGISTRY: GoalJudgeRegistryCase[] =
  registry as GoalJudgeRegistryCase[];

/** Walkthrough saturation subset GJ-001…GJ-022 (numeric sort). */
export function walkthroughCases(): GoalJudgeRegistryCase[] {
  return GOALJUDGE_REGISTRY.filter((c) => {
    const m = /^GJ-(\d+)([A-Z]?)$/.exec(c.id);
    if (!m) return false;
    const n = Number(m[1]);
    return n >= 1 && n <= 22;
  }).sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
}

export function caseById(id: string): GoalJudgeRegistryCase | undefined {
  return GOALJUDGE_REGISTRY.find((c) => c.id === id);
}

export function filterCases(opts?: {
  caseFilter?: string;
  limit?: number;
}): GoalJudgeRegistryCase[] {
  let rows = walkthroughCases();
  if (opts?.caseFilter) {
    rows = rows.filter((c) => c.id === opts.caseFilter);
  }
  if (opts?.limit && opts.limit > 0) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}
