# Adding an eval probe to the summarizer (`services/summarizer.py`)

Here's the plan to take the summarizer from "no monitoring at all" to a **shipped Tier-A probe**:
a 100%-coverage deterministic check plus one offline CI regression row, with the Tier-B judge track
left as an explicitly-gated next step we only earn if the data justifies it.

The monitoring spine (`eval_capture` → `eval_telemetry`, `meta/run_eval`, `meta/drift`,
`guardrail_validator`) already exists. Our job is to **register this seam into it**, not build new
infrastructure.

## What I found in the repo first (grounding, not assumptions)

- **The seam is `services/summarizer.py`** — two pure functions: `should_compact_trajectory(...)` and
  `build_compaction_summary(*, task_input, reasoning_trace, tool_results, latest_output) -> str`,
  plus a `CompactionResult` pydantic model. It is **fully deterministic — there is no LLM call**.
  This is the single most important finding and it shapes the whole plan (see the call-out below).
- **It is a live seam, not greenfield.** It's already wired into the agent loop at
  `orchestration/react_loop.py:1490-1505`: when `should_compact_trajectory(...)` returns true, the
  loop calls `build_compaction_summary(...)`, writes the result to an offload file
  (`.agent_offload/trajectory_summary_<wf>.md`), and **replaces `reasoning_trace` with the summary**.
  So the summary literally becomes the agent's memory of everything before compaction. A bad summary
  silently corrupts every downstream step. That's exactly the kind of high-harm, currently-blind seam
  a probe earns its keep on.
- **No `eval_capture.record(...)` call exists at that site today** — confirmed by grep. So Phase 1's
  real work is wiring Recording in; nothing scores the summarizer right now.
- Confirmed signatures we'll build against: `services.eval_capture.record(target, ai_input,
  ai_response, config, step=0, model=None, ...)` (async); `ValidationResult(passed, severity,
  fail_action, ...)` in `services/governance/guardrail_validator.py`; the benchmark JSON pattern in
  `tests/fixtures/task_understanding/gate_benchmark_v1.json` (`_meta` block + `must_accept` /
  `must_reject` arrays); and the Tier-A exemplar scripts `scripts/generate_guardrail_dataset.py` +
  `scripts/probe_guardrail.py`.

> ### The deterministic-seam call-out (read this before anything else)
> The one rule that governs the skill is: **write evaluators only for failures you have observed.**
> A second rule applies here specifically: `build_compaction_summary` has **no model in the loop** —
> it's string slicing (`[-3:]`, `[:120]`, `[:280]`). So the failure modes are *truncation and
> omission*, not hallucination. The skill's summarization template lists "Faithfulness (no
> fabrication vs source)" as a **Tier-B judge** criterion — but a deterministic concatenator can't
> fabrize content it never generates. **Most of the summarizer's real failures are L1-detectable**,
> which means this seam is a strong candidate to **ship Tier-A and stop** (like Guardrails did), not
> to graduate to a judge. We do not pre-build a judge to feel thorough.

---

## Phase 0 — Confirm the seam is worth a probe (short, because the data already points here)

Goal: don't instrument by vibes. Use the transition failure matrix over `phases.jsonl`
(`WorkflowPhase` transitions, zero new instrumentation; definition in `reference.md §7`).

For the summarizer this is mostly a sanity check rather than a discovery exercise, because we already
know two things: (1) compaction fires inside the `MODEL_INVOCATION → EVALUATION` region of the loop
(`react_loop.py:1483`, `WorkflowPhase.EVALUATION`), and (2) its output replaces `reasoning_trace`, so
any post-compaction failure is plausibly *caused* by a lossy summary. Concretely:

1. Aggregate `phases.jsonl` by hand (the `meta/analysis.py` aggregator is still a planned deliverable
   per the skill): rows = last clean state, columns = first-failure state.
2. Look specifically at tasks where `truncation_applied: true` appears in state and a failure follows.
   If those over-index on first-failures in/after `EVALUATION`, that's the cell that justifies the
   probe.

**Done when:** I can point at the cell (or the truncation-correlated failure cluster) that justifies
instrumenting the summarizer rather than some other seam.

## Phase 1 — Pick the seam + altitude, and wire Recording (the real work of this phase)

- **Altitude: span.** Each `build_compaction_summary(...)` call is evaluated in isolation — input
  (task_input + reasoning_trace + tool_results + latest_output) → output (summary string). We do not
  need trace altitude: the summary's quality is judgeable from the single call's inputs/output, and a
  bad summary is *visible* at span level (a dropped key fact is in the inputs but not the output).
  Start span; widen only if a failure turns out invisible there.

- **Wire `eval_capture.record(...)` at the call site.** This is the Recording-pillar write every probe
  scores against, and it's the thing that's missing today. At `orchestration/react_loop.py:1495`,
  right after `summary_text = build_compaction_summary(...)`, add:

  ```python
  from services import eval_capture
  await eval_capture.record(
      target="trajectory_summarizer",   # stable name → becomes the probe key
      ai_input={
          "task_input": state.get("task_input", ""),
          "reasoning_trace": state.get("reasoning_trace", []),
          "tool_results": state.get("tool_results", []),
          "latest_output": content,
          "token_count": token_count,
      },
      ai_response=summary_text,
      config=config,                    # carries task_id / user_id from configurable
      step=state.get("step_count", 0),
  )
  ```

  `eval.*` fields get the 8192-char BlackBox exemption, so capturing the full inputs and summary is
  fine. (Layer note: `react_loop.py` is orchestration, so the *call* lives there; the pure check we
  build in Phase 4 stays in `services/`.)

**Done when:** seam named (`trajectory_summarizer`), altitude chosen (span), and I can see its
`EvalRecord`s landing in `eval_telemetry` for compaction-triggering tasks.

## Phase 2 — Open coding (the phase that actually matters — budget 60–80% of effort here)

No rubric, no judge, no tooling — just read summaries and write what's wrong, first-failure only.

1. Pull **≥ 100** captured summarization traces. Compaction is rare per task, so if live volume is too
   low, synthesize inputs along the seam's natural dimensions: long vs short `reasoning_trace`,
   many vs few `tool_results`, a critical fact that lands in the *4th-from-last* trace entry (which
   the `[-3:]` slice silently drops), a `latest_output` longer than 280 chars, an empty trace.
2. For each, label the **first** thing wrong, in free text. The Three Gulfs lens, specialized to a
   deterministic truncator:
   - **Comprehension** — n/a-ish (no model misreading input), but watch for *encoding* issues: a tool
     result that's a dict with no `tool_name` key renders as nothing in `recent_tools`.
   - **Specification** — did we ask for the wrong compaction? e.g. `[-3:]` on `reasoning_trace`
     assumes the *last 3* steps carry the load-bearing context; the truncation budgets (120 / 280 /
     200 chars) are guesses. If the dropped material is what mattered, that's a spec failure.
   - **Generalization** — the tail: empty inputs, all-None tool dicts, a single 10k-char tool result.
3. **Stop rule:** ~20 consecutive traces with no new failure category = saturation.

Likely categories I expect to *find* (but will only commit to after reading, never before):
key-fact-dropped-by-`[-3:]`, critical-content-past-the-char-budget, empty-or-degenerate-summary,
tool-name-missing-so-tools-line-says-"none", task-line-truncated-mid-word.

**Sanity band:** if ~100% of synthesized cases pass, the sample's too easy — push harder on the tail
until the seam sits around ~70% pass under genuine stress.

**Done when:** ~100+ traces read, every failure has a first-failure note, ~20 in a row with nothing new.

## Phase 3 — Axial coding → a binary, testable taxonomy

1. Let an LLM propose clusters over the Phase-2 notes, then **I rename/merge** — human owns the names.
   Target **5–6 categories**, each **binary** (present/absent, never a 1–5 Likert), distinguishable,
   and **testable from the trace alone**.
2. Re-label the traces against the structured taxonomy (some notes will move — that's healthy).
3. Write the taxonomy down as the seam's source of truth (the `meta/judge.py` `load_taxonomy()` +
   `meta/judge_prompt.j2` path expects one, *if* we ever go Tier-B).

**Avoid generic metrics.** "Summary quality" means nothing. Every category must be summarizer-specific,
e.g. *"a fact present in the inputs but absent from the summary"* — concrete enough to test.

**Done when:** 5–6 binary, evidence-grounded categories exist and traces are re-labeled against them.

## Phase 4 — Ship the Tier-A probe ★ (the milestone)

The cheapest thing that catches the failures we found: an L1 deterministic check on 100% of traffic +
one frozen CI regression row.

**4a. The L1 check — a new pure module `services/summarizer_eval.py`.**
Modeled on `guardrail_validator.py`'s `validate(content) -> list[ValidationResult]` shape. Pure: stdlib
+ pydantic only, **no `components` / `langgraph` / `langchain` / network imports** (this is the
load-bearing layer rule). It takes the captured `EvalRecord` (inputs + summary) and returns per-category
`ValidationResult`s. Start from the skill's **Summarization/compaction template** (`reference.md §2`:
"length bound; no empty output") and **specialize it** to the categories Phase 3 produced — never ship
the template raw. Deterministically-detectable checks I expect to implement:

- **non-empty** — summary isn't `""` / `"(empty)"` (the `or "(empty)"` fallback is itself a fail signal).
- **length bound** — within expected min/max; flag the degenerate "everything truncated to fallbacks".
- **key-span coverage** — a deterministic check the summarizer's own logic makes possible: did any
  load-bearing token from a *dropped* `reasoning_trace` entry (beyond `[-3:]`) or a past-budget tail of
  `latest_output` fail to appear in the summary? This is the coverage/faithfulness floor, and crucially
  it's **decidable without a model** because the source text is right there in `ai_input`.
- **tools-line integrity** — `recent_tools` didn't collapse to "none" when `tool_results` was non-empty.

The genuinely model-needing parts (e.g. "is the *paraphrase* faithful in meaning") — there may be none
here, because the function paraphrases nothing — wait for Tier-B and are not built now.

**4b. The offline CI regression row.** Freeze the Phase-2 failures as
`tests/fixtures/summarizer/summarizer_benchmark_v1.json`, following the
`tests/fixtures/task_understanding/gate_benchmark_v1.json` pattern exactly: a `_meta` block (name,
built date, source, `source_sha256`) plus `must_accept` / `must_reject` arrays of real captured cases
(synthetic clearly flagged). Add a replay test `tests/services/test_summarizer_eval.py` that runs the
L1 check over the fixture and asserts every `must_*` lands on the right side. Score it:

```bash
python -m meta.run_eval \
  --golden-set tests/fixtures/summarizer/summarizer_benchmark_v1.json \
  --output /tmp/summarizer_report.json \
  --report-id summarizer-tierA
```

Verify the L1 module didn't leak a framework import (must print nothing):

```bash
grep -nE "from components|import langgraph|import langchain" services/summarizer_eval.py
```

Optionally model an interactive probe script on `scripts/probe_guardrail.py` →
`scripts/probe_summarizer.py` for ad-hoc local replay (lives in `scripts/`, **never CI**).

**Done when:**
- [ ] L1 check is a pure function in `services/summarizer_eval.py`, no framework imports
- [ ] It runs on 100% of compaction traffic, scoring the `eval_capture.record` write from Phase 1
- [ ] `tests/fixtures/summarizer/summarizer_benchmark_v1.json` holds the frozen Phase-2 failures
- [ ] `python -m meta.run_eval` (and `tests/services/test_summarizer_eval.py`) score it green in CI
- [ ] I did **not** build a judge

## Phases 5–7 — The judge track (on-demand; for this seam, probably skip)

Graduate **only** if Tier-A shadow data shows persistent failures worth a gating judge. As flagged in
the call-out, the summarizer is a deterministic concatenator, so I expect the L1 check to catch nearly
all real failures and this seam to **stop at Tier-A — the Guardrails outcome, which is what "done"
looks like.** If Tier-A data later surprises us (e.g. the *selection* of which spans to keep turns out
to need semantic judgment), then and only then:

- **Phase 5 — rubric + gold set + IAA.** Promote the taxonomy to a binary judge rubric; build a
  ≥100-example labeled gold set; **split dev/test**, tune on dev only, **freeze + hash** the test split
  (κ ≥ 0.6 is a measurement *prerequisite*, not the headline; IAA via `services/governance/iaa.py`).
- **Phase 6 — calibration + enable-gate.** Generalize the §2.8 evaluator
  (`services/governance/goaljudge_calibration.py`). Headline = **TPR/TNR on the frozen test split**
  (positive class = "judge says *not-met*", so a false positive is a false downgrade); report the
  bias-corrected `θ̂ = (p_obs + TNR − 1)/(TPR + TNR − 1)` with a bootstrap 95% CI. Thresholds:
  precision ≥ 0.90, recall(TPR) ≥ 0.70, false-downgrade(1−TNR) ≤ 0.02, flip ≤ 0.05, κ ≥ 0.6. The gate
  is **fail-closed** — a seam that doesn't clear stays shadow / L1-only. Keep a golden-number fixture
  (like GoalJudge's TP=69/FP=8/FN=8/TN=12 ⇒ α=0.4987) so the math can't drift.
- **Phase 7 — Tier-B probe + the loop.** Register an L2 sampled judge (5–10%, `meta/judge.py`) and L3
  drift (`meta/drift.py`). **Cadence is the authority:** re-open coding on 100+ fresh traces every
  2–4 weeks, plus a **change-event hook** — if the truncation budgets (`[-3:]`, 120/280/200) or
  `trajectory_compaction_token_threshold` in `services/base_config.py` ever change, re-run the offline
  probe immediately. EWMA/CUSUM only *surface candidates between cycles*; threshold on **θ̂ + CI**,
  never a raw judge count. A new failure mode → back to Phase 2; a confirmed regression → a new
  offline CI row (gold-set promotion is human-gated).

The terminal acting decision (e.g. changing the truncation budgets, or gating compaction on a quality
score) is a **runtime-config / code change a human owns** — the probe produces the decision and stops.

## Files this touches (all absolute)

- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/orchestration/react_loop.py` — add the
  `eval_capture.record(target="trajectory_summarizer", ...)` write at line ~1495 (Phase 1).
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/summarizer_eval.py` — **new** L1 pure
  check module (Phase 4a).
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/tests/fixtures/summarizer/summarizer_benchmark_v1.json`
  — **new** frozen benchmark (Phase 4b), modeled on
  `tests/fixtures/task_understanding/gate_benchmark_v1.json`.
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/tests/services/test_summarizer_eval.py` —
  **new** replay regression test (Phase 4b).
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/scripts/probe_summarizer.py` — optional
  interactive probe, modeled on `scripts/probe_guardrail.py` (Phase 4, never CI).

## Numbers to hold myself to

≥100 traces to start · ~20-no-new saturation · ~70% pass = stress-testing (100% = too easy) · 60–80%
of effort on analysis, not code · do **not** build a judge until Tier-A data earns it.
