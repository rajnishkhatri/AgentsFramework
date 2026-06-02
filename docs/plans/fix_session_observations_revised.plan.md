---
name: Fix Session Observations Revised
overview: "Revised Stage-1 fix set after feasibility review: ship the real redaction bug fix, rescope the scorer fix to deterministic-safe coherence plus judge-conditional gating (no keyword-overlap gating), gate the suppression precheck behind FP tests, and redesign the loop-termination fix around a clean return contract that preserves two-tier escalation."
todos:
  - id: fix-redaction
    content: Broaden api_key.openai regex in services/governance/guardrail_validator.py to catch sk-/sk-proj- short keys; add sk-proj-abc123456789 case to TestRedactAPIKeys in test_black_box_publisher.py; confirm _SAFE_NUMERIC_KEYS unaffected
    status: pending
  - id: fix-scorer-coherence
    content: Add pure _assert_score_coherence helper (structural invariants, log-and-clamp runtime / hard-assert tests) and telemetry-only coherence note in components/evaluator.py; do NOT fold branch_coverage with unmet_conditions
    status: pending
  - id: fix-scorer-gate
    content: Apply success->partial gate ONLY on judge-sourced goal_met=False in orchestration/react_loop.py after GoalJudge overlay (~line 1266); keep evaluate_task_outcome heuristic path decoupled
    status: pending
  - id: fix-scorer-tests
    content: KEEP test_goal_met_does_not_change_outcome; add test_judge_false_goal_downgrades_success (mocked GoalJudge) + _assert_score_coherence invariant tests
    status: pending
  - id: fix-suppression
    content: Add suppression_marker DEFER stage before clean_short in services/guardrails.py precheck_input; add suppression-phrase DEFER tests + benign retry-until ACCEPT controls + the Step-4 prompt as an explicit now-DEFER case in test_guardrails.py
    status: pending
  - id: fix-loop
    content: Add pure count_trailing_identical + count_trailing_failures to components/evaluator.py (leave count_trailing_repeats unchanged); add no_progress_identical_threshold to base_config.py; thread new counts into check_continuation + 3 react_loop callsites preserving directive-before-hardstop ordering; add tests in test_no_progress.py
    status: pending
  - id: validate
    content: Run pytest tests/ -q and pytest tests/architecture/ -q; confirm sk-proj-abc123456789 redacts and Step-4 impossible-task still halts after the new DEFER
    status: pending
isProject: false
---

## Revised Fix Session Observations

Feasibility review changed four things vs the original plan: Fix 1 ships as-is; Fix 2 drops keyword-overlap outcome gating and instead adds deterministic coherence invariants + judge-conditional gating; Fix 3 proceeds only with explicit FP controls; Fix 4 is redesigned around the single-int return contract of `count_trailing_repeats`.

### Why the changes (evidence)

- The default `goal_met` is keyword overlap and is **deliberately decoupled** from `outcome`: `[components/evaluator.py](components/evaluator.py)` lines 288-291, schema docstring `[components/schemas.py](components/schemas.py)` lines 82-84 ("NEVER changes outcome"), and a passing invariant test `test_goal_met_does_not_change_outcome` at `[tests/components/test_evaluator.py](tests/components/test_evaluator.py)` lines 621-636. AGENTS.md names this TAP-3 (determinism theater).
- The research invariant `outcome=success ⟹ goal_met=True` (synthesis Domain 2, line 48) is only safe when `goal_met` is trustworthy. The codebase already has the trustworthy source: the flag-gated L3 `GoalJudge` overlay at `[orchestration/react_loop.py](orchestration/react_loop.py)` lines 446-456 / 1258-1270, which "NEVER changes outcome" today (comment lines 1254-1256).
- `count_trailing_repeats` returns a single `int` consumed at three callsites (`[orchestration/react_loop.py](orchestration/react_loop.py)` lines 827, 1238, 1352) and 8 exact-int assertions in `[tests/orchestration/test_no_progress.py](tests/orchestration/test_no_progress.py)`. A second threshold cannot be carried by that int.

## Fix 1 — API-key redaction (P0): unchanged

Broaden the OpenAI rule in `[services/governance/guardrail_validator.py](services/governance/guardrail_validator.py)` (line 204) to `r"\bsk-(?:proj-)?[A-Za-z0-9_-]{8,}\b"`. Add a `sk-proj-abc123456789` case to `TestRedactAPIKeys` in `[tests/services/governance/test_black_box_publisher.py](tests/services/governance/test_black_box_publisher.py)`. Confirm `_SAFE_NUMERIC_KEYS` numeric values are untouched. Satisfies walkthrough G1.2 (`[docs/walk-through/01_phaselogger_gcp_validation_walkthrough.md](docs/walk-through/01_phaselogger_gcp_validation_walkthrough.md)` line 191).

## Fix 2 — Scorer coherence (rescoped: deterministic-safe + judge-conditional)

Drop the original keyword-overlap outcome gating. Instead:

- **Coherence assertions (pure, always on).** Add `_assert_score_coherence(outcome)` in `[components/evaluator.py](components/evaluator.py)` encoding only invariants true in *this* codebase's semantics: `score`/`criteria_met`/`branch_coverage` within `[0,1]`, `outcome in {success,partial,failed}`. Log-and-clamp at runtime, hard-assert in tests. Do NOT apply a keyword-goal_met score ceiling (fragile).
- **branch_coverage vs unmet_conditions:** do NOT `min`/fold them — they measure different reference sets (`plan_steps[].goal` lines 266-273 vs `success_conditions` lines 280-286), so the research's `branch_coverage==1.0 ⟹ unmet==[]` does not hold here. Add a telemetry-only `coherence_flag` note when both are simultaneously perfect-and-unmet, without mutating either metric.
- **Judge-conditional outcome gate (trustworthy source only).** Apply `success → partial when goal_met is False` ONLY when goal_met is judge-sourced. Implement in `[orchestration/react_loop.py](orchestration/react_loop.py)` immediately after the GoalJudge overlay (~line 1266): if `goal_judge is not None` and `verdict.goal_met is False` and `task_outcome.outcome == "success"`, downgrade to `partial`. Keep `evaluate_task_outcome` pure default behavior unchanged so the heuristic path stays decoupled.
- **Tests:** KEEP `test_goal_met_does_not_change_outcome` (heuristic path contract). Add `test_judge_false_goal_downgrades_success` at the react_loop level (mocked GoalJudge). Add invariant tests for `_assert_score_coherence`.

## Fix 3 — Suppression precheck (proceed with FP controls)

- Add a `suppression_marker` stage before the `clean_short` ACCEPT in `precheck_input` (`[services/guardrails.py](services/guardrails.py)` lines 231-233), verdict `DEFER` (not reject), reason `suppression_marker`, mirroring `_SOFT_DEFER_PATTERNS` (lines 126-138).
- Patterns scoped to self-behavior suppression: "do not stop", "do not explain", "never refuse", "keep (searching|going|trying) until", "do not (tell|mention|say) ... (why|that)".
- **FP control (mandatory):** the Step-4 validation prompt "...retry repeatedly until you find exactly 50 results" (`[docs/walk-through/01_phaselogger_gcp_validation_walkthrough.md](docs/walk-through/01_phaselogger_gcp_validation_walkthrough.md)` line 168) will shift from ACCEPT to DEFER. Add it as an explicit test asserting the now-intended DEFER, plus benign controls that must still ACCEPT. Confirm DEFER→judge still lets the impossible-task scenario run.
- Tests in `[tests/services/test_guardrails.py](tests/services/test_guardrails.py)`.

## Fix 4 — Result-aware loop termination (redesigned contract)

- **Do not change `count_trailing_repeats`** (preserve its 8 exact-int tests and 3 callsites). Add two new pure helpers in `[components/evaluator.py](components/evaluator.py)`: `count_trailing_identical(tool_results)` (byte-identical `(tool_name, tool_input, tool_output)`) and `count_trailing_failures(tool_results)` (trailing error outputs).
- Add `no_progress_identical_threshold: int = 2` to `[services/base_config.py](services/base_config.py)`.
- **Preserve two-tier escalation.** Thread `identical_repeats` (and optionally `failure_streak`) into `check_continuation` as new params. In `call_llm_node`, trigger the wrap-up directive when `repeats >= repeat_threshold OR identical >= identical_threshold` (and not already sent) — self-correction fires first. In `check_continuation`, hard-stop on `identical >= identical_threshold AND no_progress_directive_sent`, mirroring lines 206-209. Wire new counts at the three callsites (827, 1238, 1352).
- Tests in `[tests/orchestration/test_no_progress.py](tests/orchestration/test_no_progress.py)`: identical-output trips at the lower threshold but only after the directive; output-changed polling does NOT trip early; failure-streak trips.

## Validation

- `pytest tests/ -q` and `pytest tests/architecture/ -q` (all edits in `services/`, `components/`, `orchestration/`; no `trust/`, no new nodes/services).
- Confirm `sk-proj-abc123456789` redacts.
- Confirm walkthrough Step 4 still halts and the impossible-task input still reaches the loop after the new DEFER.

## Out of scope (unchanged)

OTel GenAI conventions, `pass^k` harness, AgentDojo/InjecAgent CI suites, spotlighting/datamarking, CaMeL isolation, durable replay.
