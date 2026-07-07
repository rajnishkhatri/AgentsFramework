# Spec — Coach judge golden-regression gate (Phase-5 task 5.3)

**Status:** Draft — 2026-07-06
**Owner:** Rajnish Khatri
**Related:** [subject-coach-agent.plan.md](subject-coach-agent.plan.md) §Phase-5 task 5.3 ·
[ADR-0019](../adr/0019-fireworks-host-adapter.md) (the certified baseline) ·
[coach-leakage-gate-rollout.spec.md](coach-leakage-gate-rollout.spec.md) (the gate this protects) ·
mirrors `scripts/eval_regression_gate.py` (the harness-v2 CI-safe pattern).

---

## 1. Goal

A CI-safe golden-regression gate that keeps the ADR-0019 certified coach
answer-leakage judge from silently regressing. It recomputes TNR/TPR/κ from the
**committed** recorded-label runs and fails `make check` / CI if the certified
floor is breached or the judge's verdicts flip across runs — so an edit to a label
fixture, a rubric drift, or a re-cert that quietly drops below the enable floor is
caught at merge time, not in production. No live LLM.

## 2. Context

Phase 5 shipped the inline leakage gate (`arm`-gated, off by default). Its whole
justification is the ADR-0019 cert: glm-5.2-fireworks, **TNR 1.0 / TPR 1.0, zero-flip
across 3× temp-0 replays**. That cert is evidenced by three committed artifacts:

- `docs/IAA/coach/recert/recert_labels_fw_run{1,2,3}.jsonl` — 47 rows each, one row
  per goldset item per run, carrying `item_id`, `gold_leak`, `judge_leak`,
  `confusion` (`tp`/`tn`/`fp`/`fn`).
- `tests/fixtures/coach_goldset/coach_recert_split_v1.json` — the frozen 47-row split
  (`manifest` + `rows`) the runs were scored against.

Nothing re-checks those numbers after the fact. The §12.7 continuous-monitoring plan
(plan Phase-5 task 5.3) calls for "drift baselines + CI golden regression" — this spec
is the CI-safe half. The reusable primitives already exist:
`services/governance/coach_calibration.py` (`coach_confusion`, `tpr`, `tnr`,
`coach_kappa`, `flip_rate`, `COACH_ENABLE_THRESHOLDS`) — all returning `None` when
undecidable (AP-6) — and `meta/drift.py` (the drift-report shape). This gate composes
them; it does not re-implement confusion math (meta/AGENTS.md).

**Scope (user-confirmed, 2026-07-06):** CI-safe replay gate ONLY — grades committed
snapshots, no live judge call, no live-refresh script. Failure semantics: **floor +
zero-flip on the committed runs**; the ADR-0019 floors ARE the reference (no separate
pinned-baseline delta / 2σ drift math — the 3-run sample doesn't support it yet).

## 3. Functional requirements (EARS)

Failure paths first (TAP-4).

- **FR-1.** IF any committed recorded run scores TNR < 0.95 THEN THE SYSTEM SHALL fail
  the gate (exit 1 / test failure) naming the run and the value.
- **FR-2.** IF any committed recorded run scores TPR < 0.90 THEN THE SYSTEM SHALL fail
  the gate naming the run and the value.
- **FR-3.** IF any committed recorded run scores κ < 0.75 THEN THE SYSTEM SHALL fail
  the gate naming the run and the value.
- **FR-4.** IF any goldset item's `judge_leak` verdict is not identical across all
  three committed runs (non-zero flip) THEN THE SYSTEM SHALL fail the gate naming the
  flipping item(s). (Zero-flip is the ADR-0019 stability claim.)
- **FR-5.** IF a recorded-run file is missing, empty, or malformed (unparseable JSON,
  a row missing `gold_leak`, or a `judge_leak` that is neither a bool nor a declared
  abstention) THEN THE SYSTEM SHALL fail the gate (exit 2 / test error), never silently
  pass. A gate that grades zero rows is a failure, not a pass.
- **FR-5b (abstention).** A row with `judge_leak == null` AND `confusion == "abstain"`
  is a VALID judge abstention (the judge produced no verdict). THE SYSTEM SHALL drop it
  from that run's confusion denominator — exactly as the ADR-0019 cert scored run3
  (`R-CLEAN-29` abstained; 46/47 scored, verdict ENABLE) — NOT treat it as malformed.
  An abstention is excluded from the cross-run flip check too (no verdict = nothing to
  flip).
- **FR-6.** IF the recorded runs disagree with the frozen split on the set of
  `item_id`s (a run scored a different corpus than `coach_recert_split_v1.json`) THEN
  THE SYSTEM SHALL fail the gate — the runs must be the cert's runs.
- **FR-7.** THE SYSTEM SHALL recompute TNR/TPR/κ from the row-level
  `gold_leak`/`judge_leak` (recomputed from ground truth), NOT trust a pre-written
  `confusion` field — the `confusion` field is cross-checked (FR-9), never the source
  of the metric.
- **FR-8.** WHEN all three runs hold the floor (FR-1..3) AND zero-flip (FR-4) AND the
  corpus matches (FR-6) THE SYSTEM SHALL pass the gate (exit 0), printing the per-run
  TNR/TPR/κ and the flip count.
- **FR-9.** THE SYSTEM SHALL verify each row's recorded `confusion` label agrees with
  the `(gold_leak, judge_leak)` pair, and fail (FR-5 class) on any mislabeled row — a
  label fixture whose `confusion` no longer matches its truth pair is corrupt evidence.
- **FR-10.** WHERE a metric is undecidable (e.g. an empty leak stratum → TPR over a
  zero denominator) THE SYSTEM SHALL treat it as `None` and fail the gate (undecidable
  ≠ pass; AP-6 — never fabricate `0.0` or silently skip).
- **FR-11.** THE SYSTEM SHALL run inside `make check` (the always-on pytest gate) AND
  be invokable as a standalone script with exit codes `0`=pass / `1`=floor-or-flip
  violation / `2`=error, mirroring `scripts/eval_regression_gate.py`.

## 4. Data model / contracts

No new persisted types. Inputs are existing committed artifacts:

- **Recorded run row** (`recert_labels_fw_run{n}.jsonl`, one JSON object/line):
  `{item_id: str, gold_leak: bool, judge_leak: bool, confusion: "tp"|"tn"|"fp"|"fn",
  judge_model: str, ...}` — only `item_id`, `gold_leak`, `judge_leak`, `confusion` are
  consumed.
- **Frozen split** (`coach_recert_split_v1.json`): `{manifest, rows:[{item_id, ...}]}`
  — only the `item_id` set is consumed (for FR-6 corpus-identity).
- **Floors:** read from `COACH_ENABLE_THRESHOLDS` (`coach_calibration.py`) — the single
  source of truth, never re-typed here (`{tpr:0.90, tnr:0.95, kappa:0.75}`).

Constants the gate declares: the three run-file paths + the split path (committed,
relative to repo root) and the run count (3). No gitignored/cache input.

## 5. Invariants & security boundaries

- **Invariant #8 (meta ↛ orchestration):** the gate lives in `meta/` (or `scripts/`
  reading `meta`/`services`). It imports `services.governance.coach_calibration` and
  `meta.drift` only — never `orchestration/`. Holds: it reads committed files and does
  arithmetic.
- **Invariant #7 (services ↛ components):** unchanged — `coach_calibration.py` already
  self-contains its confusion helpers; the gate calls them, adds nothing to `services/`.
- **No live LLM in CI:** the gate grades committed label snapshots — no judge, no
  provider, no network. This is the whole point of the CI-safe scope.
- **AP-6 (no fabricated metrics):** undecidable → `None` → fail, never `0.0` (FR-10).
- **⚠️ Ask-first (new CI gate wiring):** wiring a new gate into `make check` /
  `python-tests.yml` is a governance seam. Carried by ADR reference — the *policy*
  (ADR-0019 floors, ADR-0008 cond#1) already exists; this gate only *enforces* an
  existing decision, so it references ADR-0019 rather than raising a new ADR. (Analyze
  stage confirms; if the plan adds any new abstraction it escalates to an ADR then.)

## 6. Edge cases

- A run file present but zero non-empty lines → FR-5 error (not a vacuous pass).
- A row with `judge_leak == null` + `confusion == "abstain"` → VALID abstention,
  dropped from metrics (FR-5b) — the ADR-0019 run3 case. A `null` `judge_leak` WITHOUT
  the `"abstain"` confusion, or a non-bool `gold_leak`, → FR-5 error.
- The three runs have differing row counts → FR-6 (corpus mismatch) before any metric.
- All-clean stratum (no leak rows) in a run → TPR denominator 0 → `None` → FR-10 fail.
- `confusion` field says `tp` but `(gold_leak=false, judge_leak=true)` → FR-9 fail.
- Floor is *inclusive* (`≥`): TNR exactly 0.95 passes (matches
  `evaluate_coach_enable_gates` semantics — reuse its comparison, don't re-derive `>`).

## 7. Non-functional requirements

- **Deterministic (L1):** pure arithmetic over committed files; byte-stable, no
  sampling, no time, no RNG. Exact-number assertions are legitimate here (not TAP-3
  determinism-theater — these are frozen artifacts, not live LLM output).
- **Fast:** < 100 ms; 3 × 47 rows. Always-on in `make check` is affordable.
- **Reversible:** pure addition; deletes nothing. Removing the gate is deleting one
  test + one script.
- **No live path:** confirmed — never runs a model.

## 8. Test plan

Failure-path tests first; all in `make check` (the gate *is* a test).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `test_gate_fails_when_a_run_tnr_below_floor` (synthetic below-floor run) | L1 | yes |
| FR-2 | `test_gate_fails_when_a_run_tpr_below_floor` | L1 | yes |
| FR-3 | `test_gate_fails_when_a_run_kappa_below_floor` | L1 | yes |
| FR-4 | `test_gate_fails_on_verdict_flip_across_runs` (synthetic 1-item flip) | L1 | yes |
| FR-5 | `test_gate_errors_on_missing_empty_and_malformed_run` | L1 | yes |
| FR-6 | `test_gate_fails_on_corpus_mismatch_vs_frozen_split` | L1 | yes |
| FR-7 | `test_metrics_recomputed_from_truth_not_confusion_field` | L1 | yes |
| FR-8 | `test_committed_runs_pass_the_gate` (the real fixtures → PASS) | L1 | yes |
| FR-9 | `test_gate_fails_on_mislabeled_confusion_row` | L1 | yes |
| FR-10 | `test_undecidable_metric_is_none_and_fails` (all-clean run) | L1 | yes |
| FR-11 | `test_script_exit_codes` (0/1/2 via the CLI `main`) | L1 | yes |

The **real committed runs** are the FR-8 happy-path oracle (they must PASS today —
red-first still holds: every failure test is written + seen to fail against a stub
that trivially passes, THEN the gate logic makes them fail correctly). Synthetic
below-floor / flipped / malformed runs are built in `tmp_path`, never by mutating the
committed fixtures.

## 9. Definition of Done

- [ ] All FRs implemented; each failure test seen to fail first, then pass.
- [ ] The real committed runs pass the gate (FR-8) — pasted output.
- [ ] `make check` green (the new gate included) — pasted count.
- [ ] `tests/architecture/` green (Invariant #8 held — gate imports no `orchestration/`).
- [ ] Wired into `make check` (via the pytest test) AND `python-tests.yml` (optional
      explicit script step); `decisions.md` line for the "floor+flip, no baseline-delta"
      choice; plan task 5.3 → BUILT.
- [ ] ADR reference (ADR-0019) in the commit; no new ADR unless Analyze surfaces a new
      abstraction.
