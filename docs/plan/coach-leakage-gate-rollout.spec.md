---
type: spec
title: 'Coach answer-leakage gate rollout (Phase 5) — off → shadow → enforce'
authored: 2026-07-06
---

# Spec — Coach answer-leakage gate rollout (Phase 5)

**Status:** Draft (replanned 2026-07-06 — ADR-0009 supersede added, FR-12/FR-13)
**Owner:** Rajnish Khatri
**Related:**
[coach-goldset-enable-policy.plan.md](coach-goldset-enable-policy.plan.md) (Phase 3.9 cert, DONE) ·
[subject-coach-agent.plan.md](subject-coach-agent.plan.md) (Phase 5 board, task 5.1) ·
[ADR-0019](../adr/0019-fireworks-host-adapter.md) (judge CERTIFIED on glm-5.2-fireworks) ·
ADR-0020 (this rollout — the ⚠️ Ask-first payload: live-judge-in-path enforcement seam) ·
carrier-gate precedent (`orchestration/react_loop.py` `_carrier_gate` off/degrade/raise).

---

## 1. Goal

Turn the **certified-but-dormant** coach answer-leakage judge into an enforcing
production gate that prevents a leaking coach reply from reaching a learner —
rolled out on a reversible `off → shadow → enforce` ladder so the live behavior
change is observable before it acts, and never below the Phase-3.9 cert floor.

## 2. Context

Phase 3.9 certified the answer-leakage judge (`glm-5.2-fireworks`, ADR-0019:
TNR 1.0 / TPR 1.0 / κ pass, 0 FP, zero-flip). But **`coach_leakage_gate_enabled`
is read by nothing on the live request path** — its only consumer is the offline
`meta/subject_coach_judge_sampler.py` telemetry job. So Phase 5 is not "flip a
flag": it is **building the enforcement call-site** that consumes the flag, then
rolling it out.

The repo already has the exact rollout shape to mirror: the **carrier gate**
(`orchestration/react_loop.py:_carrier_gate` + `trust.governance_carrier_spec`)
runs `off / degrade(shadow) / raise(enforce)` driven by one `enforce_mode`, with
all policy in a pure `decide_enforcement` and orchestration doing only the act
(AP-4/AP-5 thin shim). This spec reuses that discipline.

**Clarified decisions (2026-07-06):**
- **Enforce action** — regenerate the coach reply once with a stronger no-leak
  instruction; if the retry still leaks, suppress and substitute a safe Socratic
  fallback (never emit the leaking text).
- **Judge in path** — keep the current sampled/async telemetry as the *shadow*
  stage; in *enforce* the judge runs inline on every coach turn; on judge
  outage/timeout **fail OPEN** (let the reply through) with a loud carrier — a
  judge availability blip must not black out all coaching.
- **Rollout control** — a 3-mode string `off | shadow | enforce`
  (`coach_leakage_gate_mode`), config-driven, reversible per-deploy.
- **Flag migration** — add `coach_leakage_gate_mode` (default `off`); keep the
  deprecated boolean `coach_leakage_gate_enabled` readable and derive the mode
  from it when the new field is absent (`true → enforce`). Backward-compatible;
  no deployed config JSON breaks under `extra="forbid"`.
- **ADR** — ADR-0020 (new): the live-judge-in-path enforcement seam + rollout
  policy is a load-bearing architectural decision on a trust boundary.

## 3. Functional requirements (EARS)

Failure paths first (TAP-4).

**Fail-safe / degradation (write & test these first):**

- **FR-1.** IF the leakage judge errors or exceeds its per-call timeout WHILE the
  gate is in `enforce` mode THEN THE SYSTEM SHALL let the coach reply through
  unchanged AND record a loud `coach_leakage_gate` carrier tagged
  `judge_unavailable` (fail-open, never black out coaching).
- **FR-2.** IF the runtime config is malformed or unreadable THEN THE SYSTEM SHALL
  resolve the gate mode to `off` (fail DARK — no enforcement on an unknown
  posture), consistent with the existing reader's fail-dark contract.
- **FR-3.** IF the regenerated reply *still* flags as leakage in `enforce` mode
  THEN THE SYSTEM SHALL suppress it and emit the canned Socratic fallback — THE
  SYSTEM SHALL NEVER emit coach text that the certified judge flagged, in
  `enforce` mode.
- **FR-4.** IF `coach_leakage_gate_mode` is absent from the config document but the
  deprecated `coach_leakage_gate_enabled` boolean is present THEN THE SYSTEM SHALL
  derive the mode (`true → enforce`, `false → off`).

**Core behavior:**

- **FR-5.** WHILE the gate mode is `off` THE SYSTEM SHALL neither judge nor alter
  any coach reply on the live path (zero added latency, current behavior).
- **FR-6.** WHILE the gate mode is `shadow` THE SYSTEM SHALL judge coach replies
  per the existing sample rate, record a `coach_leakage_gate` carrier with the
  verdict, AND let every reply through unchanged (observe-only, never blocks).
- **FR-7.** WHEN the gate mode is `enforce` AND the certified judge flags a coach
  reply as `answer_leakage=true` THE SYSTEM SHALL regenerate the reply once with a
  stronger no-leak directive before re-judging (FR-3 governs the retry outcome).
- **FR-8.** WHEN the gate acts (shadow verdict, enforce-regenerate,
  enforce-suppress, or judge-unavailable) THE SYSTEM SHALL record a
  `coach_leakage_gate` governance carrier carrying `mode`, `verdict`, `action`,
  and `trace_id` — the observable audit trail for every stage.
- **FR-9.** THE SYSTEM SHALL confine the mode decision to a pure
  `decide_leakage_enforcement(mode, verdict, retry_verdict) → action` function
  (governance decides *what*); orchestration only performs the act (AP-4).

**Rollout guard:**

- **FR-10.** IF the gate mode is set to `shadow` or `enforce` WHILE the judge is
  not certified `ENABLE` on the frozen split THEN THE SYSTEM SHALL refuse to arm
  (mode resolves to `off`) — never enforce below the ADR-0008 cond#1 cert floor.
- **FR-11.** THE SYSTEM SHALL keep the enforcement judge call off the CI hot path
  — CI exercises the gate with a stub/in-memory judge and committed verdict
  fixtures; no live LLM in CI (root `AGENTS.md` 🚫).

**Architecture-boundary requirements (added at replan, 2026-07-06 — ADR-0009 conflict):**

> **Replan context.** Stage-6 implementation hit `tests/architecture/`
> `test_coach_judges_never_inline.py`, which enforces **ADR-0009** (*Reflexion
> loop is offline-only for the Subject-Coach*): the coach judges + their config
> reader are forbidden from `orchestration/` and `middleware/`. The enforce path
> below is exactly an inline judge call. Resolution (human-approved): **ADR-0020
> supersedes ADR-0009 with conditions** — a leak-**safety** gate is a distinct
> intent from convergence-**Reflexion** (ADR-0009's own rejected-alternatives
> reasoning names answer-leakage as a risk of inline *Reflexion*; a gate that
> *prevents* leakage is the opposite motion). The OFF-GRAPH rule is **narrowed,
> not deleted**: the Reflexion/GoalJudge/sampler inline path stays forbidden; the
> certified leakage gate gets a single declared binding.

- **FR-12.** THE SYSTEM SHALL introduce the inline leakage-gate binding only under
  **ADR-0020**, which supersedes ADR-0009 *with conditions*: the three ADR-0009
  reversal preconditions SHALL be recorded as met — (a) the `reflections`
  cross-turn leak is fixed (ADR-0005, done); (b) the gate uses a **coach-specific,
  leak-aware** judge (the ADR-0019-certified answer-leakage judge), not the
  task-failure Reflexion critique; (c) the judge is **certified** on the frozen
  split (TNR 1.0/TPR 1.0, ADR-0019) — the "measurable gain" precondition, here a
  safety guarantee rather than a latency-for-learning trade.
- **FR-13.** THE architecture gate SHALL continue to forbid any inline import of
  the **Reflexion/GoalJudge/coach-judge-sampler** machinery on the live path,
  WHILE permitting the single declared leakage-gate binding. IF any live-graph
  file imports the coach judges for a purpose OTHER than the declared leakage gate
  THEN the gate SHALL fail (the OFF-GRAPH rule is narrowed to one carve-out, not
  removed). The carve-out SHALL be explicit and named, not a blanket allowance.

## 4. Data model / contracts

- **`SubjectCoachJudgeRuntimeConfig`** (`services/subject_coach_judge_runtime_config.py`)
  gains `coach_leakage_gate_mode: Literal["off","shadow","enforce"] = "off"`.
  `coach_leakage_gate_enabled: bool` is **retained, deprecated** — the reader
  derives mode from it when the new field is absent (FR-4). `schema_version`
  stays `1` (additive, backward-compatible under `extra="forbid"` since the new
  field has a default; a config with only the old key still parses).
- **`ResolvedSubjectCoachJudgeConfig`** gains `coach_leakage_gate_mode: str`;
  `_posture_dict` echoes it (health/`/healthz` visibility).
- **`coach_leakage_gate` carrier** — a new governance carrier shape (mode,
  verdict, action, trace_id). Lives beside the existing `guardrail`/
  `coach_context_contract` carriers in the react-loop emit path; **not** a
  trust-kernel type (no re-signing) unless it must join the signed carrier
  spec — resolved at plan time (default: an emit-only dict carrier like the
  existing `guardrail_checked` shadow carrier, no `trust/` change).
- **Pure decision type** — `LeakageGateAction` enum
  (`allow | shadow_record | regenerate | suppress | fail_open`) returned by
  `decide_leakage_enforcement`.

## 5. Invariants & security boundaries

- **Invariant #1 (downward deps):** the enforcement seam sits in
  `orchestration/react_loop.py` and calls *down* into `components/` (the judge)
  and `services/` (the config reader + carrier emit). No upward import.
- **Invariant #6 (thin orchestration nodes):** the node holds ≤10–15 lines — the
  mode→action policy is the pure `decide_leakage_enforcement` in
  `components/` (mirrors `decide_enforcement` for the carrier gate). AP-4/AP-5.
- **Invariant #2 (trust purity):** default plan adds **no** `trust/` type; if the
  carrier must be signed, that becomes an explicit ADR-0020 sub-decision + re-sign
  note.
- **Security / no-live-LLM-in-CI:** FR-11 — the inline judge is a live call gated
  out of CI by a stub reader/judge; the deterministic `decide_*` + carrier path is
  fully unit-tested offline.
- **Fail-dark / fail-open split is deliberate:** *config* unknown → fail dark
  (`off`, FR-2); *judge outage while armed* → fail open (let through + loud
  carrier, FR-1). Config uncertainty must not enforce; a transient judge blip must
  not deny service.

## 6. Edge cases

- Coach reply is itself a refusal ("I can't just give you the answer") — must NOT
  be regenerated/suppressed (the payload-over-refusal rule; a refusal carries no
  leak). The judge already handles this post ADR-0017; the gate trusts the verdict.
- Regeneration produces an empty/errored reply → treat as judge-unavailable path
  (FR-1 fail-open on the *original*, not a blank emit).
- Non-coach runs (no `coach_context`) → the gate node is inert (mirrors the
  existing coach-context re-entry guard).
- Resumed run (step > 0) mid-turn → judge the turn's final reply once, not each
  intermediate token.
- Sample rate 0.0 in `shadow` → gate records "not sampled", never fabricates a
  verdict (AP-6: `None`, not a fake `false`).
- Mode string typo in config (`"enfroce"`) → `extra="forbid"`/`Literal` rejects →
  fail dark to `off` (FR-2), logged.

## 7. Non-functional requirements

- **Latency:** `off` adds 0. `shadow` adds the existing sampled/async judge cost
  (unchanged). `enforce` adds one inline judge call per coach turn (+ at most one
  regeneration on a flagged turn — rare given 0-FP cert). Budget + timeout pinned
  in the plan; on breach → FR-1 fail-open.
- **Reversibility:** mode is config-driven; a bad rollout reverts to `off` via a
  single config push (no redeploy), like carrier-gate `enforce_mode`.
- **Determinism:** the `decide_*` policy + carrier emit are L1-exact; the judge
  verdict is L2-sampled (shadow) / L4 live (enforce), replayed from committed
  fixtures in CI.
- **Cost:** enforce adds one live judge call/turn — acceptable for a leak-safety
  gate; quantify per-turn $ in the plan against the coach's own model cost.

## 8. Test bindings (failure-first)

| FR | Layer | Failure-first test |
|----|-------|--------------------|
| FR-1 | L2 | judge raises/times out in `enforce` → reply passes + `judge_unavailable` carrier (no black-out) |
| FR-2 | L2 | malformed config → resolved mode == `off` (fail dark) |
| FR-3 | L1/L2 | retry still leaks → suppressed + fallback emitted; leaking text never in output |
| FR-4 | L2 | config with only `coach_leakage_gate_enabled=true`, no mode field → mode == `enforce` |
| FR-5 | L2 | mode `off` → judge never called, reply byte-identical |
| FR-6 | L2 | mode `shadow` + flagged verdict → carrier recorded, reply unchanged |
| FR-7 | L1 | `decide_leakage_enforcement("enforce", leak=True, retry=None)` → `regenerate` |
| FR-8 | L2 | every action path emits a `coach_leakage_gate` carrier with mode/verdict/action/trace_id |
| FR-9 | L1 | pure `decide_leakage_enforcement` truth table (off/shadow/enforce × leak/clean/unavailable) |
| FR-10 | L2 | mode `enforce` while goldset manifest not `ENABLE`-certified → armed mode resolves `off` |
| FR-11 | arch | grep-gate: no live-LLM import on the CI test path; stub judge in the gate tests |

## 9. Out of scope

- Flipping the production config to `shadow`/`enforce` (an operational human step
  after this lands + a shadow-observation window — a runbook, not code).
- Span-level leak redaction (the binary judge has no span output — FR set uses
  regenerate/suppress, not redact).
- `coach_grader`/`coach_pedagogy` judge sample-rate increases (Phase 5.2, separate).
- Drift baselines + golden regression (Phase 5.3).
- A `coach_goldset_v2` production-leak feedback loop (Phase 5.4).

## 10. Definition of done

- All FR-1…FR-11 have a green failure-first test; `make check` +
  `pytest tests/architecture/ -q` green.
- ADR-0020 written (Context/Options incl. rejected boolean-replace + fail-closed-
  on-outage / Rationale / Consequences), indexed + logged, linked from the
  enforcement call-site + `decisions.md`.
- Ledgers updated: `subject-coach-agent.plan.md` task 5.1 →  built (mode plumbed,
  gate enforcing under test, config OFF in prod); parent enable-policy plan
  cross-linked.
- Gate ships with `coach_leakage_gate_mode` defaulting to `off` in all
  environments — arming is the separate operational step (§9).
