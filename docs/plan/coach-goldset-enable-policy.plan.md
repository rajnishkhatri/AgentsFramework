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
| 3.1 Environment posture checker | ⬜ | Spec FR-G1 (EvalRecord-only; C9) |
| 3.2 Coding-sample export + holdout ledger | ⬜ | Spec FR-G2 |
| 3.3–3.4 Human open + axial coding | ⬜ **HUMAN** | Spec FR-G3 |
| 3.5 Optional strata gap-fill | ⬜ OPTIONAL | Spec FR-G7 |
| 3.6 Rubric revision | ⬜ | Spec FR-G4 |
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
