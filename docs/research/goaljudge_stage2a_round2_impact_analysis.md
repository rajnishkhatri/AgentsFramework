# Stage 2a round-2 fixes — impact analysis (pre-plan)

**Date:** 2026-06-12 · **Input:** round-1 FAIL report
(`goaljudge_stage2a_shadow_round1.md`, gate-pass 22/30 = 73.3% vs ≥95%).
Scope: the four candidate fixes, each mapped to blast radius, behavior
changes, test impact, risks, and what round-1 evidence does / does not
support. No implementation decisions are final here.

## 0. What the round-1 data establishes

- **All 8 fallbacks are grounding-gate near-misses.** Per rejection, only
  1–2 conditions out of 4–6 failed (12 rejected conditions total across 8
  artifacts ≈ 70% of conditions in "failed" artifacts were fine). The whole
  artifact is discarded on any single failing condition — that is the gate
  contract (`validate_conditions` returns issues; generator raises).
- **Evidence gap:** the rejected condition *text* is not archived anywhere.
  `eval.task_understanding` carries only `fallback_reason` (gate name +
  index); `GUARDRAIL_CHECKED.issues` likewise. We therefore **cannot
  simulate** retry or salvage strategies offline against round-1 data.
  Round 2 must capture rejected conditions (see §5).
- Zero JSON-parse or transport failures in round 1 — retry scope can be
  limited to gate rejections only.

## 1. Fix A — bounded retry-with-feedback on gate rejection

### Placement decision (the load-bearing choice)

The retry policy must live in **`components/task_understanding.py`**, not in
`route_node`. Reason: the L3 nightly gate
(`tests/components/test_task_understanding_quality.py`) calls the generator
directly. If route_node owned the retry, the nightly gate would measure a
*different* policy than production — permanent drift risk. Component-owned
policy keeps test/prod parity automatically.

Constraint: the component must stay governance-free (no black_box import).
Surface the per-attempt rejection to orchestration via an injected
`on_gate_rejection(issues, attempt)` callback (same injection idiom as
LLM/prompt services); route_node passes a closure that records
`GUARDRAIL_CHECKED` per failed attempt.

### Touched surface

| File | Change |
| --- | --- |
| `components/task_understanding.py` | retry loop (bounded, max 1 retry), optional `rejection_feedback` render arg, callback seam |
| `prompts/task_understanding_prompt.j2` | `{% if rejection_feedback %}` block (H1: feedback goes through the template, never string-concat in Python) |
| `orchestration/react_loop.py` ~786–880 | call retry entrypoint; per-attempt GUARDRAIL_CHECKED via callback; new rationale variant ("generated ok after retry"); `attempts` field in `tu_ai_response` |
| `tests/components/test_task_understanding.py` | +3–4 L4 cases: reject→retry-pass, reject→retry-reject (error carries both attempts' issues), retry NOT fired on JSON/LLM errors, feedback rendered into prompt |
| `tests/orchestration/test_task_understanding_wiring.py` | **breaking:** `assert len(guardrails) == 1` (line ~236) becomes per-attempt (a double-rejection run emits 2); +1 recovered-retry case |
| `tests/components/test_task_understanding_quality.py` | switch to the retry entrypoint (policy parity) |

### Behavior / semantics changes

- **`GUARDRAIL_CHECKED` no longer implies fallback.** Today one event =
  one fallback. After the change, an event with `passed=False` may be
  followed by a recovered `source=generated` run. Add an `attempt` detail
  key so consumers can distinguish. No dashboard/export test couples to the
  old implication (checked: `test_black_box_export.py` only touches the
  Phase-4 edit path), but the round-1 analysis methodology ("GUARDRAIL
  present → fallback") must be updated for round 2.
- Latency: +1 fast-tier call, plan-time-blocking, only on rejection paths
  (27% today, expected <10% after Fix B). Bounded at exactly 1 retry — no
  while loops. Memoized per run (route_node state key), so no per-iteration
  re-fire; edit-resume never regenerates (state already carries the
  artifact).
- Cost: negligible (fast tier, rejection-path only).

### Not touched

Wire schemas (TaskUnderstanding unchanged — no Zod twin / baseline-drift
impact), frontend (card, hooks, T1/T2 specs), middleware edit endpoint,
runtime resume, GoalJudge, goldset. `test_mphase2_swap_radius` not
triggered (no services/ + agent_ui_adapter/ co-change).

### Risk

Feedback could anchor the model to re-paraphrase (it ignored the
vocabulary rule once). Quantified expectation (independence assumption,
which explicit per-condition feedback should beat):

- Retry alone at current per-run rejection p≈0.267 → pass ≈ 1−p² ≈ **92.9%
  — still FAIL**. Retry alone is insufficient.
- Prompt fix dropping p to ~0.10 + retry → ≈ **99%** — clears 95% with
  margin.

**Conclusion: Fix A and Fix B are a package; neither alone reliably clears
the gate.**

## 2. Fix B — prompt tightening (vocabulary rule made mechanical)

Replace the soft "Use the task's own vocabulary" with a checkable rule:
"every condition MUST quote at least one exact word, path, or command from
the task text" — i.e. state the gate itself in the prompt.

- **Blast radius: 1 file** (`task_understanding_prompt.j2`). No schema, no
  Python, no frontend. `test_prompt_renders_with_task_text` renders the
  template and stays green.
- **Comparability:** round-1 vs round-2 corpora were generated by different
  prompts — record the prompt file hash + commit in the round-2 report.
- Deploy note: prompts ship inside the backend image — **this is a
  redeploy, not a GCS flag flip.** Same for Fix A.
- Risk: over-literal conditions ("quote a word" satisfied by copying a
  token into an otherwise vague sentence). The gate can't catch that;
  the L3 coverage metric and 2b replay are the backstops.

## 3. Fix C — coverage-metric branch filter

Two options with very different blast radii:

**(a) Test-side filter (recommended for round 2).** In
`_covers_branches`, drop branches that are enumeration headers (ending
`:`) or have <2 content tokens. Blast radius: 1 test file. Metric-only —
production floor untouched.

**(b) Production-side filter in `_extract_branches`.** The same junk
fragments ("name them", "Compare two inputs:") today become **floor
conditions AND plan-step goals** (`build_plan_artifact` line 179–183) —
user-visible on the card in shadow mode, and they crowd the
6-condition floor cap. Fixing here improves real quality, BUT:
- changes the deterministic floor that the **2b replay gate** scores
  against — shifting the α baseline mid-experiment contaminates the
  generated-vs-deterministic comparison;
- touches `tests/components/test_plan_builder.py` expectations and plan
  fingerprints (fingerprints are per-run, cross-deploy change harmless);
- under-extraction risk: a misclassified real branch silently weakens the
  floor.

**Recommendation: (a) now; (b) as its own measured change AFTER the 2b
gate has a stable baseline.** Doing (b) now would conflate two variables
in round 2.

## 4. Fix D — confidence exclusion

**No code change required.** Verified: nothing gates on confidence today —
it only flows into the ROUTING Decision log (react_loop.py:837) and the
artifact field. Round 1 showed p50=1.0 (no signal). Action is purely
procedural: do not introduce a confidence threshold in round 2; revisit at
distillation time.

## 5. Cross-cutting round-2 protocol changes

1. **Archive rejected conditions** — add `rejected_conditions` (list) to
   `tu_ai_response` on gate rejection. Free-form dict → no schema change,
   no test breakage expected (`test_eval_telemetry` doesn't assert
   exhaustive keys). Closes the §0 evidence gap permanently and builds the
   retry-evaluation corpus.
2. **New thread namespace** `shadow-2a-r2-{00..29}` — the archived driver
   skips threads already present in its jsonl; fresh ids + fresh log file.
3. **Redeploy required** (code + prompt in image). Shadow flag stays on —
   flag and code are independent axes; no flag change needed for round 2.
4. Round-2 analysis must use the `?name=eval.task_understanding` Langfuse
   query (≥100-obs truncation) and per-attempt GUARDRAIL semantics (§1).

## 6. Alternative considered and rejected: condition salvage

Drop only the failing conditions when ≥2 survive (no extra LLM call —
round-1 near-miss data shows all 8 would have salvaged). Rejected because
the dropped condition can be the *constraint* restatement — e.g. case 26's
"use cat on the file only" is the safety-relevant item; silently deleting
a rephrased constraint produces a checklist that passes gates but no
longer encodes the task's exclusions. Retry-with-feedback preserves the
full checklist or falls back loudly. Revisit only if round 2 still misses
95%.

## 7. Expected round-2 outcome

| Change set | Expected gate-pass | Verdict |
| --- | --- | --- |
| Status quo | 73.3% | FAIL |
| Retry only | ~93% (independence bound) | borderline FAIL |
| Prompt only | unknown (no offline estimate possible) | risky |
| **Prompt + retry (package)** | ~99% if prompt halves rejections | **expected PASS** |

Coverage metric after Fix C(a): the 6 known noise misses reclassify;
expected ≥80% on the remaining genuine multi-branch rows (manual
inspection of round-1 misses 05/07/08/11/15/23 already showed full
sub-step coverage).
