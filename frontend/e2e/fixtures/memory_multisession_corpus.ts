/**
 * Memory multi-session corpus for the T3 cross-session memory stress run.
 *
 * Regenerate: `python scripts/build_memory_multisession_corpus.py`
 *   → frontend/e2e/fixtures/memory_multisession_corpus.json
 *
 * Each CASE is a conversation = an ordered list of SESSIONS; each session is one
 * `/run/stream` invocation (one thread) driven through the live UI. The memory
 * layer keys on `user_id` (`identity.owner`), so each case carries a PER-CASE-
 * UNIQUE `user_id` — that uniqueness is what makes the cross-user-leak guard
 * observable. The spec is a driver + capture; the `want_*`/`expect_substring`
 * keys are NOT asserted per-case in the spec (T3 is non-deterministic — the
 * trace-analysis half scores aggregate rates). See
 * `docs/plans/memory_multisession_e2e_stress.plan.md`.
 */
import corpus from "./memory_multisession_corpus.json" with { type: "json" };

export type MemoryAbility =
  | "recall"
  | "multi-session"
  | "temporal"
  | "leak-control"
  | "knowledge-update"
  | "abstention"
  | "persona-drift"
  // Hermes / memory-os adoptions (docs/research/memory/hermes_adoptions_design.md):
  | "relevance-floor" // A2: weak off-topic facts filtered by the recall floor
  | "recall-dedup" // A2: duplicate fact rendered once
  | "salience-tier" // A3: [confirmed]/[inferred] provenance tiers
  | "budget-consolidation"; // A1: over-budget store consolidates (evicts low salience)

export type SessionKind = "seed" | "filler" | "probe" | "crud-seed";

/** A memory planted directly via the /agent/memory CRUD route (A1/A3) — lets a
 * case set salience/type explicitly, bypassing shadow autocapture. */
export type SeedMemory = {
  key: string;
  text: string;
  type: "semantic" | "episodic" | "procedural";
  /** Omitted → the record renders unmarked (A3 backward-compat path). */
  salience?: number;
};

export type MemorySession = {
  session_idx: number;
  kind: SessionKind;
  turns: string[];
  /** Deterministic per-session trace_id (stable report/join fallback). */
  trace_id: string;
  date?: string;
  // probe-only expectations:
  want_recall?: boolean;
  expect_substring?: string[];
  evidence_session_idx?: number;
  // Hermes-adoption expectations (all optional, additive):
  /** A2/A3: text that must NOT appear in the probe answer (filtered/evicted). */
  expect_absent_substring?: string[];
  /** A1/A3: memories to plant via CRUD before the probe (kind = "crud-seed"). */
  seed_memory?: SeedMemory[];
  /** A1: the probe run should carry a MEMORY_CONSOLIDATED carrier (evicted>0). */
  expect_consolidation?: boolean;
};

export type MemoryCase = {
  case: string;
  /** Regex-conforming id (MEM-XXXX) the mem: thread bridge requires. */
  mem_id: string;
  ability: MemoryAbility;
  provenance: "longmemeval-derived" | "synthetic-locomo-shape" | "synthetic";
  /** Per-case UNIQUE synthetic memory subject; satisfies [0-9A-Za-z]+. */
  user_id: string;
  sessions: MemorySession[];
  rationale: string;
  lme_question_type?: string;
};

export const MEMORY_MULTISESSION_CORPUS: MemoryCase[] = corpus as MemoryCase[];

/**
 * Filter cases by single-case id, ability, and limit.
 *   MEM_CASE_FILTER=MEM-RECALL-units-01   — one case
 *   MEM_ABILITY=knowledge-update          — one ability
 *   MEM_LIMIT=4                            — cap (applied AFTER ability filter)
 */
export function filterCases(opts?: {
  caseFilter?: string;
  ability?: string;
  limit?: number;
}): MemoryCase[] {
  let rows = MEMORY_MULTISESSION_CORPUS;
  if (opts?.ability) {
    rows = rows.filter((c) => c.ability === opts.ability);
  }
  if (opts?.caseFilter) {
    rows = rows.filter((c) => c.case === opts.caseFilter);
  }
  if (opts?.limit && opts.limit > 0) {
    rows = rows.slice(0, opts.limit);
  }
  return rows;
}

/** One case per ability — the smoke subset (confirm carriers + screenshots). */
export function smokeCases(): MemoryCase[] {
  const seen = new Set<string>();
  const out: MemoryCase[] = [];
  for (const c of MEMORY_MULTISESSION_CORPUS) {
    if (!seen.has(c.ability)) {
      seen.add(c.ability);
      out.push(c);
    }
  }
  return out;
}
