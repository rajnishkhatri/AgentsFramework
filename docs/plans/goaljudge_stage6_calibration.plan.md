# GoalJudge Stage 6 — Judge Calibration against `goaljudge_goldset_v1`

> **Status:** AUTHORED 2026-06-12 — development unblocked against the **v0.9 provisional manifest**
> ([contract](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_v0_9_contract.md)); the §2.8 enable
> decision itself is hard-gated on the **v1 freeze** (Phase 4 wave 2 →
> [wave-2 plan](goaljudge_stage5_phase6c_v09_and_wave2.plan.md)).
> **Terminates in:** the [§2.8 enable gates](../research/fix2_goaljudge_rubric_feasibility_pyramid.md)
> decision on `goal_judge_downgrade_enabled` — **flag stays default-off until every gate clears.**
> **Owner pattern:** TDD (RED → GREEN per phase), L1-pure metrics, no live LLM in CI, no
> `langgraph`/`langchain`/`components` imports in the new L1 module. User runs deploys/commits.

---

## 1. Mission

Stage 5 produced a trusted gold-set (101 rows now at v0.9; ~250 at v1). Stage 6 answers one
question with it:

> **Is the GoalJudge accurate enough that its `goal_met=False` verdict may downgrade a
> production run's outcome from `success` to `partial`?**

The answer is the §2.8 **precision-floor-first enable policy**. All five gates must clear
simultaneously, measured against the frozen v1 test split:

| # | Gate | Threshold | Why this number |
|---|---|---|---|
| G-P | Precision on `goal_met=False` | **≥ 0.90** | ≤ 10 % of downgrades are undeserved |
| G-R | Recall on `goal_met=False` | **≥ 0.70** | below this the gate isn't worth enabling |
| G-FD | False-downgrade rate over clean successful runs | **≤ 2 %** | population-level bound — stricter than G-P because successes dominate the base rate |
| G-FLIP | Red-team verdict-flip rate (CoT gaming) | **≤ 5 %** (soft 10 %) | judge must not be argued out of its verdict by fabricated progress |
| G-κ | Agreement vs. human gold labels | **κ ≥ 0.6** | measurement prerequisite — below this the other numbers aren't trustworthy |

Plus: **ECE is diagnostic-only** (reported, never gating), and the flag remains
**default-off until all five clear**. Source: foundation pyramid Decision 5
(confidence 0.74) and the Stage 5 master plan [§12 handoff](goaljudge_stage5_goldset.plan.md).

### What Stage 6 is NOT

* Not a rubric revision (rubric locked at `stage4_confirmed`; a revision reopens Stage 4).
* Not the gold-set build (Stage 5 owns the sheet, labels, manifest, hash).
* Not the flag flip itself — Stage 6 produces the **evaluated gate decision**; the user
  flips `goal_judge_downgrade_enabled` (GCS runtime config / env) and owns the deploy.

---

## 2. Inputs — the two-manifest reality

| Input | Now (v0.9 era) | At v1 |
|---|---|---|
| Manifest | `cache/goaljudge_eval/goldset_v0_9_manifest.json` (101 items, hash `ad5eccc0…`, `provisional=true`) | `goldset_v1_manifest.json` (≥ 250 items, `provisional=false`) |
| Sheet | [`goaljudge_stage5_goldset_combined_sheet.csv`](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv) | wave-2-extended sheet |
| Gate behavior | `gate_goldset_v1_floors()` **raises** — per-cell-power code paths stay inert | gate **passes** — full per-cell calibration fires |
| What runs | end-to-end harness, all metrics, headline numbers labeled PROVISIONAL | the §2.8 enable decision |

Everything in Phases 0–5 below is **developable and runnable against v0.9 today**. The only
thing v0.9 cannot do is *decide* — per-cell confidence intervals are useless at 4-row cells,
so any number produced before v1 is labeled `provisional` in the report and the §2.8
evaluator refuses to emit an ENABLE verdict (it calls `gate_goldset_v1_floors()` first).

---

## 3. Architecture — where code lives

```
   manifest.json ──► load + gate + hash-verify ──┐
   sheet.csv ──────► GoldsetItem iterator ───────┤
   corpus JSONL ───► success_conditions join ────┼──► replay loop (LIVE LLM, script-only)
                                                 │        │ one GoalVerdict per item
                                                 │        ▼
                                                 │   verdicts.jsonl (capture artifact)
                                                 │        │
                                                 ▼        ▼
                                       services/governance/goaljudge_calibration.py
                                       (L1 PURE: confusion counts, P/R/F1, FD-rate,
                                        κ/α, ECE bins, flip-rate, §2.8 evaluator)
                                                 │
                                                 ▼
                                       calibration report .md + gate decision JSON
```

| Surface | File | Layer rules |
|---|---|---|
| Pure metrics + §2.8 evaluator | `services/governance/goaljudge_calibration.py` (NEW) | L1: stdlib + pydantic only. Zero `components/`, `langgraph`, `langchain` imports. Same discipline as `iaa.py`. |
| Replay harness CLI | `scripts/run_goaljudge_calibration.py` (NEW) | scripts/ (outside grid). The ONLY place the live judge is invoked. Never in CI. |
| Red-team flip harness | extend the existing offline red-team fixture pin (`tests/components/test_goal_judge_redteam_offline.py` stratum + fixture) | replay variants via the same CLI `--redteam` mode |
| L1 tests | `tests/services/test_goaljudge_calibration.py` (NEW) | mocked verdicts, golden numbers, failure-paths-first |
| L2 tests | `tests/scripts/test_run_goaljudge_calibration.py` (NEW) | subprocess contract tests with a stub judge (`--judge stub`), no network |
| Untouched | `components/goal_judge.py`, the `.j2` rubric, `GoalVerdict`, orchestration gate, `trust/` | calibration *measures* the judge; it must not modify it |

**Reuse, do not reinvent:**
* `krippendorff_alpha` from [`services/governance/iaa.py`](../../services/governance/iaa.py) —
  for G-κ. For 2 raters (judge vs. gold) with complete data, nominal α coincides with Cohen's
  κ; report it as the κ-gate input and document the equivalence (same convention as Stage 5).
* `gate_goldset_v1_floors`, `compute_test_split_hash`, `row_to_goldset_item` from
  [`goaljudge_goldset_dataset.py`](../../services/governance/goaljudge_goldset_dataset.py).
* `GoalJudge.evaluate` + `GoalVerdict` — invoked as-is by the replay script; the judge code
  path being measured is the production code path.
* The corpus-sidecar join pattern (`trace_id`-keyed) from
  [`build_goaljudge_stage5_combined_sheet.py`](../../scripts/build_goaljudge_stage5_combined_sheet.py).

---

## 4. The replay seam — three decisions to lock at Phase 0

> **Phase 0 COMPLETE (2026-06-12) — decisions locked + amended in
> [the replay audit](../research/goaljudge_stage6_replay_audit.md).** Coverage gate
> PASS (100/101). Key amendments the audit forced: (1) full judge inputs were never
> persisted — a 200-char publish-time cap (`black_box_publisher._MAX_DETAIL_VALUE_LEN`)
> truncated every span field, so the **recorded production verdicts** (full input
> fidelity in-process) become the primary v0.9 signal and replay is for harness
> validation + drift measurement; (2) replay `final_answer` sources from `ui_batch`
> `response_text` (101/101 full coverage), not the span; (3) `success_conditions`
> turned out to be one constant generic pair across all 100 rows — the join is
> trivial and a production finding in its own right; (4) **new wave-2 prerequisite:**
> lift the telemetry caps before the wave-2 GCP batch; (5) the free shadow
> calibration already says the deployed judge would fail §2.8 today (α=0.50,
> FD=8/20) — see audit §4. The subsections below record the original reasoning.

### 4.1 Evidence must be digest-frozen, not re-derived

`GoalJudge.evaluate(evidence=…)` takes the raw trajectory and builds the digest internally
(`_summarize_evidence`, last-8 cap, redaction). But the gold labels were assigned by humans
reading the **frozen** `GoldsetItem.evidence_digest`. If replay re-derives the digest from the
trajectory, any drift in summarization/redaction silently changes what the judge sees vs. what
the humans labeled — an invisible validity hole.

**Decision: replay renders the rubric prompt with the stored `evidence_digest` string
directly** (the prompt template takes `evidence` as a string), bypassing `_summarize_evidence`.
Implementation: a small `evaluate_from_digest()` seam — either a module-level helper in the
replay script that mirrors `GoalJudge.evaluate`'s render-invoke-parse sequence, or (preferred)
a thin keyword path on the component. Phase 0 picks; the constraint is that the
render → invoke → `_parse_verdict` chain is byte-identical to production apart from the digest
source.

### 4.2 `success_conditions` are not on the GoldsetItem — join them from the corpus

The judge's fourth input, `success_conditions`, is **plan-derived at runtime**
([components/plan_builder.py:158](../../components/plan_builder.py)) and not a gold-set field.
The enriched `eval.goal_judge` telemetry payload records it
([orchestration/react_loop.py:1400](../../orchestration/react_loop.py)), so the corpus JSONL
sidecars should carry it per trace.

**Decision: join `success_conditions` from the corpus sidecar by `source_trace_id`** — the
same two-sidecar pattern Tier 3 used for D5 classification. **Phase 0 must audit** that every
v0.9 item's trace actually has the field in
`cache/goaljudge_eval/corpus_gcp_*.jsonl`; any absent rows fall back to `[]` **and are
flagged in the report** (a judge scored without conditions is a different measurement —
count them, don't hide them).

### 4.3 Confidence proxy for ECE

The verdict has no explicit confidence field; `criteria_met ∈ [0,1]` is the closest proxy
(fraction of success conditions the judge found satisfied). **Decision: ECE uses
`criteria_met` as the confidence signal, 10 equal-width bins, reported diagnostic-only** —
with the proxy choice stated in the report so nobody mistakes it for a calibrated probability.
If the proxy proves degenerate (e.g. bimodal at {0,1}), report that finding instead of the ECE
number.

### 4.4 Determinism posture

The judge is an LLM. Production invokes it **once** per run, so calibration replays it
**once** per item (matching the deployed behavior is the measurement). A `--repeat k` flag
(default 1) exists for an optional variance study; repeat runs report verdict-instability
alongside the headline metrics but never replace single-shot numbers in the gate evaluation.

---

## 5. Metric definitions (locked, so the code and the report can't drift)

With gold label `g ∈ {met, not-met}` and judge verdict `j ∈ {met, not-met}`, on the test split:

* **TP** = judge not-met ∧ gold not-met (correct downgrade signal)
* **FP** = judge not-met ∧ gold met (**the harm case** — false downgrade)
* **FN** = judge met ∧ gold not-met (missed failure)
* **TN** = judge met ∧ gold met
* **G-P precision** = TP / (TP + FP) — gate ≥ 0.90
* **G-R recall** = TP / (TP + FN) — gate ≥ 0.70
* **G-FD false-downgrade rate** = FP / (FP + TN) — fraction of *clean successes* the judge
  would wrongly downgrade — gate ≤ 0.02. Note v0.9's `goal_met_false_share = 0.792` means
  only ~21 gold-met rows exist now: a single FP ≈ 5 % — **this gate is mathematically
  undecidable until v1**, one more reason the evaluator refuses on provisional manifests.
* **G-κ** = nominal Krippendorff α over the (judge, gold) pair on `goal_met` — gate ≥ 0.6.
* **G-FLIP flip rate** = over the red-team stratum + offline CoT-gaming fixture: fraction of
  paired (clean, gamed) evidence variants where the verdict flips met→not-met or not-met→met
  under fabricated-progress pressure — gate ≤ 0.05 (soft 0.10).
* **ECE** = Σ |bin| / N · |acc(bin) − conf(bin)| over 10 `criteria_met` bins — diagnostic.
* **Secondary (report-only):** macro-F1, per-`failure_mode` recall, per-`provenance` split
  (production-only subset is the headline per master plan §8.2), per-D1/D5 cell table
  (v1-gated), `partial_fraction` MAE on gold not-met rows, `graceful_failure` agreement.

---

## 6. Phases (TDD, RED → GREEN each)

### Phase 0 — Replay-input audit + seam decisions (small, blocking)
Audit the corpus sidecars: does every v0.9 `source_trace_id` resolve, and does its
`eval.goal_judge` payload carry `success_conditions`? Output: a short
`docs/research/goaljudge_stage6_replay_audit.md` with per-item coverage counts + the locked
§4 decisions (digest-frozen replay mechanism, conditions-join fallback count, ECE proxy).
**Gate to proceed:** ≥ 90 % of items have joinable conditions; below that, escalate before
building (the calibration would measure a judge materially different from production's).

### Phase 1 — L1 pure metrics (RED → GREEN)
`tests/services/test_goaljudge_calibration.py` first: failure-paths-first (empty verdict set,
single-class degenerate input, division-by-zero guards, unknown item_id in verdicts, length
mismatch), then golden-number cases (hand-computed confusion matrix → exact P/R/FD/κ/ECE).
Then implement `services/governance/goaljudge_calibration.py`:
`confusion_counts()`, `precision_recall_fd()`, `judge_gold_kappa()` (delegates to
`iaa.krippendorff_alpha`), `expected_calibration_error()`, `flip_rate()`,
`evaluate_section_2_8_gates(metrics, manifest) -> GateDecision` — the last one calls
`gate_goldset_v1_floors(manifest)` and returns `REFUSE_PROVISIONAL` on v0.9 **by design**.

### Phase 2 — Replay harness CLI (RED → GREEN)
L2 contract tests with `--judge stub` (deterministic fake verdicts, no network): manifest
load + hash verify happens before any replay; refuses on hash mismatch; writes
`cache/goaljudge_eval/calibration_verdicts_<run>.jsonl` (one row per item: item_id, verdict
fields, latency, model name, prompt sha); `--resume` skips already-captured items;
`--redteam` mode replays the paired CoT-gaming variants. Then implement
`scripts/run_goaljudge_calibration.py` wiring the real `GoalJudge` behind the same interface.

### Phase 3 — Report builder (RED → GREEN)
Pure function: verdicts JSONL + sheet + manifest → markdown report
(`docs/IAA/goalJudge/goldset/goaljudge_stage6_calibration_report.md`) + machine-readable
`gate_decision.json`. Sections: headline gates table (PASS/FAIL/UNDECIDABLE per gate),
per-provenance, per-failure-mode, per-cell (emitted only when the v1 gate passes; v0.9 prints
"floor-gated — v1 required"), ECE reliability table, variance study if `--repeat` > 1.

### Phase 4 — Live v0.9 dry calibration (script run, not CI)
Run the harness for real against v0.9 (101 items × fast-tier judge — cheap). Purpose: shake
out the replay seam end-to-end and get **provisional** headline numbers. Expected output:
report labeled PROVISIONAL, `gate_decision.json` = `REFUSE_PROVISIONAL`. This run also
back-validates Stage 5: gross judge-vs-gold disagreement (κ « 0.6) at this step would be an
early warning to investigate *before* paying for wave 2 labeling.

### Phase 5 — Red-team flip-rate harness
Wire `--redteam` against the red_team stratum (2 rows at v0.9) + the existing offline
CoT-gaming fixture pairs. Report flip-rate with its CI; at v0.9 sample sizes this is
directional only.

### Phase 6 — Docs + handoff
Update master plan §12 (Stage 6 plan now exists), tier review, goldset README. Write the
runbook section: the exact two commands (v0.9 dry run; v1 decision run) + the post-v1
procedure: re-run harness → all five gates PASS → user flips
`goal_judge_downgrade_enabled` via runtime config and deploys (**user-owned step**).

---

## 7. Verification

1. **L1:** `.venv/bin/python -m pytest tests/services/test_goaljudge_calibration.py -q` — all green.
2. **L2:** `.venv/bin/python -m pytest tests/scripts/test_run_goaljudge_calibration.py -q` — stub-judge contract green, zero network.
3. **Dependency-leak audit:** `grep -n "from components\|import langgraph\|import langchain" services/governance/goaljudge_calibration.py` → empty.
4. **Golden numbers:** hand-computed 12-item confusion fixture reproduces exact P/R/FD/κ to 6 dp.
5. **Determinism:** report builder over the same verdicts JSONL twice → byte-identical output.
6. **Live smoke (Phase 4):** v0.9 run completes 101/101, report labeled PROVISIONAL, decision JSON = `REFUSE_PROVISIONAL`.
7. **Regression sweep:** existing `iaa`/`goldset_dataset` suites untouched and green.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| `success_conditions` missing from corpus for many items | Phase 0 audit gates the build at 90 % coverage; absent rows fall back to `[]` and are counted in the report, never silently |
| Judge model/prompt drifts between calibration and the enable decision | verdicts JSONL records model name + rendered-prompt SHA per item; the §2.8 evaluator refuses if verdicts span ≠ 1 model or ≠ 1 prompt hash |
| v0.9 numbers leak as if they were the decision | evaluator hard-refuses on `provisional=true` (calls `gate_goldset_v1_floors`); report banner; G-FD mathematically undecidable at 21 gold-met rows |
| LLM nondeterminism makes the gate decision unstable | single-shot matches production; optional `--repeat` variance study quantifies instability before the v1 decision run |
| Live LLM sneaks into CI | live invocation exists only in the script; L2 tests use `--judge stub`; AGENTS.md rule re-checked in review |
| Flip-rate sample too thin even at v1 | red-team stratum + offline fixture pairs combined; report the CI; soft threshold 10 % exists for exactly this |

---

## 9. Done-ness

1. ⏸ Phase 0 audit doc + locked seam decisions.
2. ⏸ Phases 1–3 landed under TDD, all verification green.
3. ⏸ Phase 4 v0.9 dry calibration: provisional report + REFUSE_PROVISIONAL decision artifact.
4. ⏸ Phase 5 red-team mode wired.
5. ⏸ Phase 6 docs flipped; runbook written.
6. ⏸ (post-wave-2, separate session) v1 decision run → five-gate evaluation → user flips flag or the report says why not.

Items 1–5 are fully executable now against v0.9. Item 6 waits on the
[wave-2 plan](goaljudge_stage5_phase6c_v09_and_wave2.plan.md) closing the floors.

---

## 10. References

| Doc | Why |
|---|---|
| [fix2 feasibility pyramid §2.8](../research/fix2_goaljudge_rubric_feasibility_pyramid.md) | The enable-policy decision: thresholds, options considered, "threshold to change" |
| [Stage 5 master plan §12](goaljudge_stage5_goldset.plan.md) | The handoff contract this plan consumes |
| [v0.9 contract](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_v0_9_contract.md) | What's blessed against v0.9; gate API; cutover protocol |
| [wave-2 plan](goaljudge_stage5_phase6c_v09_and_wave2.plan.md) | What gates v1 (and therefore the §2.8 decision) |
| [`services/governance/iaa.py`](../../services/governance/iaa.py) | κ/α implementation to reuse |
| [`components/goal_judge.py`](../../components/goal_judge.py) | The judge under measurement — `evaluate()` signature, `_parse_verdict` |
| [`services/goal_judge_runtime_config.py`](../../services/goal_judge_runtime_config.py) | Where `goal_judge_downgrade_enabled` resolves at runtime |
