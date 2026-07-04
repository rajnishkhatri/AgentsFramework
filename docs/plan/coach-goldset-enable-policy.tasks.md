# Tasks — Coach gold set + enable-policy cert (Phase 3)

Derived from [coach-goldset-enable-policy.spec.md](coach-goldset-enable-policy.spec.md) +
[coach-goldset-enable-policy.plan.md](coach-goldset-enable-policy.plan.md).

**Legend:** ‖ = parallelizable after dependency column satisfied · **HUMAN** = process gate.

---

| # | Task | Files | Verifies | Depends |
|---|---|---|---|---|
| **3.1** | **Posture checker** — confound (manifest mode mismatch, missing `coach_mode` carrier), `partial_context`, counts-only report | `meta/coach_corpus_posture.py`, `tests/meta/test_coach_corpus_posture.py` | FR-G1.1–G1.4 | 3.0 ✅ |
| **3.2** ‖ | **Coding-sample export** — deterministic holdout ledger + open-coder JSONL (`trace_id`/`prompt`/`final_answer` map); confounds excluded; shortfall report | `scripts/export_coach_coding_sample.py`, `tests/scripts/test_export_coach_coding_sample.py` | FR-G2.1–G2.5 | 3.1 |
| **3.2b** ‖ | **Run posture + export on batch-2** — paste posture counts + per-mode shortfall; commit `cache/coach_shadow/batch2_coding_sample.jsonl` + `holdout_ledger.json` | batch manifest + harvest input | DoD evidence; confirms ≥100/mode **coding-eligible** | 3.1, 3.2 |
| **3.3a** ‖py | **Cases builder (thin adapter)** — **reuse** `export_coach_coding_sample.build_coder_rows` (posture-filter + manifest join + C11 map) over merged EvalRecords → seed-select ≥100/mode → mode-contiguous `cases.json` array. **Fail-closed** on sub-floor mode; confounds/refused already excluded by the reused draw. **Do not rebuild the join** (Stage-4: answer is in `logs/evals.log`, not `outcomes.jsonl`). Failure-first tests. | `scripts/build_coach_open_coding_cases.py`, `tests/scripts/test_build_coach_open_coding_cases.py` | FR-G3.1.1–.3, .5–.7 | 3.2, 3.2b |
| **3.3b** ‖py | **Coded verifier** — flag rows with empty `open_codes` (per-mode uncoded count + `trace_id`s). Failure-first. | `scripts/verify_coded_open_codes.py`, `tests/scripts/test_verify_coded_open_codes.py` | FR-G3.1.4 | 3.1 |
| **3.3c** ‖py | **Inventory generator** — `coded.jsonl` → CSV with GoalJudge columns (`code,short_definition,source_doc,first_seen_case,alias_note,example,example_ref`). | `scripts/build_coach_open_code_inventory.py`, `tests/scripts/test_build_coach_open_code_inventory.py` | FR-G3.1.9 | 3.1 |
| **3.3d** ‖py | **Dataset export wrapper** — coach-specific args over skill exporter; dataset `coach-phase3-open-coding`; `uuid5(trace_id)` idempotent; **dry-run default**. Unit test dry-run only (no network). | `scripts/export_coach_open_coding_to_dataset.py`, `tests/scripts/test_export_open_coding_dataset.py` | FR-G3.1.11–.12 | 3.3a |
| **3.3e** | **HUMAN — open coding** — copy coder→`$WORK`, run 3.3a builder, serve over http, code ≥100 turns/mode, declare saturation (~20-trace no-new-code tail per mode) | coder session + `coded.jsonl` (verified by 3.3b) | FR-G3.1 (human), .8 | 3.3a, 3.3b |
| **3.3f** | **HUMAN — Stage-1 artifacts** — author `coach_phase2_open_coding.md` (method + **per-mode saturation log** + freq table + insights); generate inventory CSV (3.3c); Langfuse dry-run→`--write` (3.3d) | `docs/research/coach_phase2_open_coding.md`, `coach_step1_open_code_inventory.csv` | FR-G3.1.8–.12 | 3.3e, 3.3c, 3.3d |
| **3.4** | **HUMAN — axial taxonomy** — 5–6 categories, IAA ≥ 0.80 | `docs/research/coach_phase3_axial_coding.md`, `coach_evaluation_pipeline_open_axial_coding_rubric.md` | FR-G3.2–G3.3 | 3.3f |
| **3.5** | **OPTIONAL — strata gap-fill** — targeted synthetic batch if taxonomy gaps | `scripts/build_coach_shadow_corpus.py` (quota flags only if needed) | FR-G7.1–G7.2 | 3.4 |
| **3.6** ‖py | **Rubric revision** — REVISED headers; refusal-aware grader; `rule-naming-as-leak` criterion | `prompts/subject_coach_grader_judge.j2`, `prompts/subject_coach_pedagogy_judge.j2`, `tests/components/test_subject_coach_judge_prompts.py` | FR-G4.1–G4.3 | 3.4 |
| **3.6b** ‖py | **Taxonomy frozen-set artifact** — parse axial doc → `COACH_FAILURE_MODES` JSON consumed by goldset validator | `docs/research/coach_failure_modes_v1.json` (or inline in dataset module) | FR-G5.3 | 3.4 |
| **3.7a** ‖py | **`CoachGoldsetItem` + firewall + taxonomy validator** | `services/governance/coach_goldset_dataset.py`, `tests/services/test_coach_goldset_dataset.py` | FR-G5.1–G5.3, G5.7 | 3.6b |
| **3.7b** ‖py | **Assembly script** — manifest join (FR-G5.6), 200–300 rows, 60/40 split, holdout seed, test hash, Langfuse upsert | `scripts/assemble_coach_goldset.py`, `tests/services/test_coach_goldset_dataset.py` | FR-G5.4–G5.6 | 3.7a, 3.6, 3.2b |
| **3.7c** | **HUMAN — double-label + adjudicate** — α ≥ 0.80 on `answer_leakage` | `docs/IAA/coach/goldset/` | FR-G5.5 | 3.7b |
| **3.8a** ‖py | **`evaluate_coach_enable_gates`** — thresholds + verdict enum; positive class = leak; reuse metric fns | `services/governance/coach_calibration.py`, `tests/services/test_coach_calibration.py` | FR-G6.1–G6.3, G6.5–G6.7 | 3.7a |
| **3.8b** ‖py | **Replay harness** — judge replay on frozen test split → cert JSON | `scripts/run_coach_calibration.py` | FR-G6.2–G6.4 | 3.8a, 3.7c |
| **3.9** | **Phase-3 exit** — paste cert report; update parent plan ledger; code review; `make check` | docs + review | DoD §10 | 3.8b |

---

## Checklist verdict (Stage 3 — revised)

| Criterion | Verdict |
|---|---|
| Every automated FR has a named test | ✅ §8 closed (Stage-4 cross-check added FR-G4.2, G4.3, G5.5, G5.7, G6.3, G6.7) |
| Human gates explicit | ✅ 3.3e/3.3f, 3.4, 3.7c (3.3a–d are ‖py tooling) |
| Holdout disjointness measurable | ✅ was **missing** in v1; fixed FR-G2.1–G2.2 + tests |
| Coded-vs-raw gate enforceable | ✅ FR-G2.5 shortfall (raw 146/mode ≠ coded gate) |
| Taxonomy → validator dependency | ✅ 3.6b added (was implicit) |
| Cert claim pinned by artifact | ✅ 3.9 pasted `run_coach_calibration.py` output |

## Parallelization notes

**3.3a–3.3d** (the ‖py tooling) can all proceed in parallel after **3.2b** (3.3b/3.3c need
only 3.1; 3.3d needs 3.3a). **3.3e** (human coding) waits on 3.3a+3.3b; **3.3f** (artifacts)
waits on 3.3e+3.3c+3.3d. **3.4** waits on **3.3f**.
After **3.4**: **3.6**, **3.6b**, and **3.8a** can proceed in parallel.
**3.7b** waits on **3.7a + 3.6 + 3.2b** (holdout ledger seeds test-split candidacy — FR-G5.4).
**3.8b** waits on adjudicated sheet (**3.7c**).

## First executable increment

**3.1 → 3.2 → 3.2b** — no human gate; unblocks coding while human schedules 3.3.

**3.2b acceptance:** posture report pasted showing ≥100 coding-eligible rows/mode (or explicit shortfall + remediation plan before 3.3).
