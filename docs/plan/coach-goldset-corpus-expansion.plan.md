---
type: plan
title: 'Coach gold-set corpus expansion — Implementation Plan (3.9 unblock)'
authored: 2026-07-05
---

# Coach gold-set corpus expansion — Implementation Plan

**Spec:** [coach-goldset-corpus-expansion.spec.md](coach-goldset-corpus-expansion.spec.md) ·
**Parent:** [coach-goldset-enable-policy.plan.md](coach-goldset-enable-policy.plan.md) (Task 3.9)

## Status ledger

| Item | Status | Evidence |
|---|---|---|
| E1 Dedup + seeded dev sampler | ✅ DONE | `scripts/sample_coach_dev_rows.py` — deterministic + dedupe + bait-bias; 7 L1 tests. On the real corpus: 283 unique of 292, bait fraction lifted **5.7% → 12%** in a 130-row sample. |
| E2 Fresh test-batch authoring | ⬜ **HUMAN — NEXT** | Template + coverage checklist authored: `docs/evals/eng-coach/coach_test_batch_v1.template.md` (5 channels + 2 carve-outs, `fresh-authored`/`test`, §9 discipline). Author → `coach_test_batch_v1.jsonl`. |
| E3 Expanded blind sheets | ✅ DONE (ready for E2) | `export_coach_goldset_iaa_sheets.py` extended: `join_dev_and_test` (dev→synthetic/dev + test-batch passthrough, deterministic dev ids) + Mode-B CLI (`--dev-sample`/`--test-batch`). 5 red-first join tests. Smoke-proven on the real E1 sample + a synthetic batch: 130 dev + N test, blind. **Runs the moment `coach_test_batch_v1.jsonl` lands.** |
| E4 Human double-label round 2 | ✅ DONE | 246-row blind double-label; **α = 0.834** (PASS ≥ 0.80), 12/12 disagreements adjudicated. `docs/IAA/coach/goldset/coach_goldset_combined_sheet.csv`. |
| E5 dev/test disjointness gate | ✅ DONE | `assert_dev_test_disjoint` in `coach_goldset_dataset.py` (FR-1) + 3 red-first tests; firewall (FR-4) + provisional guard (FR-2) already covered. 24 L1 tests green. |
| E6 Non-provisional re-freeze | ✅ DONE | `coach_goldset_v1.json` re-frozen from the adjudicated combined sheet: **246 rows** (130 dev / 116 test), **`provisional=false`**, α=0.834, leak_share 0.175. `assemble_coach_goldset.py --combined-sheet`; +4 E6 tests, 3 provisional-fixture tests repointed (G8-aware). `make check` 5065 pass. See `docs/adr/decisions.md`. |
| E7 Real cert run → 3.9 | ✅ DONE — CERTIFIED | First live cert (gpt-4o, 246-row set) **REFUSED** (TNR 0.9186<0.95, 7 FP); recert round (ADR-0018 → ADR-0019 Fireworks re-host) **CERTIFIED** the judge on `glm-5.2-fireworks`: 3× temp-0 replays all ENABLE, TNR 1.0/TPR 1.0/κ pass, 0 FP, zero-flip (frozen `coach_recert_split_v1.json`, 47 rows). commit `dcb5b56`. Full trail in `coach-goldset-enable-policy.plan.md` (3.9 row) + `coach-recert-fireworks-rehost.plan.md`. Gate stays OFF (Phase-5). |

**FR-5 amended mid-implement** (sdd-replan, 2026-07-05): the corpus has no leak
label, so E1 oversamples by a **bait-signal proxy** (raises the leak prior), not a
measured share; actual `leak_class_share` is measured post-E4. See spec FR-5 +
`docs/adr/decisions.md`.

---

## Architecture

The whole round is **data assembly around unchanged types**. No new service, no
new abstraction, no schema change — `CoachGoldsetItem`/`CoachGoldsetManifest` and
the firewall already encode every invariant. We add **deterministic tooling** to
populate them and a **human labeling round** to bless the labels.

```
292 synthetic corpus ──(E1 dedup+seed sample, leak-oversample)──▶ ~130 DEV rows ┐
                                                                                 ├─▶ expanded
fresh-authored test batch (E2, 5 channels + 2 carve-outs) ───────▶ ~80 TEST rows ┘   sheets (E3)
                                                                                        │
                        (E4) 2 raters label blind ─▶ α ≥ 0.80 ─▶ adjudicate ───────────┘
                                                                                        │
                        (E5) disjointness + firewall gates ─▶ (E6) freeze non-provisional
                                                                                        │
                        (E7) run_coach_calibration.py ─▶ real ENABLE/REFUSE ─▶ Task 3.9
```

**Split math (target ~210):** ~130 dev + ~80 test ≈ 62/38 (within the 60/40
intent; the guard only requires test > 0 and total ≥ 200). Leak share ~0.20–0.25
across both splits.

## File-level touchpoints

| File | Change | Layer |
|---|---|---|
| `scripts/sample_coach_dev_rows.py` | **new** — seeded dedup + leak-oversampling sampler over `cache/coach_shadow/coach_corpus.jsonl` → dev-candidate rows | script (pure) |
| `docs/evals/eng-coach/coach_test_batch_v1.jsonl` | **new (human)** — fresh-authored test turns, `fresh_authored` provenance, all 5 channels + 2 carve-outs | data |
| `scripts/export_coach_goldset_iaa_sheets.py` | extend — accept dev-sample + test-batch sources, not just the fixture; carry `split`/`provenance` through | script |
| `scripts/assemble_coach_goldset.py` | extend — merge dev(synthetic)+test(fresh) sources; enforce dev/test disjointness (FR-1) | script |
| `services/governance/coach_goldset_dataset.py` | **maybe** add a disjointness validator helper if not already present (FR-1); no type change | services (L1) |
| `tests/services/governance/test_coach_goldset_dataset.py` | +disjointness test (FR-1), +leak-share test (FR-5) | test |
| `tests/scripts/test_coach_goldset_iaa.py` | +fresh-batch coverage test (FR-6), +sampler determinism (FR-5) | test |
| `docs/IAA/coach/goldset/*` | regenerated expanded sheets + round-2 α results | data |
| `tests/fixtures/coach_goldset/coach_goldset_v1.json` | re-frozen non-provisional | fixture |

## Migration / sequencing

1. **E1** (agent, pure): build the seeded sampler; watch determinism test fail→pass.
2. **E2** (human): author the fresh test batch — the one irreducibly human authoring step.
3. **E3** (agent): extend the exporter; regenerate the expanded blind sheets (dev+test).
4. **E4** (human): the double-label round → α ≥ 0.80 → adjudicate disagreements.
5. **E5** (agent, red-first): disjointness + leak-share gates.
6. **E6** (agent): re-freeze → `provisional=false`.
7. **E7** (human-run, live): `run_coach_calibration.py` → real cert → paste into 3.9.

## Constitution check (⚠️ Ask-first triggers)

- **No new dependency**, **no trust-kernel change**, **no new graph node**, **no
  new service**, **no new abstraction** — the types + firewall already exist. So
  **no ADR is required**; design choices (sampler seed policy, split ratio landing
  at 62/38, fresh-vs-production) go in `docs/adr/decisions.md`.
- **No rubric `.j2` edit** — the rubric is frozen for this cert (AP-3 not tripped).
- If E5 turns out to need a genuinely new validator abstraction in
  `coach_goldset_dataset.py` (not just a function), that's a **G1** gate → revisit
  for an ADR before adding it.

## Risks

- **α regression on harder rows** (spec §6) — the round-1 0.8327 was on 21 easy
  rows; fresh Socratic/criterion-then-verdict rows are the hard cases. Mitigation:
  the walkthrough guide already codifies these; budget a re-label iteration.
- **Thin leak class in test** (spec §6) — if TPR ends undecidable, the cert
  returns `REFUSE` honestly; oversample the leak strata into the test batch (FR-6).
- **Labeling burden** — ~210×2 labels is the real cost; the ~210 target was chosen
  as the *minimum* that clears the floor for exactly this reason.
