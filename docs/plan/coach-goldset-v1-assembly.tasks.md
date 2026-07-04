# Tasks — `coach_goldset_v1` assembly (Task 3.7)

**Spec:** [coach-goldset-v1-assembly.spec.md](coach-goldset-v1-assembly.spec.md) ·
**Plan:** [coach-goldset-v1-assembly.plan.md](coach-goldset-v1-assembly.plan.md)

Atomic, file-level, dependency-marked, 1:1 to the spec FRs. Failure-path
(rejection) tasks precede happy-path (TAP-4). Red/green TDD throughout — every
test seen to fail first. Legend: **[dep: …]** must precede · **‖** parallel.

---

## 3.7a — `CoachGoldsetItem` type + reject paths [no dep] — Stage A
`services/governance/coach_goldset_dataset.py` (new). Define the row type and its
three reject validators. **Failure-path first.**
- **3.7a-1 (FR-6)** Define `CoachGoldsetItem(BaseModel, extra="forbid")` with the
  FR-6 field set; the six `*_pass` axes (incl. `mistake_location_pass`) typed
  **`bool | None`** (None = unconstrained — the fixtures label only probed axes;
  AP-6 forbids a fabricated bool). Only `answer_leakage` is a required gold label.
  Reuse `GoldsetSplit`/`GoldsetProvenance` from `goaljudge_goldset_dataset.py`;
  mirror `LeakChannel` values LOCALLY (no `components/` import). Test
  `::test_coach_goldset_item_extra_forbid`, `::test_mistake_location_pass_present`,
  `::test_pass_axes_accept_none`.
- **3.7a-2 (FR-1)** Red→green: `model_validator` firewall — `provenance=synthetic` +
  `split!=dev` ⇒ `ValidationError`. `::test_synthetic_in_test_split_rejected`.
- **3.7a-3 (FR-2)** Red→green: `answer_leakage` REQUIRED — missing/null ⇒
  `ValidationError`, never default False. `::test_missing_answer_leakage_rejected`.
- **3.7a-4 (FR-3)** Red→green: `field_validator` — unknown `leak_channel` OR
  `failure_mode` (not in frozen set) ⇒ reject; AND `leak_channel` set while
  `answer_leakage=false` ⇒ reject (gold rows are authored, stricter than the judge).
  `::test_unknown_leak_channel_rejected`, `::test_unknown_failure_mode_rejected`,
  `::test_channel_on_false_leak_rejected`.
- **Pass:** 6 reject/shape tests green; `pytest tests/architecture/ -q` green (NO
  `services/`→`components/` import — Invariant #7).
- **Fail if:** any `from components` appears; `answer_leakage` gets a default;
  `extra="forbid"` omitted.

## 3.7b — hash + manifest + provisional/α [dep: 3.7a] — Stage A
Same module: the freeze + honesty machinery.
- **3.7b-1 (FR-5)** `compute_test_split_hash` (SHA-256 over sorted-by-`item_id`
  canonical-JSON of TEST rows; copy the GoalJudge shape). Red→green:
  `::test_test_split_hash_is_deterministic`, `::test_hash_changes_on_test_row_edit`.
- **3.7b-2 (FR-9)** `alpha_answer_leakage(labels_a, labels_b) -> float | None` —
  **calls `services.governance.iaa.krippendorff_alpha_nominal`** (reuse, never
  reimplement) and maps its `NaN` (undecidable: empty / no item with ≥2 raters) →
  `None` (AP-6). Red→green: `::test_undecidable_alpha_returns_none`,
  `::test_alpha_below_080_stays_provisional`, `::test_alpha_uses_iaa_krippendorff`.
- **3.7b-3 (FR-4, FR-7, FR-8)** `build_coach_goldset_manifest(rows, *, frozen_at,
  rubric_version, provisional)` → `CoachGoldsetManifest{frozen_at, test_split_hash,
  row_counts, human_alpha_answer_leakage, rubric_version, taxonomy_version,
  provisional}`; record leak-class share (FR-7, report-only); `rubric_version`
  default `coach_rubric_v1_revised`, `taxonomy_version` default `coach_axial_v1`;
  stamp `provisional=true` when rows<200 OR α null OR `--provisional` (FR-4).
  Red→green: `::test_provisional_manifest_flagged`, `::test_manifest_field_set`,
  `::test_rubric_version_is_v1_revised`, `::test_taxonomy_version_is_axial_v1`,
  `::test_leak_class_share_recorded`.
- **Pass:** 8 tests green; hash is byte-stable for fixed input; manifest carries all
  8 fields; provisional stamp fires on the N=22 case.
- **Fail if:** α returns `0.0` when undecidable; hash insensitive to a test-row edit;
  a sub-200 set produces `provisional=false`.

## 3.7c — assembler CLI + seed from cases.jsonl [dep: 3.7a, 3.7b] — Stage B
`scripts/assemble_coach_goldset.py` (new). Thin CLI mirroring
`assemble_goaljudge_goldset.py`.
- **3.7c-1 (FR-10)** Map the corrected `cases.jsonl` rows → `CoachGoldsetItem`s:
  `answer_leakage`/`leak_channel`/`question` direct; the six `*_pass` DERIVED from
  `axis_fails`(⇒False)/`axis_passes`(⇒True)/unnamed(⇒None); `scorable=false` rows
  EXCLUDED (I1 truncated); provenance=synthetic ⇒ dev. Red→green:
  `::test_seeds_from_cases_jsonl`,
  `::test_axis_pass_derived_fails_false_passes_true_unnamed_none`,
  `::test_unscorable_case_excluded`.
- **3.7c-2 (FR-11)** CLI: `--cases`/`--out`/`--frozen-at`/`--provisional`/
  `--rubric-version` (default `coach_rubric_v1_revised`); write local JSON (rows +
  manifest); NO network. Non-zero exit on any firewall/parse violation (never write
  a bad artifact). Red→green: `::test_writes_local_artifact_no_network` (inject a
  no-op client like the GoalJudge test).
- **Pass:** both tests green; assembler runs end-to-end on cases.jsonl offline.
- **Fail if:** any network/Langfuse call on this path; a violation still writes an
  artifact; the answer key from post_feedback rows contaminates a pre_submit item.

## 3.7d — produce + commit the provisional artifact [dep: 3.7c] — Stage C
- **3.7d-1** Run: `.venv/bin/python -m scripts.assemble_coach_goldset --provisional
  --frozen-at <ts> --out tests/fixtures/coach_goldset/coach_goldset_v1.json`. Paste
  the output.
- **3.7d-2** Commit the artifact — assert it carries `provisional=true`,
  `human_alpha_answer_leakage=null`, `row_counts` summing to 22,
  `rubric_version=coach_rubric_v1_revised`, a frozen `test_split_hash`.
- **Pass:** `make check` green; artifact committed with the 4-field honesty stamp.
- **Fail if:** the committed artifact reads cert-ready (provisional=false or α set).

## 3.7e — close-out [dep: 3.7d]
- Ledger row 3.7 → DONE (provisional); record the remaining human gate (double-label
  + α ≥ 0.80 on `answer_leakage`) as the explicit blocker before 3.8.
- Small non-obvious choices → `decisions.md` (e.g. the local-`LeakChannel`-mirror
  rationale if not already covered by ADR-0017 FR-12).
- **Pass:** ledger updated; 3.8 entry gate names the human-α dependency.

---

## Dependency graph

```
3.7a ─▶ 3.7b ─▶ 3.7c ─▶ 3.7d ─▶ 3.7e
```
Linear: the type + validators (3.7a) underpin the hash/manifest (3.7b), which the
assembler (3.7c) calls, which produces the artifact (3.7d), which closes out (3.7e).
No parallelism — each stage's output is the next stage's input.

## Out of scope

- Human double-labeling + real α (gates 3.8, not 3.7).
- Langfuse push of `coach_goldset_v1` (creds-gated, later).
- `evaluate_coach_enable_gates` cert (Task 3.8).
