# Stage 4 A2 Human IAA — Results (G5)

> **Gate:** Cohen's κ ≥ 0.8 on binary `a2_fail` across two human annotators  
> **Status:** **CLOSED — G5 PASS** (κ = 1.0 on the gate-eligible set)  
> **Instrument:** [`README.md`](README.md)

---

## Progress

| Phase | Status | Document |
|---|---|---|
| Walkthrough observations (8/8) | Complete | [`goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md`](goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md) |
| Annotator 1 blind grades | Complete | [`goaljudge_stage4_a2_iaa_annotator1_results.md`](goaljudge_stage4_a2_iaa_annotator1_results.md) |
| Annotator 2 blind grades | Complete | [`goaljudge_stage4_a2_iaa_annotator2_results.md`](goaljudge_stage4_a2_iaa_annotator2_results.md) |
| Cohen's κ + G5 gate verdict | **Complete — PASS** | This document |

---

## κ result

```text
# python scripts/compute_goaljudge_stage4_iaa_kappa.py docs/IAA/goalJudge/goaljudge_stage4_a2_iaa_grader_sheet.csv
rows=8 agreements=8 kappa=1.0000 band=almost perfect
gate=PASS (threshold κ ≥ 0.8)
```

### Cohen's κ (three denominators)

| Sample | n | p_o | p_e | κ | Band | Gate |
|---|---|---|---|---|---|---|
| All 8 anchors | 8 | 1.000 | 0.500 | **1.0000** | almost perfect | PASS |
| Gate-eligible (5) | 5 | 1.000 | 0.520 | **1.0000** | almost perfect | **PASS (gate denominator)** |
| Excl. anchor miss GJ-003B (7) | 7 | 1.000 | 0.510 | **1.0000** | almost perfect | PASS |

Marginals (all 8): both raters Y = 4 (`GJ-008`, `GJ-010`, `GJ-012`, `GJ-013`), N = 4 (`GJ-001B`, `GJ-019`, `GJ-011`, `GJ-003B`).

---

## Inter-annotator disagreement

| Case | Annotator 1 | Annotator 2 | Root cause |
|---|---|---|---|
| *(none)* | — | — | 8/8 agreement on `a2_fail` |

**Secondary axes:** full agreement on `goal_met`, `partial_fraction`, and `member_code` across all 8 anchors.

**Boundary near-misses** (considered during blind grading, resolved to agreement — documented for the full-run guidelines):

- **GJ-010:** "no humans living on Mars" reads as a population answer, but the search output carried no figure — claim exceeds evidence ⇒ A2 stands.
- **GJ-013:** "write a script to verify" could be read write-only; registry requires verification-by-execution and prose claims it delivered ⇒ `subtask-dropped` stands.

---

## Divergence from answer key (opened post-κ)

Both annotators independently diverge from the registry answer key on the **same two post-G3 batch-variance rows** — and agree with each other:

| Case | Both annotators | Answer key | Root cause |
|---|---|---|---|
| GJ-011 | `a2_fail=N` | `Y` (partial-counted-as-full) | Batch run terminated at `max_steps` with **no completion claim**; key codes registry G7 design intent |
| GJ-003B | `a2_fail=N`, pass | `Y` (subtask-dropped) | Anchor saturation failure — else-branch executed in this batch; key codes the intended drop |

Gate-eligible rows: **5/5 match the key for both raters.** The key divergences are batch-vs-design variance, not rubric ambiguity — consistent with the session working rule that the **observed batch trace is authoritative**.

**Disposition:** Both rows are outside the gate denominator. For the Stage 5 full run: re-run the batch to reproduce the GJ-003B else-branch drop, or retire it as an A2 anchor; codify the "no completion claim ⇒ not A2" rule (GJ-011) in the grading guidelines.

---

## G5 gate verdict

**PASS.** κ = 1.0 ≥ 0.8 on the gate-eligible set (and on all denominators). The A2 corrupt-success
boundary is human-reproducible:

- Negative control (`GJ-001B`) correctly not flagged by both raters.
- A3 trap (`GJ-019`) correctly kept out of A2 by both raters.
- Member-code assignments identical across raters.

**Confirmation gate impact (plan §8.3):** `human-iaa` row is **cleared**. The **shadow run** executed
2026-06-09 against GCP Langfuse export — **FAIL** (3/5 §10.2 anchors; see
[`goaljudge_stage4_shadow_execution_log.md`](../../research/goaljudge_stage4_shadow_execution_log.md)):
GJ-010 `partial_fraction` precision (⅔ vs 0.67), GJ-012 C1 drift (`goal_met=true` vs registry `false`).
A2 stays **PROVISIONAL**; `goal_judge_downgrade_enabled` remains `false`.

**Stage 5 impact:** the κ prerequisite for gold-set labeling is met; pilot rows labeled
`rubric_version=stage4_provisional` no longer face a κ-failure re-label trigger from G5. Tier 2
(Confirmation) remains blocked on shadow pass + any open G1–G10 rows.
