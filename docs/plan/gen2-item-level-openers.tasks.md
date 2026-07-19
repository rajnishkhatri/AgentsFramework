# Tasks — Gen2 item-level (no-pick) hint opener authoring — pilot shard

**Spec:** [gen2-item-level-openers.spec.md](gen2-item-level-openers.spec.md) · **Plan:** [gen2-item-level-openers.plan.md](gen2-item-level-openers.plan.md)
**Status:** Draft — 2026-07-19

---

## Checklist — is every EARS criterion measurable?

| FR | Measurable? | Metric |
|----|-------------|--------|
| FR-1 leak | ✅ | leak-lint returns 0 hits over pilot rows |
| FR-2 neutrality | ✅ | no opener references a named distractor error-type; lint 0 hits |
| FR-3 no-unreviewed-serve | ✅ | `emit_hint_bank.py` exits non-zero on an unreviewed row |
| FR-4 rung shape | ✅ | every pilot item: exactly 3 rows, choice_letter=null, rungs {1,2,3}, no rung 4 |
| FR-5 diversity | ✅ | max rung-1 template frequency ≤20% |
| FR-6 anchor provenance | ✅ | few-shot set = only rows with reviewed=true + Gen1 generated_by |
| FR-7 acceptance sampling | ⚠️ partial | scorecard has n/Ac=0/defect-classes; the human verdict itself is manual (deferred) |
| FR-8 provenance stamp | ✅ | generated_by matches `<model>@<run_id>`; confinement test accepts |
| FR-9 pilot decision gate | ✅ | scorecard artifact exists; no full-corpus job auto-triggered |

FR-7's human verdict is intentionally out of implementation scope (clarified: build funnel, defer review). Everything else is deterministically checkable in `make check`.

## Tasks (atomic, file-level; [P]=parallelizable, →=depends on)

### T1 — Freeze the pilot shard [P]
- **File:** `docs/plan/gen2-item-level-openers.pilot-shard.json` + `docs/adr/decisions.md`
- **Do:** deterministically sample ~15/skill × 6 skills (both item types, difficulty spread) from `coach-item-bank-gen2.reviewed.json`; write the frozen id list; record the selection rule in `decisions.md` (2–4 lines).
- **Pass/fail:** shard has 50–100 items, all 6 skills present, both item_types present; `decisions.md` entry exists. (Maps: spec §9 shard-selection DoD.)

### T2 — Author the item-level opener prompt →T1
- **File:** `prompts/hint_item_level_opener.j2`
- **Do:** misconception-neutral pre-pick opener prompt; 3 rungs pump→hint→prompt; handles underlined-span AND rhetorical items; inherits no-leak + ≥10-opener-diversity contracts; few-shot slot for reviewed Gen1 openers.
- **Pass/fail:** template renders for one underlined-span and one rhetorical sample without a hardcoded answer reference (F-R5: no answer strings; it's a `.j2` in `prompts/`). (Maps: FR-2, FR-4, FR-5.)

### T3 — Write the lints, RED first [P] (independent of generation)
- **Files:** opener-lint test module co-located with hint cascade tests; reuse `components/hint_leakage.py`.
- **Do (red→green):**
  - FR-1 test: a fixture opener naming the correct label/letter → lint REJECTS. *Watch it fail first, then wire the lint.*
  - FR-2 test: a fixture opener that presumes distractor C's error → REJECTS.
  - FR-4 test: a 2-rung or rung-4-bearing item → REJECTS.
  - FR-5 test: a batch where >20% share a rung-1 template → REJECTS.
- **Pass/fail:** each test seen to fail before the lint exists, then green. (Maps: FR-1/2/4/5 — failure paths first, TAP-4.)

### T4 — Run the offline generation job →T1,T2,T3
- **Command:** `.venv/bin/python scripts/generate_hints.py --questions docs/plan/gen2-item-level-openers.pilot-shard.json --out docs/questionbank/coach-bank-openers-pilot.raw.json` (with the new prompt wired + Gen1 few-shot).
- **Pass/fail:** `openers-pilot.raw.json` produced; every row `reviewed=false`; generated_by = `<model>@<run_id>` (FR-8). NOT in CI (offline, live LLM). (Maps: FR-6, FR-8.)

### T5 — Cascade + lints over 100% of pilot rows →T3,T4
- **Do:** run schema + FR-1/2/4/5 lints + dedup (vs served bank) on every raw row; route failures to repair; three-strikes → stop + re-plan the prompt.
- **Pass/fail:** 0 leak hits, 0 neutrality hits, rung-shape valid, diversity ≤20%, 0 dedup collisions; rows remain `reviewed=false`. (Maps: FR-1/2/4/5, spec §6 dedup edge case.)

### T6 — Assert emit fail-closed unchanged [P]
- **File:** emit test.
- **Do:** feed `emit_hint_bank.py` a pilot row with `reviewed=false` → assert non-zero exit.
- **Pass/fail:** emit refuses the unreviewed row (FR-3 not weakened). In `make check`. (Maps: FR-3.)

### T7 — Provenance confinement holds [P] →T4
- **Do:** run `tests/architecture/test_test_item_provenance_confinement.py` against a hypothetically-flipped pilot row.
- **Pass/fail:** a `reviewed=true` row with the cascade generated_by format is accepted; a hand-stamped one is rejected. (Maps: FR-8.)

### T8 — Build the Step-5 sampling harness + scorecard →T5
- **Files:** `docs/questionbank/coach-bank-openers-pilot-step5-scorecard.md` (mirror `coach-bank-gen2-step5-scorecard.md`); sampling record mirroring `coach-bank-gen2-aql-sample.json`.
- **Do:** compute Z1.4 n for the pilot lot size; scorecard fields = n, critical Ac=0, five critical classes, minor AQL 2.5, defect log; leave the human-verdict field UNFILLED (deferred).
- **Pass/fail:** scorecard artifact exists with all fields; n derived from the Z1.4 table (not invented). (Maps: FR-7 partial, FR-9.)

### T9 — Pilot decision gate + no auto-trigger [P] →T8
- **Do:** confirm no full-816 job is wired to fire on pilot completion; the scorecard is the explicit human go/no-go input.
- **Pass/fail:** grep shows no full-corpus generation call auto-chained; DoD note that full-corpus is a separate human decision. (Maps: FR-9.)

### T10 — Green gate
- **Command:** `make check`.
- **Pass/fail:** lint + format + pyright + deterministic tests (T3/T5/T6/T7 in-CI portions) green; `tests/architecture/` green. Paste actual output. (Maps: spec §9 DoD.)

## Dependency graph

```
T1 ─┬─ T2 ─┐
    │       ├─ T4 ─ T5 ─ T8 ─ T9
    └─ T3 ──┘         │
T3 (red) ────────────┘
T6 [P]  T7 [P] (→T4)   T10 (gate, last)
```

Parallelizable: T1, T3, T6 start immediately; T7/T9 gate on their inputs; T10 last.

## Verification map (1:1 EARS → task)

FR-1→T3/T5 · FR-2→T3/T5 · FR-3→T6 · FR-4→T3/T5 · FR-5→T3/T5 · FR-6→T4 · FR-7→T8 · FR-8→T4/T7 · FR-9→T8/T9.
