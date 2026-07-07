---
type: tasks
title: 'Coach answer-leakage gate rollout (Phase 5) — Task list'
authored: 2026-07-06
---

# Coach answer-leakage gate rollout — Tasks

**Spec:** [coach-leakage-gate-rollout.spec.md](coach-leakage-gate-rollout.spec.md) ·
**Plan:** [coach-leakage-gate-rollout.plan.md](coach-leakage-gate-rollout.plan.md) ·
**ADR:** ADR-0020 (authored in T0).

Legend — **Dep:** hard dependency · **∥** may run parallel to siblings ·
each task is **red-first** (write the failing test, paste the fail, then implement).
Every task maps 1:1 to spec FRs and pins its own pass/fail oracle.

---

## T0 / P0.5 — ADR-0020 supersedes ADR-0009 + arch-test rework *(Dep: none · GATING FRONT — blocks T4/T5/T7)* — FR-12, FR-13

> **Added/expanded at replan (2026-07-06).** Stage-6 hit
> `tests/architecture/test_coach_judges_never_inline.py` (enforces ADR-0009:
> coach judges OFF-GRAPH). The inline enforce path reverses that. ADR-0020 now
> **supersedes ADR-0009 with conditions** AND the arch test is narrowed — they
> must land together (the ratchet + no-test-weakening gates require it). This is
> the new gating task; T4/T5/T7 cannot proceed until it is green.

**Do (ADR):** `docs/adr/0020-coach-leakage-gate-rollout.md` from
`docs/adr/0000-template.md`, frontmatter `related:` includes `0009-*`, body states
**Supersedes ADR-0009 with conditions**. Context (judge CERTIFIED but no live-path
consumer; ADR-0009 forbade inline coach judgment). Options (incl. rejected:
delete-the-arch-test, middleware-enforce, shadow-only-defer-enforce,
boolean-replace-outright, fail-closed-on-outage, decision-in-`services/`). Decision
(off/shadow/enforce, regenerate-once→suppress, fail-open on outage,
decision-in-`components/`, inline regen via `llm_service`; **ADR-0009 narrowed to
one declared leakage-gate binding** — the 3 reversal preconditions recorded met:
reflections-leak-fixed / coach-specific-leak-aware-judge / certified-TNR1.0). Update
ADR-0009 frontmatter `related:` + a "superseded-in-part by ADR-0020" note.
Consequences (config additive no-resign; one live call/turn in enforce; the
OFF-GRAPH invariant survives for Reflexion/sampler). Add `index.md` entry +
newest-first `log.md` line + a `decisions.md` pointer line.

**Do (arch test):** rework `tests/architecture/test_coach_judges_never_inline.py`
**red-first** (G8 — this is a mass test change, justify each weakened assertion):
- KEEP `test_live_graph_layers_never_import_the_coach_judges` forbidding
  `subject_coach_judge_sampler` on the live path (the Reflexion/sampler rule stands).
- NARROW the `subject_coach_judges` / `subject_coach_judge_runtime_config` tokens:
  permit exactly the ONE declared leakage-gate binding (the `evaluate_node` seam +
  its `components/coach_leakage_gate.py` adapter), forbid any other live-graph
  import. Add a positive test asserting the carve-out is *named*, not blanket
  (e.g. an allowlist of the exact permitted file+symbol), and a negative test that
  a *second* undeclared inline judge import still fails.
- Justify the weakening with a `G8-OK: ADR-0020 supersedes ADR-0009` token in the
  commit + an inline comment citing FR-13.

**Pass/fail:**
- `pytest tests/architecture/test_adr_ratchet.py -q` green (`docs/adr/0020-*` exists).
- `pytest tests/architecture/test_no_test_weakening.py -q` green (G8 token present).
- the reworked `test_coach_judges_never_inline.py`: sampler-inline still fails;
  the one declared leakage binding passes; a second undeclared binding fails.
- `scripts/okf_lint.py` green on ADR frontmatter/index/log.

---

## T1 — Pure decision core + action enum ✅ DONE *(Dep: none)* — FR-9, FR-3, FR-7

**File:** `components/coach_leakage_gate.py` (new) ·
**Test:** `tests/components/test_coach_leakage_gate.py` (new)

**Do:** define
- `LeakageGateMode = Literal["off","shadow","enforce"]`
- `LeakageGateVerdict = Literal["clean","leak","unavailable"]`
- `LeakageGateAction = Literal["allow","shadow_record","regenerate","suppress","fail_open"]`
- pure `decide_leakage_enforcement(mode, verdict, *, retry_verdict=None) -> LeakageGateAction`.

Import only stdlib/pydantic + (if needed) `components/schemas.py`. No I/O, no LLM.

**Truth table (failure rows FIRST):**
| mode | verdict | retry_verdict | → action |
|---|---|---|---|
| enforce | leak | leak | `suppress` (FR-3) |
| enforce | leak | None | `regenerate` (FR-7) |
| enforce | leak | clean | `allow` (regen cleared) |
| enforce | unavailable | — | `fail_open` (FR-1) |
| enforce | clean | — | `allow` |
| shadow | leak / clean | — | `shadow_record` (FR-6) |
| shadow | unavailable | — | `shadow_record` |
| off | * | — | `allow` (FR-5) |

**Pass/fail:** every row asserted; `pytest tests/components/test_coach_leakage_gate.py -q`
green; watched-fail first (NameError before impl).

---

## T2 — `arm` cert-floor guard ✅ DONE *(Dep: T1)* — FR-10

**File:** `components/coach_leakage_gate.py` (extend) ·
**Test:** same test file (extend)

**Do:** `arm(mode, *, goldset_certified: bool) -> LeakageGateMode` — returns `mode`
if `goldset_certified` else `"off"`. Pure. (The caller derives `goldset_certified`
from the goldset manifest being `ENABLE`-certified / non-provisional; that read is
wired in T7, but the *guard* is pure + unit-tested here.)

**Pass/fail:** `arm("enforce", goldset_certified=False) == "off"`;
`arm("enforce", goldset_certified=True) == "enforce"`; `arm("shadow", certified=False) == "off"`.
Failure row (uncertified) asserted first.

---

## T3 — Config `coach_leakage_gate_mode` + bool-derivation ✅ DONE *(Dep: none)* — FR-2, FR-4

**File:** `services/subject_coach_judge_runtime_config.py` (extend) ·
**Test:** `tests/services/test_subject_coach_judge_runtime_config.py` (extend)

**Do:**
- add `coach_leakage_gate_mode: Literal["off","shadow","enforce"] = "off"` to
  `SubjectCoachJudgeRuntimeConfig` and `coach_leakage_gate_mode: str` to
  `ResolvedSubjectCoachJudgeConfig`.
- **Derivation (FR-4):** when the parsed config has no explicit mode field but
  carries the deprecated `coach_leakage_gate_enabled`, resolve
  `true → "enforce"`, `false → "off"`. (Both fields present → the explicit mode
  wins; both absent → `off`.)
- env fallback `COACH_LEAKAGE_GATE_MODE` (validated against the 3 literals; invalid
  → `off`); keep the existing `COACH_LEAKAGE_GATE_ENABLED` env derivation for FR-4.
- `_posture_dict` echoes `leakage_gate_mode` for `/healthz`.

**Pass/fail (failure first):**
- malformed/unparseable config → resolved mode `"off"` (FR-2 fail-dark).
- config `{"coach_leakage_gate_enabled": true}` (no mode field) → mode `"enforce"` (FR-4).
- config `{"coach_leakage_gate_mode": "enfroce"}` (typo) → parse rejected → `"off"`.
- `extra="forbid"` still parses a legacy doc carrying only the old bool.
`pytest tests/services/test_subject_coach_judge_runtime_config.py -q` green.

---

## T4 — Runtime judge adapter (stub-injectable) *(Dep: T0/P0.5 — the arch carve-out must exist first)* — FR-11, FR-1

**File:** a thin callable seam — `components/coach_leakage_gate.py` `judge_leakage(...)`
protocol OR a small factory in the node closure ·
**Test:** covered in T7's node test (stub) + a unit test for the outage mapping.

**Do:** define the runtime verdict source: given `(coach_reply, mode, learner_utterance,
question)` return a `LeakageGateVerdict`. It wraps `PedagogyJudge.evaluate(...)`
(`components/subject_coach_judges.py`) reading `.answer_leakage`; a `None` verdict
(judge error / parse fail — the judge already fails CLOSED to `None`) maps to
`"unavailable"` (→ `fail_open` downstream, FR-1). **CI never calls the live judge**
— the node accepts an injected judge; tests pass a stub (FR-11).

**Pass/fail:** unit test — judge returns `answer_leakage=True` → `"leak"`;
`answer_leakage=False` → `"clean"`; judge returns `None`/raises → `"unavailable"`.
Grep-gate: no live-LLM import on the gate's CI test path.

---

## T5 — Regenerate mechanism (inline, no topology change) *(Dep: T1, T4)* — FR-7, FR-3

**File:** `orchestration/react_loop.py` (helper inside `evaluate_node` closure) ·
**Test:** `tests/orchestration/test_coach_leakage_gate_node.py` (new, stub `llm_service`)

**Do:** on a `regenerate` action, call the closure-level **`llm_service`** (the same
handle `call_llm_node` uses — confirmed reachable, so **no graph edge / loop-back**)
with a stronger no-leak directive, then re-judge the regenerated text once
(`retry_verdict`) and re-`decide`. **No second regenerate** — one retry only, then
`suppress`→ canned Socratic fallback (FR-3). The fallback string is a constant
(not a `.j2` rubric edit — AP-3 untripped).

**Pass/fail (failure first):**
- regen still leaks → emitted `content` is the fallback, and the leaking text
  (original AND regen) never appears in output (FR-3).
- regen clears → emitted `content` is the regenerated reply.
- exactly one regen call made (assert `llm_service` call count == 1 on a flagged turn).

---

## T6 — `coach_leakage_gate` carrier emit *(Dep: T1)* — FR-8

**File:** `orchestration/react_loop.py` (emit in the OUTPUT_VALIDATION block) ·
**Test:** T7 node test asserts the carrier on every path.

**Do:** a `guardrail_checked`-style `TraceEvent` (mirror the existing
OUTPUT_VALIDATION `output_scan` emit) with
`details={"guardrail":"coach_leakage_gate","mode":..,"verdict":..,"action":..,
"trace_id":..,"checked":True}`. Emitted on **every** gated path — shadow record,
enforce allow/regenerate/suppress, and `fail_open` — never silent (mirrors
`carrier_gate`'s always-emit).

**Pass/fail:** each of the 5 action paths produces exactly one
`coach_leakage_gate` carrier carrying mode/verdict/action/trace_id.

---

## T7 — Orchestration act wiring in `evaluate_node` *(Dep: T1–T6)* — FR-1, FR-3, FR-5, FR-6, FR-7, FR-8

**File:** `orchestration/react_loop.py` `evaluate_node` OUTPUT_VALIDATION phase ·
**Test:** `tests/orchestration/test_coach_leakage_gate_node.py` (extend)

**Do:** coach-only (`coach_context is not None`) block beside `output_guardrail_scan`:
```
mode  = arm(reader.get().coach_leakage_gate_mode, goldset_certified=<manifest ENABLE>)
if mode == "off": (emit nothing, content unchanged)          # FR-5
else:
    verdict = await judge_leakage(content, mode, ...)         # T4 (stub in CI)
    action  = decide_leakage_enforcement(mode, verdict)       # T1 pure
    content = act(action, content, ...)                       # T5 regen/suppress; shadow=noop
    record coach_leakage_gate carrier                         # T6 / FR-8
```
Node stays a **thin wrapper** (Invariant #6): all policy in `decide_*`/`arm`, the
act is branch-per-action + one `llm_service` call. Add the ADR-0020 link comment.

**Pass/fail (failure first, stub judge + in-memory reader — NO live LLM):**
- FR-1: judge stub raises in `enforce` → `content` unchanged + `judge_unavailable`/`fail_open` carrier.
- FR-5: mode `off` → judge stub never called, `content` byte-identical, no carrier.
- FR-6: mode `shadow` + leak verdict → carrier recorded, `content` unchanged.
- FR-3/FR-7: enforce + leak → regen path (T5) exercised end-to-end.
- non-coach run (`coach_context` None) → block inert, trace byte-identical.
`pytest tests/orchestration/test_coach_leakage_gate_node.py -q` +
`pytest tests/architecture/ -q` green.

---

## T8 — Ledgers + Stage-7 review + gate ships OFF *(Dep: T0–T7)* — DoD

**Do:**
- `docs/plan/subject-coach-agent.plan.md` task 5.1 → "built under test (mode plumbed,
  gate enforcing in tests; `coach_leakage_gate_mode=off` in all envs)".
- cross-link this bundle from `coach-goldset-enable-policy.plan.md`.
- confirm no env/deploy config sets a non-`off` mode (grep the terraform/env).
- `make check` + `pytest tests/architecture/ -q` green.
- run the **code-review** skill over the Phase-5 diff (deterministic); interpret
  the report; fix criticals.

**Pass/fail:** `make check` green; reviewer verdict ≠ reject; ledgers updated;
grep confirms `off` everywhere. Arming to `shadow`/`enforce` is the separate
operational runbook (spec §9) — explicitly NOT in this task.

---

## T9 — Step 0 composition wire (cert attestation) ✅ DONE *(Dep: T7, T8)* — FR-10, Recipe 9 §Step 0

**File:** `middleware/composition.py` ·
**Test:** `tests/middleware/test_coach_shadow_wiring.py::TestCoachLeakageCertAttestation` (new)

**Context:** T8 shipped the gate `off`, but `build_runtime_graph` did not pass
`coach_goldset_certified`, so `arm()` pinned the gate `off` in prod *regardless of
config* — shadow/enforce were unreachable. Recipe 9 flagged this as the open Step-0
prerequisite. This closes it.

**Do (red-first):**
- add `coach_leakage_cert_attested: bool = False` to `AgentRuntimeSettings`
  (env `COACH_LEAKAGE_CERT_ATTESTED`, default OFF — never arm a gate by default).
- `build_runtime_graph` forwards `coach_goldset_certified=bool(settings
  .coach_leakage_cert_attested)` into `build_graph`. Off ⇒ `arm` keeps `off`.
- update Recipe 9 Step 0 (attestation is now an env var, not a pending code wire).

**Pass/fail (failure first):**
- unattested/default settings → `build_graph` receives `coach_goldset_certified=False`
  (fail-safe — gate pinned off regardless of mode).
- attested settings → `coach_goldset_certified=True`.
- `AgentRuntimeSettings()` default is `False`.
- `make check` green (**5159 passed**); `scripts/okf_lint.py` 0 failures.

**NOT in this task:** flipping `COACH_LEAKAGE_CERT_ATTESTED=true` on a real deployment
(that's the operator's arming act, Recipe 9 Steps 1–2), and the shadow-observation
window before enforce. This only makes arming *reachable*.

---

## FR ↔ task coverage matrix (Stage-4 pre-check)

| FR | Covered by |
|----|-----------|
| FR-1 judge outage → fail-open + carrier | T4 (map), T7 (act), T6 (carrier) |
| FR-2 malformed config → off (fail dark) | T3 |
| FR-3 retry still leaks → suppress, never emit leak | T1, T5 |
| FR-4 bool-derive mode | T3 |
| FR-5 off → no judge, unchanged | T7 |
| FR-6 shadow → record, unchanged | T7, T6 |
| FR-7 enforce leak → regenerate once | T1, T5 |
| FR-8 carrier every path | T6, T7 |
| FR-9 pure decision truth table | T1 |
| FR-10 refuse to arm below cert | T2, T7 (manifest read) |
| FR-11 no live LLM in CI | T4 (stub-injectable), T7 (stub), T8 (grep) |

**No FR is unmapped; no task lacks an FR** — Stage-4 zero-coverage check passes on this decomposition.
