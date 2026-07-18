# Gen2 Step 4 scorecard — solve-consistency + contamination

Generated 2026-07-17 · follows `synthetic-data-pipeline` Step 4 · lot:
`research/synthetic_data_pipeline_handover/docs/questionbank/coach-item-bank-gen2.promoted.json`
(1,000 items, all `reviewed=false`).

> **Law:** this gate never flips `reviewed`. Quarantine on fail; Step 5 still
> owns acceptance sampling.

---

## 4a. Contamination (deterministic) — PASS

| Comparison | Field | Exact | Jaccard ≥0.85 | Jaccard ≥0.75 |
|---|---|---:|---:|---:|
| vs live bank (171) | `context_html` | 0 | 0 | 0 |
| vs live bank | context+stem | 0 | 0 | 0 |
| vs Test-01 timed corpus (48) | `context_html` | 0 | 0 | 0 |
| vs Test-01 | context+stem | 0 | 0 | 0 |

- Timed corpus scope (open decision B.6.3): set to
  `frontend/lib/adapters/engine/_test01_english_corpus.ts` — the only evidenced
  timed-test English corpus in-repo.
- Machine report: `docs/questionbank/coach-bank-gen2-step4-contamination.json`

## 4b. Solve-consistency (live multi-family) — COMPLETE (lot FAIL → quarantine)

| Parameter | Value |
|---|---|
| Job | `scripts/run_solve_consistency.py` |
| Families | `openai:gpt-4o-mini+gpt-4o>=d4` + `anthropic:claude-haiku-4-5+claude-sonnet-4-6>=d4` |
| Routing | d≥4 → capable tier within each family; else fast |
| Contract | answer-blind (`_solver_view`); unanimous letter == declared key |
| Output | `docs/questionbank/coach-bank-gen2-step4-solve.json` (never stamps `reviewed`) |
| Scored | **1000 / 1000** |
| Verdict | **FAIL** (c=0 on the full lot — 184 quarantined) |

| Status | n | Action |
|---|---:|---|
| `pass` | **816** | eligible for Step 5 lot |
| `disagree` | 154 | quarantine → human-review (cross-family disagreement) |
| `mismatch` | 30 | quarantine → human-review (both families agree, ≠ key) |
| `undecidable` | 0 | — |

Failures by difficulty: {1: 7, 2: 43, 3: 78, 4: 42, 5: 14}.

**Step 5 lot size:** N=**816** (solve-PASS ∩ leak-green). Quarantine IDs are in
`coach-bank-gen2-step4-solve.json` → `quarantine_ids`.

## Exit criteria

- [x] Contamination vs live + timed corpus = 0 critical hits
- [x] Solve-consistency: 100% of lot scored; quarantine list frozen (184)
- [x] Step 5 AQL sample drawn only from solve-PASS ∩ leak-green items (N=816) → `coach-bank-gen2-aql-sample.json` (n=80, seed=20260717)
