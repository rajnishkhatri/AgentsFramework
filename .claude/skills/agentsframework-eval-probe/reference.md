# agentsframework-eval-probe — Reference

Deep tables for the probe workflow. The [SKILL.md](SKILL.md) body walks the phases; this file
holds the facts you look up *inside* a phase. Read the section you need, not the whole file.

## Table of contents

1. [Probe taxonomy — what gets registered, and where](#1-probe-taxonomy)
2. [Component-type rubric templates (Stage 4 starting points)](#2-component-type-rubric-templates)
3. [The three evaluation altitudes](#3-the-three-evaluation-altitudes)
4. [Layer discipline (binds to FOUR_LAYER_ARCHITECTURE)](#4-layer-discipline)
5. [Enable-gate metrics — TPR/TNR, the §2.8 refinement, θ̂](#5-enable-gate-metrics)
6. [Drift methods — EWMA vs CUSUM, cadence-first](#6-drift-methods)
7. [The transition failure matrix (seam prioritizer)](#7-transition-failure-matrix)
8. [Hamel/Shreya hard numbers](#8-hamelshreya-hard-numbers)
9. [Repo primitives — quick map](#9-repo-primitives)

---

## 1. Probe taxonomy

A "probe" is one of six concrete things, each reusing a primitive that already exists. You almost
never build new infrastructure — you *register a seam into* the existing harness.

| Probe tier | Coverage | Lives in | Reuses | Cost |
|---|---|---|---|---|
| **L1 deterministic** | 100% of invocations | pure check in `services/` + `eval_capture.record` **+ a `publish_<seam>` sink** | `guardrail_validator` pattern; `ValidationResult` shape (per-category) | ~0 |
| **L2 sampled judge** | 5–10% | `meta/judge.py` scorer over sampled `EvalRecord`s | `load_taxonomy`, `build_judge_prompt`, `parse_judge_response`, `compute_metrics` | per-sample LLM |
| **L3 drift** | over the L1/L2 stream | `meta/drift.py` (`run_full_drift_check`) | `DriftAlert`/`DriftReport`; EWMA/CUSUM upgrade path | scheduled batch |
| **Offline CI regression** | every PR | `tests/.../<seam>_benchmark_v1.json` + replay test | the `gate_benchmark_v1.json` pattern | CI |
| **Per-component enable-gate** | decision artifact | a §2.8-style evaluator (generalize `goaljudge_calibration`) | `evaluate_section_2_8_gates`, `GateDecision` | none (pure) |
| **Seam prioritizer** (which seam next) | offline analysis | transition failure matrix over `phases.jsonl` | `phase_logger` `WorkflowPhase`; new fn in `meta/analysis.py` | scheduled batch |

**Tier-A = the first two rows you ship: L1 (100%) + the offline CI regression row.** Everything
else is Tier-B, earned on-demand once Tier-A data proves the seam is worth a gating judge.

---

## 2. Component-type rubric templates

Stage 4 (the rubric) is never a blank page. Look up your seam type, take the template, and
**specialize it** — generic metrics shipped as-is are, per the canon, *worse than useless* because
they manufacture false confidence. The template is a starting prompt, not a deliverable.

| Seam type | Example here | Tier-A L1 check (100%) | Tier-B rubric criteria (sampled judge) |
|---|---|---|---|
| **Goal / outcome judge** | `components/goal_judge.py` | deterministic process floor ("ran cleanly", required fields present) | goal_met, criteria_met, evidence-grounded per-criterion |
| **Input/output guardrail** | `services/guardrails.py`, `guardrail_validator.py` | regex PII/key/length, entropy injection check | policy-compliance, over/under-blocking on benign vs adversarial |
| **Tool-calling** | (future tool seams) | tool ∈ allowed set; args schema-valid | Tool Correctness, Argument Correctness, Step Efficiency |
| **Planning / routing** | `components/plan_builder.py`, router | plan non-empty; depth in range | Plan Quality (complete + realistic), Plan Adherence (execution matched plan) |
| **Summarization / compaction** | `services/summarizer.py` | length bound; no empty output | Faithfulness (no fabrication vs source), coverage of key spans |
| **Condition generation** | `components/task_understanding.py` | grounding budget (≤1 ungrounded), ≥N conditions | conditions topical + answer-shape-aware, non-fabricated |
| **Pre-judge deterministic gate** | `components/synthesis_validator.py` | **must ship a must-accept/must-reject benchmark BEFORE it gates** (process rule) | n/a (deterministic) — the benchmark IS the probe |

---

## 3. The three evaluation altitudes

Choose before you code; it decides what a "trace" means for the seam.

| Altitude | Scopes | Use for | What a "trace" is |
|---|---|---|---|
| **Span** | one LLM call in isolation | most seams: a judge, a guardrail, a summarizer call | one request/response pair |
| **Trace** | a whole multi-step run | router, `plan_builder` — quality depends on the trajectory, not one call | the full `phases.jsonl` chain for a task |
| **Persona** | a simulated user across turns | multi-turn conversation health (rare here) | a whole session, multiple turns |

Most seams here are **span-level**. A planner or router is the classic case where span is *wrong*:
a plan can look fine in isolation and still be the wrong plan for the trajectory — those need
**trace** altitude. If unsure, start span; widen only when a failure is invisible at span level.

**Find the real seam first.** The component named in the request isn't always where the model
decides. `plan_builder` is deterministic; the LLM/heuristic decision is upstream in
`router.select_planning_depth`. A deterministic helper is still worth a probe — but score the right
thing (upstream decision / artifact / trajectory), and if there's *no model in the seam at all*
(e.g. the summarizer is string-slicing), expect truncation/omission failures rather than
hallucination, and expect the seam to **stop at Tier-A** — there is nothing for a judge to grade.
For trace altitude, capture the upstream decision inputs (e.g. `planning_depth` + `depth_reason`)
in the `ai_input` payload, or you can't score the trajectory later.

---

## 4. Layer discipline

Binds to [FOUR_LAYER_ARCHITECTURE.md](../../Architectures/FOUR_LAYER_ARCHITECTURE.md). An agent
that puts eval code in the wrong layer trips the dependency-leak audit.

| Piece | Layer | May import | Must NOT import |
|---|---|---|---|
| L1 deterministic check, pure metrics, enable-gate | **L1/L2 Horizontal** (`services/`) | stdlib, pydantic, sibling services | `components`, `langgraph`, `langchain`, framework, any network I/O |
| The judge under measurement | **L3 Vertical** (`components/`) | `components.schemas`, injected `services` types | `langgraph`/`langchain` directly |
| Live replay / scoring harness | **`scripts/` or `meta/`** (outside the grid) | the real component, LLM clients | — (but **never imported by CI tests**) |
| Probe registration into drift | `meta/` | `services.observability`, `meta.drift` | `components` from inside a pure metric |

**The load-bearing rule:** pure functions (checks, metrics, gates) are L1 — stdlib + pydantic, zero
framework imports. The thing that *calls the model* is L3 or a script. The gate **evaluates but
never acts** — it returns a decision; a human flips the runtime flag. This is exactly the split the
GoalJudge §2.8 evaluator already obeys.

---

## 5. Enable-gate metrics

The gate decides whether a seam's judge is trustworthy enough to graduate from shadow to
acting (L2 sampled, or downgrading). It is **fail-closed**: undecidable (None/NaN) or a provisional
gold set ⇒ REFUSE before any metric is read.

**Headline (Hamel/Shreya vocabulary):** report **TPR and TNR on a frozen held-out test split.**
That is the canon's explicit judge-alignment metric — *"achieve high TPR and TNR on a held-out
labeled test set."*

**The §2.8 refinement (the GoalJudge thresholds, generalize per seam):**

| Metric | Threshold | Why |
|---|---|---|
| precision | ≥ 0.90 | when the judge says "not-met", it must usually be right (downgrades are costly) |
| recall (= TPR) | ≥ 0.70 | catch most real failures |
| false-downgrade rate (= 1 − TNR) | ≤ 0.02 | the harm case: downgrading a clean success |
| flip rate | ≤ 0.05 (soft 0.10) | judge ↔ deterministic disagreement budget |
| κ (judge vs gold) | ≥ 0.6 | **measurement prerequisite**, not the headline |
| ECE | diagnostic-only | calibration sanity, not a gate |

> **Vocabulary bridge** (on the "judge says *not-met*" = positive convention):
> **TPR = recall**, and **TNR = 1 − false-downgrade-rate**. Same numbers, two names — say both so a
> reader from either tradition isn't confused.

**Confusion convention:** positive class = "judge says **not-met**" (the downgrade signal). So a
**false positive is a false downgrade** — the judge flunked a clean success. This inverts the usual
"positive = pass" intuition; spell it out every time.

**Bias-corrected production success rate (§5.6).** A judge with TPR or TNR < 1 gives a *biased* raw
pass-rate on unlabeled production traffic. Correct it:

```
θ̂ = (p_obs + TNR − 1) / (TPR + TNR − 1)      # p_obs = k/m, raw judge pass-rate on m new traces
```

with a **bootstrap 95% CI** (resample the test-split labels B times, recompute θ̂, take the
2.5th/97.5th percentiles). If the CI is wide, the fix is *improve the judge's TPR/TNR*, not the
prompt alone. This θ̂ — not a raw judge count — is what the loop trigger thresholds.

**Golden-number anchor** (the GoalJudge L1 suite pins this): shadow confusion TP=69 FP=8 FN=8
TN=12 ⇒ α=0.4987. Any generalized evaluator should keep an equivalent golden fixture so the math
can't silently drift.

**Data-split rule (§5.4):** every seam's labeled set is split **dev / test**. Tune the judge prompt
and rubric on **dev only**; **freeze and hash** the test split and never tune on it — the same
discipline the GoalJudge 2b α baseline enforces.

---

## 6. Drift methods

`meta/drift.py` already implements three levels (2σ performance, κ calibration, governance-artifact)
plus a CLI. You register a seam into it; you don't rebuild it.

**Cadence is primary, not the chart.** The authority for re-opening the loop is:

1. **Calendar cadence** — re-run open coding on **100+ fresh traces every 2–4 weeks**.
2. **Change-event hook** — a prompt edit / model swap / new feature → re-run that seam's offline
   probe immediately.
3. **Weekly spot-checks** — eyeball **10–20 outliers** between cadence cycles.

SPC charts are the **between-cycle early-warning layer** — they cut mean-time-to-detect, but a human
re-analysis cycle remains the authority. Which detector for which signal:

| Detector | Watches | Catches |
|---|---|---|
| **EWMA** | the L2 judge-score stream | gradual average quality decay |
| **CUSUM** | the per-category fail-rate (on θ̂) | small, persistent shifts / batch drift |

`meta/drift.py` currently uses 2σ + κ; EWMA/CUSUM is the documented upgrade path, not a rewrite.
Threshold on the **bias-corrected θ̂ and its CI**, never the raw judge count.

---

## 7. Transition failure matrix

The seam prioritizer (PDF §8.3, the "error-propagation index"). It answers *which seam to probe
next* — without it, you instrument by vibes and waste the 60–80%.

- **Rows** = "From State" = the last `WorkflowPhase` that completed cleanly.
- **Columns** = "In State" = the state where the **first** failure occurred.
- **Cell (i, j)** = count of failed traces whose first failure happened in state *j* right after
  state *i* completed.
- **The highest-count cell is where the next probe earns the most.** (PDF example:
  `GenSQL→ExecSQL = 12` ⟹ instrument SQL generation first.)

**States are the repo's real `WorkflowPhase` enum** (`services/governance/phase_logger.py`),
already logged to `phases.jsonl` — zero new instrumentation:

```
INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION → TOOL_EXECUTION
→ OUTPUT_VALIDATION → EVALUATION
```

Graph node order: `guard_input → route → call_llm → execute_tool → evaluate`. (Note: the enum
*declares* `OUTPUT_VALIDATION` after `EVALUATION`; the graph *executes* output validation around
the model call — use the graph order for the matrix, not the enum declaration order.)

First-failure attribution reuses checks that already exist: `synthesis_validator`,
`guardrail_validator`, `goal_judge goal_met=false`. So the matrix is a **pure offline aggregation**
over `phases.jsonl` + first-failure labels — a natural new function in `meta/analysis.py`, L1-pure
(the function itself, e.g. `build_transition_failure_matrix()`, is **not built yet** — aggregate by
hand until it lands).

**Once you have the top cell, map the phase to its seam:**

| Re-attributed phase | Seam to instrument |
|---|---|
| `EVALUATION` | `goal_judge` (outcome judge) |
| `OUTPUT_VALIDATION` | `synthesis_validator` (pre-judge gate) |
| `INPUT_VALIDATION` | `guardrail_validator` (input rail) |
| `ROUTING` | `router.select_planning_depth` / `plan_builder` (planning) |
| `TOOL_EXECUTION` | the tool seam |
| (compaction, fires under token pressure) | `summarizer` |

**Blast-radius tie-break:** when two cells are close, the higher-harm seam wins, not the higher
count — a false downgrade that corrupts a real success (`goal_judge`) beats a cosmetic failure
elsewhere.

---

## 8. Hamel/Shreya hard numbers

| Quantity | Value |
|---|---|
| Traces to open-code before first taxonomy | **≥ 100** |
| Saturation stop rule | **~20 consecutive traces, no new category** |
| Labeled examples to validate a judge | **≥ 100** |
| Production re-analysis cadence | **100+ fresh traces every 2–4 weeks** |
| Between-cycle spot-checks | **10–20 outliers weekly** |
| Pass-rate sanity band | **100% ⇒ too easy; ~70% ⇒ stress-testing** |
| Effort allocation | **60–80% on error analysis / eval, not code** |
| Judge ↔ human agreement before scaling | **85–90%** |
| IAA prerequisite | **κ ≥ 0.6** (prerequisite, not headline) |

Proof the loop works (the canon's exemplar): NurtureBoss date-handling **33% → 95%** via
analyze → measure → improve.

---

## 9. Repo primitives

| Phase | Primitive | File |
|---|---|---|
| 0 prioritize | `WorkflowPhase`, `phases.jsonl` | `services/governance/phase_logger.py` |
| 1 capture | `record(target=…)` | `services/eval_capture.py` · `services/eval_telemetry.py` |
| 3 taxonomy | `load_taxonomy()`, prompt template | `meta/judge.py` · `meta/judge_prompt.j2` |
| 4 L1 check | `GuardRailValidator`, `ValidationResult`, `pii_rules/api_key_rules/length_rule` | `services/governance/guardrail_validator.py` |
| 4 CI gate | **pytest replay** over a must-accept/must-reject fixture | `tests/components/test_task_understanding_gate_benchmark.py` (exemplar) |
| 5 IAA | κ / α | `services/governance/iaa.py` |
| 6 gate | §2.8 evaluator, `SECTION_2_8_THRESHOLDS`, `GateDecision`, `confusion_counts`, `precision_recall_fd` | `services/governance/goaljudge_calibration.py` |
| 7 judge | `build_judge_prompt`, `parse_judge_response`, `compute_metrics`; **LLM scorer** `python -m meta.run_eval` | `meta/judge.py` · `meta/analysis.py` · `meta/run_eval.py` |
| 7 drift | `python -m meta.drift --baseline … --production … --level all` | `meta/drift.py` |

**Recording-pillar binding:** `eval_capture.record(target=…)` → `eval_telemetry.publish_*()` on the
same `trace_id`; `eval.*` fields get the 8192-char exemption vs the 200-char BlackBox cap. The eval
pipeline and the [`governance-trace-audit`](../governance-trace-audit/SKILL.md) check read the same
telemetry — defer pillar audits there.
