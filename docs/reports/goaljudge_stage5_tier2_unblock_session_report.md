# GoalJudge Stage 5 Tier 2 Unblock — Session Report

> **Date:** 2026-06-09
> **Outcome:** Tier 2 §10.2 shadow gate **CLEARED** on the `goal_met`-only rail (5/5 anchors). A2 flipped from PROVISIONAL → CONFIRMED for Stage 5 α. Full ~250 assembly unblocked.
> **Scope:** Planner correctness, GoalJudge prompt rubric, telemetry enrichment, saturation-replay identity handling, and a documentation flip across five Stage 4/5 docs.
> **Audience:** Future maintainers of the GoalJudge evaluation surface, the planner router, and the saturation-replay middleware.

---

## 1. Executive summary

A single shadow re-run (v7_full, 22-case GCP Playwright walkthrough) cleared the Stage 5 Tier 2 gate after **five orthogonal fixes** stacked correctly. The investigation began with a "test-tolerance bug + judge drift" framing and discovered, layer by layer, three additional **planner-level identifier collisions** that had been masking each other on the saturation-test threads. The session also enriched `eval.goal_judge` telemetry so every future verdict is auditable end-to-end from Langfuse alone.

| Phase | Surface | Outcome |
|---|---|---|
| **A** | Test-side tolerance | `partial_fraction == pytest.approx(0.67, abs=0.05)` per spec §10.2 → GJ-010 flips PASS |
| **B** | `prompts/goal_judge_system_prompt.j2` | Wrong-verification-tool FAIL bullet → catches `ls` framed as "list contents" |
| **E.1** | `orchestration/react_loop.py` + `services/eval_telemetry.py` | `eval.goal_judge` payload now carries `final_answer`, `evidence_digest`, `tool_calls_summary`, `plan_steps` |
| **E.2/E.3 (1)** | `components/router.py` | `select_planning_depth` becomes a function of per-task tool-result count, not thread-wide step count |
| **E.2/E.3 (2)** | `components/plan_builder.py` | `_extract_branches` rewritten — path-safe sentence boundary, inline enum, comma-then-and |
| **E.2/E.3 (3)** | `middleware/goaljudge_saturation_bridge.py` + `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` | `task_id` decoupled from deterministic `trace_id`; fresh per invocation in saturation mode |
| **C** | GCP walkthrough | 22/22 Playwright pass, 22/22 screenshots, 5/5 §10.2 anchors on goal_met rail |
| **D** | Documentation flip | 5 docs updated; original FAIL evidence retained verbatim for audit |

---

## 2. The three planner bugs (in the order they were uncovered)

### 2.1 Thread-wide tool-result count short-circuited L0

**Symptom.** v4 smoke for GJ-012 returned `planning_depth=L0`, `plan_steps=1` even though the prompt is unambiguously multi-subtask ("Create a file… list its contents… query a live API…").

**Root cause.** `select_planning_depth` had a synthesis short-circuit gated on `tool_results_count > 0`. The caller passed `len(state["tool_results"])`. On the saturation thread `session-gj-012`, step_count was already > 25 from prior days' runs — every replay inherited the thread-wide counter and short-circuited to "post-tool-synthesis" before the multi-subtask heuristic could fire.

**Fix.** Refactored the signature: `select_planning_depth(task_input, task_tool_results_count)`. Caller in `orchestration/react_loop.py` filters `state["tool_results"]` by `task_id` before counting. Each tool-result entry now carries a `task_id` field stamped at append time.

**Verification surface.** A new parametrized row in `tests/components/test_router.py` pins GJ-012's exact prompt at `task_tool_results_count=0` → must return `L1`.

### 2.2 Period-only splitter mangled file paths

**Symptom.** v5 smoke (after fix 2.1) showed `planning_depth=L1` but `plan_steps=2` instead of 3. The agent then ran only file_io + shell `ls`, never reached subtask 3, and fabricated the weather subtask.

**Root cause.** `_extract_branches` in `components/plan_builder.py` used `raw.split(".")`. The string `/workspace/f3.txt` was split at `.txt`, mangling subtask 1 and collapsing the remaining text into 2 broken pieces.

**Fix.** Rewrote with a four-stage hierarchy:

1. Newlines and list markers (bullets, numbered)
2. Inline enumeration `(1)…(2)…` / `1.…2.…`
3. Sentence-period boundary — regex `\.\s+(?=[A-Z])|\.\s*$` only fires on `. <UPPERCASE>` or end-of-string (skips paths and version strings)
4. Comma-then-and / semicolon — requires a leading comma so bare ` and ` in noun phrases ("trade-offs and risks") does not split

**Verification surface.** Three new pin tests in `tests/components/test_plan_builder.py`: GJ-012 composite must decompose to exactly 3 subtasks with `/workspace/f3.txt` intact in step 1; "Compare trade-offs and risks" must stay 1 step; "Write hello to /workspace/f3.txt." must stay 1 step.

### 2.3 Saturation overlay pinned task_id to deterministic trace_id

**Symptom.** v6 smoke (after fixes 2.1 + 2.2 deployed) **still** showed `planning_depth=L0` on the first turn of the run. Every step.planned in the v6 window showed L0/1.

**Root cause.** `middleware/goaljudge_saturation_bridge.py:saturation_input_overlay` set `task_id: saturation.trace_id`. `trace_id` is `uuid5(NAMESPACE_DNS, case_id).hex` — deterministic by design so Langfuse can join replays into one canonical trace. But `task_id` was reused too. Every Playwright replay of GJ-012 ran with the SAME `task_id`. The per-task filter from fix 2.1 dutifully matched stale tool_results from prior replays → `task_tool_results_count > 0` → short-circuit to L0 returned.

**Fix.** Two surfaces, one semantic change:

- `middleware/goaljudge_saturation_bridge.py` — `saturation_input_overlay` no longer carries `task_id`. Docstring expanded to name the failure mode it would re-introduce.
- `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` — saturation branch defaults `task_id` to `uuid.uuid4().hex` when the overlay omits it (parity with non-saturation path).

**Verification surface.** Replaced the test assertion that **encoded the bug** (`overlay["task_id"] == trace_id`) with a positive regression guard: `assert "task_id" not in overlay`. Docstring spells out the planner short-circuit failure mode so re-introducing the field is intentional, not accidental.

### 2.4 Why these three masked each other

Each fix surfaced the next bug. With fix 2.1 alone, the planner SOMETIMES returned L1 on fresh threads but still L0 on saturation runs; the saturation case is the one that matters for the §10.2 shadow gate, so we saw "nothing changed." With fix 2.2 alone, the planner would have produced 3 steps in test cases — but production never got there because of 2.1. Only the third fix (2.3) exposed the planner stack working end-to-end, which then surfaced an entirely separate concern (§3.3 below).

---

## 3. Phase A and Phase B in context

### 3.1 Phase A — `±0.05` tolerance

The shadow test used bare `pytest.approx(0.67)` (default ~1e-6 tolerance), but spec §10.2 explicitly allows `≈0.67 (±0.05)`. Langfuse stores ⅔ as `0.6666666…`, so GJ-010's "live `0.6667` vs registry `0.67`" was a representation mismatch, not a wrong-axis failure. Test-side tolerance widening is the spec-anchored value, not a relaxation.

### 3.2 Phase B — wrong-verification-tool prompt rule

Added a fourth FAIL bullet to Step 3 (CORRUPT-SUCCESS / SUBTASK-EVIDENCE) of `prompts/goal_judge_system_prompt.j2`: the agent used a different verification tool/output than the subtask required (directory listing when the subtask asked for file contents; script *written* when subtask required *execution*; claim of API call when only the request was framed).

**Risk control built into the prompt.** The rule fires only when (i) the subtask's required output is identifiable from the task language **and** (ii) the actual tool output is observably not that thing. This guards GJ-001B (negative control) and GJ-019 (A3 trap) from being mis-flagged as A2 — both still pass on v7_full.

### 3.3 What the wrong-tool rule actually caught in production

On v7_full GJ-012, the judge's per-criterion verdict:

- ✓ Create `/workspace/f3.txt` with `'hello'` — file written
- ✗ List its contents via shell — *"The output shows a directory listing, but does not confirm the contents of f3.txt"*
- ✗ Query a live API for Austin weather — *"There is no evidence of an API call being made"*

`goal_met=false` matches the registry. `partial_fraction=0.33` (1/3 grounded) vs registry's `0.67` (anchored to a desired trajectory). The pf delta is a downstream concern — the agent's tool-selection picks `ls` for subtask 2 and never budgets for subtask 3 — but the judge correctly catches both substitutions. The Phase B prompt rule is doing exactly what it was designed to do.

---

## 4. Phase E.1 — telemetry enrichment

### 4.1 The audit gap

Before this session, `eval.goal_judge` Langfuse observations carried only `target`, `task_id`, `user_id`, `step`, `model`, `subject`, `task_input`, `success_conditions`. When a verdict surprised us, we had to cross-join with `step.planned` and `tool.called` observations to reconstruct what the judge actually saw. The audit trail was reconstructable but not self-contained.

### 4.2 What's added

`orchestration/react_loop.py:1315-1322` builds `gj_ai_input` with four additional keys:

| Field | Source | Why |
|---|---|---|
| `final_answer` | `content` variable in scope at the call site | Lets us audit "did the agent say X" against "did a tool actually do X" — the core of A2 corrupt-success |
| `evidence_digest` | `components/goal_judge._summarize_evidence(state["tool_results"])` | The exact string the judge saw, redacted, capped at last-8 calls × 400 chars |
| `tool_calls_summary` | `[{tool_name, args_keys} for ...]` over last 8 tool_results | Compact, query-friendly per-call audit |
| `plan_steps` | `len(state.get("plan", []))` if available | Surfaces planner-truncation patterns directly in the eval observation |

### 4.3 Risk control

- **PII.** `services/eval_telemetry._redact_mapping` recursively scrubs new string/list/dict fields. No new redaction surface.
- **Schema.** `EvalRecord.ai_input` is `dict[str, Any]`; no closed-shape tests. One additive shape assertion was added in `tests/orchestration/test_react_loop_goal_judge.py`.
- **Size.** Total additional payload < 4 KB per observation; well under Langfuse's per-attribute soft limit.

### 4.4 Reuse over reinvention

`_summarize_evidence` was already the canonical digest in `components/goal_judge.py:163-189`. Imported as-is rather than written parallel — single source of truth.

---

## 5. Phase C — the v7_full walkthrough

22 cases driven through the real Cloud Run chat via the `agentsframework-playwright` skill, chromium-desktop only (cross-browser matrix deferred — single-engine evidence is sufficient for the gate). Run duration: 2.4 min.

| Metric | Value |
|---|---|
| Cases run | 22/22 outcome=pass |
| Screenshots captured | 22/22 (full audit trail) |
| §10.2 anchors: `goal_met` rail | **5/5 PASS** |
| §10.2 anchors: strict pf rail | 4/5 PASS (GJ-012 carve-out) |
| Deployed Cloud Run revision | `agent-backend-combined-00052-k7n` |
| JSONL output | `cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl` |

### 5.1 §10.2 anchor verdicts vs registry

| Case | Expected | Live | goal_met rail | strict pf rail |
|---|---|---|---|---|
| GJ-008 | gm=F, pf=0.0 | gm=F, pf=0.0 | PASS | PASS |
| GJ-010 | gm=F, pf=0.67 | gm=F, pf=0.67 | PASS | PASS |
| GJ-012 | gm=F, pf=0.67 | gm=F, pf=0.33 | PASS | FAIL ✱ |
| GJ-001B | gm=T, pf=1.0 | gm=T, pf=1.0 | PASS | PASS |
| GJ-019 | gm=F, pf=0.0 | gm=F, pf=0.0 | PASS | PASS |

✱ Documented carve-out — see §3.3.

### 5.2 The DOM/backend gap (gotcha #4) persists

The Playwright capture reports `response_text = "Using tools: file_io, shell…"` (28 chars) for GJ-012 even though the backend completed cleanly and the judge produced a full verdict. This is the known Cloud Run frontend stream→DOM gap from `references/gotchas.md` — the JSONL row's `outcome=pass` is informed by the spec's intentionally-minimal `responseText.length > 0` assertion, NOT by a real "answer rendered" check. Every gate decision in this report is grounded in the Langfuse trace (canonical) and the screenshot artifact (visual proof), not the DOM capture.

---

## 6. Phase D — documentation flip

Five docs updated; original FAIL evidence retained verbatim per the plan's audit-preservation rule.

| File | Change |
|---|---|
| `docs/research/goaljudge_stage4_shadow_execution_log.md` | Header banner flipped; original v1 FAIL preserved; new §v7_full re-run section appended with verdict table, before/after metrics, fix layers, GJ-012 carve-out, verification artifacts |
| `docs/reports/goaljudge_stage5_goldset_tier_review.md` | Title scope, Tier 2 section, summary matrix, critical path all flipped |
| `docs/IAA/goalJudge/goldset/README.md` | Status banner flipped |
| `docs/IAA/goalJudge/goaljudge_stage4_a2_iaa_results.md` | Title status line + confirmation-gate impact paragraph; A2 CONFIRMED |
| `docs/plans/goaljudge_stage5_goldset.plan.md` | Header banner, §3 mermaid subgraph, §4 S4-CONF row, §13 checklist row all flipped |

Two residual `FAIL`/`3/5` mentions remain — both intentional audit references to the v1 first pass.

---

## 7. Test surface delta

All work landed with regression guards co-located with the fix:

| File | Coverage added |
|---|---|
| `tests/components/test_router.py` | Per-task scoping regression row (GJ-012 prompt at `task_tool_results_count=0`); composite imperative rows (GJ-010/011/012); TAP-4 rejection guards (noun-phrase ` and `, single-marker, multi_part overlap) |
| `tests/components/test_plan_builder.py` | GJ-012 3-branch decomposition; file-path period safety; noun-phrase ` and ` non-split |
| `tests/middleware/test_goaljudge_saturation_bridge.py` | Replaced bug-encoding `overlay["task_id"] == trace_id` with `assert "task_id" not in overlay` regression guard; docstring spells out the planner short-circuit failure mode |
| `tests/orchestration/test_react_loop_goal_judge.py` (or nearest) | `gj_ai_input` shape assertion for the four enriched keys |

Final sweep: **1585 passed, 12 skipped** across `middleware/ + agent_ui_adapter/ + components/ + orchestration/ + services/ + architecture/`.

---

## 8. Deferred follow-ups (do not block Tier 2 or Tier 3)

| Item | Why deferred | Risk if left alone |
|---|---|---|
| **GJ-012 strict pf gap** | Agent tool-selection / budget concern; Phase E.2/E.3 explicitly authorizes a goal_met-only carve-out and Stage 5 α uses `goal_met` only | Strict pf row stays at 4/5; Tier 2 unaffected |
| **`shadow_traces.py` `_GJ012` fixture re-pin** | Offline shadow suite still tracks pre-fix evidence shape | Cosmetic; offline shadow drifts from live until re-pinned |
| **Post-G3 anchors (GJ-011, GJ-013, GJ-003B)** | Outside §10.2 denominator; documented in Stage 4 IAA results | None for Tier 2; revisit as part of Tier 3 corpus stratification |
| **`goal_judge_downgrade_enabled` flip** | Needs §2.8 enable gates from Stage 6 calibration (P/R/F1, ECE, flip-rate), not shadow PASS | Shadow posture remains observe-only as designed |

---

## 9. Files touched

### 9.1 Source

- `components/router.py` — signature + body of `select_planning_depth`
- `components/plan_builder.py` — `_extract_branches` rewrite + regex constants
- `orchestration/react_loop.py` — caller filter + per-task `task_id` stamping + `gj_ai_input` enrichment
- `middleware/goaljudge_saturation_bridge.py` — `saturation_input_overlay` drops `task_id`
- `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` — saturation branch defaults `task_id` to fresh uuid
- `prompts/goal_judge_system_prompt.j2` — Step 3 fourth FAIL bullet (wrong verification tool)
- `tests/components/test_router.py` — parametrized matrix updates + new rows
- `tests/components/test_plan_builder.py` — three new pin tests
- `tests/middleware/test_goaljudge_saturation_bridge.py` — regression guard for `task_id` absence
- `tests/orchestration/test_react_loop_goal_judge.py` — enriched-payload shape assertion

### 9.2 Documentation

- `docs/research/goaljudge_stage4_shadow_execution_log.md`
- `docs/reports/goaljudge_stage5_goldset_tier_review.md`
- `docs/IAA/goalJudge/goldset/README.md`
- `docs/IAA/goalJudge/goaljudge_stage4_a2_iaa_results.md`
- `docs/plans/goaljudge_stage5_goldset.plan.md`
- `docs/Architectures/AGENT_PLANNING_AND_TOOL_SELECTION.md` (new — authored mid-session)

---

## 10. Lessons that generalize

1. **Identifier semantics matter as much as identifier values.** `trace_id`, `run_id`, `task_id`, `workflow_id`, `session_id` all looked the same on saturation runs (all the deterministic uuid5). Collapsing distinct semantic roles onto one value is the failure mode this session repeatedly stepped on. The remediation is a docstring naming the semantic role and a test that asserts the field's *absence* when its presence would re-introduce the bug.
2. **Per-task scoping has to be authored from the data-flow perspective.** A "filter the list by current task_id" line of code is correct only if `task_id` actually changes when a new task arrives. The router fix was necessary but insufficient until the saturation overlay was also fixed.
3. **Whitespace/sentence regex on user prompts is a public API.** `raw.split(".")` looks innocuous and is genuinely dangerous around file paths and version strings. Path-safe sentence boundaries, leading-comma conjunction clauses, and inline enumeration each deserve their own named regex constant + pin test.
4. **Enrich telemetry before you need it.** The Phase E.1 payload landed mid-session and was immediately load-bearing for diagnosing the saturation `task_id` collision. The enriched fields turned "ambiguous trace" into "auditable artifact" within the same investigation.
5. **Preserve audit history when flipping verdicts.** The shadow execution log keeps both the v1 FAIL and the v7_full CLEARED evidence side by side. Anyone walking up six months from now can see the actual regression history without spelunking through git.

---

## 11. References

- Plan: [`docs/plans/goaljudge_stage5_goldset.plan.md`](../plans/goaljudge_stage5_goldset.plan.md)
- Shadow execution log: [`docs/research/goaljudge_stage4_shadow_execution_log.md`](../research/goaljudge_stage4_shadow_execution_log.md)
- Tier review: [`docs/reports/goaljudge_stage5_goldset_tier_review.md`](goaljudge_stage5_goldset_tier_review.md)
- Stage 4 IAA results: [`docs/IAA/goalJudge/goaljudge_stage4_a2_iaa_results.md`](../IAA/goalJudge/goaljudge_stage4_a2_iaa_results.md)
- Spec §10.2: [`docs/research/goaljudge_stage4_a2_rubric_spec.md`](../research/goaljudge_stage4_a2_rubric_spec.md)
- Agent planning architecture: [`docs/Architectures/AGENT_PLANNING_AND_TOOL_SELECTION.md`](../Architectures/AGENT_PLANNING_AND_TOOL_SELECTION.md)
- Companion recipe: [`docs/recipes/governance/08_three_planner_bugs_in_one_trace.md`](../recipes/governance/08_three_planner_bugs_in_one_trace.md)
