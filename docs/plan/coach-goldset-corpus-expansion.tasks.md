# Tasks — Coach gold-set corpus expansion (3.9 unblock)

**Spec:** [coach-goldset-corpus-expansion.spec.md](coach-goldset-corpus-expansion.spec.md) ·
**Plan:** [coach-goldset-corpus-expansion.plan.md](coach-goldset-corpus-expansion.plan.md)

Atomic, file-level, 1:1 pass/fail from the EARS FRs. Failure-path tasks first
within a unit (TAP-4). Red/green TDD on every code task. Legend: **[dep: …]** ·
**‖** parallel · **HUMAN** = human gate.

---

## E1 — Seeded dev sampler `scripts/sample_coach_dev_rows.py` [no dep] ‖ E2
Deterministic dedup + leak-oversampling sample over
`cache/coach_shadow/coach_corpus.jsonl` → ~130 dev-candidate rows (incl. the 21
already labeled, so they are not re-labeled).
- **E1-1 (FR-5, red first)** same seed ⇒ byte-identical row set; different seed ⇒
  differs.
- **E1-2 (FR-5)** dedupe on `(learner_utterance, coach_reply)` — no duplicate
  survives into the sample.
- **E1-3 (FR-5, amended)** bait-signal oversample: a seeded sample with bait-bias
  ON contains a **strictly higher** fraction of bait-signal utterances than the
  corpus baseline (the sampler *raises the leak prior*; it does NOT assert a
  measured leak share — leakage is unknown pre-E4). Actual `leak_class_share` is
  measured post-labeling.
- **Pass:** determinism + dedupe + bait-bias tests green; sampler imports only
  stdlib/`meta`/`services`.
- **Fail if:** any nondeterministic ordering (unsorted set iteration) leaks into
  the output.

## E2 — Fresh test batch `docs/evals/eng-coach/coach_test_batch_v1.jsonl` [no dep] — HUMAN ‖ E1
Author ~80 fresh coach turns (`fresh_authored` provenance) as the held-out test
split. **Fresh text only** — never the batch-2 utterances.
- **E2-1 (FR-6)** every one of the 5 indirect-leak channels (rule-naming,
  socratic-clothing, strong-implication, criterion-then-verdict, cross-question)
  appears ≥ once, tagged by `stratum`/`leak_channel`.
- **E2-2 (FR-6)** both carve-outs present as explicit rows: a post-reveal-naming
  row (`post_feedback`, no-leak) and an underline-locus row (no-leak).
- **Pass:** file parses; channel/carve-out coverage checklist met.
- **Fail if:** any row reuses a batch-2/dev utterance verbatim (§9 discipline).

## E3 — Extend exporter `scripts/export_coach_goldset_iaa_sheets.py` [dep: E1, E2]
Accept the dev-sample + fresh test batch as sources (not just the fixture); carry
`split`/`provenance` into the sheets so the split is fixed **before** labeling.
- **E3-1** regenerated blind sheets cover all ~210 rows; the 21 round-1 labels are
  carried forward, not blanked.
- **Pass:** `test_coach_goldset_iaa.py` extended + green; blind invariant still
  holds (no `answer_leakage` guess in annotator sheets).
- **Fail if:** the exporter leaks `split`-implied leak info that would bias labeling.

## E4 — Human double-label round 2 [dep: E3] — HUMAN
Two raters label `answer_leakage` blind over the ~210 rows; α on the full set.
- **E4-1 (FR-7)** `compute_coach_goldset_alpha.py` on the combined sheet ⇒
  **α ≥ 0.80**; else revise the walkthrough, re-label, re-score (do NOT adjudicate
  to a number).
- **E4-2** every `r1 ≠ r2` row adjudicated → `adjudicated_answer_leakage`.
- **Pass:** α ≥ 0.80 recorded in `coach_goldset_alpha_results.md`; 0 blank gold
  cells.

## E5 — Disjointness + leak-share gates `tests/services/governance/test_coach_goldset_dataset.py` [dep: E1, E2] ‖ E4
Red-first, before the re-freeze relies on them.
- **E5-1 (FR-1, failure first)** assembly REJECTS a test row overlapping a dev row
  on id / `(utterance, reply)`, naming the id.
- **E5-2 (FR-2)** `test:0` OR `<200` ⇒ `provisional=true` (guard un-weakened).
- **E5-3 (FR-4)** synthetic→test still rejected (firewall re-assert).
- **Pass:** each seen red then green; `pytest tests/architecture/ -q` green.

## E6 — Non-provisional re-freeze `scripts/assemble_coach_goldset.py` [dep: E4, E5]
Merge dev(synthetic)+test(fresh) adjudicated rows; stamp real α; freeze.
- **E6-1 (FR-8)** manifest: `provisional=false`, `row_counts.test > 0`, total ≥ 200,
  non-empty `test_split_hash`, `human_alpha_answer_leakage ≥ 0.80`.
- **E6-2 (FR-3)** null-`answer_leakage` rows excluded.
- **Pass:** re-frozen `coach_goldset_v1.json` clears provisional; `make check` green.
- **Fail if:** any in-place mutation of an existing frozen test row (re-freeze is a
  new hash, not an edit).

## E7 — Real cert run → Task 3.9 [dep: E6] — HUMAN-run (live)
`run_coach_calibration.py` replays the frozen test split through the judge → cert.
- **E7-1 (FR-9)** verdict ∈ {`ENABLE`, `REFUSE`} — NOT `REFUSE_PROVISIONAL`.
- **E7-2 (FR-10)** flags stay OFF regardless of verdict.
- **Pass:** cert JSON emitted; gate table + verdict pasted into the parent ledger
  (Task 3.9); code-review the diff; `make check` green.

---

## Dependency graph

```
E1 ─┬─▶ E3 ─▶ E4 ─┬─▶ E6 ─▶ E7
E2 ─┘             │
E1,E2 ─▶ E5 ──────┘
```
E1 ‖ E2 (author while sampler builds). E5 ‖ E4 (gates while labeling).

## Human gates (explicit)

- **E2** — fresh test-batch authoring (irreducible).
- **E4** — the double-label round + adjudication.
- **E7** — the live cert run (manual, keys from env).

## Out of scope (re-stated)

- Production harvest, any rubric `.j2` edit, flag flips, threshold/ratio changes.
