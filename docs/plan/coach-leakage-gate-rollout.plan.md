---
type: plan
title: 'Coach answer-leakage gate rollout (Phase 5) — Implementation Plan'
authored: 2026-07-06
---

# Coach answer-leakage gate rollout — Implementation Plan

**Spec:** [coach-leakage-gate-rollout.spec.md](coach-leakage-gate-rollout.spec.md) ·
**Parent:** [subject-coach-agent.plan.md](subject-coach-agent.plan.md) (Phase 5, task 5.1) ·
**Cert:** [ADR-0019](../adr/0019-fireworks-host-adapter.md) (judge CERTIFIED) ·
**ADR:** ADR-0020 (this rollout — live-judge-in-path enforcement seam + off/shadow/enforce policy).

## Status ledger

> **Replanned 2026-07-06 (Stage-5).** Stage-6 hit a plan-invalidating blocker at
> the judge-in-path step: `tests/architecture/test_coach_judges_never_inline.py`
> enforces **ADR-0009** (coach judges OFF-GRAPH, forbidden from `orchestration/` +
> `middleware/`). Human decision: **ADR-0020 supersedes ADR-0009 with conditions**
> — enforce stays inline; the OFF-GRAPH rule is *narrowed* (Reflexion/sampler path
> still forbidden, one declared leakage-gate binding permitted). New gating task
> **P0.5** carries the supersede + the arch-test rework; it blocks P4/P5. T1–T3
> already landed green and are graph-clean. See spec FR-12/FR-13 + `decisions.md`.

| Item | Status | Evidence |
|---|---|---|
| P1 Pure decision core (T1) | ✅ DONE | `components/coach_leakage_gate.py` `decide_leakage_enforcement` truth table; 14 L1 tests green (with T2). Graph-clean. |
| P2 Cert-arming guard (T2) | ✅ DONE | `arm(mode, goldset_certified)` refuses live mode below cert (FR-10); same test file. |
| P3 Config mode field (T3) | ✅ DONE | `coach_leakage_gate_mode` + FR-4 bool-derivation + FR-2 fail-dark; 25 L2 tests green. Graph-clean. |
| P0.5 ADR-0020 supersedes ADR-0009 + arch-test rework | ⬜ NEW — gating front | ADR-0020 records the supersede + 3 ADR-0009 reversal preconditions met (FR-12); rework `test_coach_judges_never_inline.py` to forbid the Reflexion/sampler inline path while permitting ONE declared leakage-gate binding (FR-13), red-first. Blocks P4/P5. |
| P4 Runtime judge adapter (T4) | ✅ DONE | `judge_leakage` in `components/coach_leakage_gate.py` — maps verdict→`LeakageGateVerdict`, `None`/raise → `unavailable` (FR-1); stub-injectable, no live LLM in CI (FR-11). 5 L2 tests. |
| P5 Orchestration act + carrier (T5/T6/T7) | ✅ DONE | `_run_coach_leakage_gate` + `_record_leakage_gate_carrier` in `react_loop.py`; inline regen via `make_regenerate(llm_service)` (no topology edge — confirmed `llm_service` reachable in node closure); wired into `evaluate_node` OUTPUT_VALIDATION, coach-only + arm-gated. 6 L2 helper tests. FR-1/3/5/6/7/8. |
| P6 Ledgers + review (T8) | 🔵 in progress | `make check` **green (5156 passed)**; config OFF in all envs (default `off` + `arm` refuses below cert). Ledgers updated; Stage-7 code-review NEXT. |

---

## Architecture

**This is the carrier-gate pattern, re-aimed at coach output.** The repo already
has the exact shape in `services/governance/carrier_gate.py`:
pure `decide_enforcement(gap, mode) → EnforcementDecision` + `record_carrier_gap`
(shadow) + `record_enforcement` (loud), with orchestration doing only the act
(AP-4/AP-5). The leakage gate mirrors it 1:1, substituting a **judge verdict** for
a **carrier gap** and a **regenerate/suppress act** for a **degrade/raise act**.

The enforcement point is the **`OUTPUT_VALIDATION` phase in `evaluate_node`**
(`orchestration/react_loop.py:~2430`) — the pre-emit checkpoint where
`output_guardrail_scan` already runs on the final `content`, already inside a
`phase_logger.phase(...)` context with `black_box`, and already carries the
"always emit a `guardrail_checked` even on a clean pass" pattern the spec's FR-8
needs. The leakage gate is a sibling check in that same block, gated on
`coach_context is not None` (non-coach runs stay byte-identical).

```
evaluate_node → OUTPUT_VALIDATION phase (react_loop.py:~2430)
    content (final coach reply) ─┐
                                 ▼
  [coach run only]  mode = reader.get().coach_leakage_gate_mode        ← P2 (FR-4/FR-2)
                    mode = arm(mode, goldset_manifest)                  ← P3 (FR-10 cert floor)
                                 │
              mode == "off" ─────┴──▶ emit nothing, content unchanged   (FR-5)
                                 │
              verdict = await judge(content, mode) [live; stub in CI]   ← P4 (FR-11)
                    │  (judge outage/timeout → verdict = UNAVAILABLE)    (FR-1)
                                 ▼
      action = decide_leakage_enforcement(mode, verdict, retry=None)    ← P1 pure (FR-9)
                                 │
   ┌── shadow ──────────────────┼── enforce ─────────────────────────┐
   ▼                            ▼                                     ▼
 record carrier,             leak → regenerate once (FR-7),      unavailable →
 content unchanged (FR-6)    re-judge → decide(retry_verdict):   allow + loud
                              still leak → suppress→fallback(FR-3) carrier (FR-1)
                              clean now → emit regenerated
                                 │
                                 ▼
        record_leakage_gate carrier {mode,verdict,action,trace_id}      (FR-8)
```

**Layering.** Pure policy + action enum live in `components/` (framework-agnostic,
Invariant #3) — NOT `services/`, because the carrier-gate precedent puts its pure
decision in a governance *service*, but this decision is coach-domain (it knows the
leakage verdict semantics), so it belongs with the coach judges in `components/`
(sibling to `subject_coach_judges.py`, no peer import — Invariant #5, it imports
only `components/schemas.py`). The **judge call** and **carrier emit** are I/O and
stay in orchestration's node body (Invariant #6 thin wrapper: the node calls
`decide_*` and acts; ≤15 lines of new act logic, all branch-per-action).

**Why not the output guardrail?** `output_guardrail_scan` is a deterministic
regex/PII rail (`services/guardrails.py`). Leakage is semantic (0/200 direct leaks
in the human coding — ADR-0017 rejected a lexical pre-filter). The gate is a
*separate* LLM-judge check beside it, not folded into it.

## File-level touchpoints

| File | Change | Layer |
|---|---|---|
| `components/coach_leakage_gate.py` | **new** — `LeakageGateMode(off/shadow/enforce)`, `LeakageGateVerdict(leak/clean/unavailable)`, `LeakageGateAction(allow/shadow_record/regenerate/suppress/fail_open)`, pure `decide_leakage_enforcement(mode, verdict, retry_verdict) → LeakageGateAction`. Imports only `components/schemas.py` + stdlib/pydantic. | components (L1) |
| `tests/components/test_coach_leakage_gate.py` | **new** — the FR-9 truth table (3 modes × {clean, leak, unavailable} × {retry None, retry leak, retry clean}); failure rows first. | test |
| `services/subject_coach_judge_runtime_config.py` | extend — add `coach_leakage_gate_mode: Literal["off","shadow","enforce"]="off"` to `SubjectCoachJudgeRuntimeConfig` + `ResolvedSubjectCoachJudgeConfig`; derive from deprecated `coach_leakage_gate_enabled` when the field is absent (FR-4); env fallback `COACH_LEAKAGE_GATE_MODE`; `_posture_dict` echoes it. Fail-dark to `off` on malformed (FR-2, existing contract). | services (L2) |
| `tests/services/test_subject_coach_judge_runtime_config.py` | extend — FR-2 malformed→off, FR-4 bool-derive, invalid mode string→off (extra=forbid/Literal). | test |
| `components/coach_leakage_gate.py` (or a small `arm` helper) | `arm(mode, *, goldset_certified: bool) → mode` — returns `off` unless certified (FR-10). Keeps the cert-floor guard pure + testable. | components (L1) |
| `orchestration/react_loop.py` | extend `evaluate_node` OUTPUT_VALIDATION block: coach-only judge→decide→act + `coach_leakage_gate` carrier (FR-1/3/5/6/7/8). Node stays thin (delegates to `decide_leakage_enforcement` + the judge + one regenerate call). Reuse the existing regenerate path (same model-call the node already makes) for FR-7. | orchestration |
| `tests/orchestration/test_coach_leakage_gate_node.py` | **new (L2)** — stub judge + in-memory config reader: FR-1 outage fail-open, FR-3 suppress, FR-5 off byte-identical, FR-6 shadow observe, FR-7 regenerate-once, FR-8 carrier shape. No live LLM (FR-11). | test |
| `docs/adr/0020-coach-leakage-gate-rollout.md` + `index.md` + `log.md` + `decisions.md` | **new** — ADR-0020 (the ⚠️ Ask-first payload). Link from the `evaluate_node` seam. | docs |
| `docs/plan/subject-coach-agent.plan.md` | task 5.1 status → built-under-test (config OFF in prod). | docs |

## Migration / sequencing (dependency order)

1. **P0** ADR-0020 authored alongside the seam it governs (ratchet needs it before merge).
2. **P1** pure `decide_leakage_enforcement` + action enum — red-first truth table. No deps. Do first.
3. **P2** config `coach_leakage_gate_mode` + bool-derivation — red-first (malformed→off, bool-derive). Depends on nothing runtime.
4. **P3** `arm` cert-floor guard — red-first (armed-below-cert → off). Depends on P1 types.
5. **P4** runtime judge adapter callable (stub-injectable) — the live seam; CI uses the stub.
6. **P5** orchestration act in `evaluate_node` — needs P1–P4. The one thin-wrapper node change.
7. **P6** ledgers + Stage-7 review; `make check` + `pytest tests/architecture/ -q` green; ship with mode `off` everywhere.

**Reuse (do not rebuild):** the carrier-gate pure/shadow/loud triplet
(`services/governance/carrier_gate.py`) as the structural template; `PedagogyJudge`
(`components/subject_coach_judges.py`) as the verdict source (it already returns
`answer_leakage` with mode-awareness + a fail-CLOSED `None` on judge error — the
gate maps `None`→`unavailable`→fail-open per FR-1); the existing OUTPUT_VALIDATION
`guardrail_checked` emit block as the carrier template.

## Constitution check (⚠️ Ask-first triggers)

- **Supersedes ADR-0009 (Accepted)** → the load-bearing ⚠️ Ask-first trigger,
  found at replan. ADR-0009 declared the coach judges OFF-GRAPH; putting the
  certified leakage judge inline reverses that. **ADR-0020 supersedes ADR-0009
  *with conditions*** (FR-12): the OFF-GRAPH rule is *narrowed*, not deleted — the
  Reflexion/GoalJudge/sampler inline path stays forbidden; the leakage gate gets
  ONE named, declared binding. All three ADR-0009 reversal preconditions are
  recorded met: (a) `reflections` leak fixed (ADR-0005); (b) coach-specific
  leak-aware judge, not the task-failure critique; (c) judge certified TNR 1.0/TPR
  1.0 on the frozen split (ADR-0019). The `test_adr_ratchet` + `test_no_test_weakening`
  gates apply — P0.5 must ship the ADR + the narrowed arch test together.
- **New graph-node logic in `orchestration/react_loop.py`** → ⚠️ Ask-first. But it
  is *added logic in an existing node* (`evaluate_node`), not a new node in the
  topology, and it stays ≤15 lines by delegating to the pure `decide_*` +
  judge + one regenerate — **Invariant #6 holds**. Covered by **ADR-0020**.
- **Live LLM call added to the live request path** → ⚠️ Ask-first (behavior change
  on a trust boundary). Covered by **ADR-0020**; FR-11 keeps it out of CI.
- **Config schema change** (`SubjectCoachJudgeRuntimeConfig` new field) →
  additive, default `off`, `schema_version` unchanged, backward-compatible under
  `extra="forbid"` (a config with only the old bool still parses, FR-4). Not a
  trust-kernel type → **no re-signing**. Logged in ADR-0020 §Consequences.
- **No new pyproject dependency** (judge rides the existing Fireworks adapter);
  **no trust-kernel type change**; **no new horizontal service** (policy is a
  `components/` pure fn, act is in-node). **No `.j2` rubric edit** (the certified
  rubric is frozen — AP-3 untripped).
- **G1 new-abstraction gate:** the gate reuses the carrier-gate triplet shape
  rather than inventing one; the only new abstraction is the `LeakageGateAction`
  enum, which earns its place as the pure-decision contract (ADR-0020 states it).

## Risks

- **Latency on every coach turn in `enforce`** — one inline judge call + a possible
  regenerate. Mitigation: pin a per-call timeout; FR-1 fail-open on breach; the
  shadow stage measures real added latency before enforce is ever armed.
- **Regeneration divergence** — a regenerated reply may lose pedagogical quality
  even when it clears leakage. Mitigation: the fallback is a *safe Socratic
  redirect*, not a hard error; shadow-stage telemetry quantifies regen frequency
  (expected rare — 0 FP certified) before enforce.
- **Fail-open leak window** — a judge outage in `enforce` lets replies through
  (FR-1). Accepted trade-off (availability > a rare leak during an outage), made
  loud via the `judge_unavailable` carrier so it is observable + alertable. The
  opposite (fail-closed) was rejected in the clarify pass.
- **Arming below cert** — FR-10 refuses to arm unless the manifest is
  `ENABLE`-certified, so a config typo can't enforce on an uncertified judge.

## TDD binding (failure-first)

| Artifact | Layer | Watch-fail-first test |
|---|---|---|
| `decide_leakage_enforcement` | L1 | `enforce`+leak+retry-still-leak → `suppress` BEFORE the allow path |
| config mode | L2 | malformed config → `off` (fail dark) BEFORE valid parse |
| bool-derivation | L2 | old-bool-only config, `true` → mode `enforce` |
| arm guard | L1 | armed `enforce` while not certified → `off` |
| outage | L2 | judge raises in `enforce` → reply passes + `judge_unavailable` carrier |
| suppress | L2 | leaking text never appears in emitted `content` (enforce) |
| carrier | L2 | every action path emits `coach_leakage_gate` with mode/verdict/action/trace_id |
| off parity | L2 | mode `off` → judge never called, `content` byte-identical |

## Verification

- Per task: red-first per §8 of the spec; watch fail before implement.
- Phase exit (P6): `make check` + `pytest tests/architecture/ -q` green;
  ships with `coach_leakage_gate_mode=off` in all environments (arming is the
  separate operational runbook — spec §9).
- Stage-7: code-review skill over the Phase-5 diff before declaring 5.1 built.
