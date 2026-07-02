---
name: agentsframework-eval-probe
type: skill
description: >-
  Add and operate a continuous-evaluation PROBE on any LLM-call seam in THIS repository (the
  AgentsFramework `agent` monorepo). Walks a component from open coding -> failure/improvement
  taxonomy -> axial coding -> rubric -> judge -> a registered probe (L1 deterministic 100%, L2
  sampled judge 5-10%, L3 drift, offline CI regression, per-component enable-gate), then keeps it
  healthy with a cadence + drift loop that re-opens error analysis. Tiered: a light Tier-A probe
  ships first; the gold-set + judge track is earned on-demand. Use this whenever the work is
  "add an eval probe", "monitor this component", "instrument a seam for evaluation", "add a
  regression benchmark", "wire up drift detection", "which component should we evaluate next",
  "build a judge/rubric for X", "add continuous monitoring", or "close the production-failure ->
  regression-test loop" — even when the user names only the component (summarizer, plan_builder,
  router, a tool call) and not the word "probe". Builds on meta/drift.py, meta/judge.py,
  eval_capture, observability, and the guardrail/GoalJudge precedents. For the GoalJudge-specific
  calibration flip path defer to agentsframework-eval; for the generic provider-agnostic
  methodology defer to llm-eval-grounded-theory; for trace-pillar audits defer to
  governance-trace-audit.
disable-model-invocation: false
paths:
  - meta/drift.py
  - meta/judge.py
  - meta/analysis.py
  - meta/run_eval.py
  - services/eval_capture.py
  - services/eval_telemetry.py
  - services/observability.py
  - services/governance/guardrail_validator.py
  - services/governance/goaljudge_calibration.py
  - components/**
---

# Add an Eval Probe to the Pipeline

Take *any* LLM-call seam in this repo from "no monitoring" to a **shipped Tier-A probe**
(a 100%-coverage deterministic check + one offline CI regression row), then know exactly what
gates the Tier-B upgrade (sampled judge + drift). The monitoring spine already exists — your job is
to *register a seam into it*, not build new infrastructure.

> **Docs mirror.** Canonical install: `.claude/skills/agentsframework-eval-probe/` and
> `.cursor/skills/agentsframework-eval-probe/`. This folder versions the skill with the repo.
>
> **Deep tables:** [reference.md](reference.md) — probe taxonomy, rubric templates, altitudes,
> layer rules, enable-gate metrics, drift methods, the transition matrix, hard numbers.
> **Worked anchors:** [examples.md](examples.md) — Guardrails (Tier-A) + GoalJudge (full track).
> **Invocations:** [commands.md](commands.md) — the exact `run_eval` / `drift` / leak-audit calls.

## When to use / when to defer

Use this skill to instrument a new seam, add a regression benchmark, wire drift, define a
per-seam judge/rubric, or close the production-failure → regression-row loop. Defer:

- **Generic, provider-agnostic methodology** → `llm-eval-grounded-theory`.
- **GoalJudge-specific operation** (the exact §2.8 flip path, current gold-set state, landmines)
  → `agentsframework-eval`.
- **Trace-pillar audits** (is this trace governance-compliant?) → `governance-trace-audit`.

## The one rule that governs everything

**Write evaluators for failures you have observed, never for failures you imagine.** Open coding
(Phase 2) strictly precedes the rubric (Phase 5). If you catch yourself writing a check before
you've read traces, stop — you're building the wrong thing.

And the budget reality: expect **60–80% of your effort on Phases 2–3** (reading traces, building
the taxonomy), not on code. If most of your time is going into checks, you're skipping the
analysis that makes them worth anything.

## The shape of the journey

```
Phase 0  Decide IF a probe is worth it      → transition failure matrix picks the seam
Phase 1  Pick the seam + altitude           → span / trace / persona; verify Recording works
Phase 2  Open coding                         → read ≥100 traces, label first-failures
Phase 3  Axial coding → taxonomy             → cluster into 5–6 binary, testable categories
Phase 4  Ship the Tier-A probe  ★ MILESTONE  → L1 deterministic check (100%) + CI regression row
─────────────────────────────────────────────  many seams should stop here  ─────
Phase 5  Rubric + gold set + IAA             → only when Tier-A data shows it's worth it
Phase 6  Judge calibration + enable-gate     → TPR/TNR + θ̂; fail-closed
Phase 7  Tier-B probe + the self-improving loop → sampled judge, drift, cadence re-analysis
```

Phases 0–4 are the spine. Phases 5–7 are the on-demand judge track — earned with Tier-A data, never
front-loaded.

---

## Phase 0 — Decide whether this seam even needs a probe

Don't instrument by vibes. The repo logs every `WorkflowPhase` transition to `phases.jsonl`, so let
the data name the seam.

1. Build the **transition failure matrix**: rows = last state that completed cleanly, columns =
   state of first failure, cell = count. The **highest-count cell is where a probe earns the most.**
2. States are the real `WorkflowPhase` enum — zero new instrumentation. First-failure attribution
   reuses `synthesis_validator`, `guardrail_validator`, `goal_judge goal_met=false`.

Full definition + the graph-vs-enum state-order gotcha: [reference.md §7](reference.md). The
aggregation function is a planned `meta/analysis.py` deliverable; until it lands, aggregate by hand
from `phases.jsonl` — but **still do it.** Picking the seam by gut feel is the most common way an
eval effort wastes its 60–80%.

**Run the matrix even on thin data — and never let "this seam obviously matters" stand in for a
counted cell.** A 2-hour hand-aggregation over 72 workflows is directional and worth it; "the
output replaces `reasoning_trace`, so it's clearly high-harm" is a *hypothesis*, not a count.
**Plausible harm ≠ the highest-count first-failure cell.** Two caveats the matrix itself will throw
at you: (a) you likely want ≥100 traces for a stable read, so treat a thin pass as directional;
(b) failures pile into a terminal "completion"/"evaluation" *attribution sink* — re-attribute them
to their true origin using the existing first-failure signals (`synthesis_validator`,
`guardrail_validator`, `goal_judge`) before reading the top cell, or the matrix points everywhere
at once.

**Done when:** you ran the aggregation (however thin), re-attributed the sink, and can point at the
counted cell — not just a harm story — that justifies the seam.

---

## Phase 1 — Pick the seam and its altitude

A "seam" is one LLM-call boundary. Two decisions here, both of which you must make *explicitly* and
write down — they are the decisions a thoughtful engineer most often skips, and skipping them is
what sends a probe to the wrong place.

**1. Find the real seam — especially when the named component is deterministic.** The component a
user points at is not always where the LLM decision lives. `plan_builder` is *deterministic* (pure
decomposition); the actual LLM/heuristic decision is upstream in `router.select_planning_depth`.
A deterministic helper is still probe-able — but be honest about *what* you're scoring: the
upstream decision, the artifact, or the trajectory. If the seam has no model in it at all (e.g. the
summarizer is string-slicing), say so, because it changes the failure modes (truncation/omission,
not hallucination) and usually means the seam should **stop at Tier-A** — there's nothing for a
judge to grade.

**2. Choose the altitude and defend it in one sentence.** This decides what a "trace" means:
**span** (one call — most seams), **trace** (a multi-step run — router, `plan_builder`, where
quality depends on the trajectory, not one call), or **persona** (a simulated user across turns,
rare). Table in [reference.md §3](reference.md). The test: *can you see the failure from one
call's inputs and output?* If yes, span. If the failure is only visible across the trajectory
(a plan that looks fine but was the wrong plan; an adherence gap), it's **trace** — and a span
check will silently miss the dominant failure mode. A planner is the classic case where span is
*wrong*. Don't confuse a `phase_logger` Decision entry ("log that we chose depth L1") with eval
altitude — that's Reasoning-pillar logging, not a trajectory-level evaluation.

**Wire Recording, and capture what scoring will need.** Every probe scores against the
Recording-pillar write — `eval_capture.record(target=…)` → `eval_telemetry` on the same `trace_id`.
Confirm your seam calls `record(...)` or add it. **The payload is not boilerplate:** capture the
inputs the *scorer* needs, not just the output. For a trace-altitude planner that means
`planning_depth` + `depth_reason` from the upstream decision in `ai_input`; for any seam it means
the full source material (so an offline re-score has everything), within the 8192-char `eval.*`
exemption. A probe whose capture dropped the field you need to score is a probe you can't score.

**Done when:** the real seam is named (with its altitude defended in a sentence), Recording is
wired with a scoring-complete payload, and you can see its records landing in telemetry.

---

## Phase 2 — Open coding (read traces, label first-failures)

The phase people skip and the one that matters most. No tooling, no rubric, no judge — just you
reading outputs and writing what's wrong, in your own words.

1. Pull **≥ 100 traces** for the seam. Bias toward real traffic; if volume is genuinely too low,
   synthesize inputs along the seam's natural dimensions (reference-grade, not gospel).
2. For each, find the **first** thing that goes wrong (downstream errors are usually consequences).
   Write a short free-text note. Don't pre-categorize.
3. Use the **Three Gulfs** as the *why* lens: **Comprehension** (misread input), **Specification**
   (we asked for the wrong thing), **Generalization** (works on seen cases, breaks on the tail).
4. **Stop rule:** keep going until **~20 consecutive traces with no new category** — saturation.

**Sanity band:** ~100% passing ⇒ your sample is too easy; a seam worth probing sits around **~70%
pass** under genuine stress.

**Keep open coding pure — don't pre-write the taxonomy.** It is tempting (and the model is good at
it) to list "the categories I expect to find" before reading. Resist it: a pre-committed list
anchors your labeling and you'll see what you predicted. If you have a hunch about a failure mode,
write it as a *falsifiable hypothesis to look for* (one line, in a sidebar), not as a category — and
let the traces confirm or kill it. The taxonomy is an output of Phase 3, never an input to Phase 2.

**Done when:** ~100+ traces read, every failure has a first-failure note, ~20 in a row with nothing
new.

---

## Phase 3 — Axial coding → a testable taxonomy

Turn the messy notes into structure.

1. Let an LLM **propose clusters** over your notes, then **you rename and merge** — the human owns
   the final names. Aim for **5–6 categories**, each **binary** (present/absent — never a 1–5
   Likert, which hides uncertainty in the middle), **distinguishable**, and **testable from the
   trace alone**.
2. Re-label your traces against the structured taxonomy (some notes move — healthy criteria drift).
3. Write the taxonomy down as the seam's source of truth (`meta/judge.py` `load_taxonomy()` +
   `meta/judge_prompt.j2` expect one).

**Avoid generic metrics.** "Helpfulness", "quality", "correctness" with no seam-specific definition
are *worse than useless* — they manufacture false confidence. Every category must mean something
specific to *this* seam.

**Done when:** 5–6 binary, evidence-grounded categories exist and traces are re-labeled against them.

---

## Phase 4 — Ship the Tier-A probe ★

The milestone: the **cheapest thing that catches the failures you found** — a deterministic L1 check
on **100% of traffic** + **one offline CI regression row** so the failure can't silently return.

**4a. The L1 check.** A pure function (trace → pass/fail **per category**), modeled on
`guardrail_validator.py` (`ValidationResult`). Pick the *deterministically detectable* subset of
your taxonomy — the rest waits for the Tier-B judge. Start from the **component-type template** for
your seam ([reference.md §2](reference.md)) and **specialize it** — never ship a template raw.
Emit **per-category binary results, not a single 0–1 score** — a scalar tells you something
regressed but not *what*, and drift on a named category is the signal you actually act on.

**At trace altitude, the L1 check has two surfaces — say which is which.** Structural checks that
are decidable at the moment the seam produces its output run **inline** (e.g. plan depth, MECE,
branch coverage). Trajectory checks that need the *whole run* — plan-adherence, "did execution
follow the plan" — can't be decided inline; they run as an **offline replay over `phases.jsonl`**
in `meta/`. A trace-altitude probe that only ships the inline half is half-implemented; name both.

**Layer discipline:** the L1 check and any pure metric live in **`services/`** (stdlib + pydantic,
**no framework imports**). The judge, later, is **L3 `components/`**. Live replay goes in
**`scripts/`/`meta/`** — **never CI.** Full table: [reference.md §4](reference.md).

**The layer-tension rule** (you *will* hit this): if a signal your L1 check needs is computed in
`components/` (e.g. `_extract_branches`), the pure `services/` check **cannot import it**. Two ways
out: pass the *derived value* through the capture payload (`ai_input["extracted_branches"]`) so the
pure check reads it, or move that particular check to the offline `meta/` replay where importing
the component is allowed. Never reach from `services/` into `components/` to dodge the rule.

**Wire it where the seam runs, and publish it.** A pure check that nothing calls is dead code —
invoke it in the orchestration node right after the seam produces its output (e.g. after
`build_compaction_summary`, *after* the trajectory replacement so the captured `ai_input` matches
what was actually processed), and embed the `ValidationResult`s in the `ai_response` you record.
"Lands in telemetry" also means the **Langfuse sink** sees it: add a `publish_<seam>(...)` method
mirroring `eval_telemetry.publish_task_understanding` (it must never raise — contract O1) and its
sink adapter, so the `eval.<seam>` observation appears on the trace and `governance-trace-audit`
can see it. `eval_capture.record(target=…)` alone is necessary but not sufficient.

**4b. The offline CI regression row.** Freeze the Phase-2 failures as a must-accept / must-reject
fixture (the `gate_benchmark_v1.json` pattern), and **gate it in CI with a pytest replay** that runs
your pure L1 check over the fixture and asserts every case lands on the right side — mirror
`tests/components/test_task_understanding_gate_benchmark.py`. This is the merge-blocking gate.

> **`meta.run_eval` is the *judge-track* scorer, not the deterministic CI gate.** It expects
> `EvalRecord` JSONL and runs an LLM judge — useful in Phase 7, wrong as the Tier-A merge gate. For
> a deterministic L1 check, the pytest replay is the gate; reach for `meta.run_eval` only once you
> have a judge to score.

**Done when:**
- [ ] L1 check is a pure function in `services/`, no framework imports, returns **per-category** results
- [ ] Invoked in the orchestration node on 100% of the seam's traffic; results recorded via `eval_capture.record` **and** published through a `publish_<seam>` sink so the `eval.<seam>` observation lands on the trace
- [ ] A frozen `<seam>_benchmark_v1.json` (must-accept / must-reject) holds the Phase-2 failures
- [ ] `python -m meta.run_eval` scores it green in CI, with a replay test asserting it
- [ ] You did **not** build a judge yet

> **"100% of traffic" means 100% of the seam's invocations** — for a rarely-fired seam (compaction
> only triggers under token pressure), say that explicitly so you don't overstate monitoring breadth.

**A large fraction of seams should stop here.** Reach for the judge track only when Tier-A shadow
data proves the seam has persistent failures you'll iterate on repeatedly.

---

## Phases 5–7 — The judge track + the self-improving loop (on-demand)

You graduate **only** when Tier-A data shows persistent failures worth a gating judge. Details and
formulas live in [reference.md §5–6](reference.md); the GoalJudge worked path is in
[examples.md](examples.md).

- **Phase 5 — rubric + gold set + IAA.** Promote the taxonomy to a binary judge rubric. Build a
  labeled gold set (**≥ 100 examples**), **split dev/test**, tune on dev only, **freeze + hash** the
  test split (κ ≥ 0.6 is a measurement *prerequisite*, not the headline; IAA via `iaa.py`).
- **Phase 6 — calibration + enable-gate.** Generalize the §2.8 evaluator (`goaljudge_calibration.py`).
  **Headline = TPR/TNR on the frozen test split** (TPR = recall; TNR = 1 − false-downgrade-rate;
  positive class = "judge says *not-met*", so a false positive is a *false downgrade*). Also report
  the **bias-corrected production rate** `θ̂ = (p_obs + TNR − 1)/(TPR + TNR − 1)` with a **bootstrap
  95% CI**. The gate is **fail-closed**; a seam that doesn't clear stays shadow / L1-only.
- **Phase 7 — Tier-B probe + loop.** Register an **L2 sampled judge** (5–10%, `meta/judge.py`) and
  **L3 drift** (`meta/drift.py`). **The loop trigger is cadence-first:** re-run open coding on 100+
  fresh traces **every 2–4 weeks**, plus a **change-event hook** (prompt/model/feature change → re-run
  the offline probe); EWMA/CUSUM only *surface candidates between cycles* — a human re-analysis cycle
  is the authority, and you threshold **θ̂ + CI**, never a raw judge count. A new failure mode → back
  to **Phase 2**; a confirmed regression → a new **offline CI row** (gold-set promotion is
  human-gated). That production → open-coding arrow is the whole point of a *continuous* probe.

The terminal *acting* decision (e.g. flipping a downgrade flag) is a **runtime-config write a human
owns** — this skill produces the decision and stops. For the GoalJudge flip path specifically, defer
to `agentsframework-eval`.

---

## Numbers to memorize

≥100 traces to start · ~20-no-new saturation · ≥100 labeled to validate a judge · 100+ fresh traces
every 2–4 weeks · 10–20 weekly spot-checks · ~70% pass = stress-testing (100% = too easy) · 60–80%
of effort on analysis · κ ≥ 0.6 prerequisite. Full table + sources: [reference.md §8](reference.md).
