---
type: plan
title: 'Coach gold set + enable-policy cert — Implementation Plan (Phase 3)'
status: 'Revised — 2026-07-03 (critical review pass + Stage-4 cross-check fixes; derived from coach-goldset-enable-policy.spec.md)'
authored: 2026-07-03
---

# Coach gold set + enable-policy cert — Implementation Plan

## Status ledger

| Item | Status | Evidence |
|---|---|---|
| 3.0 Raw corpus volume (≥100/mode raw) | ✅ DONE | Batch 2: 292 turns, 146/mode; PR #124 |
| 3.1 Environment posture checker | ✅ DONE | `meta/coach_corpus_posture.py` + tests; PR #125 |
| 3.2 Coding-sample export + holdout ledger | ✅ DONE | `scripts/export_coach_coding_sample.py` + holdout ledger; PR #125 |
| 3.3 Human open coding (Stage-1) | ✅ DONE | tooling 3.3a–d green (PR #125); **HUMAN gate met**: `docs/evals/eng-coach/coded.jsonl` = 200 rows, 100/mode, all `open_codes` populated; `coach_phase2_open_coding.md` + `coach_step1_open_code_inventory.csv` |
| 3.4 Human axial coding (Stage-2) | ✅ DONE | `docs/evals/eng-coach/coach_axial_coding.md` (categories A1–A4/B1/C1/D1/E1 + minimal pairs) + a selective-coding pass (`coach_selective_coding.md`) + `judge_test_cases.jsonl` |
| Task 3.5 (judge-validation harness, feeds 3.6) | ✅ DONE | separate bundle; Opus 4.8 baseline TPR=0.000/TNR=1.000; 3.5f miss-list; PR #126 |
| 3.5 Optional strata gap-fill | ⬜ OPTIONAL | Spec FR-G7 |
| 3.6 Rubric revision | ⬜ **NEXT** (spec in progress) | Spec FR-G4; grounded by 3.4 codes + 3.5f miss-list |
| 3.6b Taxonomy frozen-set artifact | ⬜ | Spec FR-G5.3 (blocks 3.7a validator) |
| 3.7 `coach_goldset_v1` assembly | ⬜ | Spec FR-G5 |
| 3.8 `evaluate_coach_enable_gates` | ⬜ | Spec FR-G6 |
| 3.9 Cert exit → ENABLE/REFUSE | ⬜ | Human accepts report; unlocks Phase 5 |

**Spec:** [coach-goldset-enable-policy.spec.md](coach-goldset-enable-policy.spec.md)

---

## Architecture

Mirror the GoalJudge Stage 5→6 vertical slice with coach-specific fields. **Posture reads
EvalRecords only** — not blackbox traces (C9). Eval capture truncates at 200/500 chars (C12);
gold-set assembly joins batch `manifest.json` for full text.

```
logs/evals.log + batch manifest.json
        │
        ▼
meta/coach_corpus_posture.py          ← FR-G1 (coach_mode, manifest mode, partial_context)
        │
        ▼
scripts/export_coach_coding_sample.py ← FR-G2 coder JSONL + holdout_ledger.json
        │
        ▼
docs/skills/.../serve_open_coder.py   ← FR-G3 human open/axial coding UI
        │
        ▼
docs/research/coach_* artifacts       ← FR-G3 + 3.6b taxonomy JSON
        │
        ▼
prompts/subject_coach_*_judge.j2      ← FR-G4 REVISED rubrics
        │
        ▼
services/governance/coach_goldset_dataset.py   ← FR-G5 CoachGoldsetItem + firewall
scripts/assemble_coach_goldset.py              ← FR-G5 manifest join + Langfuse upsert
        │
        ▼
services/governance/coach_calibration.py       ← FR-G6 pure metrics + evaluate_coach_enable_gates
scripts/run_coach_calibration.py               ← FR-G6 on-demand replay harness
```

**Reuse (do not rebuild):**

| Existing | Reused for |
|---|---|
| `meta/subject_coach_corpus_harvest.py` | Corpus rows + raw gate counts |
| `meta/subject_coach_judge_sampler.mode_of` | Mode derivation (fail-closed) |
| `components/coach_context.py` (`coach_context_contract`) | Carrier semantics (orchestration stamps `coach_mode`) |
| `services/governance/goaljudge_goldset_dataset.py` | Firewall, manifest, Langfuse client protocol |
| `services/governance/goaljudge_calibration.py` | Metric fns; **positive class inverts** (leak=True) |
| `services/governance/iaa.py` | Human α on `answer_leakage` |
| `scripts/assemble_goaljudge_goldset.py` | Assembly pipeline shape |
| `docs/skills/agentsframework-open-coding/` | Human coding UI (`serve_open_coder.py`; export adapter is coach-specific) |
| `scripts/build_coach_shadow_corpus.py` | Batch manifest for mode/stratum/question join |

**No ⚠️ Ask-first triggers** fire for this plan (no new pyproject dep, no trust-kernel
change, no new graph node, no new horizontal service abstraction beyond the GoalJudge
sibling modules in `services/governance/`).

---

## TDD binding

| Artifact | Layer | Failure-first test |
|---|---|---|
| Posture checker | L1 | manifest mode mismatch → confound BEFORE eligible path |
| Holdout ledger | L1 | coding ∩ holdout = ∅ BEFORE happy export |
| Coder export | L1 | missing `trace_id` field map rejected BEFORE happy export |
| Coded-entry gate | L1 | shortfall report when <100/mode AFTER posture |
| `CoachGoldsetItem` | L1 | synthetic+test firewall BEFORE valid row |
| Manifest join | L1 | truncated harvest row gets full text BEFORE assembly pass |
| `evaluate_coach_enable_gates` | L1 | `REFUSE_PROVISIONAL` BEFORE pass path |
| Revised rubrics | L1 | header must say REVISED; refusal-aware criterion present |
| Orphan criteria | L1 | rubric criterion unmapped to taxonomy → rejected (FR-G4.2) |
| Judge flags default OFF | L1 | `COACH_*_ENABLED=false` until ENABLE verdict (FR-G4.3) |
| Manifest α gate | L1 | manifest refused without `human_alpha_answer_leakage ≥ 0.80` (FR-G5.5) |
| Pedagogy axes | L1 | `mistake_location_pass` field present on `CoachGoldsetItem` (FR-G5.7) |
| Augmenting gates | L1 | precision / false-action / flip evaluated individually (FR-G6.3) |
| κ<0.6 unreliable | L1 | non-gating axis below 0.6 marked unreliable telemetry (FR-G6.7) |
| Human coding | L3 | saturation + IAA worksheet (not CI) |

---

## Task 3.3 — Human open coding (Stage-1)

Executable expansion of FR-G3.1 (folded into the spec 2026-07-03). Turns the merged
coding-eligible pool into a served coding surface, captures **human** first-pass codes,
and emits the Stage-1 artifacts 3.4 consumes.

### File-level touchpoints

| File | New/Reuse | Role | Spec FR |
|---|---|---|---|
| `scripts/build_coach_open_coding_cases.py` | **new (thin adapter)** | **Reuse `export_coach_coding_sample.build_coder_rows`** (already does posture-filter → `coding_eligible` + manifest full-text join + C11 field map `trace_id←task_id, prompt←learner_utterance, final_answer←coach_reply`) over the **merged** EvalRecords; then seed-select ≥100/mode, order mode-contiguous, and emit the skill's `cases.json` array. Fail-closed on sub-floor mode. **Do NOT re-derive the join** (Stage-4: `outcomes.jsonl` has no `trace_id`/answer; the answer lives in `logs/evals.log` EvalRecords, which `build_coder_rows` already reads). | G3.1.1–.3, .5–.7 |
| `scripts/verify_coded_open_codes.py` | **new** | Read `coded.jsonl`; report per-mode uncoded (`open_codes==[]`) count + `trace_id`s. | G3.1.4 |
| `scripts/build_coach_open_code_inventory.py` | **new** | Roll `coded.jsonl` → `coach_step1_open_code_inventory.csv` (GoalJudge columns). | G3.1.9 |
| `scripts/export_coach_open_coding_to_dataset.py` | **new (thin)** | Coach-specific arg wrapper over the skill's `export_coded_to_dataset.py`; dataset `coach-phase3-open-coding`, dry-run default. | G3.1.11–.12 |
| `.claude/skills/agentsframework-open-coding/scripts/serve_open_coder.py` | **reuse** | Serve coder over http (Step 2). | — |
| `.claude/skills/agentsframework-open-coding/scripts/export_coded_to_dataset.py` | **reuse** | Underlying idempotent Langfuse upsert. | G3.1.11 |
| `.claude/skills/agentsframework-open-coding/assets/coder.html` | **reuse (copy)** | Coding surface into `$WORK`. | — |
| `scripts/export_coach_coding_sample.py` | **reuse** | `build_coder_rows` (posture-filter + manifest join + C11 map) — the join engine 3.3a wraps, not rebuilds. | G3.1.1–.3, .5 |
| `meta/coach_corpus_posture.py` | **reuse (transitive)** | `coding_eligible`/`confound` classification, via `build_coder_rows` (no re-derive). | G3.1.1 |
| `docs/research/coach_phase2_open_coding.md` | **new (human)** | Method + per-mode saturation log + freq table + insights. | G3.1.8, .10 |
| `docs/research/coach_step1_open_code_inventory.csv` | **new (generated)** | Distinct-code inventory. | G3.1.9 |
| `tests/scripts/test_build_coach_open_coding_cases.py` | **new** | Failure-first: sub-floor, unjoined, confound-excluded, min/keys, contiguous, seed. | G3.1.1–.7 |
| `tests/scripts/test_verify_coded_open_codes.py` | **new** | Failure-first: empty-`open_codes` flagged. | G3.1.4 |
| `tests/scripts/test_build_coach_open_code_inventory.py` | **new** | CSV columns = GoalJudge parity. | G3.1.9 |
| `tests/scripts/test_export_open_coding_dataset.py` | **new** | Item shape + `uuid5` idempotency + dry-run-default (no network). | G3.1.11–.12 |

### Build order (dependency-ordered)

1. `build_coach_open_coding_cases.py` + tests (red→green) — failure paths first (G3.1.2/.3/.1).
2. `verify_coded_open_codes.py` + test.
3. `build_coach_open_code_inventory.py` + test.
4. `export_coach_open_coding_to_dataset.py` + test (dry-run unit-tested; no live Langfuse).
5. **Serve + human codes** (HUMAN): copy coder into `$WORK=cache/open_coding/coach-phase3-3.3`, run `cases.json` builder, serve, code ≥100/mode, declare saturation.
6. Generate inventory CSV; author `coach_phase2_open_coding.md` (with saturation log).
7. Langfuse dry-run → eyeball → `--write`.
8. `make check`; thread `index.md` + `log.md`; Stage-7 code review over the 3.3 diff.

### Invariant / ADR check (Stage-4 local)

- **Invariant #8** — the four new scripts live in `scripts/` and import `meta.coach_corpus_posture` (which is meta, not orchestration) + stdlib + the skill exporter; none import `orchestration`/`langgraph`/`langchain`. Held.
- **No ADR trigger** — build/verify scripts of the same class as the dozen existing `build_coach_*`/`build_goaljudge_*` scripts; coder + exporter + `langfuse_dataset_client.py` pre-exist; **no new pyproject dep, no service, no node, no abstraction.**
- **No live LLM in CI** — all four scripts operate on harvested `outcomes.jsonl`; the exporter's only network path is the `--write` Langfuse upsert, off the CI hot path and dry-run by default; tests offline.

---

## Constitution cross-check (Stage 4)

| Check | Result |
|---|---|
| Spec ↔ plan FR coverage | All FR-G1..G7 mapped to tasks 3.1–3.9 (+ 3.6b) |
| Plan ↔ tasks 1:1 verification | Each task cites spec FR + named test path |
| Every automated FR has a named test | **Fixed (Stage-4)** — 6 missing tests added (FR-G4.2, G4.3, G5.5, G5.7, G6.3, G6.7) |
| Task 3.7b test file | **Fixed (Stage-4)** — `tests/services/test_coach_goldset_dataset.py` listed |
| Task 3.7b → 3.2b dependency | **Fixed (Stage-4)** — holdout ledger seeds test-split candidacy (FR-G5.4) |
| Invariants #1–#8 | Held (see spec §5) |
| ADR-0008 cond#1 | This plan is the closure path |
| Live LLM in CI | None — cert replay on-demand only |
| Referenced files exist | GoalJudge precedents + harvest verified; coach modules are planned creates |
| Eval-log vs trace posture | **Fixed** — C9; no false dependency on blackbox join |
| Open-coder wire shape | **Fixed** — C11 field map in FR-G2.3 |

**Baseline gate:** `make check` + `pytest tests/architecture/ -q` green before task 3.1 starts.

---

## Verification

- Per task: red-first tests per spec §8; watch fail before implement.
- Phase exit (3.9): paste cert report output (gate table + verdict); update parent plan ledger.
- Stage-7 review: code-review skill over Phase-3 diff before declaring 3.9 complete.
