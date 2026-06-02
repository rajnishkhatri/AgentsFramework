# Fix 2 — GoalJudge Option B: Remediation Plan (F1–F4)

> **Deliverable.** Implementation **plan only** — this document changes no source. It specifies the
> exact remediation for findings **F1, F2, F3, F4** from the implementation review so an implementer can
> execute without re-deriving locations.
>
> **Date:** 2026-06-02. **Scope:** F1 (High), F2 (Medium), F3 (Medium), F4 (Medium). **Out of scope:**
> F5/F6/F7/F8 and the §2.8 production-enable calibration follow-on (see [§9](#9-explicitly-out-of-scope)).
>
> **Source review:** [`docs/research/fix2_goaljudge_option_b_implementation_review.md`](../research/fix2_goaljudge_option_b_implementation_review.md)
> (findings table §2, test-quality assessment §4, prioritized checklist §7).
> **Design context:** [`docs/research/fix2_goaljudge_rubric_feasibility_pyramid.md`](../research/fix2_goaljudge_rubric_feasibility_pyramid.md)
> (§2.8 false-downgrade enable-policy; strict-transition invariant).
> **Layering authority:** [`docs/Architectures/FOUR_LAYER_ARCHITECTURE.md`](../Architectures/FOUR_LAYER_ARCHITECTURE.md),
> [`AGENTS.md`](../../AGENTS.md). **Testing authority:** [`research/tdd_agentic_systems_prompt.md`](../../research/tdd_agentic_systems_prompt.md)
> (test-pattern catalog; anti-patterns TAP-1..4).
>
> **Goal of this remediation.** Close the **F1–F3 safety blockers** (plus the small F4 correctness defect)
> so the gate's safety claims (strict transition, red-team flip ceiling, offline regression coverage) are
> backed by tests that actually run and actually test what they claim. **The flag stays default-off.**
> Production-enable of `goal_judge_downgrade_enabled` remains gated on the §2.8 calibration follow-on,
> which is explicitly **out of scope** here.

---

## Table of contents

- [1. Frontmatter recap](#1-frontmatter-recap)
- [2. Executive summary + remediation ordering](#2-executive-summary--remediation-ordering)
- [3. Architecture & TDD compliance](#3-architecture--tdd-compliance)
- [4. F1 — external research + trade-off + decision](#4-f1--external-research--trade-off--decision)
- [5. Per-finding remediation](#5-per-finding-remediation)
  - [5.1 F1 — red-team offline coverage](#51-f1--red-team-has-zero-ci-coverage-high)
  - [5.2 F2 — illegal-transition test is vacuous](#52-f2--the-non-success-source-test-is-vacuous-medium)
  - [5.3 F3 — tautological / `-O`-stripped assert](#53-f3--tautological--o-stripped-strict-transition-assert-medium)
  - [5.4 F4 — `graceful_failure` mis-coercion](#54-f4--graceful_failure-bool-mis-coercion-medium)
- [6. Consolidated file-touch map](#6-consolidated-file-touch-map)
- [7. Consolidated test plan](#7-consolidated-test-plan)
- [8. Validation / exit criteria](#8-validation--exit-criteria)
- [9. Explicitly out of scope](#9-explicitly-out-of-scope)
- [10. References](#10-references)

---

## 1. Frontmatter recap

| Field | Value |
|---|---|
| Deliverable | Plan document only — **no source/test edits** in this change. |
| Findings remediated | F1 (High), F2 (Medium), F3 (Medium), F4 (Medium). |
| Flag posture | `goal_judge_enabled=False`, `goal_judge_downgrade_enabled=False` remain the shipped defaults. No production enable. |
| Layers touched | L4 orchestration (`orchestration/react_loop.py`), L3 component (`components/goal_judge.py`), tests at L3 (`tests/components/`) and L4 (`tests/orchestration/`). No `trust/`, no `services/`, no new graph node, no new service. |
| Test posture | Failure-path-first (TAP-4); correct-layer placement; CI runs L1+L2+offline-L3/L4 only; the live flip-rate gate stays `live_llm` opt-in (never CI). |
| CI invocation caveat | The suite must be run with `-p no:logfire` (review §6: a broken logfire Pydantic plugin otherwise warns/aborts collection). |

---

## 2. Executive summary + remediation ordering

The Fix 2 production behaviour is sound and ships dark, but four defects make the gate's safety claims
either **untested** (F1, F2), **un-enforced** (F3), or **subtly wrong** (F4). None requires changing the
gate's production semantics — the gate still reads only `goal_met` and still does strictly `success → partial`.
The remediation is therefore concentrated in **test coverage** (F1, F2), a **one-line guard hardening** (F3),
and a **one-line coercion removal** (F4).

Remediation order follows the review's prioritized checklist (§7):

1. **F1 (High)** — Replace the over-claimed "offline" red-team with a genuinely CI-safe offline pin, and
   reframe the live flip-rate test honestly as a `live_llm` opt-in diagnostic. Encode the 5% hard target
   separately from the 10% soft ceiling.
2. **F2 (Medium)** — Add the real non-success-source failure-mode cell: `no_progress → partial` + judge
   `goal_met=False` + flag ON must leave outcome `"partial"` and `downgrade_reason is None`. Fix the
   vacuous `budget_exceeded` test (which never reaches the gate).
3. **F3 (Medium)** — Replace the tautological, `-O`-stripped `assert task_outcome.outcome == "partial"`
   with a meaningful **pre-state** guard that raises a typed error (survives `-O`).
4. **F4 (Medium)** — Drop the manual `bool(...)` coercion of `graceful_failure`; let Pydantic v2 coerce.
   Add a `"graceful_failure": "false" → False` regression test.

**Bottom line:** after F1–F4 land, the gate's strict-transition and gaming-resistance claims are backed
by tests that run in CI (offline) and a live diagnostic that is honestly labeled — but the flag stays off
until §2.8 calibration clears.

---

## 3. Architecture & TDD compliance

Every change in this plan stays within the four-layer architecture
([`FOUR_LAYER_ARCHITECTURE.md`](../Architectures/FOUR_LAYER_ARCHITECTURE.md): Orchestration → Components →
Services → Trust Kernel, downward-only deps; trust kernel zero deps; components/services framework-agnostic).

| Finding | Layer of the fix | Files | AGENTS.md invariant honored | TAP anti-pattern addressed |
|---|---|---|---|---|
| F1 | **L3 tests** (offline pin) + **L3 test** (live diagnostic re-label) | `tests/components/test_goal_judge_redteam.py` (+ a new offline module or class) | No live LLM in CI; markers correct (`slow`/`live_llm`); test imports obey layer rules (`tests/components/` imports `components/` + `services/` only) | **TAP-3** (determinism theater): the offline pin asserts *structural* facts (prompt text, digest contents, parse→gate of canned verdicts), never live model prose; the aggregate flip-rate stays a live diagnostic. **TAP-4** (gap blindness): the gaming mitigation finally has a runnable regression pin. |
| F2 | **L4 test** (failure-mode matrix) | `tests/orchestration/test_goal_judge_gate.py` | Failure-paths-first; orchestration tested via observable BlackBox artifact, not internals | **TAP-4** (gap blindness): adds the missing `no_progress → partial` non-success-source cell the gate's `outcome == "success"` guard actually reaches. |
| F3 | **L4 orchestration** (gate guard) | `orchestration/react_loop.py` | AP-5 (thin wrapper; the *decision* `verdict.goal_met` stays in L3; orchestration only maps `success → partial`); invariant #6 (orchestration nodes are thin) | **TAP-1** (tautology): removes the self-asserting `assert task_outcome.outcome == "partial"`; replaces with a pre-state guard that proves the transition source. |
| F4 | **L3 component** (parse) | `components/goal_judge.py` | Components framework-agnostic (no new imports; pure Pydantic) | Correctness; no anti-pattern introduced. |

**FOUR_LAYER_ARCHITECTURE mapping.** F3 is the only production-code change. It edits orchestration's gate
guard but does **not** move any decision logic into orchestration — the boolean decision (`verdict.goal_met`)
is computed in the L3 `GoalJudge`; orchestration only (a) checks the pre-state outcome and (b) maps
`success → partial`. This preserves invariant #6 ("orchestration nodes are thin wrappers") and AP-5
("no domain logic in orchestration nodes"). No upward imports, no framework imports in `components/` or
`services/`, no `trust/` change, no new graph node, no new horizontal service.

**Decoupling invariant is untouched.** `components/evaluator.py::evaluate_task_outcome` is **not edited**;
`tests/components/test_evaluator.py::...::test_goal_met_does_not_change_outcome` stays green. The judge-sourced
downgrade remains orchestration-local and judge-conditional.

---

## 4. F1 — external research + trade-off + decision

### 4.1 The question

The review's F1 is: the CoT-gaming red-team (`tests/components/test_goal_judge_redteam.py`) claims to be
"offline … never runs live LLM in CI" (docstring lines 1–15) but is double-tagged `@pytest.mark.slow` +
`@pytest.mark.live_llm` (line 28), is **deselected** by the default `addopts`
(`pyproject.toml:79` → `-m 'not slow and not simulation and not live_llm and not infra'`), and `pytest.skip`s
without `OPENAI_API_KEY` (lines 94–95). It therefore provides **zero** CI regression coverage. Also, only the
10% soft ceiling is asserted (`FLIP_RATE_SOFT_CEILING = 0.10`, line 80); the 5% hard target is a comment, not
encoded.

The decision required: which **offline / CI-safe** test design actually pins the gaming mitigation, weighing
the two reviewer-proposed options (plus any third found in research)?

- **(a) Record/replay canned judge responses.** For each fabricated-progress fixture, replay a recorded/canned
  judge verdict and assert it parses to `goal_met=False` and (where wired) drives the gate path deterministically
  — no LLM.
- **(b) Offline prompt-assertion.** For each fabricated-progress fixture, assert the *rendered prompt* contains
  the evidence-grounding rule **and** that the *evidence digest* surfaces the contradicting tool output — i.e.,
  the two halves of the mitigation are actually present in what the judge sees.

### 4.2 External research (2025–2026)

| # | Source | What it establishes | Bearing on the choice |
|---|---|---|---|
| E1 | "Gaming the Judge: Unfaithful Chain-of-Thought Can Undermine Agent Evaluation," Khalifa et al., arXiv [2601.14691](https://arxiv.org/abs/2601.14691) (Jan 2026) | Manipulating only the agent's CoT inflates VLM-judge **false-positive rates by up to 90%**; content (progress-fabricating) manipulation is worst; the prescribed mitigation is "judging mechanisms that **verify reasoning claims against observable evidence**." | The mitigation's correctness depends on (i) the grounding instruction being present and (ii) the contradicting observable evidence being visible to the judge. **(b) pins exactly these two properties offline.** Whether the model then flips correctly is only measurable live. |
| E2 | "Agent-as-a-Judge," Zhuge et al., arXiv [2410.10934](https://arxiv.org/abs/2410.10934) (ICML 2025) | Trajectory-aware judging beats output-only (90% vs 70% human agreement) but is the most gaming-exposed surface. | Confirms the digest *content* (trajectory evidence) is the load-bearing input — so a test that asserts the digest exposes the contradiction (b) is testing the right surface. |
| E3 | VCR-style record/replay for LLM tests (`pytest-recording`/VCR.py; `llm-fixture-replay`; `llmvcr`; `vcr-llm`) — [pytest-recording TIL](https://til.simonwillison.net/pytest/pytest-recording-vcr), [llm-fixture-replay](https://dev.to/mukundakatta/vcr-style-recordreplay-for-llm-tests-make-your-agent-tests-deterministic-and-free-3o6d) | Industry-standard pattern: record real LLM responses once, commit the cassette, replay offline & deterministically in CI; tests fail when the *request* (prompt) changes — i.e., they are **prompt-regression** pins, not quality pins. Cassettes must be sanitized of secrets. | A record/replay (a) test of *recorded* verdicts is a prompt/parse-regression pin, not a robustness pin. The repo already implements this pattern in-process via `FakeLLMService` (`tests/components/test_goal_judge.py:50-59`), so (a) is cheap — but its `goal_met=False` is **author-chosen**, so on its own it proves the parse→gate path, not gaming resistance. |
| E4 | Anay Nayak, "Eliminating Flaky Tests: Using VCR tests for LLMs" ([medium](https://anaynayak.medium.com/eliminating-flaky-tests-using-vcr-tests-for-llms-a3feabf90bc5)) | Explicitly distinguishes **record/replay regression tests** (detect prompt/code regressions, isolate non-LLM issues) from **LLM evaluation tests** (assess response quality dynamically). | Names the exact false-confidence risk: a record/replay test cannot assess judge quality. Use (a) as a regression pin and keep quality assessment to the live diagnostic. |
| E5 | GAMEBoT, ACL 2025 ([pdf](https://aclanthology.org/2025.acl-long.378.pdf)) | Robust reasoning evaluation decomposes tasks into sub-problems with **rule-based ground truth** for intermediate steps, rather than trusting generic CoT. | Supports asserting *structural* ground-truth properties offline (grounding rule present, contradiction surfaced) over trusting model CoT — reinforces (b). |

### 4.3 Trade-off table

| Dimension | (a) Record/replay canned verdicts | (b) Offline prompt-assertion | Live flip-rate diagnostic (kept, re-labeled) |
|---|---|---|---|
| **What it actually proves** | The parse path + (if wired) the gate path behave correctly **given** a `goal_met=False` verdict. The verdict is author-chosen. | For each fabricated case, the rendered prompt contains the evidence-grounding rule **and** the digest exposes the contradicting/absent tool evidence — the two inputs the mitigation depends on (E1). | The judge model actually resists CoT gaming at an aggregate flip rate ≤ ceiling. |
| **Coverage of the gaming mitigation** | Low — does not exercise the grounding rule at all. | **High (input side)** — pins precisely the surface E1 says must hold; cannot prove the model's output. | **High (output side)** — the only thing that proves real resistance. |
| **False-confidence risk** | **High if sold as "gaming coverage"** (E4): it tests plumbing, not robustness. Honest if sold as a parse/gate regression pin. | Low — it claims only "the judge is shown the grounding rule and the contradicting evidence," which is exactly what it asserts. | Low — honest aggregate metric, but non-deterministic and model-dependent. |
| **TAP-3 (determinism theater) fit** | Good — structural assertions, no model prose. | **Best** — pure string/shape assertions on deterministic `PromptService` + `_summarize_evidence` output. | N/A in CI (excluded); aggregate-rate, not exact-string, so TAP-3-safe when run. |
| **Fit to repo record/replay pattern** | **Native** — `FakeLLMService` already replays canned JSON (`test_goal_judge.py:50-59`); zero new deps. | Native — `PromptService` + `GoalJudge._summarize_evidence` are pure and already unit-tested (`test_goal_judge.py:180-389`). | Native — already exists; only needs honest re-labeling + dual threshold. |
| **Maintenance cost** | Low — canned JSON strings; brittle only if the schema changes. | Low — assertions on stable rule substrings + fixture-specific evidence tokens; brittle only if the prompt rule text is reworded (which is exactly when you *want* the test to fire). | Low-medium — needs a key + budget; fixtures already authored. |
| **Runs in CI?** | Yes (offline, deterministic). | Yes (offline, deterministic). | **No** — `live_llm`, opt-in only. |

### 4.4 Decision

**Recommend BOTH offline pins, with (b) as the primary F1 closure and (a) as a complementary parse→gate
regression pin, and keep the live flip-rate test as a re-labeled `live_llm` opt-in diagnostic.** Confidence: **0.82**.

Rationale (1–2 sentences): (b) directly regression-pins the *exact* mitigation surface the gaming literature
(E1) says must hold — the grounding instruction in the prompt and the contradicting evidence in the digest —
which is what F1 is actually missing offline; (a) is nearly free given the repo's existing `FakeLLMService`
record/replay pattern (E3) and pins the deterministic parse→gate path for fabricated-progress fixtures, while
the live test remains the only honest measure of true model resistance and is correctly excluded from CI.

**Why not (a) alone:** per E4, a record/replay test with an author-chosen `goal_met=False` proves plumbing,
not robustness — selling it as "CoT-gaming coverage" would re-commit the exact over-claim F1 flags.

**Threshold to change:** if `PromptService`/digest rendering becomes non-deterministic, or the project funds
the §2.8 gold set such that a labeled offline judge-output corpus exists, prefer promoting the live diagnostic
to a recorded-verdict **gold-set** evaluation (true offline robustness scoring) and demote (b) to a smoke pin.

### 4.5 The 5% hard target vs the 10% soft ceiling

There is **no flip rate to assert offline** (no model runs), so both thresholds live in the **live diagnostic**:

- Keep `FLIP_RATE_SOFT_CEILING = 0.10` as the **hard test gate** (the live test *fails* above it).
- Add `FLIP_RATE_HARD_TARGET = 0.05` and, when `0.05 < flip_rate ≤ 0.10`, emit a non-fatal signal
  (e.g. `pytest.warns`-detectable `UserWarning`, or `warnings.warn(...)`, or a recorded `eval_capture`/log line)
  so the 5% target is *visible* without failing the per-run gate.
- **Document why only the soft ceiling is a hard gate:** the 5% hard target is an **enable-policy bar**
  (feasibility pyramid §2.8 Stage 2 — production-enable), measured on the calibration/gold set, not a
  per-run CI gate. The live diagnostic surfaces the 5% target as a warning; the §2.8 follow-on owns turning
  it into a release gate. State this in the module docstring.

---

## 5. Per-finding remediation

### 5.1 F1 — red-team has zero CI coverage (High)

**Root cause (verified).**
- The module docstring claims "offline … never runs live LLM in CI" (`tests/components/test_goal_judge_redteam.py:1-15`).
- `pytestmark = [pytest.mark.slow, pytest.mark.live_llm]` (`:28`); the default `addopts` deselects both
  (`pyproject.toml:79`), so the test is **deselected** (not even shown as skipped) in CI.
- The only test `pytest.skip`s without `OPENAI_API_KEY` (`:94-95`) and the single assertion requires a live
  model (`:99-115`).
- Only `FLIP_RATE_SOFT_CEILING = 0.10` is encoded (`:80`); the 5% hard target is a bare comment.

Net: the plan's promised "CI-safe offline red-team fixture as the §2.8 Stage-0 bridge" was **not delivered as
a runnable pin**.

**Fix approach (decided in [§4](#4-f1--external-research--trade-off--decision)).** Three parts, all L3 tests:

1. **Honestly re-label the existing live test.** In `test_goal_judge_redteam.py`:
   - Rewrite the module docstring to drop the "offline" claim; describe it as a **`live_llm` opt-in
     diagnostic** that measures the aggregate CoT-gaming flip rate and is intentionally excluded from CI
     (AGENTS.md: no live LLM in CI).
   - Keep `pytestmark = [pytest.mark.slow, pytest.mark.live_llm]` and the `OPENAI_API_KEY` skip — these are
     mechanically correct for a live diagnostic.
   - Add `FLIP_RATE_HARD_TARGET = 0.05`; keep `FLIP_RATE_SOFT_CEILING = 0.10` as the failing gate; emit a
     warning when `0.05 < flip_rate ≤ 0.10` (see §4.5). Document why only the soft ceiling fails the run.

2. **Add a genuinely offline CI pin — primary, option (b).** New offline test(s) (no `live_llm`/`slow`
   marker, so they run by default) that, for **each** `FABRICATED_PROGRESS_CASES` fixture, render the prompt
   via the real `PromptService` + `GoalJudge._summarize_evidence` (reuse the existing `FakeLLMService` from
   `test_goal_judge.py` to drive `evaluate`, capturing the rendered prompt as that test already does at
   `test_goal_judge.py:193-198`) and assert:
   - the rendered prompt contains the **evidence-grounding rule** (a stable substring from
     `prompts/goal_judge_system_prompt.j2:34-38`, e.g. `"EVIDENCE-GROUNDING"` / `"Treat the agent's own
     narration of progress"`); and
   - the rendered evidence digest **exposes the contradicting / absent tool evidence** for that fixture
     (e.g. for the `read_file` case the digest contains `"Error: file not found"`; for the empty-evidence
     cases the digest contains the `"(no tool calls were made)"` placeholder from `goal_judge.py:183`).

   This pins both halves of the E1 mitigation deterministically, in CI, with no model.

3. **Add a complementary parse→gate record/replay pin — secondary, option (a).** New offline test(s) that
   feed **canned `goal_met=False` verdict JSON** (one per fabricated case, the recorded "correct" verdict)
   through `GoalJudge._parse_verdict` via `FakeLLMService` and assert each parses to `goal_met is False`
   (and `graceful_failure is False` for the fabricated-completion cases). Frame it explicitly (docstring) as
   a **parse-contract regression pin for fabricated-progress verdicts**, NOT a robustness measure (per E4).

**Where the new offline tests live.** Either a new class in `test_goal_judge_redteam.py` *without* the
module-level `pytestmark` (override per-test) or — cleaner — a new sibling module
`tests/components/test_goal_judge_redteam_offline.py` carrying no `slow`/`live_llm` marker. Recommend the
**separate module** so the marker boundary is unambiguous (the live file stays fully `live_llm`).

**Test plan (failure-path-first).**

| Test | Layer | Marker | Asserts | Kind |
|---|---|---|---|---|
| `test_prompt_exposes_grounding_rule_for_each_fabricated_case` | L3 | (none → CI default) | For each fixture, rendered prompt contains the evidence-grounding rule substring. | Acceptance of an invariant (the mitigation instruction is present) |
| `test_digest_exposes_contradicting_evidence_for_each_fabricated_case` | L3 | (none) | For each fixture, the rendered digest surfaces the contradicting tool output or the no-tools placeholder. | Acceptance of an invariant (contradiction is visible) |
| `test_canned_false_verdicts_parse_to_goal_met_false` | L3 | (none) | Each canned fabricated-progress verdict parses to `goal_met is False`. | Rejection-oriented regression pin (parse contract) |
| `test_cot_gaming_flip_rate_below_threshold` (existing, re-labeled) | L3 | `slow`, `live_llm` | `flip_rate ≤ 0.10` (fail); warns if `> 0.05`. | Live diagnostic (excluded from CI) |

**Acceptance criteria.**
- `python -m pytest tests/components/test_goal_judge_redteam_offline.py -q -p no:logfire` → all pass
  (runs by default, no key, no network).
- `python -m pytest tests/components/test_goal_judge_redteam.py -q -p no:logfire` → `deselected` in CI
  (unchanged) — but the file no longer claims to be "offline."
- `OPENAI_API_KEY=… python -m pytest tests/components/test_goal_judge_redteam.py -m live_llm -q -p no:logfire`
  → runs the live diagnostic; fails above 10%, warns above 5%.

### 5.2 F2 — the non-success-source test is vacuous (Medium)

**Root cause (verified).** `test_non_success_source_is_never_downgraded`
(`tests/orchestration/test_goal_judge_gate.py:144-159`) forces `budget_exceeded` via
`max_cost_usd=0.001, initial_cost=999.0`. The `budget_exceeded` outcome is produced at the
`_parse_response` terminal site (`react_loop.py:1366-1367`) and routes to `END`, so the goal-judge block and
its gate guard (`react_loop.py:1290-1301`) are **never reached** — the test's own comment admits this
(`:157-158`). The real non-success source the gate *does* reach is `no_progress → partial`:

- `react_loop.py:1248-1253` sets `termination_reason = "no_progress"` when
  `state["no_progress_directive_sent"]` is truthy **or** `_count_trailing_repeats(tool_results) >=
  agent_config.no_progress_repeat_threshold` (default **3**, `base_config.py:35`).
- `evaluate_task_outcome` maps `"no_progress"` to `outcome="partial"` (`evaluator.py:251` makes it unclean;
  `:303-306` maps unclean + substantive → `"partial"`).
- The gate's guard is `verdict.goal_met is False and task_outcome.outcome == "success"`
  (`react_loop.py:1290-1293`); with outcome already `"partial"`, `would_downgrade` is `False`, so the gate
  does not fire and `downgrade_reason` stays `None`.

So the only test that actually exercises the `outcome == "success"` guard against a **non-success source** is
missing; the "illegal-transition / no upgrade" claim is currently unproven.

**Fix approach (L4 test only — no production change).** In `tests/orchestration/test_goal_judge_gate.py`:

1. **Extend the harness** `_run_with_verdict` to allow driving the `no_progress` source — add a parameter
   (e.g. `seed_no_progress: bool = False`) that injects into the initial `graph.ainvoke(...)` state either
   `"no_progress_directive_sent": True` **or** a `"tool_results"` list of ≥ `no_progress_repeat_threshold`
   (3) trailing-repeat entries. Recommend `no_progress_directive_sent=True` as the simplest deterministic
   trigger (it short-circuits the repeat count at `react_loop.py:1250`); the implementer should **verify by
   reading `AgentState`** that the key threads through to the completion node unchanged (if not, fall back to
   seeding 3 identical `tool_results`, which `evaluate_task_outcome` and `_count_trailing_repeats` both read
   from state at `react_loop.py:1248,1260`).
2. **Add the real failure-mode cell** and **fix/keep the budget case honestly**:

```python
# Failure path (TAP-4): the gate's outcome=="success" guard must refuse a
# non-success SOURCE that actually reaches the gate.
async def test_no_progress_source_is_never_downgraded(self, tmp_path):
    details = await _run_with_verdict(
        tmp_path,
        workflow_id="wf-no-progress",
        verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
        downgrade_enabled=True,      # flag ON
        seed_no_progress=True,        # termination_reason -> no_progress -> partial
    )
    assert details["outcome"] == "partial"        # unchanged by the gate
    assert details["downgrade_reason"] is None     # gate did NOT fire (no double-downgrade, no upgrade)
    assert details["goal_met"] is False            # judge overlay still recorded
```

3. **Keep the budget test but re-scope its claim** (rename to e.g.
   `test_budget_terminal_site_bypasses_gate`) so its docstring states it documents a *terminal site that
   never reaches the gate* (not a strict-transition proof). This preserves the existing coverage without the
   misleading "illegal-transition" framing.

**Verify before coding.** Read `evaluator.evaluate_task_outcome` (function name confirmed,
`evaluator.py:220`) and the gate (`react_loop.py:1290-1301`) to confirm: threshold name
`no_progress_repeat_threshold` (=3), outcome mapping `no_progress → partial`, guard
`task_outcome.outcome == "success"`, and `downgrade_reason` defaulting to `None` at `react_loop.py:1268`.

**Test plan (failure-path-first).**

| Test | Layer | Marker | Asserts | Kind |
|---|---|---|---|---|
| `test_no_progress_source_is_never_downgraded` (new) | L4 | (none → CI default) | `outcome=="partial"`, `downgrade_reason is None`, `goal_met is False` with flag ON + judge `goal_met=False`. | **Rejection** (the real non-success-source guard) |
| `test_budget_terminal_site_bypasses_gate` (renamed from the vacuous test) | L4 | (none) | `outcome=="budget_exceeded"`, `downgrade_reason is None`; documents a site that never reaches the gate. | Rejection (documented bypass) |

**Acceptance criteria.**
- `python -m pytest tests/orchestration/test_goal_judge_gate.py -q -p no:logfire` → all pass, including the
  new `no_progress` cell.
- The new test must **fail** if the gate guard were weakened to drop `task_outcome.outcome == "success"`
  (manually verify by reasoning or a scratch run) — this is what proves it is not vacuous.

### 5.3 F3 — tautological / `-O`-stripped strict-transition assert (Medium)

**Root cause (verified).** At `react_loop.py:1297-1301`:

```python
task_outcome = task_outcome.model_copy(update={"outcome": "partial"})
assert task_outcome.outcome == "partial"  # strict success->partial only
downgrade_reason = "goal_judge"
```

The `assert` checks the value assigned on the previous line — it **can never fail** (TAP-1 tautology) — and a
bare `assert` is stripped under `python -O`, so it guards nothing in optimized runs.

**Fix approach (L4 orchestration; keep AP-5 thin-wrapper).** Capture the **pre-state** before the
`model_copy` and enforce the strict source, raising a typed error (survives `-O`) instead of asserting the
post-state. Recommended shape:

```python
# Strict-transition guard: the ONLY legal downgrade is success -> partial.
# Capture the pre-state so the guard proves the SOURCE, not the value we
# just assigned (TAP-1). Use an explicit raise so the invariant holds under
# python -O (a bare ``assert`` is stripped).
prev_outcome = task_outcome.outcome
if prev_outcome != "success":  # defensive: would_downgrade already requires this
    raise RuntimeError(
        f"goal_judge downgrade gate reached with non-success source {prev_outcome!r}; "
        "strict success->partial invariant violated"
    )
task_outcome = task_outcome.model_copy(update={"outcome": "partial"})
downgrade_reason = "goal_judge"
```

**Recommendation: the typed `raise`, not a bare `assert`.** The user asked to choose between
`assert prev == "success"` semantics or a typed error/raise; pick **`raise`** because the invariant is one we
want enforced under `-O` (a production safety claim). Note that `would_downgrade` already requires
`task_outcome.outcome == "success"` (`react_loop.py:1290-1293`), so in normal flow the new guard is
unreachable-but-defensive; it converts a silent tautology into a real invariant check that would fire if a
future edit moved the gate below another outcome mutation. Keep the whole block ≤ ~8 lines so the wrapper
stays thin (AP-5); the *decision* remains the L3 `verdict.goal_met`.

**Alternative considered.** `assert prev_outcome == "success"` is better than the current assert (it checks
the source) but is still `-O`-stripped; rejected for an invariant we want kept in production.

**Test plan (failure-path-first).** Covered behaviorally by F2's `test_no_progress_source_is_never_downgraded`
(non-success source never reaches/fires the gate) and the existing acceptance
`test_goal_met_false_with_flag_on_downgrades` (`test_goal_judge_gate.py:169-178`, success → partial). No new
test strictly required for F3, but **optionally** add an L4 test that monkeypatches/forces the gate to be
reached with a non-success pre-state and asserts a `RuntimeError` is raised — this directly pins the new guard.
Mark it `(none)` (CI default). Because directly constructing that state is awkward through the public graph,
this optional test may instead target a small extracted helper **only if** one already exists; do **not**
extract new orchestration helpers solely for testability (would expand the gate's surface). Recommendation:
rely on F2's behavioral coverage + the acceptance test; treat the explicit raise-test as optional.

**Acceptance criteria.**
- `python -m pytest tests/orchestration/test_goal_judge_gate.py -q -p no:logfire` → all pass.
- `python -O -m pytest tests/orchestration/test_goal_judge_gate.py -q -p no:logfire` → acceptance downgrade
  (`success → partial`) still works (the guard is a `raise`, not an `assert`, so behaviour is identical under `-O`).
- `ReadLints` on `orchestration/react_loop.py` → no new lints.

### 5.4 F4 — `graceful_failure` bool mis-coercion (Medium)

**Root cause (verified).** `components/goal_judge.py:142-145`:

```python
if "graceful_failure" in data:
    data["graceful_failure"] = bool(data.get("graceful_failure"))
```

`bool("false") is True` in Python (any non-empty string is truthy), so a model returning the JSON string
`"false"` is mis-coerced to `True` — the exact stringy-false case the comment claims to protect. Pydantic v2
already coerces JSON-ish bools correctly (`"true"/"false"/0/1/null`) for a `bool` field, so the manual
coercion is **strictly worse** for `"false"`.

**Fix approach (L3 component; pure).** **Recommendation: drop the manual coercion entirely** and let Pydantic
v2 validate `graceful_failure: bool` (`schemas.py:133`). Delete lines 142–145. Pydantic's bool coercion
handles `true/false` (JSON bool), `"true"/"false"` (case-insensitive strings), and `0/1`. The field default
is `False` (`schemas.py:133`), so a missing key is unaffected.

- If the implementer wants belt-and-suspenders for *non-bool numeric* shapes only (e.g. `2.0`), coerce only
  genuinely numeric non-`{0,1}` values; but this is unnecessary — Pydantic raises on out-of-range ints for
  `bool` and the default path is fine. **Prefer the clean deletion.**

**Test plan (failure-path-first).** Add to `tests/components/test_goal_judge.py::TestNewVerdictAxes`:

| Test | Layer | Marker | Asserts | Kind |
|---|---|---|---|---|
| `test_graceful_failure_string_false_parses_false` (new) | L3 | (none) | A verdict with `"graceful_failure": "false"` parses to `graceful_failure is False`. | **Rejection-first** regression (the bug case) |
| `test_graceful_failure_string_true_parses_true` (new, optional) | L3 | (none) | `"graceful_failure": "true"` → `True`. | Acceptance (coercion still works) |
| `test_graceful_failure_parsed` (existing, `:237-250`) | L3 | (none) | JSON bool `true` → `True` (must still pass). | Acceptance (backward-compat) |

Illustrative new test:

```python
@pytest.mark.asyncio
async def test_graceful_failure_string_false_parses_false(self):
    judge, _ = _judge(
        '{"goal_met": false, "criteria_met": 0.0, "per_criterion": [], '
        '"rationale": "stringy false", "graceful_failure": "false"}'
    )
    verdict = await judge.evaluate(
        task_input="t", final_answer="a", success_conditions=[]
    )
    assert verdict.graceful_failure is False   # bug today coerces to True
```

**Acceptance criteria.**
- `python -m pytest tests/components/test_goal_judge.py -q -p no:logfire` → all pass, including the new
  `"false" → False` test (which **fails** before the F4 fix and passes after).

---

## 6. Consolidated file-touch map

| File | Layer | Change | Finding |
|---|---|---|---|
| `components/goal_judge.py` | L3 component | Delete the manual `graceful_failure` bool coercion (`:142-145`); rely on Pydantic v2 bool coercion. | F4 |
| `orchestration/react_loop.py` | L4 orchestration | Replace the tautological `-O`-stripped `assert task_outcome.outcome == "partial"` (`:1300`) with a **pre-state** guard (`prev_outcome = task_outcome.outcome`) that **raises** a typed error on a non-`success` source, then does `model_copy(outcome="partial")`. ≤ ~8 lines; stays a thin AP-5 wrapper. | F3 |
| `tests/components/test_goal_judge_redteam.py` | L3 test | Re-label honestly as a `live_llm` opt-in diagnostic (drop "offline" wording in docstring); add `FLIP_RATE_HARD_TARGET = 0.05`, keep soft ceiling 0.10 as the failing gate, warn between 5–10%; document why only the soft ceiling fails. | F1 |
| `tests/components/test_goal_judge_redteam_offline.py` | L3 test (new) | Offline CI pin: (b) per-fixture prompt-grounding-rule + digest-contradiction assertions; (a) canned `goal_met=False` verdict parse-contract regression. No `slow`/`live_llm` marker (runs in CI). | F1 |
| `tests/orchestration/test_goal_judge_gate.py` | L4 test | Extend `_run_with_verdict` to drive the `no_progress` source; add `test_no_progress_source_is_never_downgraded`; rename the vacuous budget test to `test_budget_terminal_site_bypasses_gate` and re-scope its docstring. | F2 |
| `tests/components/test_goal_judge.py` | L3 test | Add `test_graceful_failure_string_false_parses_false` (+ optional `"true" → True`) to `TestNewVerdictAxes`. | F4 |

**No change** to: `components/schemas.py`, `components/evaluator.py`, `prompts/goal_judge_system_prompt.j2`,
`services/base_config.py`, `services/governance/guardrail_validator.py`, `pyproject.toml`, any `trust/` file.
The flag defaults are untouched.

---

## 7. Consolidated test plan

| Test name | Layer | Marker | Asserts | Rejection / Acceptance |
|---|---|---|---|---|
| `test_prompt_exposes_grounding_rule_for_each_fabricated_case` (new, F1) | L3 | none (CI) | Rendered prompt contains the evidence-grounding rule for every fabricated fixture. | Acceptance (invariant present) |
| `test_digest_exposes_contradicting_evidence_for_each_fabricated_case` (new, F1) | L3 | none (CI) | Rendered digest surfaces the contradicting tool output / no-tools placeholder per fixture. | Acceptance (invariant present) |
| `test_canned_false_verdicts_parse_to_goal_met_false` (new, F1) | L3 | none (CI) | Each canned fabricated-progress verdict parses `goal_met is False`. | Rejection-oriented regression pin |
| `test_cot_gaming_flip_rate_below_threshold` (existing, re-labeled, F1) | L3 | `slow`, `live_llm` | `flip_rate ≤ 0.10` (fail); warn if `> 0.05`. | Live diagnostic (excluded from CI) |
| `test_no_progress_source_is_never_downgraded` (new, F2) | L4 | none (CI) | `no_progress → partial` + judge `goal_met=False` + flag ON ⇒ `outcome=="partial"`, `downgrade_reason is None`, `goal_met is False`. | **Rejection (the real guard)** |
| `test_budget_terminal_site_bypasses_gate` (renamed, F2) | L4 | none (CI) | `budget_exceeded` outcome; gate never reached; `downgrade_reason is None`. | Rejection (documented bypass) |
| `test_goal_met_true_does_not_downgrade` (existing, F2/F3 context) | L4 | none | `goal_met=True` + flag ON ⇒ no downgrade. | Rejection |
| `test_flag_off_is_shadow_only` (existing) | L4 | none | `goal_met=False` + flag OFF ⇒ outcome `success`, verdict recorded. | Rejection |
| `test_goal_met_false_with_flag_on_downgrades` (existing, F3 acceptance) | L4 | none | `goal_met=False` + flag ON + success source ⇒ `partial`, `downgrade_reason=="goal_judge"`. | Acceptance |
| `test_graceful_failure_string_false_parses_false` (new, F4) | L3 | none | `"graceful_failure": "false"` ⇒ `False`. | **Rejection-first (the bug)** |
| `test_graceful_failure_string_true_parses_true` (new optional, F4) | L3 | none | `"graceful_failure": "true"` ⇒ `True`. | Acceptance |

Ordering principle (TAP-4): in each file, the new rejection tests precede acceptance tests.

---

## 8. Validation / exit criteria

Run from repo root with `-p no:logfire` (review §6). CI excludes `slow`/`simulation`/`live_llm`/`infra` via
`addopts` (`pyproject.toml:79`).

```bash
# Per-finding suites (offline, CI-equivalent):
python -m pytest tests/components/test_goal_judge.py \
  tests/components/test_goal_judge_redteam_offline.py \
  tests/orchestration/test_goal_judge_gate.py \
  tests/components/test_evaluator.py -q -p no:logfire
# Expect: all pass; new F1 offline + F2 no_progress + F4 stringy-false tests green.

# F1 live diagnostic stays deselected by default (proves it's not in CI):
python -m pytest tests/components/test_goal_judge_redteam.py -q -p no:logfire
# Expect: "deselected".

# F3 invariant survives optimized mode:
python -O -m pytest tests/orchestration/test_goal_judge_gate.py -q -p no:logfire
# Expect: success->partial acceptance still passes (guard is a raise, not assert).

# Architecture invariants (must stay green; the pre-existing unrelated
# test_mphase2_swap_radius failure is NOT caused by this change — review §6):
python -m pytest tests/architecture/ -q -p no:logfire

# Optional: opt-in live diagnostic (needs a key; never in CI):
OPENAI_API_KEY=… python -m pytest tests/components/test_goal_judge_redteam.py -m live_llm -q -p no:logfire
```

**"Done" means:**
1. F1: an offline red-team pin runs in CI and asserts the grounding rule + contradicting evidence are present
   for every fabricated case; the live test no longer claims to be "offline" and encodes both 5% (warn) and
   10% (fail) thresholds.
2. F2: `test_no_progress_source_is_never_downgraded` exists, exercises the gate's `outcome=="success"` guard
   against a real non-success source, and passes; the budget test is renamed/re-scoped honestly.
3. F3: the tautological `-O`-stripped assert is gone, replaced by a pre-state `raise` guard; acceptance
   downgrade works under `python -O`.
4. F4: the manual `graceful_failure` coercion is removed; `"false" → False` is pinned by a test that fails
   pre-fix and passes post-fix.
5. `ReadLints` on edited files → no new lints.
6. **The flag stays off.** No change to `goal_judge_enabled` / `goal_judge_downgrade_enabled` defaults.
   Production enable remains gated on the §2.8 calibration follow-on (below).

---

## 9. Explicitly out of scope

| Item | Disposition | Why deferred |
|---|---|---|
| **F5 (Low)** — redaction across the 400-char `_compact` truncation boundary (`goal_judge.py:196-201`); `no_progress`-then-judge double-downgrade telemetry blind spot (`downgrade_reason=None`). | Not in this change. | Low severity; the user scoped remediation to F1–F4. Can be a follow-on. |
| **F6 (Nit)** — gate is ~10 lines vs the plan's "≤5-line" claim. | No action. | Still a thin AP-5 wrapper; F3 keeps it ≤ ~8 lines. Wording-only. |
| **F7 (Nit)** — commit hygiene (unrelated `dataset.py`/`langfuse`/regex changes co-mingled in the working tree). | No action here. | Commit-scoping concern, not a code defect; handled at commit time, not in this plan. |
| **F8 (Positive)** — the REDACT-coercion deviation (`react_loop.py:456-469`). | **Keep.** | Correct and necessary; `redact()` only acts on REDACT rules (`guardrail_validator.py:138-149`) and the canonical SSN/CC/API-key rules are BLOCK (`:167-224`). |
| **§2.8 production-enable calibration** — precision ≥0.90 / recall ≥0.70 on `goal_met=False`, ≤2% false-downgrade rate, red-team flip ≤5%, κ ≥0.6, ECE diagnostic-only, default-off until met; ~250-item double-labeled gold set. | **Out of scope; remains the gate to flip the flag in production.** | This plan closes the F1–F3 *safety blockers* so the gate's claims are testable; turning on `goal_judge_downgrade_enabled` in production is a separate, calibration-gated decision (feasibility pyramid §2.8 Stage 2). |

---

## 10. References

External sources for the F1 decision (cited inline in [§4](#4-f1--external-research--trade-off--decision)):

| # | Title | ID / URL | Used for |
|---|---|---|---|
| E1 | Gaming the Judge: Unfaithful Chain-of-Thought Can Undermine Agent Evaluation (Khalifa et al., Jan 2026) | arXiv [2601.14691](https://arxiv.org/abs/2601.14691) | CoT-gaming FPR inflation ≤90%; mitigation = "verify claims against observable evidence" → option (b) pins this surface offline. |
| E2 | Agent-as-a-Judge: Evaluate Agents with Agents (Zhuge et al., ICML 2025) | arXiv [2410.10934](https://arxiv.org/abs/2410.10934) | Trajectory-aware judging is the gaming-exposed surface; the digest content is the load-bearing input. |
| E3 | VCR-style record/replay for LLM tests (`pytest-recording`/VCR.py; `llm-fixture-replay`; `llmvcr`; `vcr-llm`) | [pytest-recording TIL](https://til.simonwillison.net/pytest/pytest-recording-vcr); [llm-fixture-replay](https://dev.to/mukundakatta/vcr-style-recordreplay-for-llm-tests-make-your-agent-tests-deterministic-and-free-3o6d) | Record/replay is a prompt/parse *regression* pin (option a), cheap given the repo's existing `FakeLLMService`. |
| E4 | Eliminating Flaky Tests: Using VCR tests for LLMs (Anay Nayak) | [medium](https://anaynayak.medium.com/eliminating-flaky-tests-using-vcr-tests-for-llms-a3feabf90bc5) | Names the false-confidence risk: record/replay ≠ quality/robustness evaluation → keep (a) honestly framed, keep the live diagnostic. |
| E5 | GAMEBoT: Transparent Assessment of LLM Reasoning in Games (ACL 2025) | [aclanthology 2025.acl-long.378](https://aclanthology.org/2025.acl-long.378.pdf) | Prefer structural/rule-based ground-truth assertions over trusting model CoT → reinforces option (b). |

In-repo authorities (cited throughout): the implementation review (§2/§4/§7), the feasibility pyramid
(§2.8 enable-policy, References R1–R14), `AGENTS.md` (TAP-1..4, layer rules, pytest markers), and
`docs/Architectures/FOUR_LAYER_ARCHITECTURE.md`.
