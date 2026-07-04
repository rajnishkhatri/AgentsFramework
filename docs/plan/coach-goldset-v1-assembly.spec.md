# Spec — `coach_goldset_v1` assembly (Task 3.7)

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Related:** [enable-policy spec](coach-goldset-enable-policy.spec.md) FR-G5 (the
canonical *what*) · [parent plan](subject-coach-agent.plan.md) Phase 3 board row 3.7 ·
[rubric-revision spec](coach-rubric-revision.spec.md) (3.6, upstream) ·
GoalJudge precedent: `services/governance/goaljudge_goldset_dataset.py` +
`scripts/assemble_goaljudge_goldset.py`.

---

## 1. Goal

Build the **assembly machinery** for the coach gold set: a `CoachGoldsetItem` row
type and an `assemble_coach_goldset.py` that produces a frozen, hashed
`coach_goldset_v1` manifest — mirroring the GoalJudge gold-set dataset. It gates
the Phase-3 enable-policy cert (3.8). This task delivers the machinery + a
**provisional** manifest seeded from the 22 corrected `cases.jsonl` rows; the real
200–300-row **double-labeled** set (α ≥ 0.80 on `answer_leakage`) is a human coding
pass slotted before 3.8. The machinery must **fail closed** — a provisional or
sub-floor manifest must refuse the cert, never fake a pass.

## 2. Context

FR-G5 (enable-policy spec) already fixes the *what* as EARS. This spec
operationalizes FR-G5 for 3.7 by direct analogy to the GoalJudge precedent (same
`extra="forbid"` discipline, `GoldsetProvenance`/`GoldsetSplit` enums, contamination
firewall, `compute_test_split_hash` SHA-256, and the assembler's `--provisional`
mode). Two coach-specific realities shape it:

- **The only labeled coach data today is the 22-row `cases.jsonl`** (item-enriched,
  FR-13/FR-14 corrected in 3.6). The 292-turn shadow corpus is **raw/uncoded** — it
  feeds the human double-labeling pass, NOT this provisional build (clarify §Q1).
- **Provisional by construction:** 22 < the 200-row floor and there is no human α
  yet, so the manifest is stamped `provisional=true` and the cert (3.8) returns
  `REFUSE_PROVISIONAL` until the human pass lands (clarify §Q2). This is the honest
  state, mirroring GoalJudge's v0.9 provisional manifest.

Never auto-label `answer_leakage` from the judge to reach the row count — the judge
output is exactly what the cert measures; auto-labels would be circular and
contaminate the gold set (rejected in clarify §Q1).

## 3. Functional requirements (EARS)

**Failure paths FIRST (TAP-4).**

- **FR-1 (firewall — mirrors GoalJudge).** IF a row has `provenance=synthetic` and
  `split != dev` THEN the model SHALL raise `ValidationError` at parse time
  (contamination firewall: synthetic never reaches the test split).
- **FR-2 (fail-open ban — FR-G5.2).** IF `answer_leakage` is missing/null on a gold
  row THEN assembly SHALL reject the row (`ValidationError`) — never default to
  `False`.
- **FR-3 (taxonomy gate — FR-G5.3).** IF `failure_mode` (or `leak_channel`) is set
  and not in the frozen taxonomy/enum set THEN the row SHALL be rejected at parse
  time (leak_channel reuses the ADR-0017 soft-coerce-unknown→None only for the
  *judge*; on a GOLD row an unknown value is a hard reject — gold labels are
  authored, not model output).
- **FR-4 (provisional refuse — FR-G6.1 analog).** IF the manifest is `provisional`
  OR row count < 200 OR `human_alpha_answer_leakage` is null THEN the manifest
  SHALL carry `provisional=true` and any downstream cert SHALL be able to return
  `REFUSE_PROVISIONAL` **before** reading any metric.
- **FR-5 (test-split hash — determinism).** THE assembler SHALL compute a SHA-256
  over the canonical-JSON of the sorted-by-`item_id` **test-split** rows and freeze
  it in the manifest as `test_split_hash`; any field change on any test row SHALL
  change the hash (tamper-evidence: a hash mismatch at 3.8 means the test split was
  tuned on).
- **FR-6 (item shape — FR-G5.1/G5.7).** THE `CoachGoldsetItem` SHALL live in
  `services/governance/`, use `extra="forbid"`, and carry: `item_id`, `mode`
  (pre_submit|post_feedback), `question` (the rendered item), `learner_utterance`,
  `coach_reply`, gold `answer_leakage: bool` (REQUIRED), optional `leak_channel`,
  the six pedagogy `*_pass` axes **including `mistake_location_pass`** typed
  **`bool | None`** (None = unconstrained: the fixtures label only the axes each
  case probes; a fabricated bool on an unlabeled axis is an AP-6 violation), optional
  `failure_mode`, `stratum`, `split`, `provenance`, `taxonomy_version`. **Only
  `answer_leakage` is a required gold label** (it is the sole gated class, FR-G6.2);
  the `*_pass` axes are reported telemetry (FR-G5.7) and may be None.
- **FR-7 (leak-class share — FR-G5.4).** WHEN assembling THE assembler SHALL compute
  and record the **leak-class share** (`answer_leakage=true` count / scorable count)
  in the manifest — a measurable, testable value. *(Actual oversampling toward a
  target share is DEFERRED to the real 200–300-row human assembly: a fixed 21-row
  seed with 5 fixed positives has no pool to draw from, so "oversample" is not a
  testable claim now. The target ratio, when it binds, is a CLI/`routing_config`
  number — never baked into a type. For the provisional build, report-only.)*
- **FR-8 (split + freeze — FR-G5.4).** WHEN assembling THE assembler SHALL apply a
  60/40 dev/test split, keep `provenance=synthetic` rows dev-only (FR-1), and emit a
  `CoachGoldsetManifest` `{frozen_at, test_split_hash, row_counts, human_alpha_answer_leakage,
  rubric_version, taxonomy_version, provisional}`. `rubric_version` = `coach_rubric_v1_revised`
  (set at 3.6f); `taxonomy_version` = **`coach_axial_v1`** (the frozen axial taxonomy,
  `docs/evals/eng-coach/coach_axial_coding.md` Draft v1). Version bumps →
  `coach_goldset_v2`, never in-place edits.
- **FR-9 (α gate — FR-G5.5).** WHEN double-labeling completes THE assembler SHALL
  require `human_alpha_answer_leakage ≥ 0.80` (human–human) to clear `provisional`.
  THE α SHALL be computed by **`services.governance.iaa.krippendorff_alpha_nominal`**
  (the repo's canonical IAA — reused by `goaljudge_calibration` +
  `memory_extractor_calibration`; NEVER reimplemented). That function returns
  **`NaN`** when undecidable (empty, or no item with ≥2 raters); the coach wrapper
  SHALL map `NaN → None` so the manifest's `float | None` contract holds and AP-6 is
  satisfied (`None`, never a fabricated `0.0`). *(Machinery present now; the human
  labels land later — this task supplies the gate, not the labels.)*
- **FR-10 (provisional seed — clarify §Q1).** THE assembler SHALL accept the 22
  corrected `cases.jsonl` rows as the provisional single-label seed, mapping each
  case into a `CoachGoldsetItem`: `expected.answer_leakage`→`answer_leakage`,
  `expected.leak_channel`→`leak_channel`, `question`→`question`, and the six
  `*_pass` axes DERIVED from the fixture's `axis_fails`/`axis_passes` lists
  (`axis_fails` ⇒ `False`, `axis_passes` ⇒ `True`, **an axis in neither ⇒ `None`**
  — never a fabricated bool). A case with `expected.scorable=false` (e.g. the
  truncated I1) is excluded from the gold set. It produces a **local**
  `coach_goldset_v1` JSON artifact (rows + manifest) — NOT a Langfuse push
  (clarify §Q3; the dataset-name reservation `coach_goldset_v1` holds for the later
  creds-gated push).
- **FR-11 (persistence — clarify §Q3).** THE artifact SHALL be written to a local
  path under the repo (mirroring the GoalJudge assembler's local output); no network
  / Langfuse call on this path.

## 4. Data model / contracts

- **`CoachGoldsetItem`** (`services/governance/coach_goldset_dataset.py`, new) —
  `BaseModel`, `extra="forbid"`. Reuses `GoldsetSplit`/`GoldsetProvenance` enums
  from `goaljudge_goldset_dataset.py` if they are import-safe within `services/`
  (same layer — no cross-layer violation), else defines coach-local mirrors. Gold
  `answer_leakage` is REQUIRED (FR-2). `leak_channel` reuses the `LeakChannel`
  Literal from `components/schemas.py`? — **NO**: `components/` is a higher layer
  than `services/` (Invariant #7 forbids services→components). The 5-value channel
  set is mirrored as a `services/`-local Literal (drift-sensed against the enum, cf.
  ADR-0017 F2 FR-12 pattern).
- **`CoachGoldsetManifest`** — the FR-8 field set. `provisional: bool`,
  `human_alpha_answer_leakage: float | None` (None until the human pass).
- **No `trust/` type, no re-signing.** `services/governance/` only.
- **`assemble_coach_goldset.py`** (`scripts/`, new) — CLI mirroring
  `assemble_goaljudge_goldset.py`: `--provisional` (skip the 200-row + α floors,
  stamp `provisional=true`), `--frozen-at`, `--out`.

## 5. Invariants & security boundaries

- **Invariant #7 (services MUST NOT import components).** The gold-set type is in
  `services/governance/`; it MUST NOT import `components/schemas.py`. The
  `LeakChannel` values are mirrored locally, not imported upward. **This is the one
  invariant this spec must actively respect** — the GoalJudge precedent already
  lives in `services/` so the pattern is proven.
- **No trust re-sign** — not a `trust/` type.
- **No live LLM anywhere** — assembly is pure file I/O over authored labels; the
  provisional path makes no judge call (that would be the circular auto-label
  rejected in §2). Deterministic → runs in `make check`.
- **Contamination firewall (FR-1)** is a security boundary: synthetic data must
  never enter the test split that certifies the gate.

## 6. Edge cases

- **Empty / all-dev corpus:** test split empty ⇒ `test_split_hash` over zero rows is
  a defined constant, but row_counts.test=0 ⇒ `provisional=true` (can't certify on
  an empty test split).
- **`answer_leakage=null`** (a raw corpus row leaking in): hard reject (FR-2), never
  coerce.
- **`leak_channel` set while `answer_leakage=false`** on a gold row: reject
  (self-contradiction) — stricter than the judge's prose-only rule, because gold
  labels are authored.
- **Undecidable α** (single labeler, or degenerate agreement denominator): `None`,
  manifest stays provisional (AP-6).
- **Duplicate `item_id`:** reject at assembly (a re-seed must not last-wins).

## 7. Non-functional requirements

- **No new dependency** (Pydantic + stdlib `hashlib`/`json`, already present).
- **Deterministic:** same rows + same `--frozen-at` ⇒ byte-identical manifest +
  hash (L1 exact-assert on the hash).
- **Reversibility:** the artifact is a local JSON file; the type is additive.
  Version bumps are new datasets, never in-place edits (FR-8).
- **Live path off CI:** the (later) Langfuse push is creds-gated + manual; this
  task's provisional build is fully offline.

## 8. Test plan

Failure-path first. All L1 (deterministic, in `make check`) — no live LLM.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `tests/services/governance/test_coach_goldset_dataset.py::test_synthetic_in_test_split_rejected` | L1 | yes |
| FR-2 | `::test_missing_answer_leakage_rejected` | L1 | yes |
| FR-3 | `::test_unknown_leak_channel_rejected` · `::test_unknown_failure_mode_rejected` | L1 | yes |
| FR-4 | `::test_provisional_manifest_flagged` (row<200 or α null ⇒ provisional=true) | L1 | yes |
| FR-5 | `::test_test_split_hash_is_deterministic` · `::test_hash_changes_on_test_row_edit` | L1 | yes |
| FR-6 | `::test_coach_goldset_item_extra_forbid` · `::test_mistake_location_pass_present` | L1 | yes |
| FR-7 | `::test_leak_class_share_recorded` (share = leak/scorable, exact value) | L1 | yes |
| FR-8 | `::test_manifest_field_set` · `::test_rubric_version_is_v1_revised` · `::test_taxonomy_version_is_axial_v1` | L1 | yes |
| FR-9 | `::test_alpha_below_080_stays_provisional` · `::test_undecidable_alpha_returns_none` (NaN→None) · `::test_alpha_uses_iaa_krippendorff` (reuse, not reimpl) | L1 | yes |
| FR-10 | `tests/scripts/test_assemble_coach_goldset.py::test_seeds_from_cases_jsonl` | L1 | yes |
| FR-10 | `::test_axis_pass_derived_fails_false_passes_true_unnamed_none` | L1 | yes |
| FR-10 | `::test_unscorable_case_excluded` (I1 truncated ⇒ not in gold set) | L1 | yes |
| FR-11 | `::test_writes_local_artifact_no_network` | L1 | yes |

**Acceptance gate:** Task 3.7 is DONE when the assembler produces a **provisional**
`coach_goldset_v1` artifact from the corrected `cases.jsonl` — **21 scorable gold
rows** (22 cases − I1 unscorable) — with a frozen `test_split_hash`,
`rubric_version=coach_rubric_v1_revised`, `provisional=true`,
`human_alpha_answer_leakage=null`; all L1 tests green (seen to fail first); the
firewall + fail-open-ban + taxonomy-gate reject paths proven. The 200-row + α
gates are present and **binding-when-invoked**, satisfied later by the human pass.

## 9. Definition of Done

- [ ] FR-1..FR-11 implemented; each L1 test seen to fail first, then pass.
- [ ] `make check` green; `pytest tests/architecture/ -q` green (Invariant #7:
      no `services/`→`components/` import).
- [ ] Provisional `coach_goldset_v1` artifact committed (rows + manifest) with the
      4-field honesty stamp (provisional/α-null/row<200/rubric_version).
- [ ] Assembler `--provisional` mode mirrors the GoalJudge precedent.
- [ ] Parent ledger row 3.7 → DONE (provisional); the human double-labeling +
      α ≥ 0.80 recorded as the explicit remaining gate before 3.8.
- [ ] Actual command output pasted (assembler run + test run), not summarized.
