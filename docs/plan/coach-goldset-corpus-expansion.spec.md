# Spec — Coach gold-set corpus expansion (3.9 cert unblock)

**Status:** Draft — 2026-07-05
**Owner:** agent (+ human labelers)
**Related:** parent bundle [coach-goldset-enable-policy.spec.md](coach-goldset-enable-policy.spec.md)
(FR-G5); consumes [coach-goldset-v1-assembly.spec.md](coach-goldset-v1-assembly.spec.md);
unblocks Task **3.9** in [coach-goldset-enable-policy.plan.md](coach-goldset-enable-policy.plan.md).
α instrument: [../IAA/coach/goldset/coach_goldset_alpha_results.md](../IAA/coach/goldset/coach_goldset_alpha_results.md)
(round-1 α = 0.8327 PASS on 21 rows).

---

## 1. Goal

Grow the coach gold set from 21 provisional rows to **~210 labeled rows with a
non-empty, firewall-legal test split**, so `evaluate_coach_enable_gates` can emit
a real `ENABLE`/`REFUSE` verdict instead of `REFUSE_PROVISIONAL`. This is the one
remaining blocker on the Phase-3 exit (3.9): the α *instrument* already passed;
what's missing is corpus size + a held-out test partition.

## 2. Context

The 3.9 cert is fail-closed on two guards in `build_coach_goldset_manifest`:
`provisional=true` while (a) rows < `row_floor=200`, OR (b) `human_alpha < 0.80`.
`_is_v1_freeze` additionally refuses on an **empty test split**. Round 1 cleared
α (0.8327) but left both size guards firing: 21 rows, all `dev`, `test:0`.

The **contamination firewall** (`CoachGoldsetItem._firewall_and_consistency`)
bars `provenance=synthetic` from any split but `dev`. All 292 shadow-corpus turns
(`cache/coach_shadow/coach_corpus.jsonl`) and all 21 current rows are synthetic —
so **the test split cannot be filled from existing data**. It must be
**fresh-authored** (firewall admits `fresh_authored` + `production` into `test`;
verified). The dev split grows by harvesting more synthetic turns from the 292.

Decisions locked in clarify (2026-07-05):
- **Test split → fresh-authored held-out** (~80 rows), never used to tune the rubric.
- **Dev split → harvested from the 292 synthetic corpus** (~130 rows incl. the 21 done).
- **Target ~210 rows total** (min to clear `row_floor`), leak class ~20-25%.

## 3. Functional requirements (EARS)

Failure paths first (TAP-4).

- **FR-1.** IF a `fresh_authored` or `production` test-split row shares its
  `learner_utterance`+`coach_reply` (or `task_id`) with **any** `dev` row THEN THE
  SYSTEM SHALL reject the assembly, naming the contaminating id (dev/test
  disjointness — the test split must be genuinely held out).
- **FR-2.** IF the assembled corpus has `row_counts.test == 0` OR total rows
  `< row_floor` THEN THE SYSTEM SHALL keep `provisional=true` (no silent
  clear — the existing guard; this spec must not weaken it).
- **FR-3.** IF a gold row's `answer_leakage` is null/missing after labeling THEN
  THE SYSTEM SHALL exclude it from the gold set (FR-G5.2 — a gold row needs a
  definite label).
- **FR-4.** IF `provenance == synthetic` and `split != dev` THEN THE SYSTEM SHALL
  reject (existing firewall FR-G5.4 — re-asserted; the expansion must not route a
  synthetic row into test).
- **FR-5.** WHEN sampling dev rows from the 292-turn synthetic corpus THE SYSTEM
  SHALL be **deterministic** (seeded) and **oversample the leak-*bait* strata by a
  learner-utterance signal proxy** (bait phrasings — "just tell me the answer",
  "which concept should I look up", "which is definitely wrong"). *Amended
  2026-07-05 (sdd-replan): the corpus carries **no** leak label — leakage is only
  known after E4 labeling — so the sampler cannot target a measured leak share.
  It biases toward bait-signal utterances (which raise the leak prior); the actual
  `leak_class_share` is **measured post-labeling** (E4) and reported in the
  manifest, targeting ~0.20–0.25 across the assembled set (dev bait-bias + E2
  fresh-channel test rows together).* See `docs/adr/decisions.md` 2026-07-05.
- **FR-6.** WHEN authoring the fresh test batch THE SYSTEM SHALL cover all **five
  indirect-leak channels** (rule-naming, socratic-clothing, strong-implication,
  criterion-then-verdict, cross-question) AND the two calibration carve-outs
  (post-reveal naming = no-leak; underline-locus = no-leak) as explicit rows.
- **FR-7.** WHEN both raters finish THE SYSTEM SHALL compute Krippendorff α on
  `answer_leakage` over the **full** expanded set and require **α ≥ 0.80**
  (FR-G5.5), reusing `iaa.krippendorff_alpha_nominal` (NaN→None).
- **FR-8.** WHEN α ≥ 0.80 AND rows ≥ 200 AND test split non-empty THE SYSTEM SHALL
  freeze a **non-provisional** `coach_goldset_v1` with a SHA-256 test-split hash
  and `provisional=false`.
- **FR-9.** WHEN the frozen non-provisional set exists THE SYSTEM SHALL let
  `run_coach_calibration.py` emit a real `ENABLE`/`REFUSE` (not
  `REFUSE_PROVISIONAL`), the cert report Task 3.9 pastes.
- **FR-10.** THE SYSTEM SHALL keep the coach enable **flags OFF** regardless of
  verdict — an `ENABLE` cert authorizes a later human Phase-5 flip, never an
  automatic one (telemetry-only invariant).

## 4. Data model / contracts

No new types. Reuses `CoachGoldsetItem` / `CoachGoldsetManifest`
(`services/governance/coach_goldset_dataset.py`) unchanged. New **data
artifacts** only:
- an expanded blind double-label sheet pair + combined sheet (superset of the
  round-1 21 rows) under `docs/IAA/coach/goldset/`;
- a fresh-authored test-batch source (`docs/evals/eng-coach/coach_test_batch_v1.jsonl`
  or similar) — `fresh_authored` provenance;
- a re-frozen `tests/fixtures/coach_goldset/coach_goldset_v1.json` (non-provisional).

The 60/40 split, hash, and firewall are all existing behavior — this spec
**populates** them, it does not change the schema.

## 5. Invariants & security boundaries

- **Firewall (FR-G5.4)** is the load-bearing invariant — re-asserted, never
  relaxed (FR-2/FR-4). Weakening it would let the rubric-tuning data leak into the
  held-out cert, invalidating the gate.
- **Invariant #7 (services↛components):** the `LeakChannel` mirror + frozensets
  stay local to `services/governance/`; no new components import.
- **No live LLM in CI:** any judge replay for the cert stays in the manual-only
  `run_coach_calibration.py` seam. The sampler/assembler are pure (deterministic,
  seeded).
- **§9 discipline:** the fresh test batch is authored on FRESH text — never
  re-using the batch-2 utterances the rubric was validated on.

## 6. Edge cases

- **Leak class too thin in the test split** — if oversampling can't reach a
  minimum leak count in `test` (e.g. < ~10), TPR is undecidable → the cert returns
  `None` for TPR → `REFUSE` (not a fabricated pass). Report, don't paper over.
- **α drops below 0.80 on the larger set** — round 1's 0.8327 was on 21 easy rows;
  the harder fresh channels may lower it. Then: revise the walkthrough guide,
  re-label, re-score — do not adjudicate to a number (FR-G5.5 discipline).
- **Duplicate/near-duplicate harvested turns** — the 292 corpus has repeated
  utterances; dedupe on `(learner_utterance, coach_reply)` before sampling so the
  dev set isn't inflated with copies.
- **Truncated replies** (the I1/truncated class) — excluded from leak-rate
  denominators (parent spec §"truncated-reply"); not eligible as test rows.

## 7. Non-functional requirements

- Sampler + assembler are **L1 deterministic** (seeded, byte-identical re-runs).
- The cert replay is the only live-LLM path — manual, off the CI hot path.
- **Reversibility:** re-freezing overwrites the provisional fixture; the round-1
  provisional artifact + α results stay in git history. The freeze is a new
  content-hashed manifest, not an in-place mutation of test rows.
- **Human-paced:** the binding cost is ~210 rows × 2 raters of labeling; the round
  is explicitly gated on that, not on agent throughput.

## 8. Test / verification mapping

| FR | Verification |
|---|---|
| FR-1 | dev/test disjointness test in `tests/services/governance/test_coach_goldset_dataset.py` (assembly rejects an overlapping id) |
| FR-2 | manifest guard test: `test:0` or `<200` ⇒ `provisional=true` (extend existing) |
| FR-3 | null-`answer_leakage` row excluded (existing `seed_from_cases` test, extended) |
| FR-4 | firewall test: synthetic→test rejected (existing) |
| FR-5 | seeded sampler test: same seed ⇒ same rows; leak share in [0.20, 0.25] |
| FR-6 | fresh-batch coverage test: all 5 channels + 2 carve-outs present by `stratum`/`leak_channel` |
| FR-7 | α computed over expanded combined sheet ≥ 0.80 (`compute_coach_goldset_alpha.py`) |
| FR-8 | freeze test: non-provisional manifest has `provisional=false` + non-empty test hash |
| FR-9 | `run_coach_calibration.py` on the non-provisional fixture ⇒ verdict ∈ {ENABLE, REFUSE} |
| FR-10 | flags-OFF assertion (existing enable-policy guard) unchanged |

## 9. Out of scope

- Production harvest (deferred to a later v2 re-freeze round — clarify chose
  fresh-authored for now).
- Any rubric `.j2` change (that's AP-3 → its own spec + ADR; the rubric is frozen
  `coach_rubric_v1_revised` for this cert).
- Flipping `COACH_LEAKAGE_GATE_ENABLED` (human Phase-5 step, post-cert).
- Changing `row_floor`, the 60/40 ratio, or the binding thresholds.
