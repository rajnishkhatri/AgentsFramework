# Add an eval probe to `services/summarizer.py`

Short version: this seam should ship a **Tier-A probe and stop there** — a 100%-coverage
deterministic L1 check plus one frozen offline CI regression row. The reason is load-bearing and
I confirmed it in the code: **the summarizer has no model in it.** `build_compaction_summary` is
pure string-slicing, so there is nothing for an LLM judge to grade. Per the skill's Phase 1 rule
for deterministic seams, the failure modes here are **truncation / omission**, not hallucination,
and the seam stops at Tier-A — like the Guardrails exemplar, never the GoalJudge judge track.

The monitoring spine already exists (`eval_capture`, `eval_telemetry`, `meta/run_eval`,
`guardrail_validator` as the L1 template). The job is to **register this seam into it**, not build
new infrastructure.

---

## What I found in the repo (grounding)

- **The seam is deterministic.** `services/summarizer.py` exposes
  `build_compaction_summary(*, task_input, reasoning_trace, tool_results, latest_output) -> str`
  and `should_compact_trajectory(...)`. The summary is built by slicing: `reasoning_trace[-3:]`,
  per-entry `[:120]`, `latest_output[:280]`, `task_input[:200]`, recent tool names `[-3:]`. No
  LLM call. (`services/summarizer.py:14-39`)
- **It is wired into orchestration here:** `orchestration/react_loop.py:1491-1505`. Inside the
  `if should_compact_trajectory(...)` block, `summary_text = build_compaction_summary(...)` is
  built (`:1495`), then the trajectory is **replaced**: `result["reasoning_trace"] = [summary_text]`
  and `result["truncation_applied"] = True` (`:1504-1505`).
- **The seam is rarely fired.** Compaction only triggers under token pressure
  (`token_count >= trajectory_compaction_token_threshold`). So "100% of traffic" for this probe
  means **100% of compaction events**, not 100% of agent turns — state that explicitly so we don't
  overstate monitoring breadth.
- **It is monitored nowhere today.** No `eval_capture.record` call exists for it; the only
  references are the two unit tests in `tests/services/test_reasoning_tools.py`. So this is a true
  greenfield probe.
- **Primitives to reuse, confirmed present:**
  - L1 check template: `services/governance/guardrail_validator.py` (`ValidationResult`,
    `GuardRailValidator.validate(content) -> list[ValidationResult]`).
  - Recording write: `services/eval_capture.py` `record(target=…, ai_input=…, ai_response=…, config=…)`.
  - Langfuse sink: `services/eval_telemetry.py` `publish_task_understanding(...)` (the mirror
    target) + `observation_name_for_target(target)` which produces `eval.<target>`.
  - Offline scorer: `meta/run_eval.py` (`--golden-set / --output / --report-id`).
  - Frozen-benchmark shape: `tests/fixtures/task_understanding/gate_benchmark_v1.json`
    (`_meta` with `source_sha256` + `deploy`, then `must_accept` / `must_reject` arrays).

**Target name decision (lock it now):** use **`trajectory_summarizer`** as the stable
`target=` / probe key (the seam is trajectory compaction, not generic summarization). Document it
in the benchmark `_meta` before first deploy so the records, the `eval.trajectory_summarizer`
observation, and the fixture all agree.

---

## Phase 0 — Decide whether this seam deserves the budget (do not skip)

Do not commit scarce eval effort on "the output replaces `reasoning_trace`, so it's obviously
high-harm." That is a *hypothesis*, not a counted cell. Run the transition failure matrix by hand
first — even a thin, directional pass is worth it.

- The state enum is the real `WorkflowPhase` (`services/governance/phase_logger.py`), logged to
  `phases.jsonl` — zero new instrumentation. Use the **graph execution order**
  (`guard_input → route → call_llm → execute_tool → evaluate`), not the enum declaration order.
- Build rows = last clean state, columns = first-failure state, cell = count. **Re-attribute the
  terminal "completion/evaluation" sink** to its true origin using existing first-failure signals
  (`synthesis_validator`, `guardrail_validator`, `goal_judge goal_met=false`) before reading the
  top cell.
- Find the log and hand-aggregate:

  ```bash
  ls phases.jsonl 2>/dev/null || find . -name "phases.jsonl" | head
  ```

**Honest caveat for this seam:** compaction fires only under token pressure, so it will have
*thin* representation in the matrix and may not be the top cell. If it isn't, the correct outcome
is **scope this to a shadow-only Tier-A probe** (capture + offline benchmark, low priority) rather
than racing it ahead of a higher-count seam. Done when you can point at a counted cell (or
explicitly record "thin data, shadow-only justified"), not a harm story.

---

## Phase 1 — Pick the seam + altitude, and wire Recording

**Real seam:** `build_compaction_summary` in `services/summarizer.py`, invoked at
`orchestration/react_loop.py:1495`. It *is* the decision point (deterministic, but it rewrites the
agent's working memory), so it's the right thing to score.

**Altitude: span.** One sentence: each compaction call's failure is fully visible from that one
call's inputs (`task_input`, `reasoning_trace`, `tool_results`, `latest_output`) and its output
summary — no trajectory replay needed — so it is span, not trace.

**Wire Recording with a scoring-complete payload.** Capture the *full* inputs the offline scorer
needs, not just lengths — within the 8192-char `eval.*` exemption. The insertion point matters:
fire it **after** the trajectory replacement (`:1504-1505`), so the captured `ai_input` matches
what was actually compacted, and use `state.get("step_count", 0)` for `step` (`updated_step_count`
isn't defined until `:1507`).

```python
# orchestration/react_loop.py — inside the should_compact_trajectory block,
# AFTER result["reasoning_trace"] = [summary_text] / result["truncation_applied"] = True (~:1505)
from services import eval_capture, eval_telemetry
from services.summarizer_eval import probe_trajectory_summary  # new L1 check (Phase 4)

probe_results = probe_trajectory_summary(
    task_input=state.get("task_input", ""),
    reasoning_trace=state.get("reasoning_trace", []),   # the PRE-replacement source
    tool_results=state.get("tool_results", []),
    latest_output=content,
    summary_text=summary_text,
)
eval_input = {
    "task_input": state.get("task_input", ""),
    "reasoning_trace": state.get("reasoning_trace", []),
    "tool_results": state.get("tool_results", []),
    "latest_output": content,
}
eval_response = {
    "summary_text": summary_text,
    "probe_results": [r.model_dump() for r in probe_results],   # per-category ValidationResults
}
await eval_capture.record(
    target="trajectory_summarizer",
    ai_input=eval_input,
    ai_response=eval_response,
    config=config,
    step=state.get("step_count", 0),
)
await eval_telemetry.publish_trajectory_summarizer(   # new sink method, Phase 4
    trace_id=..., user_id=..., task_id=...,
    ai_input=eval_input, ai_response=eval_response, step=state.get("step_count", 0), model=None,
)
```

> Note the ordering subtlety: capture the `reasoning_trace` from `state` (the pre-replacement
> source the summary was built from) for `ai_input`; the *output* you score is `summary_text`. If
> you read `result["reasoning_trace"]` you'd capture `[summary_text]` and the scorer would have
> nothing to compare against.

**Done when:** seam named, altitude (span) defended in a sentence, Recording wired with a
scoring-complete payload, and `eval.trajectory_summarizer` records visible in telemetry.

---

## Phase 2 — Open coding (read traces, label first-failures) — the 60–80%

This is the phase to actually spend on. **Write evaluators only for failures you observe**, never
for the producer's contract.

1. Pull **≥100 compaction events.** Volume will be low (token-pressure only), so harvest real ones
   from `eval.trajectory_summarizer` records / Cloud Logging, then **synthesize the tail** along
   the seam's natural truncation dimensions (long traces > 3 entries; a critical fact in
   `trace[-4]`; `latest_output` whose load-bearing content is past char 280; `task_input` whose
   distinguishing content is in chars 61–200; 10k-char tool results). Reference-grade, not gospel.
2. For each, label the **first** thing the summary gets wrong, in free text. Don't pre-categorize.
3. Use the Three Gulfs as the *why* lens, specialized to this seam:
   - **Comprehension** — load-bearing context dropped: it lived in `reasoning_trace[:-3]` (the
     `[-3:]` slice) or past the `[:120]`/`[:280]`/`[:200]` per-field caps.
   - **Specification** — the four-section contract is the *wrong* compaction (e.g. tool *names*
     kept but the result payload that mattered is gone).
   - **Generalization** — fine on short traces, corrupts working memory on the long ones that
     actually trigger compaction.
4. **Stop rule:** ~20 consecutive traces with no new category (saturation).

**Purity guard:** the dominant failure is almost certainly the `[-3:]` slice silently dropping an
earlier load-bearing entry — but treat that as a **falsifiable hypothesis written in a sidebar**,
not a pre-committed category. Let the traces confirm or kill it. Sanity band: if ~100% pass, your
sample is too easy; a seam worth probing sits near ~70% pass under genuine stress.

**Done when:** ~100+ events read, every failure has a first-failure note, ~20 in a row with nothing new.

---

## Phase 3 — Axial coding → a binary, testable taxonomy

Let an LLM propose clusters over your notes; **you** rename and merge. Aim for 5–6 categories, each
**binary** (present/absent, never 1–5 Likert), distinguishable, and testable from the trace alone.
Avoid generic "quality"/"faithfulness-with-no-definition" — every category must mean something
specific to *this* compaction seam. A likely (post-observation) shape:

- `dropped_load_bearing_trace_entry` — a fact present only in `reasoning_trace[:-3]` is absent from
  the summary.
- `latest_output_tail_lost` — content past char 280 of `latest_output` that changed the answer is
  gone.
- `task_intent_truncated` — the distinguishing part of `task_input` was past char 200.
- `tool_result_payload_lost` — the tool that mattered was kept by name but its result is unrecoverable.
- `empty_or_degenerate_summary` — empty / all-`none` / `(empty)` summary.

Write the taxonomy down as the seam's source of truth (the same place `meta/judge.py`
`load_taxonomy()` would read, if a judge were ever earned — it won't be here).

**Done when:** 5–6 binary evidence-grounded categories exist and traces are re-labeled against them.

---

## Phase 4 — Ship the Tier-A probe ★ (the milestone)

**4a. The L1 check** — a pure function, `services/summarizer_eval.py`, modeled on
`guardrail_validator.py`. It must:

- Import **stdlib + pydantic only** — no `components`, no `langgraph`, no `langchain`. Verify:
  ```bash
  grep -nE "from components|import langgraph|import langchain" services/summarizer_eval.py   # must print nothing
  ```
- Return **per-category** `ValidationResult`s (reuse the existing shape from
  `guardrail_validator`), **not a single 0–1 score** — drift on a *named* category is the signal
  we act on.
- Implement the **deterministically detectable** subset of the taxonomy. Crucially, **align the
  scorer's windows to the producer's** (`[-3:]`, `[:120]`, `[:280]`, `[:200]`) — otherwise the
  check is tautological (it would just re-assert what the producer always emits). The valuable
  check is **dropped-span coverage**: of the load-bearing tokens in the *full* source
  (`reasoning_trace`, `latest_output`, `task_input`), how many survived into `summary_text`?
  Worked sketch:

  ```python
  def probe_trajectory_summary(*, task_input, reasoning_trace, tool_results,
                               latest_output, summary_text) -> list[ValidationResult]:
      # dropped_load_bearing_trace_entry: a non-empty entry in reasoning_trace[:-3]
      # whose key tokens never appear in summary_text -> FAIL (the [-3:] slice dropped it)
      # latest_output_tail_lost: tokens in latest_output[280:] missing from summary -> FAIL
      # task_intent_truncated: tokens in task_input[200:] missing from summary -> FAIL
      # empty_or_degenerate_summary: summary empty / all-"none" / "(empty)" -> FAIL
      ...
  ```

  Edge cases to cover in the check: entries shorter than the window; duplicate tokens; tool result
  payloads up to ~10k chars; unicode-normalized token matching.

**4b. Publish it** — a pure check nothing calls is dead code, and a record that the Langfuse sink
can't see fails Done-when. Add `publish_trajectory_summarizer(...)` in `services/eval_telemetry.py`
**mirroring `publish_task_understanding`** (must never raise — wrap in try/except and log; it's the
O1 contract) plus its sink adapter, so the `eval.trajectory_summarizer` observation lands on the
trace and `governance-trace-audit` can see it. `observation_name_for_target("trajectory_summarizer")`
already yields `eval.trajectory_summarizer` — no change needed there.

**Layer discipline:** L1 check + the `publish_*` glue → `services/`. Any future judge → `components/`
(won't happen here). Live replay → `scripts/`/`meta/`, **never CI**.

**4c. The offline CI regression row.** Freeze the Phase-2 failures as
`tests/fixtures/summarizer/summarizer_benchmark_v1.json`, following the
`gate_benchmark_v1.json` pattern: a `_meta` block (`name`, `built`, `source`, `source_sha256`,
`deploy`, and the `target: trajectory_summarizer` decision), then `must_accept` (faithful
compactions) and `must_reject` (each Phase-2 failure: the trace where `trace[-4]` held the
load-bearing fact, the >280-char `latest_output` tail, etc.). Score it deterministically:

```bash
python -m meta.run_eval \
  --golden-set tests/fixtures/summarizer/summarizer_benchmark_v1.json \
  --output /tmp/trajectory_summarizer_report.json \
  --report-id trajectory_summarizer-tierA
```

Add `tests/services/test_summarizer_eval.py`: a **replay test** that runs the L1 check over the
frozen fixture and asserts every `must_reject` fails its category and every `must_accept` passes —
this is the PR-blocking regression. (The `meta.run_eval` invocation above is the ops/CI scoring
harness; the pytest replay is what gates the merge.)

**Done when:**
- [ ] L1 check is a pure function in `services/summarizer_eval.py`, no framework imports, returns **per-category** `ValidationResult`s
- [ ] Invoked in `react_loop.py` after `:1505` (post trajectory-replacement) on **100% of compaction events**; results in `ai_response.probe_results` and recorded via `eval_capture.record(target="trajectory_summarizer")`
- [ ] Published through `publish_trajectory_summarizer` so the `eval.trajectory_summarizer` observation lands on the trace
- [ ] `tests/fixtures/summarizer/summarizer_benchmark_v1.json` (must_accept / must_reject) holds the Phase-2 failures, `target` documented in `_meta`
- [ ] `test_summarizer_eval.py` replay asserts the fixture scores green in CI; `meta.run_eval` runs clean
- [ ] You did **not** build a judge
- [ ] Coverage stated honestly: "100% of traffic" = 100% of compaction events (token-pressure only)

---

## Phases 5–7 — deliberately deferred (this seam stops at Tier-A)

There is **no model in this seam**, so there is nothing for an LLM judge to grade — the gold-set /
IAA / TPR-TNR / θ̂ / enable-gate track does not apply. Building one would manufacture false
confidence, the exact anti-pattern the canon warns against. This is the **Guardrails outcome**: a
cheap deterministic check on 100% of (compaction) traffic, a frozen benchmark, no judge.

The one piece of the loop that **does** apply, lightweight:

- **Change-event hook.** If anyone edits the truncation budgets in `build_compaction_summary`
  (`[-3:]`, `[:120]`, `[:280]`, `[:200]`) or `trajectory_compaction_token_threshold`, re-run the
  offline probe immediately — those edits directly move the failure surface this probe watches.
- **(Optional) L3 drift later.** If, after Tier-A shadow data, the per-category fail-rate is worth
  watching continuously, register the `eval.trajectory_summarizer` stream into `meta/drift.py`
  (`python -m meta.drift --baseline … --production … --level 1`). Threshold on the per-category
  binary fail-rate, never a scalar. This is on-demand, not day one.

---

## Concrete file list (absolute paths)

Touch / create:
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/summarizer_eval.py` — **new** L1 pure check (`probe_trajectory_summary` → `list[ValidationResult]`)
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/orchestration/react_loop.py` — invoke the check + `eval_capture.record` + publish, **after line 1505**
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/eval_telemetry.py` — **add** `publish_trajectory_summarizer(...)` mirroring `publish_task_understanding` (`:138`) + sink adapter
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/tests/fixtures/summarizer/summarizer_benchmark_v1.json` — **new** frozen must_accept / must_reject benchmark
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/tests/services/test_summarizer_eval.py` — **new** CI replay/regression test

Reuse / read (do not modify):
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/summarizer.py` — the seam (`:14-39`)
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/governance/guardrail_validator.py` — L1 + `ValidationResult` template
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/eval_capture.py` — `record(target=…)`
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/governance/phase_logger.py` — `WorkflowPhase` for the Phase-0 matrix
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/meta/run_eval.py` — offline scorer
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/tests/fixtures/task_understanding/gate_benchmark_v1.json` — benchmark `_meta` + must_accept/must_reject shape to copy

Optional:
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/scripts/probe_summarizer.py` — ad-hoc local replay harness (lives in `scripts/`, **never CI**), modeled on `scripts/probe_guardrail.py`

---

## The one rule, applied

Open coding (Phase 2) strictly precedes the rubric (Phase 4a). If you find yourself coding the
check before reading ~100 compaction traces, stop — you'll encode the producer's `[-3:]` contract
and ship a tautological probe that passes every happy-path summary. The 60–80% of the work is
reading the traces and building the taxonomy; the L1 check is the cheap part at the end.
