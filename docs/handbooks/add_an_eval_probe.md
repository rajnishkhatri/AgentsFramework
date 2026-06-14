# Handbook — Adding an Eval Probe to the Pipeline

> **For:** AI engineers working in the AgentsFramework `agent` monorepo.
> **Goal:** take *any* LLM-call seam from "no monitoring" to a **shipped Tier-A probe**
> (a 100%-coverage deterministic L1 check + one offline CI regression row), then know exactly
> what gates the **Tier-B** upgrade (sampled judge + drift).
> **Companion plans:** [`eval_probe_pipeline_skill.plan.md`](../plans/eval_probe_pipeline_skill.plan.md)
> (the why + research grounding) and [`llm_eval_pipeline_skill.plan.md`](../plans/llm_eval_pipeline_skill.plan.md).
>
> **The one rule that governs everything below:** *write evaluators for failures you have
> observed, never for failures you imagine.* Open coding (Phase 2) strictly precedes the rubric
> (Phase 5). If you find yourself writing a check before you've read traces, stop.

---

## The shape of the journey

```
Phase 0  Decide IF a probe is worth it      → transition failure matrix picks the seam
Phase 1  Pick the seam + altitude           → span / trace / persona; verify Recording works
Phase 2  Open coding                         → read ≥100 traces, label first-failures
Phase 3  Axial coding → taxonomy             → cluster into 5–6 testable categories
Phase 4  Ship the Tier-A probe  ★ MILESTONE  → L1 deterministic check (100%) + CI regression row
─────────────────────────────────────────────  you can stop here and many seams should  ─────
Phase 5  Rubric + gold set + IAA             → only when Tier-A data shows it's worth it
Phase 6  Judge calibration + enable-gate     → TPR/TNR + θ̂; fail-closed
Phase 7  Tier-B probe + the self-improving loop → sampled judge, drift, cadence re-analysis
```

Phases 0–4 are the spine of this handbook. Phases 5–7 are summarized at the end with pointers,
because the expensive judge track is **on-demand** — you earn it with Tier-A data, you don't
front-load it.

**Time budget reality check (Hamel/Shreya):** expect **60–80% of your effort** on Phases 2–3
(reading traces and building the taxonomy), not on code. If you're spending most of your time
writing checks, you're probably skipping the analysis.

---

## Phase 0 — Decide whether this seam even needs a probe

Don't instrument by vibes. The repo logs every `WorkflowPhase` transition to `phases.jsonl`
already, so you can let the data tell you which seam fails most.

**Do this:**

1. Build a **transition failure matrix** over recent traces: rows = the last state that completed
   cleanly, columns = the state where the *first* failure occurred, cell = count.
   States are the real [`WorkflowPhase`](../../services/governance/phase_logger.py) enum:
   `INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION → TOOL_EXECUTION →
   OUTPUT_VALIDATION → EVALUATION` (graph order: `guard_input → route → call_llm → execute_tool
   → evaluate`).
2. Read the heatmap. The **highest-count cell is the seam where a probe earns the most.** (PDF
   §8.3's worked example: `GenSQL→ExecSQL = 12` ⟹ instrument the SQL-generation seam first.)
3. First-failure attribution reuses checks that already exist — `synthesis_validator`,
   `guardrail_validator`, `goal_judge goal_met=false`. No new instrumentation needed; this is a
   pure offline aggregation.

> The matrix-building function is a planned deliverable (`meta/analysis.py`). Until it lands, do
> the aggregation by hand from `phases.jsonl` — but **still do it**. Picking the seam by gut feel
> is the single most common way an eval effort wastes its 60–80%.

**Done when:** you can name the seam and point at the cell that justifies it.

---

## Phase 1 — Pick the seam and its altitude

A "seam" is one LLM-call boundary. Before coding, choose the **altitude** you'll evaluate at —
this decides what a "trace" means for you:

| Altitude | What it scopes | Use for |
|---|---|---|
| **Span** | one LLM call in isolation | most seams: a single judge, a guardrail, a summarizer call |
| **Trace** | a whole multi-step run | router, `plan_builder` — quality depends on the trajectory |
| **Persona** | a simulated user across turns | multi-turn conversation health (rare; PDF §6) |

Most seams here are **span-level**. If you're unsure, start span — you can widen later.

**Verify Recording works before you go further.** Every probe writes to the Recording pillar via
[`services/eval_capture.py`](../../services/eval_capture.py) `record(target=…)`, which flows into
[`eval_telemetry.py`](../../services/eval_telemetry.py) under the same `trace_id` (the `eval.*`
fields get the 8192-char exemption vs the 200-char BlackBox cap). Confirm your seam already calls
`record(...)` or add the call — a probe with no captured traces has nothing to score.

```python
# inside your component, after the LLM call:
from services import eval_capture
await eval_capture.record(
    target="my_seam",            # stable name; becomes the probe's key
    ai_input={...},              # what went in
    ai_response=result,          # what came out (dict or str)
    config=config,              # carries task_id / user_id from configurable
    model=model_name,
)
```

**Done when:** seam named, altitude chosen, and you can see your seam's records landing in
telemetry for a handful of real runs.

---

## Phase 2 — Open coding (read traces, label first-failures)

This is the phase people skip and the phase that matters most. **No tooling, no rubric, no
judge yet — just you reading outputs and writing down what's wrong, in your own words.**

**Do this:**

1. Pull **≥ 100 traces** for the seam from telemetry. Bias toward real production traffic; if you
   genuinely don't have enough volume yet, synthesize inputs along the seam's natural dimensions
   (PDF §3.2 dimension→tuple→query method — reference-grade, not gospel).
2. For each trace, find the **first** thing that goes wrong (first-failure discipline — downstream
   errors are usually consequences, not root causes). Write a short free-text note. Don't
   pre-categorize.
3. Use the **Three Gulfs** as a lens for *why* it failed (PDF §1.2):
   - **Comprehension** — the model misread the input/context.
   - **Specification** — we asked for the wrong thing (prompt/rubric gap).
   - **Generalization** — it works on seen cases, breaks on the long tail.
4. **Stop rule:** keep going until you hit **~20 consecutive traces with no new failure category**.
   That's saturation. Don't stop early; don't pad past it.

**Sanity band:** if ~100% of traces look fine, your sample is too easy — go find harder traffic.
A seam worth probing usually sits around **~70% pass** when you're genuinely stress-testing it.

**Done when:** ~100+ traces read, every failure has a first-failure note, and you've seen ~20 in a
row with nothing new.

---

## Phase 3 — Axial coding → a testable taxonomy

Turn the messy notes into structure.

**Do this:**

1. Let an LLM **propose clusters** over your free-text notes (it's good at grouping), then **you
   rename and merge** them — the human owns the final names. Aim for **5–6 categories**, each:
   - **binary** (present / absent — never a 1–5 Likert; Likert hides uncertainty in the middle),
   - **mutually distinguishable**, and
   - **testable from the trace alone** (evidence-grounded).
2. Re-label your traces against the structured taxonomy (some notes will move; that's expected —
   it's criteria drift, and it's healthy on the first pass).
3. Write the taxonomy down as the seam's source of truth. The offline harness already expects a
   taxonomy file — see [`meta/judge.py`](../../meta/judge.py) `load_taxonomy()` and
   [`meta/judge_prompt.j2`](../../meta/judge_prompt.j2).

**Avoid generic metrics.** "Helpfulness", "quality", "correctness" with no seam-specific
definition are, in the canon's words, *worse than useless* — they manufacture false confidence.
Every category must mean something specific to *this* seam.

**Done when:** 5–6 binary, evidence-grounded categories exist and your traces are re-labeled
against them.

---

## Phase 4 — Ship the Tier-A probe ★

This is the milestone. You ship the **cheapest thing that catches the failures you found**: a
deterministic L1 check that runs on **100% of traffic**, plus **one offline CI regression row** so
the failure can never silently come back.

### 4a. Write the L1 deterministic check

Model it on the existing precedent —
[`services/governance/guardrail_validator.py`](../../services/governance/guardrail_validator.py)
(regex PII/key/length → `ValidationResult` with severity + fail-action). Your check is a **pure
function** that turns a trace into a pass/fail per category. Pick the subset of your taxonomy that
is *deterministically detectable* — that's your L1 surface; the rest waits for Tier-B's judge.

Use the component-type template that matches your seam as a starting point (specialize it, never
ship it raw):

| Seam type | Tier-A L1 check (100%, deterministic) |
|---|---|
| Goal/outcome judge | process floor: "ran cleanly", required fields present |
| Input/output guardrail | regex PII/key/length, entropy/injection check |
| Tool-calling | tool ∈ allowed set; args schema-valid |
| Planning/routing | plan non-empty; depth in range |
| Summarization | length bound; non-empty; no obviously truncated output |
| Condition generation | grounding budget (≤1 ungrounded); ≥N conditions |
| Pre-judge deterministic gate | **must ship a must-accept/must-reject benchmark BEFORE it gates** |

**Layer discipline** (binds to
[FOUR_LAYER_ARCHITECTURE.md](../Architectures/FOUR_LAYER_ARCHITECTURE.md)): the L1 check and any
pure metrics live in **`services/`** (L1/L2 Horizontal — stdlib + pydantic only, **no framework
imports**). The judge, when you get to it, is **L3 `components/`**. Live replay/scoring scripts go
in **`scripts/`** or **`meta/`** — **never in CI**.

### 4b. Add the offline CI regression row

Capture the failures you found as a frozen benchmark the same way GoalJudge did
(`gate_benchmark_v1.json` pattern): a small curated JSONL of input → expected-verdict rows, with
the must-pass cases your L1 check now catches. Run it deterministically in CI.

```bash
# Score a curated golden/benchmark set offline (deterministic-friendly):
python -m meta.run_eval --golden-set path/to/<seam>_benchmark_v1.json \
    --output /tmp/<seam>_report.json --report-id <seam>-tierA
# Prints: scored=… failed=… mean=…
```

**Done when:**
- [ ] L1 check is a pure function in `services/`, no framework imports
- [ ] It runs on 100% of the seam's traffic and writes via `eval_capture.record`
- [ ] A frozen `<seam>_benchmark_v1.json` exists with the failures from Phase 2
- [ ] `python -m meta.run_eval` scores it green in CI
- [ ] You did **not** build a judge yet

**A large fraction of seams should stop here.** Reach for the judge track only when Tier-A's
shadow data proves you'll iterate on this seam repeatedly.

---

## Phases 5–7 — The judge track and the self-improving loop (on-demand)

You graduate to these **only** when the Tier-A probe's accumulated data shows the seam has
persistent failures worth a gating judge. Summary + pointers:

### Phase 5 — Rubric + gold set + IAA
Promote the taxonomy into a judge rubric (binary, evidence-grounded per-criterion). Build a
labeled gold set and **split it dev / test**: tune the judge prompt on **dev only**, then
**freeze and hash the test split** and never tune on it (PDF §5.4 — the discipline the GoalJudge
2b α baseline already enforces). You need **≥ 100 labeled examples** to validate a judge. Measure
inter-annotator agreement (κ/α) via [`services/governance/iaa.py`](../../services/governance/iaa.py);
**κ ≥ 0.6 is a measurement prerequisite**, not the headline.

### Phase 6 — Calibration + the per-component enable-gate
Generalize the §2.8 evaluator
([`services/governance/goaljudge_calibration.py`](../../services/governance/goaljudge_calibration.py)).
The **headline judge-alignment metrics are TPR and TNR on the frozen test split** (Hamel/Shreya
vocabulary), with precision / false-downgrade-rate / κ as the §2.8 refinement.

> **Mapping so the two vocabularies don't confuse you** (on the "judge says *not-met*" = positive
> convention): **TPR = recall**; **TNR = 1 − false-downgrade-rate**.

Also report the **bias-corrected production success rate** — a judge with TPR or TNR < 1 gives a
biased raw pass-rate on unlabeled traffic:

```
θ̂ = (p_obs + TNR − 1) / (TPR + TNR − 1)      # p_obs = k/m, raw judge pass-rate on m new traces
```

with a **bootstrap 95% CI** (resample test labels B times; take the 2.5th/97.5th percentiles). If
the CI is wide, the fix is *improve the judge's TPR/TNR*, not just the prompt. The gate is
**fail-closed** (`GateDecision`); a seam that doesn't clear stays **shadow / L1-only**.

### Phase 7 — Tier-B probe + the self-improving loop
Once the gate passes, register:
- **L2 sampled judge** — score **5–10%** of traffic with [`meta/judge.py`](../../meta/judge.py)
  (`build_judge_prompt`, `parse_judge_response`) over sampled `EvalRecord`s.
- **L3 drift** — over the L1/L2 stream via [`meta/drift.py`](../../meta/drift.py)
  `run_full_drift_check`.

```bash
# 3-level drift check (exit 0 = no drift, 1 = drift, 2 = error):
python -m meta.drift --baseline baseline_scores.jsonl --production prod_scores.jsonl \
    --level all --output /tmp/drift_report.json
# optionally log triggered alerts as governance Decisions:
#   --alert-log-dir <dir> --workflow-id <seam>-drift
```

**The loop trigger — cadence first.** The **primary** trigger is the practitioner cadence:
**re-run open coding on 100+ fresh traces every 2–4 weeks**, plus a **change-event hook** (prompt
edit / model swap / new feature → re-run that seam's offline probe). Between cycles, run **10–20
outlier spot-checks weekly**. EWMA (on the L2 score stream) and CUSUM (on the per-category
fail-rate) are an **early-warning layer that surfaces candidates between cycles** — they reduce
mean-time-to-detect, but **a human re-analysis cycle is the authority**, not the chart. Threshold
on the **bias-corrected θ̂ and its CI**, never a raw judge count.

**Where the loop sends you back:** a new failure mode → back to **Phase 2 (open coding)**; a
confirmed regression → a new **offline CI row** (the cheap default). **Gold-set promotion is
human-gated.** That feedback arrow — production → open coding — is the whole point of a *continuous*
probe.

---

## Quick reference — the repo primitives each phase touches

| Phase | Primitive | File |
|---|---|---|
| 0 prioritize | `WorkflowPhase`, `phases.jsonl` | [`services/governance/phase_logger.py`](../../services/governance/phase_logger.py) |
| 1 capture | `record(target=…)` | [`services/eval_capture.py`](../../services/eval_capture.py) · [`eval_telemetry.py`](../../services/eval_telemetry.py) |
| 3 taxonomy | `load_taxonomy()`, prompt template | [`meta/judge.py`](../../meta/judge.py) · [`meta/judge_prompt.j2`](../../meta/judge_prompt.j2) |
| 4 L1 check | `GuardRailValidator`, `ValidationResult` | [`services/governance/guardrail_validator.py`](../../services/governance/guardrail_validator.py) |
| 4 CI score | `python -m meta.run_eval --golden-set … --output …` | [`meta/run_eval.py`](../../meta/run_eval.py) |
| 5 IAA | κ/α | [`services/governance/iaa.py`](../../services/governance/iaa.py) |
| 6 gate | §2.8 evaluator, `SECTION_2_8_THRESHOLDS`, `GateDecision` | [`services/governance/goaljudge_calibration.py`](../../services/governance/goaljudge_calibration.py) |
| 7 judge | `build_judge_prompt`, `parse_judge_response`, `compute_metrics` | [`meta/judge.py`](../../meta/judge.py) · [`meta/analysis.py`](../../meta/analysis.py) |
| 7 drift | `python -m meta.drift --baseline … --production … --level all` | [`meta/drift.py`](../../meta/drift.py) |

## Numbers to memorize (Hamel/Shreya canon)

| Quantity | Value |
|---|---|
| Traces to open-code before first taxonomy | **≥ 100** |
| Saturation stop rule | **~20 consecutive traces, no new category** |
| Labeled examples to validate a judge | **≥ 100** |
| Production re-analysis cadence | **100+ fresh traces every 2–4 weeks** |
| Between-cycle spot-checks | **10–20 outliers weekly** |
| Pass-rate sanity band | **100% ⇒ too easy; ~70% ⇒ stress-testing** |
| Effort allocation | **60–80% on error analysis / eval, not code** |
| IAA prerequisite | **κ ≥ 0.6** (prerequisite, not headline) |

## Two worked precedents to copy from

- **GoalJudge** — full path: open coding → axial → synthetic strata → rubric → gold set + IAA →
  §2.8 calibration → runtime flag-flip. The judge-track exemplar.
- **Guardrails** — `guardrail_dataset` + `guardrail_validator` → a live L1 runtime probe. The
  Tier-A exemplar; and [`scripts/probe_guardrail.py`](../../scripts/probe_guardrail.py) is a
  working interactive probe you can read end to end.
