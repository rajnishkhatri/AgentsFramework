# `agentsframework-eval-probe` — Trigger Prompt Examples

How to phrase a request so the [`agentsframework-eval-probe`](agentsframework-eval-probe/SKILL.md)
skill fires (and how to phrase one so it stays out of the way). The skill walks any LLM-call seam
in this repo from open coding → taxonomy → rubric → judge → a registered probe (L1 deterministic /
L2 sampled judge / L3 drift / offline CI regression / per-component enable-gate), Tier-A first.

> **Read this first — the one thing that actually changes triggering.** In an *agentic* client
> (Claude Code / Cursor), a model only consults a skill for work it can't already start on its own.
> If your prompt names exact files (`services/summarizer.py`, `select_planning_depth`), the model
> tends to just dive into the code — so **lead with the goal, not the file path**. State the
> outcome ("catch this in CI", "monitor this over time", "freeze this failure as a test") and let
> the skill supply the how. Naming the component is fine; opening with a file path is what suppresses
> the trigger. (This was measured — see *Why some good prompts don't trigger* below.)

---

## ✅ Prompts that SHOULD trigger the skill

Copy/adapt these. Each is a real intent the skill is built for. You do **not** need to say the word
"probe" — naming the component or the outcome is enough.

### Add a probe / instrument a seam
- "we keep finding the summarizer drops half the action items when it compacts a long thread. i want
  to **catch this in CI** instead of noticing it three weeks later in prod — can you set up some kind
  of eval so a regression like that fails the build?"
- "ok next seam i want to **instrument for evaluation** is the router. it keeps picking shallow
  planning when the task is obviously multi-step. walk me through **adding a probe** for it."
- "add an eval probe to the tool-execution step."
- "**monitor this component** — the output-validation phase — so we can score how often it actually
  catches a bad generation vs lets one through, and watch that number over time."

### Turn captured traces into a scored eval
- "i added `eval_capture.record` to the tool-execution node last week and the traces are showing up
  in langfuse. **now what** — how do i turn that captured data into an actual scored eval that runs
  on a schedule and tells me when it drifts?"

### Regression gate from a production failure
- "we shipped a fix for the goal-judge false-downgrade bug and now i want a **benchmark that freezes
  the failures** we found so they can never regress silently — like a must-accept / must-reject
  fixture that pytest runs."
- "**close the loop** between production failures and our regression tests for the synthesis
  component: when QA flags a bad output i want a clean path from 'open-code that failure' to 'it's
  now a permanent test case'."

### Build a rubric / judge
- "**build a rubric + judge** for the plan_builder output quality. it's a trace-level thing i
  think, since whether the plan was good depends on the whole run, not one span. where do i start?"

### Drift detection
- "**wire up drift detection** for the guardrail validator so we get an alert when the PII / api-key
  catch rate starts sliding. is there already a drift harness in this repo i can lean on?"

### Continuous monitoring (lightweight first)
- "**add continuous monitoring** to the model-invocation seam. i don't want a full gold-set
  calibration project right now — just something lightweight that runs 100% deterministic checks
  first, and we earn the judge later if we need it."

### Pick the next thing to evaluate
- "**which component** in the agent pipeline should we put an evaluation on next? we have limited
  time and i don't want to just guess based on vibes."

---

## 🚫 Prompts that should NOT trigger it (route elsewhere)

These share vocabulary (eval, judge, drift, calibration, trace, regression) but belong to a
different skill or to plain coding. They're listed so you know where intent actually goes.

| Prompt | Why not this skill | Goes to |
| --- | --- | --- |
| "we're ready to flip `goal_judge_downgrade_enabled` to true in prod — walk me through the §2.8 calibration sign-off and the runtime-config write." | GoalJudge-specific calibration **flip path** | `agentsframework-eval` |
| "here's a langfuse trace JSON dump — audit it against the four governance pillars and tell me if it's telling the truth." | Auditing an existing **trace** | `governance-trace-audit` |
| "review the latest production traces from the goaljudge batch — confirm the recording/identity/validation/reasoning pillars look right." | Per-pillar trace **review** | `governance-trace-audit` |
| "i'm writing a generic, provider-agnostic guide on doing LLM evals from scratch — open coding, gold sets, judge calibration." | **Generic methodology**, not this repo | `llm-eval-grounded-theory` |
| "explain how llm-as-a-judge calibration works in general — κ vs accuracy, why TPR/TNR on a held-out set matters." | Conceptual explainer | (answer directly / `llm-eval-grounded-theory`) |
| "the goaljudge gold set is still v0.9 provisional and returns `REFUSE_PROVISIONAL` — what do we do to reach v1?" | Gold-set **lifecycle**, not adding a probe | `agentsframework-eval` |
| "our p99 latency on /chat jumped to 2.1s — set up a Grafana alert + prometheus histograms." | **Perf** monitoring, not eval quality | plain ops/coding |
| "`test_summarizer.py` is flaky — find the race condition and stabilize it." | Fixing a flaky **unit test** | plain coding |
| "refactor `eval_capture.py` — `record()` has too many kwargs, dedupe the trace_id plumbing." | **Refactor**, no eval being added | plain coding |
| "add a unit test for `validate_plan_mece` that rejects overlapping subtasks — just a normal pytest." | Ordinary unit test, no probe/monitoring | plain coding |

---

## Why some *good* prompts don't trigger (measured, not theoretical)

We ran the skill-creator description-optimization loop (`scripts.run_loop`) over the 20 prompts
above (10 should-trigger, 10 near-miss negatives). **Every should-trigger prompt scored 0 triggers**
across 5 iterations — including a hand-tuned, maximally on-the-nose description.

A raw `claude -p --output-format stream-json` capture explained why: given a file-grounded prompt
("…add a probe for `select_planning_depth`…"), the model immediately fired `Glob` / `Grep` / `Read`
on the **actual repo code** and started the task — *"I'll help you add a probe… let me first explore
the codebase…"* — and **never emitted a `Skill` tool call**. The skill triggering machinery
correctly saw no trigger, because the model chose to just do the work.

**Takeaways:**
- This is a **methodology limit of the trigger loop on agentic, file-naming prompts** — not a defect
  in the skill. The loop is designed for tool-less Claude.ai prompts ("convert this xlsx").
- The skill's **content** is what was validated (with-skill **95.8%** vs no-skill baseline **66.4%**
  over the plan_builder / summarizer / seam-prioritizer seams).
- To maximize the chance the skill *is* consulted, **open with the goal, not a file path** (see the
  callout at the top).

---

## See also

- Skill: [`agentsframework-eval-probe/SKILL.md`](agentsframework-eval-probe/SKILL.md) ·
  [`reference.md`](agentsframework-eval-probe/reference.md) ·
  [`commands.md`](agentsframework-eval-probe/commands.md) ·
  [`examples.md`](agentsframework-eval-probe/examples.md)
- Engineer walkthrough: [`docs/handbooks/add_an_eval_probe.md`](../handbooks/add_an_eval_probe.md)
- Generic methodology (provider-agnostic): [`llm-eval-grounded-theory/SKILL.md`](llm-eval-grounded-theory/SKILL.md)
- Source eval set used above: [`agentsframework-eval-probe-workspace/trigger_eval.json`](agentsframework-eval-probe-workspace/trigger_eval.json)
