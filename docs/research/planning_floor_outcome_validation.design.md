# Validating the planning floor against outcomes — experiment design

**Status:** experiment-design note — **2026-06-17**. **Tier 1 has since been EXECUTED** (84 fast-tier calls; results in [`planning_floor_outcome_validation.tier1_results.md`](planning_floor_outcome_validation.tier1_results.md)). Tier 2 remains **plan-only — no deploy, no prod code change** until explicitly greenlit.
**Question:** Does the deterministic floor's *depth decision* actually matter for outcomes — specifically, would firing **L2 instead of L1** on the 4 `l2-under-promote` prompts produce a measurably better result? And which judge (**GoalJudge / Evaluator / TaskUnderstanding**) is the right instrument to answer it?
**Companion to:** [`planning_floor_baseline_walkthrough.md`](planning_floor_baseline_walkthrough.md) (the 59-row deterministic baseline), [`planning_floor_deterministic_options_tradeoff.md`](planning_floor_deterministic_options_tradeoff.md) (the option menu this would inform).
**Verdict (one line):** Run the **offline TaskUnderstanding tier first** — it answers the question deterministically-enough, cheaply, and without the confound. Only escalate to the **live GoalJudge A/B** if Tier 1 is inconclusive, because the A/B needs a production code change + deploy + an N× token budget.

---

## 1. Why GoalJudge alone is the wrong first instrument

GoalJudge (`components/goal_judge.py`) is reference-free and scores a **completed run**: `evaluate(task_input, final_answer, success_conditions, evidence) -> GoalVerdict`. The 59-row floor corpus has **no `final_answer` and no `evidence`** — nothing executed. So GoalJudge cannot score the corpus as-is; it needs live agent runs first.

Even with live runs, GoalJudge measures the wrong thing for *this* question:

- It sits **far downstream** (depth → plan → execution → answer); answer quality is dominated by model/tool behavior, not the depth budget.
- Its verdict is an **LLM** call — non-deterministic; your own stress-harness experience (trace-id superposition; re-*running* the batch jitters, only re-*scoring* is stable) means a single pass is noisy and a real signal needs N reruns per arm.
- By layering contract it **never touches depth** — it overlays `goal_met` onto `TaskOutcome` and "NEVER changes `outcome`." Depth is decided upstream of anything it sees.

So GoalJudge can confirm *"deeper planning → better answers"* end-to-end, but only via an expensive, confounded experiment. Use it as **confirmation**, not first probe.

## 2. The three candidate instruments, ranked for this question

| Instrument | Scores | Distance from depth | Deterministic | Cost to apply |
|------------|--------|---------------------|---------------|---------------|
| **TaskUnderstanding** (`components/task_understanding.py`) | `TaskUnderstanding.success_conditions: list[str]` — a pre-registered task checklist (`_MIN_CONDITIONS=2 .. _MAX_CONDITIONS=7`), generated at plan time **before acting**, independent of fired depth | **closest** — its length is a proxy for the task's *true* subtask count | LLM to generate **once**, then capturable to a fixture (free to re-score) | ~20 fast-tier calls, **no deploy** |
| **Evaluator** (`evaluate_task_outcome`) | `branch_coverage` = answer-vs-**plan-steps** keyword overlap; `criteria_met` vs success_conditions | medium — but plan steps are **already depth-capped**, so it **circularly assumes the fired depth was right** | yes (keyword) | needs a final_answer (a run) |
| **GoalJudge** | answer satisfies goal | far downstream | no (LLM) | live runs + N reruns |

**The TaskUnderstanding insight (this is the design's core).** Depth selection's job is to budget enough steps (caps L0=1 / L1=3 / L2=5) to cover the task's real subtasks. TaskUnderstanding generates the task's real checklist **independent of the fired depth**. Therefore:

> **Under-planning signal (offline):** for a prompt, if `len(TaskUnderstanding.success_conditions)` exceeds the **fired depth's step cap**, the floor budgeted fewer steps than the task provably needs — a direct, causal under-planning signal, with no agent run and no answer-quality noise.

On a `depth-l2-trap` prompt that fires **L1 (cap 3)**: if TaskUnderstanding returns a **4–5 item** list, that is the floor under-budgeting, demonstrated deterministically. That is exactly the thing the live A/B is trying to prove — obtained far more cheaply.

**Two caveats on the signal.** (a) `success_conditions` is **capped at 7** and **floored at 2**, so it can confirm "needs more than L1's 3" but saturates above 7 — fine for the L1-vs-L2 question, not for distinguishing very-deep tasks. (b) the generated list always appends a **generic tail condition** (`GENERIC_TAIL_CONDITION`, shared with the floor); subtract it (or the 1 generic item) before comparing to the step cap, exactly as `derive_success_conditions` adds it — otherwise every count is inflated by one.

The Evaluator is explicitly **not** a good probe here: `branch_coverage` compares the answer to the *already-truncated* plan, so a perfectly-covered L1 plan scores 1.0 even when the task needed L2. It bakes in the assumption under test.

---

## 3. Tier 1 (recommended first) — offline TaskUnderstanding vs. depth-cap

**Goal:** answer "does the floor under-budget steps on the trap prompts?" deterministically, no deploy.

**Scope:** the ~20 distinctive **depth-surface** prompts (the 4 L2-traps + L0/L1/L2 representatives + the 11 oracle rows). MECE/replan/conditions rows are excluded (no agent-executable form).

**Method:**
1. For each prompt, capture `TaskUnderstanding.generate(...)` output **once** to a fixture (`cache/goaljudge_eval/planning_floor_understanding.jsonl`) — the only LLM spend in Tier 1, ~20 fast-tier calls. Re-scoring is then free and deterministic.
2. Compute, per prompt: `fired_depth` (from `select_planning_depth`), `cap = {L0:1,L1:3,L2:5}[fired_depth]`, `checklist_len`, and `want_depth_cap`.
3. **Signal:** `under_budgeted = checklist_len > cap`. **Expected-divergence:** rows where `want_depth != fired_depth` should show `checklist_len > fired_cap` and `<= want_cap`.

**Pass/interpretation (calibration, not gate):**
- If the 4 L2-traps show `checklist_len ∈ {4,5}` while fired L1 cap = 3 → **floor under-plans, confirmed offline.** Strengthens the Option A `distinct_marker_count>=3 -> L2` case from the walkthrough's root-cause note; the live A/B becomes optional.
- If checklists come back ≤3 on the traps → the prompts may genuinely be L1-sized; **revisit the `want_depth=L2` labels** (a finding about our corpus, not the floor).

**Build:** new `scripts/diagnose_understanding_vs_depth.py` (captures fixture on first run, re-scores thereafter) + the fixture. Reuses `TaskUnderstandingGenerator` + `select_planning_depth`. Honesty guard: TaskUnderstanding is itself an LLM artifact, so capture **3 samples per prompt** and record checklist-length variance; a 1-item swing that flips the verdict must be flagged, not hidden.

---

## 4. Tier 2 (only if Tier 1 inconclusive) — live GoalJudge A/B with depth override

**Goal:** causal end-to-end proof that firing L2 produces better answers than L1 on the trap prompts.

**The confound and the fix.** A naive live run of `depth-l2-trap-1` fires L1 — you only observe "L1 → outcome," never the L2 counterfactual, and cross-prompt correlation is confounded by prompt difficulty. A clean test requires the **same prompt at both depths** → a **depth-override hook**, which does not exist today (`react_loop.py:837-905` takes depth only from `select_planning_depth` or the memoized state).

**Required code change (test-only, additive, revertible):**
- New env knob, e.g. `PLANNING_DEPTH_FORCE` (read at the `route_node` depth-selection site, `react_loop.py:~857`). When set to `L0|L1|L2`, it overrides the fired depth **and** records a `depth_forced` carrier on `STEP_PLANNED` so the analyzer can label the arm. Unset = production behavior (default OFF, like `T3_FANOUT_ENABLED`).
- Layer note: the override belongs in the **orchestration node** reading config, not in `select_planning_depth` (which stays a pure component — LP/OBP clean).

**Design:**
- **Arms:** each distinctive prompt run at `fired_depth` (control) and `want_depth` (treatment). For the 4 traps that is L1 vs L2.
- **N:** ≥5 reruns per arm (GoalJudge jitter); use **fresh trace_id per run** + `ui_batch.jsonl` rotation (the superposition guard — non-negotiable per prior stress findings).
- **Scoring:** GoalJudge `goal_met` / `partial_fraction` per run; paired comparison (treatment − control) per prompt; report effect size + variance, not a single number.
- **Harness reuse:** `scripts/build_planning_stress_corpus.py` (add a depth-AB family emitting both arms) + `scripts/analyze_planning_traces.py` (`_fired_depth`, `goal_met` extraction already exist; add `depth_forced` arm-labelling to `score_run`).

**Cost (must be approved before running):** 1 stress Cloud-Run revision (prod untouched, `--tag stress --no-traffic`), ~`20 prompts × 2 arms × 5 reruns = ~200 agent runs` × (planning + execution + GoalJudge) fast-tier tokens, plus Playwright wall-clock. Tear down tags after (per deploy-gcp runbook).

---

## 5. Recommendation

1. **Build & run Tier 1 first.** It is cheap (~20 fast-tier calls, no deploy), deterministic on re-score, and directly measures under-budgeting via the checklist-length-vs-cap signal — the right instrument because TaskUnderstanding is depth-independent.
2. **Treat the Evaluator as unsuitable** for this question (circular: branch_coverage assumes the fired depth).
3. **Escalate to Tier 2 (live GoalJudge A/B) only if** Tier 1 is ambiguous or a stakeholder needs end-to-end proof — and only after the `PLANNING_DEPTH_FORCE` hook + cost are explicitly approved.
4. Whatever the result, fold it back into [`planning_floor_deterministic_options_tradeoff.md`](planning_floor_deterministic_options_tradeoff.md) §7: Tier 1 confirming under-budgeting raises Option A's depth-rule ROI; Tier 1 clearing the floor strengthens the "do-nothing on depth, build Option C (evidence)" recommendation.

---

## 6. Open decisions

| ID | Question | Recommendation |
|----|----------|----------------|
| VD-1 | Run Tier 1 now (small LLM spend to capture checklists)? | **DONE 2026-06-17** — ran `--capture --samples 3` (84 calls). Results + caveats in [`planning_floor_outcome_validation.tier1_results.md`](planning_floor_outcome_validation.tier1_results.md): 3/4 traps corroborate under-budgeting, but checklist over-reads cap by a constant so it is supporting (not causal) evidence. |
| VD-2 | Build the `PLANNING_DEPTH_FORCE` hook now or defer to Tier 2 trigger? | Defer — only build if Tier 2 is greenlit (avoids a prod code change we may not need). Tier 1 is corroborating but not decisive; escalation is a stakeholder call. |
| VD-3 | TaskUnderstanding LLM non-determinism in Tier 1 | **Applied** — 3 samples/prompt; the guard surfaced 3 boundary verdict-flips a single sample would have hidden (results §2b). |

*Design only. No implementation, deploy, or token spend is implied until a plan references §3 (Tier 1) or §4 (Tier 2) explicitly.*
