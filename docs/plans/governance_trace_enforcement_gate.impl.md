# Governance-trace enforcement gate — implementation plan

**Status:** **Phase 1 BUILT — 2026-06-17** (uncommitted on `feat/t3-supervisor-fanout`). Shadow-first, deterministic, no LLM. Phase 2 (enforce) is specced but gated behind shadow calibration + separate approval.

> **Build log (2026-06-17).** Phase 1 shipped: `trust/governance_carrier_spec.py` (spec, 13 L1 tests), `services/governance/carrier_gate.py` (pure check + `record_carrier_gap`, 23 L2 tests incl. the §4.2 failure-mode matrix + drift guard + consumer contract), thin wiring in `orchestration/react_loop.py` (`_shadow_check_phase_carriers` 23-line helper + a 4-line call site after the INITIALIZATION boundary), and `tests/orchestration/test_carrier_gate_sim.py` (2 `@pytest.mark.simulation` tests). All 8 self-validation checks pass; `tests/architecture/` green (no boundary violation); L1+L2 deterministic ×10. SKILL.md updated.
>
> **Two grounded deviations from the as-written plan** (both forced by reading the code, both keep compliance stricter, not looser):
> 1. **The spec keys on the EventType/WorkflowPhase *string values*, not the enum classes.** `tests/architecture/test_dependency_rules.py` forbids `trust/` from importing `governance` — and those enums live in `services/governance/`. So the spec transcribes the wire strings (both enums are `(str, Enum)`); a **service-layer drift guard** (`test_carrier_gate.py::TestSpecDriftGuard`) asserts they still equal the real enums. This is *more* invariant-faithful than importing would have been.
> 2. **`CarrierGap`/`MissingCarrier` live in `services/governance/carrier_gate.py`, not `trust/`.** They are the *check's result type*, produced and consumed only at the service+orchestration seam — not a stable contract shared as a kernel primitive. Keeping them out of `trust/` keeps the kernel minimal (only the rubric — the genuinely-shared contract — is promoted to `trust/`).
> 3. **Wiring is instrumented at the INITIALIZATION boundary only (proof-of-wiring).** The remaining boundaries (ROUTING/MODEL_INVOCATION/TOOL_EXECUTION/OUTPUT_VALIDATION/COMPLETION) are spec-ready and the helper is generic — extending to them is mechanical and is the natural next slice once the INITIALIZATION shadow signal is observed in a real run. A resumed run (`step_count>0`) correctly skips INITIALIZATION (the init node short-circuits), so the gate emits nothing there — verified by the sim test, no false-positive on an absent boundary.
>
> **Wiring extension (2026-06-17, second slice).** Extended the shadow gate to **five of the six** boundaries — `INITIALIZATION` (Identity), `ROUTING` (Reasoning/MODEL_SELECTED), `MODEL_INVOCATION` (Recording/STEP_EXECUTED), `OUTPUT_VALIDATION` (Validation/GUARDRAIL_CHECKED), and `TOOL_EXECUTION` (Validation/ERROR_OCCURRED, conditional on tool failure). Each is one thin call at the node's normal success exit (early terminals — budget_exceeded/rejected — are legitimate skips and are deliberately *not* instrumented; per §5 a run that never reaches a phase is not a gap). The sim suite now proves all five emit clean `pass` carriers on the happy path with zero false-positives, plus the resumed-run and gap cases.
> - **One supporting production change (honest seam check):** `TOOL_EXECUTION` needs ground truth for "did a failed tool actually record `error_occurred`?" — inferring it from `tool_results[].ok` would be circular. So `_execute_tools_impl` now sets an `error_recorded` flag at each `ERROR_OCCURRED` site and returns it as a **transient** `_error_carrier_recorded` key that the wiring **pops before the dict becomes AgentState** (never persisted). This lets the gate flag the real regression: tool failed *but no error carrier was emitted*.
> - **COMPLETION deliberately NOT wired in this slice** (the one hard boundary). Its Reasoning carrier `eval.goal_judge` (a) lives in the **eval-overlay sink, not the black box** — not observable at `_emit_completion_once`; (b) is **conditional on `goal_judge_enabled`**; and (c) is only required on a genuinely *completed* outcome, not on rejected/budget_exceeded terminals (§5's canonical legitimate-skip). Wiring it correctly is a *calibrated sub-task* — it needs a new conditional spec axis (`required only when goal_judge_enabled and outcome=="completed"`) plus threading the goal-judge-ran signal from the evaluator node into the completion emitter — not a mechanical copy. Left for a dedicated slice so it doesn't ship as a guaranteed-false-positive.
**Motivation:** [`next_work_scoping_t3_vs_governance_gate.md`](../research/next_work_scoping_t3_vs_governance_gate.md) §4 — turn the governance trace from *audited-after* (the `governance-trace-audit` skill, post-hoc) into *checked-during*, realizing the [arXiv 2603.01548](https://arxiv.org/abs/2603.01548) "binary observability — never a silent skip" property the trace lacks today.
**Compliance anchors (all four the user named):** `@AGENTS.md` (layering invariants 1-8, AP-4/AP-5, V2/V6, testing rules), `@docs/Architectures/FOUR_LAYER_ARCHITECTURE.md` (dependency table, governance-event direction, `TrustTraceRecord`/`EventCategory`), `@docs/skills/governance-trace-audit/SKILL.md` (the **four-pillar rubric is reused verbatim as the gate's oracle**), `@research/tdd_agentic_systems_prompt.md` (pyramid layer + pattern + the 8 self-validation checks).

---

## 1. The gap, precisely

`services/governance/phase_logger.py` and `services/governance/black_box.py` **record** carriers but never **assert** their presence. The only `raise` in `phase_logger.py` (line 203) is a storage-write failure. So a phase can complete missing its pillar carrier and nothing surfaces it until a human runs the audit skill. The skill's own contract (`SKILL.md`: *"A fact with zero carriers is a seam defect — the worst class of finding"*) is exactly what we want enforced inline.

**What "the gate" is:** a pure function that, given the phase that just ended and the carriers recorded during it, returns the set of **missing required pillar carriers**. Phase 1 records that set as a `guardrail_checked` shadow carrier (warn). Phase 2 promotes it to a fail/degrade. Nothing about the four-pillar rubric or the carrier vocabulary changes — only whether absence is *checked*.

---

## 2. Layer placement (FOUR_LAYER + AGENTS.md compliance)

This is the load-bearing design decision; it satisfies invariants 1, 2, 6, 7 and AP-4/AP-5.

| Piece | Lives in | Why (rule) |
|-------|----------|------------|
| `PillarCarrierSpec` (which `EventType`s each `WorkflowPhase` requires, per pillar) | **`trust/`** (pure Pydantic data + the rubric mapping) | Trust-kernel criteria met: pure, shared by services+orchestration, stable, dependency-free (AGENTS.md "Trust Kernel Rules"). It's a contract, like `EventCategory`. |
| `validate_phase_carriers(phase, recorded_event_types) -> CarrierGap` (the pure check) | **`services/governance/`** | A horizontal governance service; reads the trust spec, no domain logic, no I/O, no LLM. Invariant 7 (services don't import components) trivially holds — it imports only `trust/`. |
| Wiring: after each `phase_logger.phase(...)` block, call the check and **record** the gap as a shadow carrier | **`orchestration/react_loop.py`** (thin) | The orchestration node is the only place that knows "a phase just ended." Kept to a thin call (AP-5: ≤10-15 lines, all logic in the pure fn). |

**Governance-direction compliance (AP-4 / FOUR_LAYER "command flow"):** the gate **emits** a carrier (a `TraceEvent`/`guardrail_checked`), it does **not** call upward into orchestration or mutate workflow state. In Phase 2 the "enforce" reaction (degrade/annotate) is an *orchestration* decision reading the gap carrier — governance informs, orchestration acts. This mirrors the existing identity↔governance one-directional rule.

**Why not put the check in `phase_logger` itself:** `PhaseLogger` is the *recorder*; making it also the *judge* couples recording to policy and means a policy bug can break logging. Keep them separate (single responsibility, AGENTS.md "Adding a horizontal service").

---

## 3. The oracle (no invention — reuse the skill's rubric)

The `PillarCarrierSpec` is a **direct transcription** of `SKILL.md` Step 2 + Step 3, using the **real** `EventType` (`black_box.py:40-49`) and `WorkflowPhase` (`phase_logger.py:33-46`) vocabularies — verified, not guessed:

| Pillar (SKILL.md) | Required carrier(s) | Phase(s) it's required in | Run-shape exemption (SKILL.md) |
|-------------------|---------------------|---------------------------|-------------------------------|
| **Recording** | `STEP_EXECUTED` with non-null `tokens_in/out/cost_usd` | every phase that made an LLM/tool call (`MODEL_INVOCATION`, `TOOL_EXECUTION`, fan-out `join`) | none — *"a missing or token-less `step.executed` is a FAIL"* |
| **Identity** | `TASK_STARTED` with `agent_name`/`agent_version`/`agent_facts_id` | `INITIALIZATION` only | **resumed run (lowest step > 0) ⇒ UNVERIFIABLE, not FAIL** |
| **Validation** | `GUARDRAIL_CHECKED`; `ERROR_OCCURRED` iff a tool failed | `INPUT_VALIDATION`, `OUTPUT_VALIDATION`; any phase with a failed tool | clean passes are quiet — *presence of the check span*, not an alert |
| **Reasoning** | `MODEL_SELECTED` (w/ `rationale`+`decision_id`); `STEP_PLANNED` once per distinct plan; `eval.goal_judge` on completed runs | `ROUTING`, `COMPLETION` | deterministic `conditions_source` is a weight note, not a fail |

The spec is **versioned** (`spec_version: 1`) so the rubric can evolve alongside the skill (SKILL.md is the source of truth; a test asserts the spec's pillar set equals the skill's four pillars — drift guard).

---

## 4. TDD plan (per `@research/tdd_agentic_systems_prompt.md`)

The work spans two pyramid layers; each piece gets the protocol its layer mandates. **Failure paths first** (Principle 4 / AP-6) is non-negotiable here — this *is* a gate.

### 4.1 `trust/` spec — Pyramid **L1 (Deterministic Foundations)**, Protocol A
- **Pattern 1 (property-based schema):** `PillarCarrierSpec` round-trips; every `WorkflowPhase` maps to a (possibly empty) required-carrier set — **enum completeness (A3)**: no phase unmapped, no required carrier outside the real `EventType` enum.
- **A1 schema pair:** valid spec accepted; spec naming a non-existent `EventType` rejected (`ValidationError`).
- **Drift guard:** `test_spec_pillars_match_skill_rubric` — the spec's four pillar names == the skill's four pillars (catches rubric drift).
- Exact assertions, zero flake, <10s, every commit.

### 4.2 `services/governance/` check — Pyramid **L2 (Reproducible Reality)**, Protocol B
- **Pattern 11 (Failure Mode Matrix)** — the core test, written **before** any acceptance test:

  | phase | recorded carriers | run shape | expected gap |
  |-------|-------------------|-----------|--------------|
  | `INITIALIZATION` | {} | from-step-0 | **{Identity}** ← rejection first |
  | `INITIALIZATION` | {} | resumed (step>0) | **∅ (UNVERIFIABLE)** ← the SKILL.md exemption |
  | `MODEL_INVOCATION` | {`STEP_EXECUTED` token-less} | any | **{Recording}** ← the real token-seam defect |
  | `MODEL_INVOCATION` | {`STEP_EXECUTED` w/ tokens} | any | ∅ (acceptance) |
  | `ROUTING` | {`MODEL_SELECTED` no `decision_id`} | any | **{Reasoning}** |
  | `TOOL_EXECUTION` | tool failed, no `ERROR_OCCURRED` | any | **{Validation}** ← *silent* failure |
  | `COMPLETION` | no `eval.goal_judge` | completed | **{Reasoning}** ← governance-missed corrupt-success class |
  | `COMPLETION` | full set | completed | ∅ |

- **Pattern 4 (Consumer-Driven Contract):** the gap carrier this emits is a valid `TraceEvent`/`TrustTraceRecord` with `outcome in {pass, alert}` and `EventCategory.governance` — so the audit skill (the downstream consumer) reads it unchanged.
- **No mock addiction (AP-2):** the check is pure over plain dicts/enums — *zero mocks*. The recorded-carriers input is a real in-memory set, built by a helper, not a mock.
- Mock I/O only for the `PhaseLogger`/`black_box` write in the wiring contract test; <30s, every commit.

### 4.3 Orchestration wiring — Pyramid **L4 (Behavioral)**, Protocol D, `@pytest.mark.simulation`
- **Pattern 10 (Governance Loop Simulation) + D3 binary outcome:**
  `test_system_records_a_warning_when_a_phase_skips_its_pillar_carrier` — run the graph (mocked LLM, `TestModel`) with a deliberately-suppressed `STEP_EXECUTED`; assert a shadow `guardrail_checked` gap carrier appears in the black box, and (Phase 1) **the run still completes** (warn, not block).
- **Dependency-rule test (Pattern 7):** `tests/architecture/` already enforces no upward imports — add the new modules to its sweep; assert `services/governance/` does not import `components/` or `orchestration/`.

### 4.4 The 8 self-validation checks (run before declaring done)
Coverage / layer-alignment / dependency-compliance / **failure-path coverage** (the matrix leads with rejections) / anti-pattern scan / contract coverage (gap carrier producer+consumer) / determinism audit (L1+L2 ×10 no flake) / CI-tagging (L4 sim marked `@pytest.mark.simulation`, never in CI).

---

## 5. Rollout (deterministic → shadow → consume — the floor-research discipline)

| Phase | What ships | Gate behavior | Exit criterion |
|-------|-----------|---------------|----------------|
| **1 — SHADOW (this plan)** | spec + pure check + thin wiring that **records** the gap as `guardrail_checked` (`outcome: alert` when non-empty), `would_enforce: true` flag (mirrors the floor's `would_downgrade`) | **warn only — never blocks** | a real run-corpus shows the missing-carrier rate is *true signal*, not false-positive on legitimate phase-skips (e.g. a budget-exceeded run that never reaches `COMPLETION`) |
| **2 — ENFORCE (specced, NOT built)** | promote: missing required carrier ⇒ **raise in dev / loud-degrade in prod** (annotate the trace + `RUN_FINISHED` with the gap, never silent) | gate; behind an env flag default-OFF like `T3_FANOUT_ENABLED` | Phase-1 shadow false-positive rate ≈ 0 over N runs + explicit approval |

**Calibration-before-gating is mandatory** — enforcing before the shadow phase proves the warn signal is the exact "gating before calibration is theater" trap flagged in the floor research and the GoalJudge rollout. Phase 2 is deliberately out of scope here.

---

## 6. Deliverables (Phase 1 only)

1. `trust/governance_carrier_spec.py` — `PillarCarrierSpec` (versioned, the §3 rubric transcription) + `CarrierGap` result model. **L1.**
2. `services/governance/carrier_gate.py` — `validate_phase_carriers(phase, recorded, *, run_shape) -> CarrierGap` pure fn + a `record_carrier_gap(black_box, gap, ...)` helper that emits the shadow `guardrail_checked` carrier. **L2.**
3. Thin wiring in `orchestration/react_loop.py` — one call after each `phase_logger.phase(...)` exit (≤15 lines total; AP-5). **L4.**
4. Tests: `tests/trust/test_governance_carrier_spec.py`, `tests/services/test_carrier_gate.py` (the failure-mode matrix), `tests/orchestration/test_carrier_gate_sim.py` (`@pytest.mark.simulation`), + the architecture-sweep addition.
5. One-paragraph update to `SKILL.md` noting the inline shadow gate now pre-flags what the skill audits (the skill becomes spot-check + Phase-2 oracle, not the only line of defense).

**Not in scope:** Phase 2 enforce, any change to the carrier vocabulary, any LLM, any deploy, flipping a default.

---

## 7. Verification (AGENTS.md "Key Commands")

- `pytest tests/ -q` green; **`pytest tests/architecture/ -q` green** (the must-pass layer-boundary suite — proves the new modules don't violate invariants 1/3/4/7).
- New L1+L2 tests run <30s combined, deterministic ×10 (Check 7).
- The simulation test shows: suppressed carrier ⇒ shadow gap carrier present ⇒ run still completes (Phase-1 warn semantics).
- Manual: run one real prompt, confirm the new `guardrail_checked` gap carrier appears in the black box and the `governance-trace-audit` skill reads it as a valid observation (consumer contract holds end-to-end).

---

## 8. Open decisions

| ID | Question | Recommendation |
|----|----------|----------------|
| GG-1 | Spec in `trust/` vs `services/governance/`? | **`trust/`** — it's a pure shared contract (criteria met); the *check* is the service. |
| GG-2 | Per-phase granularity vs per-run end-of-trace check? | **Per-phase** — catches the silent skip *where it happens* (the 2603.01548 property); a per-run check can't say which phase dropped it. |
| GG-3 | Phase-1 carrier: new `EventType` or reuse `GUARDRAIL_CHECKED`? | **Reuse `GUARDRAIL_CHECKED`** with a `source: "carrier_gate"` detail — no vocabulary change, the audit skill already reads it (Validation pillar). |
| GG-4 | Does shadow warn for resumed-run Identity? | **No** — encode the SKILL.md UNVERIFIABLE exemption in the spec; warning on it would be a guaranteed false-positive. |

*Plan only. No implementation until this plan is approved; Phase 2 needs separate approval after Phase-1 shadow calibration.*
