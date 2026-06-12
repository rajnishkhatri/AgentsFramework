# Trace Explainability Optimization — Curated Langfuse View over Canonical BlackBox

> **Status:** IN PROGRESS 2026-06-12. Branch: `feat/trace-explainability-optimization`
> off the `feat/goaljudge-task-understanding-gate` tip (its committed cap lift +
> react_loop changes are the dependency Phase 0.1 verifies; branching off that tip
> rather than `main` keeps them in lineage — user-confirmed). **Phase 0 DONE** (0.3
> service.name + 0.2 spikes D-0a/D-0b resolved; 0.1 GCP cap-lift smoke user-run).
> **Phase 1 DONE** (native types, model.selected→chain, trace-level outcome scores,
> would_downgrade on TASK_COMPLETED, identity registry into the compliance bundle).
> **Known inherited condition:** `tests/architecture/test_mphase2_swap_radius.py` fails
> on this branch — a pre-existing TU-gate artifact (TU-gate commits touch both
> `agent_ui_adapter/adapters/` and `components/` in one range). Architecture gate run as
> `-k 'not swap_radius'` until the user resolves it on the TU-gate branch.
> **Origin:** 2026-06-12 critical trace review of run `3869d6160cf8404a8f6d74db94212ebd`
> against the governance-triangle intent. Headline findings: (1) the terminal verdict is
> self-contradictory (`outcome: success`, `goal_met: False`, `criteria_met: 0.0`,
> `unmet_conditions: []`, `task_completion_score: 0.887`); (2) two pipelines (wire bridge
> + BlackBox relay) describe every LLM/tool fact 2–3× with no join keys (~13 observations
> per step for ~8 facts); (3) the four-pillar questions the trace exists to answer —
> "why this model?", "what was the plan?", "who ran this?" — are the parts missing.
> **External grounding:** OTel GenAI semantic conventions (one `generation` span per LLM
> call with input/output/usage; one `tool` span per tool call; spans named by function);
> Langfuse "what does a good trace look like" (correct `as_type`, meaningful
> input/output on every observation, filter out noise, trace-level scores for list-view
> scannability).
> **Governance:** [AGENTS.md](../../AGENTS.md) architecture invariants 1–8 and
> boundaries; [FOUR_LAYER_ARCHITECTURE.md](../Architectures/FOUR_LAYER_ARCHITECTURE.md)
> dependency rules; four pillars per
> [governanaceTriangle/01_explainability_fundamentals.md](../../governanaceTriangle/01_explainability_fundamentals.md)
> and the production taxonomy reconciliation in
> [governanaceTriangle/02_black_box_recording_debugging.md](../../governanaceTriangle/02_black_box_recording_debugging.md);
> testing per [tdd_agentic_systems_prompt.md](../../research/tdd_agentic_systems_prompt.md)
> (pyramid L1–L4, failure-paths-first, TAP-1..4); telemetry rule **O1** (telemetry never
> blocks/raises) and SDK isolation **F-R2/A1** (`langfuse` imports only in
> `middleware/adapters/observability/`).
> **Owner pattern:** TDD (RED → GREEN per phase, **failure paths first**), no live LLM in
> CI, `.venv/bin/python -m pytest`; `pytest tests/architecture/ -q` MUST pass after every
> phase. User runs deploys, commits, and flag flips.

---

## 1. Mission and locked decisions

Make the Langfuse trace a **curated, human-first explainability view** — every fact
exactly once, correct observation types, honest timings, scannable verdicts — while the
hash-chained BlackBox JSONL + compliance bundle remain the **canonical audit record**.
Target: ≤8 observations per agent step (from ~13), zero cross-pipeline duplicate facts,
and each pillar question answerable from the trace in one click.

### Locked decisions (2026-06-12, user-confirmed)

| Decision | Choice | Rejected alternatives |
|---|---|---|
| Canonical audit artifact | **BlackBox JSONL + compliance bundle** (dataset `agent-compliance-audit`, `hash_chain_valid` score). Langfuse trace is a curated view | Langfuse-audit-complete (lossy anyway: 200-char caps; chain not verifiable in Langfuse) |
| Pipeline ownership | **Wire bridge owns LLM/tool content; BlackBox relay owns governance-distinct events** (plan, routing, guardrails, parameter changes, errors, terminal summary) | BlackBox-owns-everything (needs R1/R3 enrichment first, loses streamed content); keep-both-with-join-keys (duplication remains) |
| Constraint | **Readability only** — no delta-encoding of prompts; a self-contained full input per generation is the Langfuse norm | Byte-shaving |
| Consumers | All three: ops triage, GoalJudge Stage 5/6 calibration, compliance demos | — |
| Guardrail clean passes | **Keep, at `DEBUG` level** (filterable; demos can still show the provable negative). Blocked → `WARNING` | Suppress from relay; keep all at DEFAULT |
| Usage source for the merged generation | **Optional fields on `LLMMessageEnded`** (`tokens_in`, `tokens_out`, `cost_usd`, `model`), populated by the runtime adapter | Keep relaying slim `STEP_EXECUTED` as the usage carrier |
| Rollout | **Flag-gated relay suppression** (`LANGFUSE_RELAY_CURATED`, default on) + per-phase GCP smoke. One flag flip restores the audit-complete dual view | Hard removal, single final verification |
| Branch | Off `main` after TU-gate merge | Stacking on `feat/goaljudge-task-understanding-gate` |

### What this plan is NOT

* **Not a change to what is recorded in the canonical JSONL** — events keep flowing to
  the hash chain. Changes are additive details, a `plan_changed` flag, and relay-side
  *export* suppression. `export()`, `replay()`, and the compliance bundle see everything.
* **Not the GoalJudge `criteria_met` parser fix** — `GoalJudge._parse_verdict` defaulting
  `criteria_met` to 0.0 against a populated `per_criterion` is a separate spawned task
  (`components/goal_judge.py:122`); Phase 1 only stops the *trace* from amplifying the
  contradiction.
* **Not prompt delta-encoding** — volume is explicitly not a constraint.
* **Not a Stage 6 calibration change** — `eval.goal_judge` attributes are untouched
  (Stage 6 slices depend on them).
* **Not the final audit-canonicality word** — Option B (audit-complete trace) stays one
  flag away by design.

---

## 2. Compliance contract

Every phase cites these rule IDs. Standing exit criteria for **every** phase:
`pytest tests/ -q` and `pytest tests/architecture/ -q` green.

| ID | Rule | Where it bites in this plan |
|---|---|---|
| **INV-1/6** | Dependencies flow downward; orchestration nodes thin | Plan fingerprint helper lives in `components/plan_builder.py`, not `react_loop.py` (AP-5) |
| **INV-3/4** | `components/`, `services/` framework-agnostic | All publisher/relay changes stay `langfuse`/`langgraph`-free (enforced by `tests/architecture/test_middleware_layer.py`) |
| **O1** | Telemetry never blocks/raises | Every new export/score path wrapped; failure-path tests first |
| **F-R2/A1** | `langfuse` SDK imports only in `middleware/adapters/observability/` | Exporter is the only file touching SDK kwargs |
| **H5** | Every LLM call through `eval_capture.record()` | Unchanged; no eval-capture path is modified |
| **W (wire ring)** | `agent_ui_adapter/wire/` framework-neutral, additive evolution | `LLMMessageEnded` gains optional fields only; old payloads must still validate |
| **TDD** | Failure paths first; L2 contract tests mock I/O; no live LLM in CI; TAP-1..4 | Each phase lists RED before GREEN; suppression tests assert the *rejection* (not-exported) before the acceptance |
| **Pillars** | Recording / Identity / Validation / Reasoning each answerable | §5 contract table maps every observation to a pillar question |

---

## 3. Current state — evidence index (from the 2026-06-12 review)

| # | Finding | Evidence |
|---|---|---|
| E1 | Terminal contradiction | `task.completed` details; judge `criteria_met: 0.0` vs `per_criterion` 4/4 met |
| E2 | 2–3 observations per fact, unjoinable | `tool.started/finished` (bridge) + `tool.called` (relay) for each call; `llm.started/finished` + `step.executed` + `model.selected` per LLM call |
| E3 | Full prompt re-exported per `llm.started`; duplicated again (truncated) in metadata | `telemetry_bridge.py:102-106`; `langfuse_cloud_exporter.py:210-215` passes `input=attrs` AND `metadata=_metadata(attrs)` |
| E4 | Type destruction: `"True"`, `"0.0"`, `"[]"`, `"None"` strings | `black_box_publisher.redact_details` coerces all values to `str` (`:100-109`) |
| E5 | Inverted observation types | `MODEL_SELECTED` → `generation` (no usage); `STEP_EXECUTED` → `span` (carries usage) (`black_box_publisher.py:53-63`) |
| E6 | Fictional timings | Point events (start==end); relayed obs stamped at relay time (~0.9s late); all `step.N` spans closed together at `release_trace` |
| E7 | Identity pillar dead | Relay calls `export_for_compliance` without `agent_facts_registry` (`black_box_to_telemetry.py:284-288`); no agent version anywhere in trace |
| E8 | Reasoning content missing | `model.selected` carries `decision_id` but rationale/alternatives only reach `decisions.jsonl`; `step.planned` carries counts + unreachable `plan_ref` |
| E9 | No trace-level scannability | Only score is `hash_chain_valid`; trace name `agent-run-{id[:12]}`; no trace input/output |
| E10 | `step.planned` identical re-emissions per iteration (route_node re-runs) | steps 7, 8 identical `{L0,1,1,2}` |
| E11 | `service.name: unknown_service` on every event | resourceAttributes |
| E12 | 200-char caps still live in deployed build (judge rationale cut mid-word) | cap lift is on the TU-gate branch, not yet deployed |

---

## 4. Target trace shape

```
trace: agent-run  (input: task_input; output: final answer;
                   scores: goal_met, criteria_met, task_completion_score, hash_chain_valid)
├─ task.started        (agent)  — agent identity: name, version, agent_facts_id
├─ step.N              (span)   — one per loop iteration
│  ├─ step.planned     (chain)  — ONLY when plan changed; plan summary + fingerprint
│  ├─ model.selected   (chain)  — model, reason, rationale, alternatives, decision_id
│  ├─ llm.call         (generation) — full input, output, model, usage, cost, latency_ms
│  ├─ tool.{name} ×k   (tool)   — args + result + ok + latency_ms (one per call)
│  ├─ guardrail.checked (guardrail) — DEBUG when clean, WARNING when blocked/redacted
│  ├─ parameter.changed (span)  — when it occurs
│  └─ error.occurred   (span, level=ERROR) — when it occurs
├─ eval.goal_judge     (evaluator) — unchanged
├─ task.completed      (agent)  — consistent summary incl. would_downgrade
└─ run.finished        (span)
```

### Per-observation contract (the curated view)

| Observation | Producer | Type | Pillar question answered | Suppressed from Langfuse |
|---|---|---|---|---|
| `task.started` / `task.completed` | relay | agent | Who ran this? Did it succeed and why? | never |
| `step.planned` (changed only) | relay | chain | What was the plan? | when `plan_changed=False` and curated flag on |
| `model.selected` | relay | chain | Why this model? | never |
| `llm.call` (merged) | bridge | generation | What did the model see/say? cost? | never |
| `tool.{name}` (merged) | bridge | tool | What did the agent actually do/observe? | never |
| `tool.called` | relay | tool | (duplicate of above) | **always when curated flag on** (JSONL keeps it) |
| `step.executed` | relay | span | (usage duplicate) | **always when curated flag on** (JSONL keeps it) |
| `guardrail.checked` | relay | guardrail | What was checked? (provable negative) | never (DEBUG on clean pass) |
| `parameter.changed`, `error.occurred` | relay | span | What changed / what broke? | never |
| `eval.goal_judge`, `eval.task_understanding` | eval sink | evaluator | Was the goal met, per what criteria? | never |

---

## 5. Phases

Convention per phase: **RED** (write failing tests, rejection/failure paths first) →
**GREEN** (implement) → **Exit** (suites + architecture tests + phase-specific GCP smoke;
user runs deploys). File paths are exact; line refs are pre-TU-merge approximations.

---

### Phase 0 — Prerequisites and spikes (no behavior change)

**0.1 (user-run gate)** TU-gate branch merged to `main`; deployed; fresh GCP run shows
`eval.goal_judge` with `final_answer`/`rationale` **longer than 200 chars** (cap lift
live, closes E12). Use the existing GCP smoke playbook
(`agentsframework-playwright` skill; Cloud Logging `thread=session-gj-XXX` form).

**0.2 (spike, ≤half day)** Langfuse SDK v4 capabilities — record outcomes in §8:
* **D-0a:** does `start_observation()` accept explicit start/end times (OTel
  `start_time`)? If yes → Phase 2 stamps relayed observations with the true
  `event.timestamp`. If no → relayed observations keep relay-time spans and the plan
  documents `details.timestamp` as the authoritative event time (no fake durations).
* **D-0b:** how to set trace-level input/output with the OTel-based v4 SDK
  (`propagate_attributes` / `langfuse.trace.input|output` attributes / root-span
  derivation). Feeds Phase 5.3.

**0.3** Set `service.name` (E11): `OTEL_SERVICE_NAME` (or SDK resource attrs) in
middleware deploy config for dev + prod apps.

**Exit:** spike notes in §8; a smoke trace shows a real service name.

---

### Phase 1 — Terminal truth and scores (E1, E4, E5, E7, E9-partial)

The largest explainability win per line changed: make the end of the trace internally
consistent and scannable from the trace list.

**RED — failure paths first**
* `tests/middleware/sidecars/test_black_box_to_telemetry.py`:
  - on `TASK_COMPLETED`, relay calls `score_trace` for `goal_met` (0/1),
    `criteria_met`, `task_completion_score` — **rejection tests first:** details with
    missing/`None` fields → no score call for that field, **no raise** (O1); publisher
    `score_trace` raising → swallowed, bundle publish still proceeds.
  - `export_for_compliance` is called **with** `agent_facts_registry` when the relay was
    constructed with one (E7).
* `tests/middleware/sidecars/test_compliance_dataset.py`: bundle includes
  `identity_cards` when a registry with a known agent is provided.
* `tests/services/governance/test_black_box_publisher.py`:
  - `redact_details` preserves native `int`/`float`/`bool` for safe keys and passes
    `None` through as `None` (not `"None"`); **failure paths:** PII inside a string
    value is still redacted; a long string under a safe key is still capped; an unsafe
    key with numeric-looking content still goes through regex redaction.
  - `MODEL_SELECTED` maps to `("chain", "model.selected")` and no longer emits
    generation usage promotion.
* `tests/orchestration/test_phase_wiring.py`: `TASK_COMPLETED` details include
  `would_downgrade` (False when judge skipped/failed; True in the shadow case).

**GREEN**
* `services/governance/black_box_publisher.py`:
  - `redact_details` → returns `dict[str, Any]`; add `_SAFE_BOOL_KEYS`
    (`plan_valid`, `checked`, `blocked`, `redacted`, `goal_met`, `termination_clean`,
    `cached`, `would_downgrade`, `plan_changed`) and extend `_SAFE_NUMERIC_KEYS`
    (`criteria_met`, `task_completion_score`, `branch_coverage`, `cost_fraction`);
    `None` passes through.
  - `_EVENT_TYPE_TO_OBSERVATION[MODEL_SELECTED] = ("chain", "model.selected")`; remove
    its I5 generation promotion branch.
* `middleware/sidecars/black_box_to_telemetry.py`: new `_publish_outcome_scores()`
  invoked from the `TASK_COMPLETED` branch; constructor accepts optional
  `agent_facts_registry` and forwards it to `export_for_compliance`.
* Middleware composition roots (`middleware/__main__.py`, `app_prod.py`): build/pass the
  registry to the relay.
* `orchestration/react_loop.py` (`TASK_COMPLETED` details): add `would_downgrade`
  (define `False` on the judge-skipped path so the field is shape-stable).

**Exit:** suites green; GCP smoke trace shows the three scores in the Langfuse list
view; `task.completed` shows native types and no `"None"` strings; compliance bundle
dataset item contains `identity_cards`.

---

### Phase 2 — Correlation keys and honest timestamps (E2-joins, E6)

**RED**
* `tests/middleware/test_telemetry_correlation.py`:
  - `TOOL_CALLED` details include `tool_call_id` → joinable to the bridge tool
    observation in the canonical record.
  - bridge tool exports carry `step` (parsed from the `"{step}:call_..."` prefix of
    `tool_call_id`); malformed prefix → `step` omitted, **no raise**.
* `tests/services/governance/test_black_box_publisher.py` (per **D-0a = no backdating**):
  every relayed observation's attributes include `event_time` (= `event.timestamp`
  ISO string) so the authoritative event instant survives even though the Langfuse
  span is stamped at relay-export time. Assert `event_time` present on a sample of each
  observation type; assert we do **not** attempt a fabricated `start_time`/`end_time`.

**GREEN**
* `orchestration/react_loop.py` `TOOL_CALLED` emissions (`:217`, `:280`): add
  `tool_call_id` (the loop owns `tool_id`).
* `middleware/telemetry_bridge.py`: derive `step` for tool events from the id prefix.
* Exporter timestamp handling per D-0a.
* **D-2a (discovery):** whether the runtime adapter can attach `step` to LLM domain
  events cheaply (`agent_ui_adapter/adapters/runtime/langgraph_runtime.py`). If not,
  document `step`-by-containment (generation nests under `step.N` once Phase 5.3 nests
  bridge events) as the join, and move on — do not contort the wire ring for it.

**Exit:** from a single Langfuse trace one can join: bridge tool obs ↔ JSONL
`TOOL_CALLED` row (by `tool_call_id`) and generation ↔ `STEP_EXECUTED` row (by `step`).

---

### Phase 3 — One observation per LLM call and per tool call (E2, E3, E6)

**RED**
* `tests/agent_ui_adapter/wire/test_domain_events.py`:
  - `LLMMessageEnded` accepts optional `tokens_in: int | None`, `tokens_out: int | None`,
    `cost_usd: float | None`, `model: str | None`; **backward-compat rejection test:** a
    pre-existing payload without the new fields still validates; unknown-field behavior
    unchanged.
* `tests/agent_ui_adapter/adapters/runtime/test_langgraph_runtime.py`: runtime populates
  usage/model on `LLMMessageEnded` from `usage_metadata` when present; absent metadata →
  fields `None`, event still emitted.
* `tests/middleware/test_telemetry_bridge.py` (substantial rewrite of the llm/tool
  cases) — **orphan/failure paths first:**
  - `LLMMessageEnded` with no prior `LLMMessageStarted` → exports with `input` absent,
    no raise.
  - `ToolResultReceived` with no prior `ToolCallStarted` → exports result-only.
  - `RunFinishedDomain` clears all per-trace buffers (started-but-never-finished calls
    do not leak — assert buffer maps empty after release).
  - Happy paths: `LLMMessageStarted` produces **zero** exports; one `llm.call`
    export on `LLMMessageEnded` carrying `input_text`, output (token-buffer fold
    unchanged), `__bb_model`, `__bb_usage`, `__bb_cost`, and `latency_ms` (wall time
    started→finished). `ToolCallStarted` produces zero exports; one `tool.{tool_name}`
    export on `ToolResultReceived` with args + result + `latency_ms`.
* `tests/middleware/test_telemetry_redaction.py`: redaction still applied to the merged
  payloads (input, args, result).

**GREEN**
* `agent_ui_adapter/wire/domain_events.py`: optional fields on `LLMMessageEnded`.
* `agent_ui_adapter/adapters/runtime/langgraph_runtime.py`: populate them.
* `middleware/telemetry_bridge.py`: buffer `LLMMessageStarted` and `ToolCallStarted`
  (extend the `_llm_token_buffers` pattern with `(trace_id, key)` maps + timestamps);
  emit single merged observations; per-trace cleanup on run-finish/release;
  `_SKIPPED_TYPES` gains `LLMMessageStarted`/`ToolCallStarted` direct-export paths.
* **D-3a (naming):** rename exports `llm.finished` → `llm.call`,
  `tool.finished` → `tool.{tool_name}` per Langfuse function-naming guidance. Grep
  dashboards/queries for the old names before the rename lands; `eval.goal_judge` and
  all relay names are untouched, so Stage 5/6 tooling is unaffected.

**Exit:** smoke trace shows exactly one generation (with cost/usage rendered natively by
Langfuse) and one tool observation per call; bridge buffer maps empty after each run.

---### Phase 4 — De-duplication: the curated view flag (E2, E3-metadata, E10 + guardrail levels)

**RED — suppression is a rejection gate; test the rejection first**
* `tests/middleware/sidecars/test_black_box_to_telemetry.py`:
  - curated flag ON (default): `TOOL_CALLED` and `STEP_EXECUTED` lines are consumed
    (offset advances, **no DLQ entry**, counted as processed-not-published) and produce
    zero `export_event` calls; `TASK_COMPLETED` still triggers scores + bundle.
  - curated flag ON: `STEP_PLANNED` with `plan_changed=False` suppressed;
    `plan_changed=True` (or flag absent — back-compat for old JSONL rows) exported.
  - curated flag OFF: all events exported exactly as today (the Option-B escape hatch).
* `tests/services/governance/test_black_box_publisher.py`:
  - `GUARDRAIL_CHECKED` level: `DEBUG` when `blocked=False`/`redacted=False`/empty
    `failed_rules`; `WARNING` when blocked or redacted. (`ERROR_OCCURRED` stays `ERROR`.)
* `tests/middleware/adapters/observability/test_langfuse_cloud_exporter.py`:
  - metadata is an **allowlist** (`step`, `workflow_id`, `event_id`, `tool_name`,
    `model`, `subject`) — full attrs appear only in `input`; assert a bulky field
    (`input_text`, `details`) is NOT duplicated into metadata.
* `tests/components/test_plan_builder.py`: `compute_plan_fingerprint()` — deterministic,
  order-sensitive over `(planning_depth, ordered_steps, constraints,
  success_conditions)`; differing plans → differing fingerprints.
* `tests/orchestration/test_phase_wiring.py`: `STEP_PLANNED` details carry
  `plan_fingerprint` + `plan_changed`; an unchanged consecutive plan is **still recorded
  to JSONL** with `plan_changed=False` (canonical record stays complete — Option A).

**GREEN**
* `components/plan_builder.py`: `compute_plan_fingerprint()` (INV-6/AP-5: logic lives in
  components; `react_loop` just calls it and compares against
  `state["last_plan_fingerprint"]`).
* `orchestration/react_loop.py` + `orchestration/state.py`: fingerprint comparison,
  `plan_changed` detail, state field.
* `middleware/sidecars/black_box_to_telemetry.py`: constructor `curated_view: bool`
  (composition roots read `LANGFUSE_RELAY_CURATED`, default `"true"`); `_process_line`
  consults a `_CURATED_SUPPRESSED = {TOOL_CALLED, STEP_EXECUTED}` set + the
  `step_planned`/`plan_changed` rule. Suppression returns "processed" (offset advances)
  — it must never look like failure to the DLQ logic.
* `services/governance/black_box_publisher.py`: guardrail level logic.
* `middleware/adapters/observability/langfuse_cloud_exporter.py`: metadata allowlist.

**Exit:** smoke trace at ≤8 observations per step; flag flipped OFF once on dev to
verify the dual view returns; flipped back ON.

---

### Phase 5 — Content and identity enrichment (E7, E8, E9)

**RED**
* `tests/orchestration/test_phase_wiring.py`:
  - `MODEL_SELECTED` details include `rationale` and `alternatives` (strings already
    composed for the PhaseLogger `Decision` at `react_loop.py:946-961` — same data, now
    also on the event).
  - `STEP_PLANNED` (changed only) includes `plan_summary`: capped list (≤5, each ≤120
    chars) of ordered-step titles.
  - `TASK_STARTED` details include `agent_name`, `agent_version`, `agent_facts_id`
    (sourced from config/registry at graph-build time — **ask-first item is not
    triggered**: no new node, only details on an existing emission).
* (Trace-level input/output is **dropped** per D-0b — `set_current_trace_io` is
  deprecated and context-incompatible. Triage-without-opening is delivered by the
  Phase 1 trace scores + a meaningful trace name; task input / final answer stay on
  `task.started` / `task.completed` / `llm.call`.)

**GREEN**
* `orchestration/react_loop.py`: the three detail enrichments (data already in scope;
  nodes stay thin).

**Exit — the pillar acceptance test (manual, on a smoke trace):**

| Pillar question | Answered by | One click? |
|---|---|---|
| What happened? (Recording) | step spans → llm.call/tool.{name} with real results | ✅ |
| Who did it? (Identity) | `task.started` agent identity; bundle `identity_cards` | ✅ |
| What was checked? (Validation) | `guardrail.checked` incl. DEBUG clean passes | ✅ |
| Why was it done? (Reasoning) | `model.selected` rationale; `step.planned` plan_summary; `eval.goal_judge` | ✅ |

---

## 6. Verification matrix

| Phase | CI (every commit) | GCP smoke (user-run, per phase) |
|---|---|---|
| 0 | — | cap-lift check on `eval.goal_judge`; service.name visible |
| 1 | `tests/services/governance`, `tests/middleware/sidecars`, `tests/orchestration/test_phase_wiring.py`, `tests/architecture` | 3 scores visible in trace list; no `"None"` strings in `task.completed`; `identity_cards` in dataset item |
| 2 | `tests/middleware/test_telemetry_correlation.py` + above | join `tool_call_id` across bridge obs ↔ bundle events |
| 3 | `tests/agent_ui_adapter/*`, `tests/middleware/test_telemetry_bridge.py`, `test_telemetry_redaction.py` | 1 generation + N tools per step; native cost on generation |
| 4 | suppression + fingerprint + exporter suites | obs/step ≤8; flag-off restores dual view (once, dev) |
| 5 | phase-wiring + bridge suites | pillar acceptance table above |

Smoke procedure per the `agentsframework-playwright` skill (T3-style single run against
Cloud Run; verify via Langfuse UI + Cloud Logging `thread=session-gj-XXX`). Never run
the full T1 tier locally.

---

## 7. Risks and rollback

| Risk | Mitigation |
|---|---|
| Curated view hides something an investigation needs | Flag flip (`LANGFUSE_RELAY_CURATED=false`) restores the full relay; JSONL/replay/bundle were never reduced |
| `redact_details` type change breaks a consumer assuming `dict[str, str]` | Contract tests updated in the same commit; bundle redaction shares the function, so dataset items change shape too — release note in PR |
| Dashboard queries referencing `llm.finished` / `tool.finished` names | D-3a grep + migration note before Phase 3 lands; relay + eval names unchanged |
| Suppression mistaken for failure → DLQ noise | Explicit test: suppressed lines advance offset with zero DLQ writes |
| `step.planned` dedup hides a plan during incident replay | Only the *export* is deduped; JSONL row recorded with `plan_changed=False` + fingerprint every iteration |
| Wire-ring evolution breaks frontend translators | Fields optional; `tests/agent_ui_adapter/translators/test_domain_to_ag_ui.py` back-compat test in Phase 3 RED |
| SDK v4 can't set explicit timestamps (D-0a negative) | Accept relay-time stamps; surface `event_time` first-class; never fabricate durations |

## 8. Decision log (fill during implementation)

| ID | Question | Outcome |
|---|---|---|
| D-0a | SDK v4 explicit start/end times on observations? | **RESOLVED (langfuse 4.7.1, 2026-06-12): NO start-time backdating.** `start_observation()` exposes only `completion_start_time` (TTFT for generations), never a span `start_time`; the OTel span starts at the `start_observation()` call. `.end(end_time=...)` accepts an explicit end but a real-start + backdated-end inverts the span. **Decision:** do NOT fabricate timings. Relayed observations stay point-in-time at relay-export instant; the authoritative event instant is surfaced first-class as `event_time` (= `details.timestamp`) on every relayed observation so a reader can reconstruct the true order. Phase 2 RED/GREEN adjusted accordingly. |
| D-0b | Trace-level input/output mechanism in v4 | **RESOLVED (4.7.1): `set_current_trace_io(input=, output=)` exists but is (1) `@deprecated` (legacy LLM-as-judge only, slated for removal) and (2) requires a *current OTel span context* (`_get_current_otel_span()`), which our `start_observation(trace_context=...)+.end()` pattern never establishes.** **Decision:** do NOT use `set_current_trace_io`. For list-view scannability rely on (a) `propagate_attributes(trace_name=...)` for a meaningful trace name and (b) the Phase 1 trace-level **scores** (goal_met / criteria_met / completion_score) — those already give triage-without-opening. The task input + final answer remain visible on `task.started` / `task.completed` / the `llm.call` generation rather than as deprecated trace-level I/O. Phase 5.3 (trace input/output wiring) is **dropped**; Phase 5 reduces to content/identity enrichment on existing observations. |
| D-2a | `step` attachable to LLM wire events cheaply? | _discovery (Phase 2)_ |
| D-3a | Observation rename fallout (`llm.call`, `tool.{name}`) | _grep before merge (Phase 3)_ |
| D-5a | Final-answer source for trace output | **MOOT** — folded into D-0b resolution; no trace-level output to source. |

## 9. Success metrics

1. **≤8 observations per step** (baseline ~13), zero cross-pipeline duplicate facts.
2. **No contradictory terminal state reachable**: `task.completed` + trace scores agree
   by construction (single source: `TaskOutcome` after judge overlay).
3. **Trace-list triage without opening the trace**: goal_met / criteria_met /
   completion-score visible as scores.
4. **Pillar acceptance table (§5 Phase 5) fully ✅ from the trace alone.**
5. **Audit unchanged or stronger**: hash chain untouched; bundle gains `identity_cards`;
   Option-B view one flag away.
