/**
 * GoalJudge registry cases exported from case_registry.py.
 *
 * Regenerate: `python scripts/export_goaljudge_registry_json.py`
 *
 * Phase 5 fresh corpus: `python scripts/export_goaljudge_fresh_tasks_json.py`
 * → `goaljudge_fresh_tasks.json`; select with `GOALJUDGE_BATCH_MODE=fresh`.
 */
import registry from "./goaljudge_registry.json" with { type: "json" };
import freshTasks from "./goaljudge_fresh_tasks.json" with { type: "json" };
import freshTasksWave2 from "./goaljudge_fresh_tasks_wave2.json" with { type: "json" };
import depthStrata from "./goaljudge_depth_strata.json" with { type: "json" };

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

/** Stage 5 pilot registry IDs (43 rows — all pilot sheet cases except GJ-STRESS-*). */
export const PILOT_REGISTRY_IDS: readonly string[] = [
  "GJ-001",
  "GJ-001B",
  "GJ-002",
  "GJ-003",
  "GJ-003B",
  "GJ-004",
  "GJ-005",
  "GJ-006",
  "GJ-007",
  "GJ-008",
  "GJ-009",
  "GJ-010",
  "GJ-011",
  "GJ-012",
  "GJ-013",
  "GJ-014",
  "GJ-015",
  "GJ-016",
  "GJ-019",
  "GJ-020",
  "GJ-021",
  "GJ-022",
  "GJ-023",
  "GJ-024",
  "GJ-025",
  "GJ-026",
  "GJ-027",
  "GJ-028",
  "GJ-031",
  "GJ-034",
  "GJ-035",
  "GJ-036",
  "GJ-039",
  "GJ-042",
  "GJ-043",
  "GJ-044",
  "GJ-045",
  "GJ-047",
  "GJ-048",
  "GJ-049",
  "GJ-050",
  "GJ-051",
  "GJ-052",
] as const;

/** Stage 5 pilot batch — 43 registry cases (numeric sort). */
export function pilotRegistryCases(): GoalJudgeRegistryCase[] {
  const idSet = new Set(PILOT_REGISTRY_IDS);
  return GOALJUDGE_REGISTRY.filter((c) => idSet.has(c.id)).sort((a, b) =>
    a.id.localeCompare(b.id, undefined, { numeric: true }),
  );
}

/** Phase 5 fresh-authored test split (79 rows after §6 drop). */
export function freshRegistryCases(): GoalJudgeRegistryCase[] {
  return (freshTasks as GoalJudgeRegistryCase[]).sort((a, b) =>
    a.id.localeCompare(b.id, undefined, { numeric: true }),
  );
}

/**
 * Wave-2 fresh-authored corpus (GJ-F-W2-*): closes the 11 under-floor cells from
 * the v0.9 manifest so the gold set can freeze v1. Selected with
 * `GOALJUDGE_BATCH_MODE=wave2`.
 * Regenerate: `.venv/bin/python -m scripts.export_goaljudge_fresh_tasks_wave2_json`.
 */
export function wave2RegistryCases(): GoalJudgeRegistryCase[] {
  return (freshTasksWave2 as GoalJudgeRegistryCase[]).sort((a, b) =>
    a.id.localeCompare(b.id, undefined, { numeric: true }),
  );
}

/**
 * Planning-depth strata (GJ-DEPTH-*): prompts engineered to span L0/L1/L2 to
 * stress the D1 planning-depth dimension the registry doesn't cover. The
 * intended depth + trigger family lives in `stratum` (`depth:Lx:family`).
 * Regenerate: `python scripts/export_goaljudge_depth_strata_json.py`.
 */
export function depthStrataCases(): GoalJudgeRegistryCase[] {
  return (depthStrata as GoalJudgeRegistryCase[]).sort((a, b) =>
    a.id.localeCompare(b.id, undefined, { numeric: true }),
  );
}

function batchModeCases(): GoalJudgeRegistryCase[] {
  const mode = process.env.GOALJUDGE_BATCH_MODE ?? "walkthrough";
  if (mode === "pilot") {
    return pilotRegistryCases();
  }
  if (mode === "fresh") {
    return freshRegistryCases();
  }
  if (mode === "wave2") {
    return wave2RegistryCases();
  }
  if (mode === "depth") {
    return depthStrataCases();
  }
  return walkthroughCases();
}

export function caseById(id: string): GoalJudgeRegistryCase | undefined {
  return GOALJUDGE_REGISTRY.find((c) => c.id === id);
}

export function filterCases(opts?: {
  caseFilter?: string;
  limit?: number;
}): GoalJudgeRegistryCase[] {
  let rows = batchModeCases();
  if (opts?.caseFilter) {
    rows = rows.filter((c) => c.id === opts.caseFilter);
  }
  if (opts?.limit && opts.limit > 0) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}
