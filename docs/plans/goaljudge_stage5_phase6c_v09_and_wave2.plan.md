# GoalJudge Stage 5 — Phase 6-C v0.9 shipment + Phase 4 wave 2 brief

> **Status:** Phase 6-C **DONE this session (2026-06-11)**; Phase 4 wave 2 **queued** as the next sourcing task.
> **Outcome of 6-C:** The provisional v0.9 gold-set manifest is shipped + gated; Stage 6 development is unblocked.
> **What remains:** ~150 fresh-authored prompts to close the 11 under-floor cells, re-label wave 2, re-freeze as v1.
> **Owners:** Phase 6-C — me (this session). Wave 2 — human-paced (annotators A1 + A2), with me as the toolchain operator.

---

## 1. Why this plan exists

At the end of the Phase 5 + Phase 6-A/B session, two facts were true:

1. **Wave 1 is done.** 79 fresh-authored + 22 pilot-production rows are labeled, adjudicated,
   and frozen with α-gate cause-analysis applied. The combined 101-row sheet passes every
   per-row `GoldsetItem` invariant.
2. **The Tier 3 floor gate fails** because per-cell power isn't there yet: D1 deficit 88, D5
   deficit 64. Six cells have ≥ 11-row gaps; three D1 cells are all under-floor.

Two paths were open: ship the smoke manifest and *call it good* (Path C), or wait for wave 2
sourcing before any Stage 6 dev can begin (Path B). Neither was right. Path C abandons the
floor calibration that's the whole point of the gold-set; Path B blocks Stage 6 development
for days/weeks while we source rows that are mostly schema-equivalent to what we already have.

**Path D — hybrid — split the work into two tracks:**

* **Track 1 (this session, ~2 h):** Ship the combined manifest as a *blessed* v0.9 provisional
  artifact with explicit provisional markers + a fails-closed gate. Stage 6 dev starts today
  on a credible 101-row artifact.
* **Track 2 (next sourcing batch, days, human-paced):** Author wave 2 against the gap report.
  Re-run Phase 4 → Phase 5 → Phase 6 on the new rows. v1 freeze. Mechanical, not architectural.

Track 1 is done. Track 2 is what this plan covers next.

---

## 2. What Track 1 shipped (recap, with paths)

### Code

* [services/governance/goaljudge_goldset_dataset.py](../../services/governance/goaljudge_goldset_dataset.py)
  * `+ GoldsetProvenance.FRESH_AUTHORED` enum value (so the fresh-authored stream isn't
    classified as either production or synthetic; firewall still gates only SYNTHETIC ⇒ dev).
  * `+ build_goldset_manifest(provisional=False, floor_gap_summary=None)` kwargs.
  * `+ provisional` + `floor_gap_summary` keys baked into every emitted manifest (default
    invocation produces `provisional=False`, `floor_gap_summary={}` — v1 shape).
  * `+ gate_goldset_v1_floors(manifest) -> None` — fails-closed with
    `AssemblyInvariantError` on: missing v1 keys, blank hash, `provisional=True`, or
    non-empty `floor_gap_summary`. Idempotent + non-mutating.
* [scripts/assemble_goaljudge_goldset.py](../../scripts/assemble_goaljudge_goldset.py)
  * `+ --provisional` flag — skips floor invariants like `--skip-cell-coverage` does, AND
    computes the per-cell `floor_gap_summary` via `compute_cell_coverage`, AND embeds both
    flags into the manifest body.
* [scripts/verify_goldset_v1_cutover.py](../../scripts/verify_goldset_v1_cutover.py) — NEW
  standalone verifier the v0.9 → v1 cutover will invoke (3 checks: gate-on-v1, hash-changed,
  schema-stable). Already smoke-tested by feeding the v0.9 manifest as both inputs — fails
  with the expected diagnostic.

### Tests

* [tests/services/test_goaljudge_goldset_dataset.py](../../tests/services/test_goaljudge_goldset_dataset.py)
  — `+9` tests across `TestBuildGoldsetManifestProvisional` (3) and `TestGateGoldsetV1Floors`
  (6). Covers: default-v1-shape, provisional+gap recorded, contradictory combo raises,
  v1 manifest passes silently, provisional raises, non-empty gap raises, missing-hash raises,
  blank-hash raises, idempotency + no mutation.
* [tests/scripts/test_assemble_goaljudge_goldset.py](../../tests/scripts/test_assemble_goaljudge_goldset.py)
  — `+2` L2 CLI contract tests (`TestAssembleCliProvisional`): with `--provisional` the
  manifest carries `provisional: true` + non-empty gap summary; without it `provisional: false`,
  empty summary.
* **Regression:** 112 L1 (up from 103) + 5 L2 (up from 3) ⇒ **133 PASS** across the three
  touched modules.

### Artifacts

* [cache/goaljudge_eval/goldset_v0_9_manifest.json](../../cache/goaljudge_eval/goldset_v0_9_manifest.json)
  — 17-key manifest, 101 items, hash `ad5eccc0abd857986e40c6b098e67448a309bd72e7fc1083b8b31db8dbc453cd`,
  `provisional=true`, 11-entry `floor_gap_summary` (D1: L0=28, L1=56, L2=35; D5: web-bound=16,
  wrong-tool=14, blocked-tool=11, compose=11, file-only=9, no-tool=7, request_approval=6,
  shell-bound=5).

### Docs

* [docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_v0_9_contract.md](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_v0_9_contract.md)
  — NEW contract. CAN/CANNOT lists for Stage 6, gate API, v0.9 → v1 transition criteria,
  cutover protocol, stage-6 dev checklist.
* [docs/IAA/goalJudge/goldset/README.md](../IAA/goalJudge/goldset/README.md) — status banner
  flipped to v0.9 milestone.
* [docs/reports/goaljudge_stage5_goldset_tier_review.md](../reports/goaljudge_stage5_goldset_tier_review.md)
  — Tier 3 row updated to `v0.9 PROVISIONAL FROZEN`; phase status table expanded with
  Phase 6-C + the wave-1 done rows + the wave-2 pending rows; critical path split into
  `§3 wave 1 DONE` + `§4 wave 2 active`.

---

## 3. The manifest's role in the broader pipeline

Important calibration on what the manifest **does** today vs. **is designed to do**:

### Today (what actually reads/writes the manifest)

1. **Producer** — `scripts/assemble_goaljudge_goldset.py` writes JSON.
2. **Pure-function builder** — `build_goldset_manifest()` assembles the 17-key dict.
3. **Gate** — `gate_goldset_v1_floors()` fails-closed for any caller that needs a v1 freeze.
   *No production caller invokes it yet; it exists for Stage 6 to call.*
4. **Cutover verifier** — `scripts/verify_goldset_v1_cutover.py` reads the old+new
   manifests at v0.9 → v1 transition only.
5. **Tests** — verify shape/keys/gate behavior.

**No middleware, no component, no agent code reads it today.** Grep confirms it.

### Designed (Stage 6, next workstream)

Per [`docs/plans/goaljudge_stage5_goldset.plan.md`](goaljudge_stage5_goldset.plan.md) §12,
Stage 6 calibration will, on every run:

1. Load `goldset_v1_manifest.json`.
2. Call `gate_goldset_v1_floors(manifest)` — refuses to proceed against v0.9.
3. Verify `rubric_version` matches the current GoalJudge rubric.
4. Pull items from Langfuse (`dataset_name`).
5. Recompute `compute_test_split_hash` on the live test items.
6. Diff against `manifest['test_split_sha256']` — refuse on mismatch (proves test split
   wasn't tuned between freezes).
7. Run GoalJudge on every item; collect per-row predictions.
8. Bucket per-cell metrics (P/R/F1 on `goal_met=False`) by the four distribution dicts.
9. Compute ECE + CoT-gaming flip-rate.
10. Compare per-cell counts to the manifest's distribution snapshots — drift report.
11. Apply §2.8 enable gates (false-downgrade ≤ 2 %, flip ≤ 5 %, κ ≥ 0.6).
12. If all green ⇒ flip `goal_judge_downgrade_enabled` to true.

The manifest is the **immutable certificate** the gold-set hands Stage 6.

---

## 4. The 17 manifest keys, grouped by purpose

| Group | Keys | Role at Stage 6 |
|---|---|---|
| **Identity** | `dataset_name`, `rubric_version`, `frozen_at` | Refuse to calibrate if rubric drifted. |
| **Integrity invariant** | `test_split_sha256` | Recomputed at every Stage 6 run; mismatch ⇒ refuse. Single most load-bearing key. |
| **Counts** | `total_items`, `dev_count`, `test_count` | Sanity check that the live Langfuse dataset matches. |
| **Distribution snapshots** | `stratum_distribution`, `planning_depth_distribution`, `tool_cluster_distribution`, `failure_mode_distribution` | Drift detection per-run; bucket basis for per-cell metrics. |
| **Quality floor** | `goal_met_false_share` | Spec §4 ≥ 0.60; confirms the failure class isn't degenerate. |
| **Informational counters** | `routing_reason_distribution_observed`, `model_tier_distribution_observed`, `cost_fraction_bins_observed` | Currently `{}`; populated when D6 telemetry feeds back. |
| **Provisional markers (new, Phase 6-C)** | `provisional`, `floor_gap_summary` | The v0.9 / v1 distinguisher; gate fails-closed on v0.9. |

---

## 5. Track 2 — Phase 4 wave 2 sourcing (the remaining critical path)

### Goal

Close the 11 under-floor cells named in the v0.9 manifest's `floor_gap_summary` so the
assembler can run **without** `--provisional` (i.e. with cell-coverage floors enforced) and
produce `goldset_v1_manifest.json`.

### Floor-gap brief (drives the sourcing)

| Dim | Cell | Floor | Have | Gap | Why this cell is hard |
|---|---|---|---|---|---|
| D1 | L0 | 60 | 32 | **28** | L0 = no-tool / single-shot answer; natural for `no-tool`, `file-only`, `request_approval` cells. |
| D1 | L1 | 100 | 44 | **56** | The bulk of agent traces; mostly file-only + shell-bound + compose. Largest single gap. |
| D1 | L2 | 60 | 25 | **35** | Multi-step planning; natural for `compose`, `wrong-tool`, `blocked-tool`. |
| D5 | file-only | 25 | 16 | 9 | Easy to fill at L0/L1; covered by basic read/write tasks. |
| D5 | shell-bound | 30 | 25 | 5 | Pilot already filled most; small top-up needed. |
| D5 | web-bound | 25 | 9 | **16** | Underrepresented across all D1 levels; need targeted web-tool prompts. |
| D5 | no-tool | 15 | 8 | 7 | L0-natural; reasoning-only prompts. |
| D5 | compose | 40 | 29 | 11 | Multi-family trajectories (file_io + shell + web_search). |
| D5 | wrong-tool | 20 | 6 | **14** | Adversarial: blocked/wrong tool selection; requires hand-stamped flag. |
| D5 | blocked-tool | 15 | 4 | **11** | Adversarial: budget-blocked tool calls; hand-stamped. |
| D5 | request_approval | 10 | 4 | 6 | HITL-gated cluster; needs prompts where the right move is to *ask*. |

**Total deficit:** D1 = 119, D5 = 79.

**Sourcing math:** rows count for both axes. The theoretical minimum (max of the two
deficits) is **~88 rows**; realistic with reasonable cell-overlap is **~150 rows**.

### Sub-steps

#### 5.1 Phase 4 wave 2 authoring

* Reuse [`FreshTask` schema](../../services/governance/goaljudge_goldset_dataset.py) — same
  fields, vocabulary, drift-guards. No schema changes.
* Validate every new row through `validate_fresh_task_set` — vocabulary, planning-depth /
  cluster correctness, jaccard < 0.5 vs. the existing 101-row corpus + the 22 pilot rows
  + the original GoalJudge registry (`frontend/e2e/fixtures/goaljudge_registry.ts`).
* Per-cell sourcing distribution sketch (overlapping by design):
  * **L0 batch (28 rows):** 8 × no-tool / answer-only, 8 × file-only single-shot read,
    7 × request_approval scenarios, 5 × wrong-tool / blocked single-call.
  * **L1 batch (56 rows):** 18 × file-only multi-call, 12 × shell-bound multi-call,
    14 × web-bound, 12 × compose pair.
  * **L2 batch (35 rows):** 14 × compose triple, 11 × wrong-tool multi-step,
    10 × blocked-tool multi-step.
  * Plus 6 dedicated `request_approval` HITL prompts (some L0, some L1).
* Output: `tests/fixtures/goaljudge/fresh_test_tasks_wave2.py` (or append to the existing
  fixture under a `WAVE` discriminator; decide at authoring time, prefer separate fixture
  for clean per-wave drift-guard reporting).

#### 5.2 GCP playwright run on wave 2

* Same `goaljudge-batch` spec as wave 1: `frontend/e2e/full-stack/goaljudge-batch.spec.ts`.
* Batch tag: `gcp_wave2_2026-MM-DD` (date the run lands).
* Capture both: UI batch JSONL (live-region DOM evidence) **and** corpus JSONL (Langfuse
  trajectories). The corpus JSONL is the one the cell-classifier reads for D5; the UI
  batch is the one annotators read for labeling evidence.
* Per the [playwright skill gotchas](~/.claude/skills/agentsframework-playwright/references/gotchas.md):
  pin locale `en-US`; target `article div[aria-live='polite']` not bare `[aria-live]`;
  wait by text-settle not by `finished()`; strip status-feed prefix before deciding what
  counts as a real answer.

#### 5.3 Phase 5 wave-2 labeling

* Both annotators (same A1, A2) cold-blind on wave-2 rows only. Wave-1 labels are frozen.
* **Use the updated protocol** — the Rule 7 push-back-success / `request_approval`
  reconciliation clauses landed during wave 1 disagreement adjudication and are merged
  into [`full_set_labeling_protocol.md`](../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md).
* α computed on **just the wave 2 rows** (not the full ~250). The original 101 are
  frozen; the labeling protocol's stability check is whether wave 2 produces α ≥ 0.8 with
  the same annotators + the now-stable protocol. Wave 1's α = 0.27 was dominated by the
  R-6 grader-bug residue (12 of 22 disagreements); that bug is fixed, so wave 2 α should
  land well above 0.8.
* Adjudicate any wave-2 disagreements with `apply_adjudication`.

#### 5.4 Phase 6 v1 freeze

* Build the combined sheet (wave 1 + wave 2) via an extension of
  [`scripts/build_goaljudge_stage5_combined_sheet.py`](../../scripts/build_goaljudge_stage5_combined_sheet.py).
* Run `scripts/assemble_goaljudge_goldset.py` **without** `--provisional` and **without**
  `--skip-cell-coverage`. The assembler succeeds only if every D1/D5 floor is met.
* `build_goldset_manifest` produces `provisional=False`, `floor_gap_summary={}`.
* Rename output `goldset_v0_9_manifest.json` → `goldset_v1_manifest.json` (keep the v0.9
  file around for 2 weeks in case rollback is needed).
* Run `scripts/verify_goldset_v1_cutover.py --v09 goldset_v0_9_manifest.json --v1 goldset_v1_manifest.json` —
  expects all 3 checks PASS (gate on v1, hash changed, schema stable).
* `gate_goldset_v1_floors()` flips from raises-`AssemblyInvariantError` to returns-`None`
  — Stage 6 calibration is fully unblocked at the engineering level.

### Acceptance for v1

All seven of these must hold simultaneously (from the v0.9 contract §"v0.9 → v1
transition criteria"):

1. Combined sheet has ≥ 250 rows.
2. Every wave-2 row blind-labeled by A1 + A2.
3. α on wave-2 rows alone ≥ 0.8.
4. Wave-2 disagreements adjudicated.
5. Assembler succeeds with **default flags** (no `--provisional`, no `--skip-cell-coverage`).
6. Manifest has `provisional=False`, `floor_gap_summary={}`.
7. `gate_goldset_v1_floors(manifest)` returns `None`.

### Verification (at each wave-2 milestone)

* **Authoring milestone** — `pytest tests/fixtures/goaljudge/test_fresh_task_drift_guard.py`
  green; combined wave-1+wave-2 jaccard report green; per-cell distribution sketch matches
  the gap-driven targets above (±5 rows per cell).
* **Playwright milestone** — verify GCP run via `scripts/verify_run.py` from the playwright
  skill: 100 % of wave-2 case ids surface in the corpus JSONL; Langfuse trace count matches
  distinct case count; status-feed prefix stripped before answer presence check.
* **Labeling milestone** — A1 + A2 sheets joined via
  `scripts/merge_goaljudge_stage5_iaa_sheets.py`; α via
  `scripts/compute_goaljudge_stage5_alpha.py --diff` ≥ 0.8 on wave 2.
* **Freeze milestone** — assembler succeeds without `--provisional`; cutover verifier all-3
  PASS; manifest hash differs from v0.9 hash `ad5eccc0…`.

---

## 6. Critical invariants (must never break)

Even though wave 2 is mostly mechanical, three invariants are easy to violate and would be
expensive to fix after the fact.

| Invariant | Why | Where enforced |
|---|---|---|
| **Wave-1 labels stay frozen.** | The 101 rows were adjudicated under a specific protocol version + a known A1 grader bug. Re-litigating them under wave-2 conditions would invalidate the v0.9 hash and break Stage 6's diff. | Wave-2 labeling sheet excludes wave-1 item_ids; wave-2 α computed on wave-2 rows only. |
| **Test-split firewall.** | Synthetic ⇒ dev only. Fresh-authored may be either, but production rows must dominate test. | `assert_firewall_batch` + `GoldsetItem` model validator + Phase 6 invariants. |
| **D1 + D5 floors apply to the combined ≥ 250-row sheet.** | Wave 1 alone can't satisfy the floors. Wave 2 alone can't either. The combined sheet is the unit-of-assertion. | Assembler invariant; no flag to override at v1 freeze. |

---

## 7. Risks + mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Wave 2 sourcing produces a cell that's still under-floor (e.g. wrong-tool requires high creativity) | medium | Per-cell targets allow ±5 row slack; if a cell falls short, do a wave-2.1 micro-batch targeting just that cell. The fixture/builder/assembler stack supports any number of waves at zero architectural cost. |
| α on wave 2 < 0.8 despite stable protocol | low | We have the grader-bug residue cause analysis from wave 1; if α dips on wave 2, the diff CSV from `compute_goaljudge_stage5_alpha.py --diff` tells us what cluster of disagreements is driving it. EvalGen revise loop available if needed (we explicitly skipped it for wave 1 because R-6 dominated). |
| v0.9 → v1 hash collision (astronomically unlikely but technically possible) | ~0 | `verify_goldset_v1_cutover.py` flags hash-unchanged as a FAIL. Even with identical row content the hash would differ because the row count changed. |
| Stage 6 code starts depending on v0.9-specific fields | medium | The v0.9 contract is explicit about what's *blessed*; the `floor_gap_summary` key is intentionally part of the manifest schema so that Stage 6 code that needs it can read it without trying to ignore it. No fields are v0.9-only. |
| Annotator availability for wave 2 | unknown | This is the binding constraint. Pre-fetch the labeling sheets + evidence bundle the moment the GCP run lands, so annotators can begin within minutes. |

---

## 8. Out of scope for this plan

The following are **deliberately not** part of this plan even though they touch the goldset:

* **Stage 6 calibration code** — separate plan; will land in a `goaljudge_stage6_calibration.plan.md`.
  This plan only ensures Stage 6 has a manifest to consume.
* **GoalJudge rubric changes.** Rubric is locked at `stage4_confirmed`. Any change requires
  a full re-labeling pass on both wave 1 + wave 2 + pilot, which we do not want.
* **D6 telemetry backfill** (`routing_reason`, `model_tier`, `cost_fraction_bins` observed
  distributions). Currently `{}` in the manifest; that's fine — they're informational, not
  load-bearing. Will be populated when D6 telemetry sink lands.
* **Flipping `goal_judge_downgrade_enabled`.** Gated on Stage 6 calibration metrics; not on
  the gold-set existing.

---

## 9. Reuse — do not reinvent

Wave 2 mostly composes existing modules. Concrete reuse list:

* `FreshTask` schema, `validate_fresh_task_set`, `jaccard_similarity` —
  [services/governance/goaljudge_goldset_dataset.py](../../services/governance/goaljudge_goldset_dataset.py).
  No changes needed.
* `select_planning_depth` (D1), `classify_tool_cluster` (D5) — same module. Drives the
  per-cell tally during wave 2 authoring + classifies pilot-style joined rows.
* `project_trajectory_tools` + `--corpus` flag — already in
  [`scripts/build_goaljudge_stage5_full_sheet.py`](../../scripts/build_goaljudge_stage5_full_sheet.py).
  Wave 2's builder is a thin extension.
* `compute_goaljudge_stage5_alpha.py --diff` — same script, same flags. α on the wave-2 subset.
* `apply_adjudication` from [`services/governance/iaa.py`](../../services/governance/iaa.py)
  + `_phase6_backfill_consensus_to_adjudicated.py` — the wave-1 backfill seam works
  identically on wave 2.
* `assemble_goaljudge_goldset.py` — the assembler. Wave-2 invocation differs only by
  *dropping* `--provisional`.
* `verify_goldset_v1_cutover.py` — already written this session.
* `goaljudge-batch` Playwright spec — drives the wave-2 GCP run.

The only new code wave 2 needs is the wave-2-specific fresh task fixture (a data file, not
a module), and arguably a small loop around `build_goaljudge_stage5_combined_sheet.py` if
we want a third wave-aware variant (or we just extend it to "fresh + pilot + wave2"; equal
cost).

---

## 10. Done-ness criteria for this plan

This plan is **DONE** when all of the following are true:

1. ✅ Track 1 — v0.9 ship — already complete this session.
2. ⏸ Track 2 sub-step 5.1 — wave 2 authored + drift-guards green.
3. ⏸ Track 2 sub-step 5.2 — wave 2 GCP run complete + verify script PASS.
4. ⏸ Track 2 sub-step 5.3 — wave 2 labeled + α ≥ 0.8 + adjudicated.
5. ⏸ Track 2 sub-step 5.4 — v1 manifest produced + cutover verifier PASS + gate passes.
6. ⏸ Stage 6 plan exists (separate doc) referencing the v1 manifest hash for calibration.

When 1-6 are green, this plan retires and the next bottleneck moves to Stage 6 calibration.

---

## 11. References

| Doc | Why |
|---|---|
| [Stage 5 goldset master plan](goaljudge_stage5_goldset.plan.md) | Defines the three-tier gate + Stage 6 handoff contract |
| [Tier 3 assembly plan](goaljudge_stage5_tier3_assembly.plan.md) | The 7-phase pipeline this plan extends |
| [v0.9 contract](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_v0_9_contract.md) | CAN/CANNOT lists; v0.9 → v1 transition criteria |
| [Phase 6-B measurement](../IAA/goalJudge/goldset/goaljudge_stage5_phase6b_combined_measurement.md) | How the fresh + pilot merge surfaced the gap |
| [Phase 6-A status](../IAA/goalJudge/goldset/goaljudge_stage5_phase6_status.md) | The three integration-seam issues fixed during Phase 6-A |
| [Round-1 α report](../IAA/goalJudge/goldset/goaljudge_stage5_round1_alpha_report.md) | Why wave-1 α was 0.27 (R-6 grader-bug residue) |
| [Round-1 adjudication](../IAA/goalJudge/goldset/goaljudge_stage5_round1_adjudication.md) | The 22-decision table — gold labels |
| [Tier review report](../reports/goaljudge_stage5_goldset_tier_review.md) | Top-level status across all three tiers |
| [Playwright skill](~/.claude/skills/agentsframework-playwright/SKILL.md) | GCP wave-2 run gotchas + selectors |
| [Labeling protocol](../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md) | Rule 7 + request_approval clauses (post-wave-1) |
| [Authoring guide](../research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md) | Wave 2 fresh-task authoring standards |
