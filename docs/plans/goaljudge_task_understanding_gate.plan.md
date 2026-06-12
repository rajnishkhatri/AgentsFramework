# GoalJudge — TaskUnderstanding Generation & Soft-Gate UI (Option D + intent card)

> **Status:** IMPLEMENTED 2026-06-12 (Phases 0–4 backend + display UI) on
> `feat/goaljudge-task-understanding-gate`. Phases 0/1/2/3 complete; Phase 4
> backend seam complete (runtime-adapter `update_task_understanding`,
> middleware `POST /run/understanding/{thread_id}` on dev + prod apps,
> PARAMETER_CHANGED governance recording, BFF handler + route, cross-instance
> hash-chain fix in BlackBoxRecorder). REMAINING: card edit-mode UI + a
> runtime/stream resume capability (`runtime.run` cannot yet resume a paused
> thread with None input) + T2 E2E; Phase 2 rollout gates (2a shadow ≥95%,
> 2b goldset replay α vs 0.50) and the Phase 0 GCP live smoke are user-run.
> **Origin:** Stage 6 replay audit [§3 finding](../research/goaljudge_stage6_replay_audit.md):
> all 100/100 production `eval.goal_judge` spans carry the identical generic
> `success_conditions` pair hardcoded at `components/plan_builder.py:158-161`. No
> task-specific derivation path ever existed. Judge-vs-gold α = 0.4987 partly attributed
> to the judge never being told task-specific completion criteria.
> **Ships with:** wave 2 ([wave-2 plan](goaljudge_stage5_phase6c_v09_and_wave2.plan.md)) —
> generator active for the batch; UI phases may slip past the batch (§8 escape hatch).
> **Governance:** [AGENTS.md](../../AGENTS.md) boundaries §2.1;
> [FOUR_LAYER_ARCHITECTURE.md](../Architectures/FOUR_LAYER_ARCHITECTURE.md) dependency
> rules §2.2; [FRONTEND_ARCHITECTURE.md](../Architectures/FRONTEND_ARCHITECTURE.md)
> invariants F-R1..F-R9 §2.3; testing per
> [tdd_agentic_systems_prompt.md](../../research/tdd_agentic_systems_prompt.md)
> (agentic pyramid L1–L4, Pattern Catalog 1–11, TAP-1..4) §2.4; trace recording per the
> governance triangle four pillars
> ([governanaceTriangle/](../../governanaceTriangle/01_explainability_fundamentals.md)) §4.7.
> **Owner pattern:** TDD (RED → GREEN per phase, **failure paths first**), no live LLM in
> CI, `.venv/bin/python -m pytest`; `pytest tests/architecture/ -q` MUST pass after every
> phase. User runs deploys/commits/flag flips.

---

## 1. Mission and locked decisions

Replace the constant generic `success_conditions` pair with a per-task
**TaskUnderstanding** artifact — an LLM-restated intent plus a task-specific success
checklist — generated once at plan time, shown to the user as a non-blocking card they
can pause/edit/resume, and consumed by the GoalJudge, the keyword evaluator, and
telemetry.

> **Hypothesis under test:** task-specific success conditions move judge-vs-gold α up
> from the 0.50 baseline ([audit §4](../research/goaljudge_stage6_replay_audit.md))
> toward the κ ≥ 0.6 prerequisite, because the judge can finally verify task-specific
> completion (the audit's FN class: GJ-F-034 subtask-dropped, GJ-F-003
> right-answer-wrong-process).

External evidence: TICK ([arXiv:2410.03608](https://arxiv.org/abs/2410.03608),
instruction-specific checklists, judge–human exact agreement 46.4% → 52.2%); RocketEval
(ICLR '25, [arXiv:2503.05142](https://arxiv.org/abs/2503.05142), instance checklists give
a 2B judge 0.965 human-preference correlation); instance-specific > generic rubrics
across all judges ([arXiv:2605.30568](https://arxiv.org/html/2605.30568)).

### Locked decisions (2026-06-12)

| Decision | Choice | Rejected alternatives |
|---|---|---|
| Generation mechanism | **Option D**: fast-tier LLM via injected `LLMService` | Local encoder-decoder (no training data — ~101 gold rows; revisit as distillation, §9.5); encoder-only (verifies, cannot generate) |
| Call site | **D1 plan-time** (step 0, `route_node`); generator sees `task_input` only — pre-registration, never the answer | D2 judge-time (no card possible; hindsight-bias risk) |
| Artifact scope | **Intent + criteria only** — pyramid Phase-1 restatement ([research/pyramid_react_system_prompt.md](../../research/pyramid_react_system_prompt.md)) as inspiration, not adoption | Full pyramid Phase 1 (issue tree — its own initiative) |
| UI gate | **Soft gate**: card streams while agent proceeds; pause/stop optional | Hard gate; adaptive |
| Correction | **Edit artifact, continue**: checkpoint `update_state` + resume; provenance → `user_edited` | Stop-and-restart |
| Sequencing | **Together with wave 2** — headless batches never pause a soft gate; calibration measures the generator alone | After v1 calibration |

### What this plan is NOT

* Not a Stage 6 change — Stage 6 measures the judge **as deployed**; its v0.9 replay
  keeps the constant pair (audit §4 seam).
* Not a rubric revision — the judge `.j2` step-3 amendment is a measured A/B arm (§7).
* Not the flag flip — phases produce evaluated gate evidence; the user owns enables and
  deploys.

---

## 2. Compliance contract

Every phase below cites the rule IDs in this section. `pytest tests/architecture/ -q`
green is a standing exit criterion for every phase that touches Python;
`tests/architecture/test_frontend_layering.ts` / `test_middleware_layering.py` for
phases 3–4.

### 2.1 AGENTS.md boundaries

| Boundary | How this plan complies |
|---|---|
| ⚠️ Ask-first: new graph nodes in `react_loop.py` | **No new node.** Generation hooks into the existing `route_node`; consumption into the existing terminal `evaluate` branch. Edit/resume lives in `middleware/`, not the graph. |
| ⚠️ Ask-first: new dependencies | **None.** Fast-tier LLM via existing `LLMService`; no torch/transformers; ONNX distillation is deferred (§9.5) and would reuse the approved `guardrails` extra. |
| ⚠️ Ask-first: new horizontal services | **None.** Flag rides the existing `GoalJudgeRuntimeConfigReader`. |
| H1 (no hardcoded prompts) | `prompts/task_understanding_prompt.j2`, rendered via `PromptService.render_prompt()`. The §3.3 deterministic floor emits *data* (conditions derived from task text), not prompt strings. |
| H2 (no hardcoded model names) | Generator profile = fast-tier resolution, same as `GoalJudge` (react_loop.py:518-521). |
| H5 / eval capture | The generator LLM call is recorded via `eval_capture.record()` with `user_id`, `task_id`, `target="task_understanding"`; an `eval.task_understanding` telemetry observation mirrors `eval.goal_judge`. |
| 🚫 No `langgraph`/`langchain` in `components/` | Generator imports services under `TYPE_CHECKING` only (the `goal_judge.py` pattern). |
| 🚫 **No peer imports between components** | **Design correction vs v1 of this plan:** the generator MUST NOT import `plan_builder` for its fallback. Contract mirrors `GoalJudge`: the generator **raises** on any failure; the orchestration thin-wrapper catches and falls back to the plan artifact's deterministic conditions (AP-5-compliant thin logic: one try/except). |
| 🚫 No domain logic in orchestration (AP-5) | route_node additions: memoization guard + try/except + state write — thin wrapper. All validation/parsing logic in `components/task_understanding.py`. |
| 🚫 No live LLM in CI | Generator mocked at L2/L3 (Pattern 6 mock provider); live calls only under `@pytest.mark.live_llm` (GCP smoke). |

### 2.2 Four-layer placement (FOUR_LAYER_ARCHITECTURE.md dependency table)

| Artifact | Layer | Imports allowed | Notes |
|---|---|---|---|
| `TaskUnderstanding` schema | `components/schemas.py` (L3) | pydantic, stdlib | NOT `trust/` — fails the trust-kernel criteria (not consumed by 2+ layers below orchestration; unstable while the design iterates). Revisit only if `middleware/` needs the Python type (§2.3 wire note). |
| `components/task_understanding.py` (generator + validation gates) | Components (L3) | `services/` + `trust/` + own schemas only; no peer components | Mirrors `components/goal_judge.py` |
| `prompts/task_understanding_prompt.j2` | Prompts | — | H1 |
| `plan_builder.py` Option-A floor | Components (L3) | unchanged (pure) | stays framework-free, deterministic |
| Flag `success_conditions_source` | `services/goal_judge_runtime_config.py` (L2) | unchanged | services never import components (invariant #7) — the flag is a string enum, no component types |
| route_node + evaluate-branch wiring | Orchestration (L4) | thin wrappers | invariant #6 |
| Telemetry fields (`conditions_source`, `restated_intent`) | `services/` sink + `middleware/adapters/observability/` | per existing sink layering | cap lift is Phase 0 |
| Edit/resume endpoint | `middleware/` (+ runtime adapter) | M1: middleware imports `agent_ui_adapter/`, `trust/`, SDKs under `middleware/adapters/` only — **never** `components/`/`orchestration/` | hence the wire-shape decision in §2.3 |
| Card UI + wire + translator | Frontend ring | §2.3 | |

**Dependency-flow check:** Orchestration → Components → Services → Trust only; the new
component depends on `LLMService`/`PromptService` (L2) and pydantic. No upward or peer
arrows added. Enforced by Pattern 7 (dependency-rule test) in `tests/architecture/`.

### 2.3 Frontend ring (FRONTEND_ARCHITECTURE.md F-R1..F-R9 + STYLE_GUIDE_FRONTEND.md)

The card and the edit round-trip touch every frontend sub-package. Placement:

| Concern | Location | Rule |
|---|---|---|
| `TaskUnderstanding` wire shape (Zod) | `frontend/lib/wire/` — extend `domain_events.ts` (`StateMutated` payload) or `agent_protocol.ts` for the edit request | wire imports stdlib + Zod only; **must update `__python_schema_baseline__.json` twin** — the `baseline_drift.test.ts` will fail otherwise (this is desired: it forces the Python↔TS schema sync) |
| Python wire twin | `agent_ui_adapter/wire/` (the `StateMutated` domain event already exists; edit-request shape added beside it) | middleware uses `agent_ui_adapter/wire/` in-process |
| Event → card props mapping | `frontend/lib/translators/` (pure function, new module or extend `ag_ui_to_ui_runtime.ts`) | translators import `wire/` + `trust-view/` only; no I/O |
| Card component | `frontend/` component tree (chat shell) | **F-R1**: receives typed props, renders, raises callbacks — zero business logic, no `adapters/` imports |
| Edit submission | BFF Route Handler `frontend/app/api/...` → delegates to a port | **F-R4**: composition only, no non-trivial branching; **F-R9**: BFF holds no credentials — checkpointer access lives in `middleware/` |
| Resume call | `middleware/` endpoint → runtime adapter `update_state` + resume (the existing HITL path) | M1 layering; SDK imports under `middleware/adapters/` only (**F-R2** mirror) |
| `trace_id` | flows verbatim from the Python runtime adapter through every hop; the edit request **echoes** the run's `trace_id`, never mints one | **F-R7** |
| SDK types | CopilotKit/LangGraph SDK types stay inside `adapters/`; card props are `wire/` shapes | **F-R2, F-R8** |
| Prompt text | none in TypeScript — the card renders model output, it contains no instruction text | **F-R5** |
| CSP | card is ordinary React in the chat shell — no new iframe, no inline scripts | AGENTS.md frontend invariants |

Frontend review dimensions FD1 (layering), FD3 (security: F-R7/F-R9), FD4
(accessibility: the card is announced via the existing `aria-live` region; pause/edit
buttons keyboard-reachable), FD5 (streaming: card must not block token rendering), FD6
(tests) apply at PR time via `prompts/codeReviewer/frontend/`.

### 2.4 Testing pyramid mapping (tdd_agentic_systems_prompt.md)

| Pyramid level | This plan's tests | Protocol / Patterns | CI cadence |
|---|---|---|---|
| **L1 Deterministic** (zero flake) | `TaskUnderstanding` schema validation (valid + invalid); validation-gate pure functions (count/length/grounding/dedupe) — property-based with Hypothesis where cheap; wire Zod parse + baseline-drift twins | Protocol A1/A2; Patterns 1, 7 | every commit, <10s |
| **L2 Reproducible** | flag contract on `GoalJudgeRuntimeConfigReader` (env/runtime/last-good); telemetry sink carries new fields; middleware edit endpoint contract (mocked runtime adapter); generator parse/fallback with **Pattern 6 mock provider** (≤3 mocks — TAP-2) | Protocol B; Patterns 4, 5, 6 | every commit, <30s |
| **L3 Probabilistic** | condition-quality rubric eval over the gold registry's subtask decompositions (formalizes the Phase-2a spot-check); trajectory check that generated conditions reference task subtasks | Protocol C2/C3; Patterns 8, 9; `@pytest.mark.slow` / `@pytest.mark.live_llm` | nightly, never CI |
| **L4 Behavioral** | memoization across loop iterations; **failure-mode matrix** for the fallback cascade; edit/resume simulation (update_state → resume → provenance in span); Playwright T1 smoke / T2 E2E | Protocol D; Patterns 10, 11 | on-demand / `@pytest.mark.simulation` |

**Anti-pattern guards baked into the test design:**

* **TAP-1**: condition-quality tests assert properties ("each enumerated task item has a
  matching condition"), never re-running the extraction regex in the test.
* **TAP-2**: generator tests use the repo's in-memory/mock `LLMService` fixture, not
  per-test mock stacks.
* **TAP-3 (determinism theater)**: NO exact-string assertions on generated conditions —
  structural assertions at L2 (count, grounding, schema), rubric scoring at L3. The
  deterministic floor (pure regex) MAY assert exact strings — it is not an LLM.
* **TAP-4 (gap blindness)**: **rejection tests written before acceptance tests** for
  every gate: each §4.2 validation gate gets its rejecting test first; the edit endpoint
  gets auth-reject and malformed-payload tests before the happy path.

---

## 3. The seams (verified 2026-06-12)

| Seam | Location | Fact that shapes the design |
|---|---|---|
| Hardcoded pair | `components/plan_builder.py:158-161` | Unconditional literal; `_extract_branches` feeds only step goals |
| Plan node re-entry | `orchestration/react_loop.py:1576-1580` | `evaluate → "continue" → route`: **route_node re-runs every loop iteration** — generation MUST memoize on a state key |
| Consumption | `react_loop.py:1293-1306` | Conditions consumed only in the terminal `done` branch by `evaluate_task_outcome`, `goal_judge.evaluate`, `gj_ai_input` |
| Service injection | `react_loop.py:483-535` | `LLMService`/`PromptService`/fast-tier profile + `GoalJudge` constructed at the `build_graph` boundary — the pattern to mirror |
| Flag machinery | `services/goal_judge_runtime_config.py` | env default + runtime override + last-good fallback; the staged shadow idiom to extend |
| MECE validator | `plan_builder.py:181-182` | Empty conditions → validation failure → capable-tier escalation side effect (`react_loop.py:775-784`); artifact must always carry ≥1 condition |
| Keyword fallback | `components/evaluator.py:284-295` | `_keyword_overlap` becomes meaningful with task vocabulary |
| Telemetry caps | `react_loop.py:1399-1401` + `services/governance/black_box_publisher.py` (`_MAX_DETAIL_VALUE_LEN=200`) | **Hard prerequisite** (Phase 0) |
| HITL resume | `build_graph(interrupt_before_execute_tool=…)` + Postgres checkpointer + middleware runtime adapter | pause/edit/resume mechanics exist — reuse |
| State event | `agent_ui_adapter/wire/domain_events.py` `StateMutated` | the natural carrier for the artifact to the UI; exact payload shape confirmed in Phase 3 RED |

---

## 4. Architecture (target design)

### 4.1 Schema (`components/schemas.py`)

```python
class TaskUnderstanding(BaseModel):
    restated_intent: str                 # pyramid Phase-1: specific, bounded restatement
    success_conditions: list[str]        # 2–7 validated, observable, YES/NO-checkable
    confidence: float = 0.0              # generator's own intent confidence, 0..1
    source: Literal["deterministic", "generated", "user_edited"] = "deterministic"
    model: str = ""                      # provenance, mirrors GoalJudge.model_name
```

### 4.2 Generator (`components/task_understanding.py`, new)

Mirrors `components/goal_judge.py`: injected `LLMService` + `PromptService` + fast-tier
`ModelProfile`; `TYPE_CHECKING`-only service imports; renders the `.j2`; tolerant JSON
extraction. **Contract: raises on any failure** (unparseable, gate rejection, LLM error)
— the orchestration wrapper owns the fallback (§2.1 peer-import rule).

Validation gates (pure functions, same module — L1-style tests):

| Gate | Rule | Catches |
|---|---|---|
| Count | 2 ≤ n ≤ 7 | runaway/empty; keeps `criteria_met` granular (de-degenerates the audit §5 trimodal ECE proxy) |
| Length | each ≤ 200 chars | prompt/span bloat |
| Lexical grounding | each condition shares ≥1 non-stopword token with `task_input` | off-topic hallucination (deterministic proxy) |
| Dedupe | normalized-text unique | repeated items skewing the fraction |

`user_edited` conditions skip lexical grounding (human is the authority) but keep
count/length bounds. A generic consistency tail condition ("The final answer is
internally consistent and directly responds to the request") is always appended —
matches the judge prompt's "supplemental constraints" framing and satisfies
`validate_plan_mece` trivially.

### 4.3 Deterministic floor (`components/plan_builder.py`)

Option A — the **fallback**, not an interim: one condition per branch from
`_extract_branches(task_input)`, using **all** branches (capped at 6), not the
depth-truncated `branches[:max_steps]` slice, plus the generic tail. `plan_builder.py`
stays pure. The generic pair never returns.

### 4.4 Prompt (`prompts/task_understanding_prompt.j2`, new)

TICK-shaped; echoes the judge prompt's step-3 subtask language so generator and judge
share a theory of subtasks; conditions must be observable and YES/NO-checkable; explicit
constraints become conditions ("without using X" → "The agent did not use X"); restate
the task as a single bounded question; self-report confidence; output ONLY JSON.

### 4.5 Orchestration (`orchestration/react_loop.py`, thin wiring only)

* Construct the generator at the `build_graph` boundary beside `GoalJudge`.
* New `AgentState` key `task_understanding` — written once at step 0 in `route_node`
  (memoization guard: skip when populated). Embedded in the plan payload.
* Flag on + generation succeeds → artifact `source="generated"`; any exception →
  artifact built from the plan artifact's deterministic conditions,
  `source="deterministic"`. One try/except — AP-5 thin.
* Terminal `done` branch reads conditions from `task_understanding` (fallback: plan
  artifact); `gj_ai_input` gains `conditions_source` + `restated_intent`;
  `eval_capture.record()` for the generation call (H5).

### 4.6 UI flow (soft gate, edit-and-continue)

1. Step 0 state write emits `StateMutated` → BFF SSE → `frontend/lib/transport/` →
   translator maps to card props → chat-shell renders "Here's my understanding" card
   (intent + checklist + pause) while the agent proceeds.
2. **Pause** = existing stop semantics.
3. **Edit** = card callback → BFF Route Handler (composition only) → middleware endpoint
   (JWT, credential-bearing) → runtime adapter `update_state(thread,
   {"task_understanding": edited})` → resume with `None` input. Provenance →
   `user_edited`; `trace_id` echoed verbatim (F-R7).
4. Post-resume steps read the corrected artifact; the terminal judge scores against the
   corrected conditions.

Mid-run edit semantics: conditions are consumed only at termination, so any edit landing
before the final evaluate is effective for judging. Intent steering (system-prompt
injection) is out of v1 scope (§9.4). A fast task may finish before the user reads the
card — accepted; late-edit re-judge is deferred (§9.3). **Silence is NOT confirmation**:
`user_edited` only on an actual edit.

### 4.7 Telemetry & trace recording — the governance triangle contract

The four pillars ([governanaceTriangle/](../../governanaceTriangle/01_explainability_fundamentals.md))
each ask one question of every run; the TaskUnderstanding lifecycle must answer all four
**from the recording alone** (the black-box investigation mindset: plan-vs-actual is the
core CVR/FDR concept — the artifact is the *intended* success definition, the judge
verdict is the *actual*; both must be reconstructable post-incident without access to
the live system).

| Pillar | Question | TaskUnderstanding obligation | Mechanism (existing idiom reused) |
|---|---|---|---|
| 1 Recording (BlackBoxRecorder) | What happened? | The generated artifact, the fallback (if fired), and any user edit land in the hash-chained `trace.jsonl` | Extend the existing `STEP_PLANNED` event (react_loop.py:761-773) `details` with `conditions_source`, `plan_ref`, and `decision_id` — **counts and join keys, not content** (compact-event discipline; full content lives in the plan file + the eval observation). A user edit is recorded as **`PARAMETER_CHANGED`** — it is exactly the FDR "control position change" / `ParameterSubstitution` concept — with `param="success_conditions"`, old/new **hashes** (compact + tamper-evident in the chain), `reason="user_edit"`, and the authenticated `user_id` |
| 2 Identity (AgentFacts) | Who did it? | Every condition set has an accountable author | `source` provenance + `model` (generated), `user_id` on the edit event (WorkOS-authenticated at the middleware), code version (deterministic). `eval_capture.record()` with `user_id`/`task_id` (H5) attributes the generation cost |
| 3 Validation (GuardRails) | What was checked? | The §4.2 anti-hallucination gates are validations and must be visible as such | `GUARDRAIL_CHECKED` TraceEvent (the input-rail idiom, react_loop.py:1020) with per-gate pass/fail in `details`; on rejection, the failing gate name is the recorded reason the fallback fired |
| 4 Reasoning (PhaseLogger) | Why was it done? | Why did THIS run use generated vs deterministic conditions? | `Decision(phase=ROUTING, description="success-conditions source", alternatives=["generated", "deterministic-fallback"], rationale=<"generated ok" \| gate/parse/LLM failure class>, confidence=<generator self-reported>)` logged via `phase_logger.log_decision`; its `decision_id` goes into the `STEP_PLANNED` details — the **cross-pillar join key**, mirroring the `MODEL_SELECTED` idiom at react_loop.py:824-845 |

Plus the Langfuse eval path: a new **`eval.task_understanding`** observation published
via `eval_telemetry` mirroring `publish_goal_judge` (react_loop.py:1432) — full
`restated_intent` + conditions + `source` + fallback reason + generator confidence.
Same **O1 contract: the publisher MUST NOT raise.** The existing `eval.goal_judge`
observation gains `conditions_source` + `restated_intent` (§4.5), so judge verdicts are
stratifiable by condition provenance without trace re-joins.

Recording invariants:

* **Plan-vs-actual joinability.** From the black box alone: `STEP_PLANNED.decision_id` →
  the PhaseLogger Decision (why this source); `STEP_PLANNED.plan_ref` → the plan file
  (what was intended); terminal `TASK_COMPLETED` + `eval.goal_judge` (what was judged).
  A `PARAMETER_CHANGED` between them proves the verdict basis changed mid-run and who
  changed it — without it, post-incident analysis cannot explain why the judge scored
  against different conditions than were generated. This is the governance-critical
  event of the whole feature.
* **Compact events, content elsewhere.** TraceEvent `details` carry counts, hashes,
  enums, and join keys; full text rides the plan payload and the `eval.*` observations
  (whose caps Phase 0 lifts). This keeps the hash chain cheap and the publish-path
  redaction story unchanged: `redact_text` still applies to everything that leaves the
  box (PII in a task restatement is redacted at publish, not at local record — same as
  `task_input` today).
* **Phase placement.** Generation + its Decision live inside the existing
  `WorkflowPhase.ROUTING` span (where the plan is built); consumption telemetry stays in
  `WorkflowPhase.EVALUATION` (the existing judge path, react_loop.py:1168-1246). No new
  phases, no new EventTypes — the nine existing types cover the lifecycle.

---

## 5. Phases

Conventions for every phase: **RED first, failure paths before success paths (TAP-4)**;
GREEN = minimal implementation; REFACTOR with architecture tests green
(`pytest tests/architecture/ -q`, and the frontend/middleware layering suites for
phases 3–4); no live LLM outside `@pytest.mark.live_llm`.

### Phase 0 — Telemetry cap lift (HARD PREREQUISITE; shared with wave-2 plan §5.2)

**Scope.** Lift `[:500]` truncations (`react_loop.py:1399-1401`, config-driven) and give
`eval.goal_judge` (and the new `eval.task_understanding`) attributes an
exemption/larger bound than `_MAX_DETAIL_VALUE_LEN=200` in `black_box_publisher`.

**Layer.** L2 (`services/governance/`) + L4 wiring. No component changes.

**RED (failure first).**
* L2: publisher truncates a non-exempt attribute at 200 (regression guard for the
  redaction contract — the exemption must be narrow, not a blanket lift).
* L2: exempted `eval.*` attribute over 200 chars survives publish intact; PII redaction
  still applies to exempted attributes (redact ≠ truncate — the L2 redactor still runs).
* L2: sink contract test (`tests/middleware/adapters/observability/`) round-trips long
  `success_conditions`.

**GREEN.** Narrow exemption list + config knob (numeric knobs in code, not prose —
AGENTS.md config convention).

**Gate.** GCP live smoke (`@pytest.mark.live_llm`, existing gate pattern): full
`success_conditions` + `restated_intent` visible in the Langfuse span.

### Phase 1 — Deterministic floor (Option A)

**Scope.** §4.3. Pure-component change.

**RED (failure first).**
* L1-style (in `tests/components/test_plan_builder.py`): empty task input → non-empty
  generic fallback (rejection of the empty case first); duplicate branches do not yield
  duplicate conditions; `validate_plan_mece` passes on every floor output (the escalation
  side effect at `react_loop.py:775-784` must never fire from floor conditions).
* Acceptance: multi-clause task yields per-branch conditions containing branch text
  (exact-string asserts allowed — pure regex, not an LLM, TAP-3 N/A); an L0-depth task
  with 3+ branches still gets all branch conditions; generic tail always last.
* Property-based (Pattern 1, Hypothesis): for arbitrary non-empty task strings, floor
  output has 1 ≤ n ≤ 7 conditions, no duplicates, tail present.
* `tests/components/test_evaluator.py`: keyword `criteria_met` > 0 for an answer
  covering the branches (impossible with the generic pair — the load-bearing assertion).

**GREEN.** Implement §4.3.

**Gate.** Offline tier green; **the generic pair string no longer appears anywhere in
`components/`** (grep-able exit check); architecture tests green.

### Phase 2 — Generator + flag (shadow → consume)

**Scope.** §4.1, §4.2, §4.4, §4.5, flag on `GoalJudgeRuntimeConfig`.

**RED (failure first).**
* L1: `TaskUnderstanding` schema — invalid payloads rejected (missing fields, conditions
  not a list, confidence out of range) before the valid-case test; validation gates as
  pure-function tests, **each gate's rejecting case first** (count 0/1/8; 201-char item;
  ungrounded condition; duplicates), then accepting cases. Property-based where cheap.
* L2 (Pattern 6 mock provider, ≤3 mocks): malformed JSON → raises; LLM exception →
  raises; fenced-JSON tolerated; gate rejection → raises; happy path → artifact with
  `source="generated"`, `model` set; prompt-render test (`.j2` resolves, task text
  present — H1).
* L2: flag contract on the reader (env default, runtime override, last-good fallback,
  default `"deterministic"`).
* L4 (orchestration, mocked graph runs):
  * **memoization**: a 3-iteration run calls the generator exactly once (Pattern 11 row);
  * flag off → deterministic conditions reach judge + span; flag on → generated; flag on
    + generator raises → deterministic (the **failure-mode matrix**, Pattern 11: ×
    {flag off, flag on+ok, flag on+raise, flag on+gate-reject} × {judge enabled/disabled}
    — every cell asserts `conditions_source` in `gj_ai_input` and which conditions the
    judge received);
  * plan payload round-trips the artifact; `eval_capture.record()` called with
    `user_id`/`task_id`/`target` (H5);
  * **governance recording (§4.7)**: `STEP_PLANNED` details carry
    `conditions_source`/`plan_ref`/`decision_id`; a ROUTING-phase Decision is logged
    with the matching `decision_id` and — on the fallback cells of the failure-mode
    matrix — a `rationale` naming the failure class (rejection cells tested first,
    TAP-4); gate rejection emits `GUARDRAIL_CHECKED` with the failing gate named;
    black-box hash chain stays valid across the new events (L2, replay the JSONL);
    `eval.task_understanding` publisher MUST NOT raise (O1 — exception-swallowing
    test before the happy-path publish test).
* L3 (`@pytest.mark.slow`/`live_llm`, nightly — Patterns 8/9): rubric eval of generated
  condition sets against the gold registry's subtask decompositions (structural
  rubric: one condition per enumerated subtask, no invented requirements); aggregate
  pass-rate threshold, not exact strings (TAP-3).

**GREEN.** Implement; wire route_node + done branch.

**Rollout & gates** (the `would_downgrade` shadow idiom):

| Stage | Behavior | Gate to advance |
|---|---|---|
| 2a Shadow | generate + validate + log to span; judge consumes deterministic | ≥95% of runs pass validation gates; L3 rubric eval over ~30 goldset rows meets threshold; human spot-check |
| 2b Consume | judge consumes generated conditions | Stage 6 goldset replay: α improves vs 0.50 recorded-verdict baseline; G-P (FN-precision ≥0.90) and FD-rate do not regress; re-check audit §4 FP rows (GJ-F-068/074 push-back) for new false failures |

### Phase 3 — AG-UI card, display-only

**Scope.** Wire twins, translator, card component, SSE plumbing. Additive — cannot
break headless batches.

**RED (failure first).**
* L1 wire: Zod parse rejects malformed `task_understanding` payloads first; valid parse;
  **Python↔TS baseline**: regenerate `__python_schema_baseline__.json`, `baseline_drift.test.ts`
  green (this test failing during development is the mechanism working — fix by syncing
  both kernels, never by loosening the test).
* L1 translator: pure mapping event → card props; unknown/absent state key → no card
  (rejection first); no I/O (enforced by frontend layering test).
* Frontend layering (`tests/architecture/test_frontend_layering.ts`): card component
  imports no `adapters/` (F-R1); new wire/translator files import nothing outside their
  ring (F-R2/F-R8).
* T1 Playwright (chromium-only smoke — full T1 tier is off-limits locally): mocked
  fetch-SSE run streams a `StateMutated` with the artifact → card appears with intent +
  conditions while tokens continue streaming (FD5: card must not block token rendering);
  run without the artifact → no card, no layout shift; card announced via the existing
  `aria-live` region (FD4).

**GREEN.** Implement both wire kernels, translator, card, chat-shell mount.

**Gate.** T1 smoke green; frontend + middleware architecture suites green; a local batch
run's JSONL output is byte-identical to pre-card (headless invariance).

### Phase 4 — Edit/resume seam

**Scope.** BFF route, middleware endpoint, runtime-adapter `update_state` + resume, card
edit mode.

**RED (failure first).**
* L2 middleware (mocked runtime adapter): unauthenticated request → 401 **first**;
  malformed payload (count/length bounds; lexical-grounding deliberately NOT enforced
  for `user_edited`) → 422; wrong/missing `trace_id` echo → 400 (F-R7); happy path →
  `update_state` called with `source="user_edited"` then resume.
* Middleware layering (`tests/architecture/test_middleware_layering.py`): endpoint
  imports no `components/`/`orchestration/` (M1) — the edit payload is an
  `agent_ui_adapter/wire/` shape, not the components Pydantic type.
* L4 simulation (Pattern 10, mocked LLM, real checkpointer in-memory): run → pause at a
  checkpoint → `update_state` → resume → final `gj_ai_input` carries
  `conditions_source="user_edited"` with the edited text; edit arriving after run
  completion → no-op with explicit error (rejection case).
* **Governance recording (§4.7)**: the edit emits a `PARAMETER_CHANGED` TraceEvent
  with `param="success_conditions"`, old/new hashes, `reason="user_edit"`, and the
  authenticated `user_id` — asserted into the hash-chained `trace.jsonl` (an edit
  WITHOUT a corresponding `PARAMETER_CHANGED` event is the rejection case and a test
  failure: the verdict basis must never change unrecorded).
* BFF route test: delegates to the port, no business-logic branches (F-R4 — review
  check, plus the route stays under the composition-only lint).
* T2 Playwright E2E: pause → edit a condition → resume → completion; span assertion via
  the existing Cloud Logging/Langfuse verification pattern.

**GREEN.** Implement; card edit mode behind the same flag.

**Gate.** T2 green; F-R9 audit: no checkpointer/DB credential in any BFF env var.

### Phase 5 — Wave-2 batch with generator ON

Run the wave-2 GCP batch with `success_conditions_source="generated"` (Phases 0–2
required; 3–4 optional — §8). Headless ⇒ all rows `source="generated"` ⇒ v1 calibration
(Stage 6 §2.8 gates) measures the generator pipeline alone, uncontaminated by the UI.
Batch verification per the workspace Playwright skill (registry batch + Cloud Logging +
Langfuse).

---

## 6. Phase dependency graph

```
Phase 0 (cap lift) ──────────────┐
Phase 1 (floor) ── Phase 2 (generator: 2a → 2b) ── Phase 5 (wave-2 batch)
                          │
                          ├── Phase 3 (card, display-only) ── Phase 4 (edit/resume)
                          │        (3 and 4 may slip past Phase 5 — §8)
Phase 0 also gates Phase 5 (span fidelity for v1 calibration)
```

## 7. Judge-prompt A/B arms (Stage 6 harness, separate variables)

| Arm | Change | Why separate |
|---|---|---|
| A (default) | judge receives generated conditions, prompt unchanged | minimal-change baseline |
| B | amend judge `.j2` step 3: trust `success_conditions` as the decomposition when they enumerate subtasks (the current demotion was a workaround for the generic pair) | prompt change must be measured, not smuggled |
| C | judge also receives `restated_intent` | plausibly real α, but a second variable |

## 8. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| Hallucinated condition | judge fails a correct answer (the §2.8 FP pain point) | lexical-grounding gate; 2b gate re-checks known FP rows |
| Merged subtasks in one condition | `partial_fraction` coarsens | acceptable — judge step 3 still decomposes from task language |
| LLM outage / malformed output | none user-visible | raise → orchestration fallback; alert if fallback rate spikes |
| Rerun non-determinism | replay variance | temperature 0; conditions persisted per-run; replay reuses recorded values (audit §4 join unchanged) |
| Wire-schema drift Python↔TS | broken card or broken batch | baseline-drift test is the enforcement; both kernels updated in the same PR |
| Wave-2 schedule pressure | UI not ready for the batch | **escape hatch:** Phases 3–4 may slip — calibration needs only Phases 0–2 |
| TTFT +0.5–1.5 s at step 0 | chat UX | the pause window is the feature; batches don't care; revisit on p95 regression |

Cost: one fast-tier call per task (~600 in / ~150 out tokens, ~$0.001/task; ~$0.15 per
wave-2 batch).

## 9. Open items

1. **§7 arm choice** — ship arm A with 2b; schedule B and C as harness runs.
2. **`StateMutated` payload shape** — confirm against `agent_ui_adapter/wire/domain_events.py`
   and the chat-shell state plumbing in Phase 3 RED.
3. **Re-judge after late edit** — deferred.
4. **Intent steering** (inject `restated_intent` into the agent system prompt; STICK) —
   deferred; D1 keeps the door open.
5. **Distillation (Option E)** — once interactive traffic accumulates `user_edited`
   artifacts, revisit a local encoder-decoder generator (MiniCheck recipe,
   [arXiv:2404.10774](https://arxiv.org/abs/2404.10774)) exported to ONNX behind the
   approved `guardrails` extra (`services/governance/injection_classifier.py`
   precedent). Out of scope until the corpus exists and volume justifies it.
