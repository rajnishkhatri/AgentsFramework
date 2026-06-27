---
type: plan
title: 'Severity-Graded Shell-Command Approval (HITL) — Brainstorm + Implementation Plan'
description: 'Replace the binary shell allowlist with a hybrid severity classifier + three-band approve/ask/deny PEP, gating risky commands behind a native AG-UI human-approval card (dynamic interrupt + resume). Includes the external-research trade-off that rejected the bespoke pause/resume and static interrupt_before in favor of the protocol-native dynamic interrupt.'
status: implemented
tags: [plan, guardrails, shell, hitl, human-in-the-loop, approval, severity, ag-ui, governance]
---

# Severity-Graded Shell-Command Approval (HITL)

> Approved 2026-06-27. **Part A** is the brainstorm + external-research trade-off; **Part B** is
> the TDD implementation plan hardened under `research/tdd_agentic_systems_prompt.md`,
> `docs/Architectures/FOUR_LAYER_ARCHITECTURE.md` + `GUARDRAILS_DIMENSION_SPACE.md`, and
> `docs/skills/governance-trace-audit`. Reuses the Part-1 live-LLM probe harness
> (`docs/plans/toolcalling_f1f7_live_validation.plan.md`) for live E2E but does not depend on it.

---

# PART A — Brainstorm + Trade-off

## Context / the need

Today `services/tools/shell.py` is a hard fail-closed allowlist (8 commands; any metacharacter,
`rm`/`curl`/`sudo`, etc. → `ValueError` → rejected pre-execution). `ALLOWLIST_DIAGNOSIS.md`
showed this *over*-blocks routine intent (`echo`/`pwd`/`python3` and `python -c` bodies are the
top rejections) while still being all-or-nothing. The user wants: **allow more commands, but have
a guardrail classify each command's severity, and gate medium-risk commands behind human/user
approval before execution** — auto-allow the safe, hard-deny the catastrophic.

This is a recognized pattern. External best-practice (OWASP AI-Agent Security; LangChain HITL
docs; Anthropic's Claude-Code Auto Mode; AG-UI/CopilotKit) converges on: **separate
decision-from-execution at a pre-execution PEP, tier actions by risk, gate only the high-blast-
radius/irreversible ones behind a fail-closed human approval, and audit every decision.**

## What already exists in-repo (reuse, don't rebuild)

| Need | Already in repo | File:line |
|---|---|---|
| Severity enum (LOW/MED/HIGH/CRIT) | `Severity(str, Enum)` | `services/governance/guardrail_validator.py:32` |
| Cascade classifier pattern (precheck→classifier→judge) | `InputGuardrail.decide()` | `services/guardrails.py:383` |
| Pre-execution PEP (deny-before-execute) | `verify_authorize_log_node` | `orchestration/react_loop.py:2135` |
| "Gated, not failed" error_class | `error_class="gating"` (task delegation) | `services/tools/task_tool.py:105` |
| Shell validation/timeout error_class (F1b) | typed `ToolExecutionResult` | `services/tools/shell.py:54` |
| Pause→side-POST→resume-same-thread transport | `register_understanding_edit_route` | `middleware/app_prod.py:539` |
| Native node pause | `interrupt_before=['execute_tool']` (OFF in prod) | `react_loop.py:3661`, `app_prod.py:254` |
| Frontend HITL primitive | CopilotKit dep + `ToolCard.tsx` + `lib/wire/ui_runtime_events.ts` | `frontend/` |
| Config-flag (shadow-first) discipline | `AgentConfig` feature flags | `services/base_config.py` |

## Decisions locked with the user

- **Classifier:** **Hybrid** — deterministic severity tables decide the clear cases; an LLM judge
  adjudicates only the ambiguous middle band (mirrors the existing `InputGuardrail` cascade).
- **Gate action:** **three-band approve / ask / deny** with a hard ceiling — below threshold
  auto-run (expands today's allowlist), middle pause-for-human, above ceiling un-approvable.
  Fail-closed on classifier/approval/audit failure or timeout.
- **HITL transport:** **Full Option 3** (see trade-off) — because the existing pause/resume
  (option 1) **is not working in practice** (users can't stop/modify/approve).

## External best-practice synthesis (what "optimum" means here)

1. **Tier by reversibility & blast radius, not by command name alone.** OWASP's four-tier
   `RiskLevel` (read=LOW, write=MED, financial/irreversible=CRIT) and the EU-AI-Act tiers both map
   risk to escalation. Apply to shell: read-only (`ls/cat/grep/find/echo/pwd/wc`) = LOW auto;
   write/move (`mkdir/cp/mv/touch`, `python -c` with side effects) = MED ask; destructive/network/
   privilege (`rm/curl/wget/nc/chmod/sudo`, redirects into files) = HIGH ask-with-ceiling;
   `rm -rf /`-class = CRIT hard-deny.
2. **Fail-closed.** OWASP: *"Fail closed when risk classification, approval validation, policy
   lookup, or audit logging fails."* A timeout = denial, no exception path.
3. **Separate decide from execute (PEP/PDP).** Already the repo's `verify_authorize_log_node`
   shape — the gate proposes; an independent check validates approval state before execution.
4. **Interrupt only the risky calls, not all tools.** LangChain docs: *static `interrupt_before`
   is "not recommended for HITL"* (debugging-only, coarse); **dynamic `interrupt()` placed inside
   the sensitive path** is the production pattern. This is the crux of the transport trade-off.
5. **Two-stage classifier to control latency/cost** (Claude-Code Auto Mode): a fast single-token
   filter, CoR reasoning only when flagged → most commands clear stage 1 free. Maps to our hybrid:
   deterministic table = stage 1; LLM judge = stage 2, ambiguous-band only.
6. **Audit every decision** with structured metadata (action class, risk score, approval id,
   outcome, policy version) → our `EventType.GUARDRAIL_CHECKED` carrier.

## THE TRADE-OFF: HITL transport — option 1 vs option 2 vs the optimum

The user's lived signal: **option 1 (manual pause-the-SSE → POST to a side route → re-invoke
`/run/stream`) is not working — users can't stop / modify / approve.** The research explains
*why*, and points to a third, better option.

| Axis | **Opt 1: understanding-edit pause/resume** (`register_understanding_edit_route`) | **Opt 2: static `interrupt_before=['execute_tool']`** | **Opt 3 (OPTIMUM): dynamic `interrupt()` in the shell path → AG-UI approval event** |
|---|---|---|---|
| How the user acts | Client must *know* to pause, hand-roll a POST to a bespoke route, then re-invoke. No native UI affordance → **this is exactly why approve/modify "doesn't work."** | Graph halts before the tool node; client must detect the halt and resume with `Command`. Still no per-command UI; **pauses before ALL tools** (coarse). | CopilotKit `useHumanInTheLoop`/render-and-wait renders an **Approve / Edit / Reject card** natively from a structured interrupt event. The exact pattern AG-UI ships for. |
| Granularity | Per-artifact, bespoke per feature | Before every tool call (over-pauses; kills cacheable/safe tools too) | **Per-command, conditional on severity** — pause only MED/HIGH shell calls |
| Resume semantics | Re-invoke whole stream; app re-derives state | `Command(resume=...)`; **node re-executes from top** → idempotency gotcha | `Command(resume=decision)`; same re-exec gotcha but the side-effect (subprocess) sits *after* the interrupt, so it's naturally idempotent |
| Modify-before-run | Not supported (approve/deny only, ad hoc) | Not natively | **Yes** — `Command(resume="edited cmd")` becomes the interrupt's return value |
| Prod readiness here | Already wired but UX-broken | Flag exists but OFF; coarse; needs SSE surfacing built anyway | Needs the interrupt + one AG-UI event mapping; **frontend HITL primitive already in the dep tree** |
| Fail-closed timeout | Manual, easy to get wrong | Halts indefinitely (no timeout) | Gate owns the timeout → deny; clean |
| Build effort | Low but **dead-ends on the UX problem** | Low flag flip, **high** to make per-command + add UI | Medium: dynamic interrupt + AG-UI approval event + `useHumanInTheLoop` card + resume handler |
| Verdict | ❌ Reject — proven not to work for stop/modify/approve | ⚠️ Reject as the primary — coarse, debug-only per LangChain, no native UX | ✅ **Recommend** — the modern, protocol-native HITL path; matches every external source |

**Why opt 1 fails (root cause):** it bolts approval onto a *token* stream as an out-of-band
side-channel. The user has no first-class "this run is awaiting your approval" event and no
render affordance, so in practice the stream just looks stuck — hence "can't stop/modify/approve."
**Why opt 2 isn't it either:** `interrupt_before` is a static debug breakpoint (LangChain
explicitly says not for HITL), and it's all-or-nothing across tools, so it would pause safe/cached
tools too and still needs all the UI work. **Why opt 3 is optimum:** a *dynamic, conditional*
`interrupt()` fired **only** when the severity gate says "ask", surfaced as a structured AG-UI
approval event that CopilotKit renders as an Approve/Edit/Reject card — exactly the
pattern AG-UI/CopilotKit (already in this stack) and the OpenAI/LangChain SDKs all standardize on.
It gives per-command granularity, native modify-before-run, and a clean fail-closed timeout.

## Scope decision (locked with user)

**Full Option 3 in one cut.** Build end-to-end so human approve/edit/reject works from day one:
hybrid severity classifier → three-band PEP → **dynamic `interrupt()`** on the "ask" band → AG-UI
approval event → CopilotKit `useHumanInTheLoop` Approve/Edit/Reject card → `Command(resume=...)`,
subprocess strictly after the interrupt (idempotent), fail-closed throughout, behind the
`shell_approval_enabled` shadow-first flag. This is net-new wiring (prod currently runs
`interrupt_before_execute_tool=False` and surfaces no interrupt over SSE) but the frontend HITL
primitive + ToolCard + wire-events layer already exist to build on.

### Sources

- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) · [OWASP Top 10 for Agentic Apps 2026](https://goteleport.com/blog/owasp-top-10-agentic-applications/)
- [LangChain — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) · [LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Anthropic — Claude Code Auto Mode (classifier-based approval)](https://www.anthropic.com/engineering/claude-code-auto-mode)
- [AG-UI Protocol overview](https://docs.ag-ui.com/introduction) · [CopilotKit AG-UI HITL](https://docs.showcase.copilotkit.ai/ag2/human-in-the-loop)
- [Design Patterns to Secure LLM Agents](https://labs.reversec.com/posts/2025/08/design-patterns-to-secure-llm-agents-in-action) · [arXiv: Securing LLM Agents against Prompt Injection](https://arxiv.org/html/2506.08837v1)

---

# PART B — Implementation Plan (Full Option 3)

> Hardened from Part A under the three discipline docs: `research/tdd_agentic_systems_prompt.md`
> (pyramid L1–L4, Protocols A–D, Pattern 6/11, failure-paths-first, anti-patterns),
> `docs/Architectures/FOUR_LAYER_ARCHITECTURE.md` + `GUARDRAILS_DIMENSION_SPACE.md` (placement,
> dependency rule, additive ring), `docs/skills/governance-trace-audit` (one carrier per fact,
> fail-closed, honest recording). **Shadow-first** rollout throughout.

## Context

`services/tools/shell.py` is a hard fail-closed 8-command allowlist that over-blocks routine
intent (per `ALLOWLIST_DIAGNOSIS.md`) while being all-or-nothing. We replace the binary
allow/reject with a **severity classifier (Execution rail, LLM06)** that tiers each command
LOW/MED/HIGH/CRIT and a **three-band PEP**: LOW→auto-run, MED/HIGH→pause for human approval via a
native AG-UI card, CRIT→hard-deny (un-approvable). The HITL transport is the protocol-native
dynamic-`interrupt()` path (Part A Opt 3), which the repo is already 80% wired for: the
`langgraph_runtime.py` adapter has a full checkpoint **resume path** (`_resume`, ~L148-165), and
`TaskUnderstood` is a proven `DomainEvent`→AG-UI **card precedent** with a `source` provenance
field and an existing pause/resume edit route.

## Architecture placement (four-layer, additive-only)

| Piece | Layer | Why (per FOUR_LAYER + GUARDRAILS_DIMENSION_SPACE §B) | File |
|---|---|---|---|
| `Severity` enum | Trust Foundation (reuse) | already a portable trust artifact | `services/governance/guardrail_validator.py:32` (reuse) |
| **Shell severity classifier** | **Horizontal / L2** | peer to `injection_classifier.py`; takes a string, returns a verdict; objective→code, subjective→LLM | **new** `services/governance/shell_severity.py` |
| Deterministic tier tables | Horizontal / L2 | objective, FP-free, runs every commit | in `shell_severity.py` |
| LLM judge (ambiguous band only) | Horizontal / L2, **additive/optional** | degrades to deterministic-only if absent (mirrors the ONNX classifier degrade rule, dimension-space §"additive and optional") | reuse `InputGuardrail._call_judge` shape |
| Three-band PEP decision | Orchestration / L4 | topology-only gate, mirrors `verify_authorize_log_node` | `orchestration/react_loop.py` (new `shell_approval` gate in the tool-exec path) |
| `interrupt()` on "ask" band | Orchestration / L4 | dynamic, conditional (LangChain-recommended over static breakpoint) | `orchestration/react_loop.py` tool-exec node |
| `ApprovalRequested` / resolve | **Adapter ring** (additive, NOT backend) | the ring "can be removed without changing a file in services/…/orchestration"; new `DomainEvent` + `to_ag_ui` mapping | `agent_ui_adapter/wire/domain_events.py`, `translators/domain_to_ag_ui.py` |
| Approval card | Frontend | CopilotKit `useHumanInTheLoop` render-and-wait | `frontend/components/tools/` (peer to `ToolCard.tsx`) |
| Config flags (shadow-first) | Services config | `AgentConfig` feature-flag discipline | `services/base_config.py` |

**Dependency-rule compliance:** the L2 classifier imports only stdlib/Pydantic + the `Severity`
trust type (no orchestration/components/langgraph import — keeps services framework-agnostic, the
invariant the F1–F7 work also held). The `interrupt()` call is the *only* new langgraph surface,
and it lives in orchestration where langgraph already lives. The AG-UI event is in the additive
adapter ring. **No `TraceEvent`/`EventType` schema change** — we reuse `GUARDRAIL_CHECKED`.

## The severity model (deterministic tier tables — the L1/objective half)

| Band | Severity | Examples | Policy |
|---|---|---|---|
| auto | LOW | read-only: `ls cat head tail grep find wc echo pwd python python3` (+ `python -c` arg exempt from metachar scan) | run, no prompt |
| ask | MEDIUM | create/modify: `mkdir cp mv touch`, `python` with file writes, `2>`/`>` redirects | pause → human card |
| ask-ceiling | HIGH | network/destructive-scoped: `rm` (non-root path), `curl wget nc`, `chmod chown` | pause → human card, default-deny on timeout |
| deny | CRITICAL | un-approvable: `rm -rf /`-class, `sudo`, fork bombs, root-path writes | hard-deny, never promptable |

Tables extend the existing `ALLOWED_COMMANDS`/`BLOCKED_PATTERNS`/`BLOCKED_ARGS` sets into
LOW/MED/HIGH/CRIT maps (objective, decidable from bytes). The **LLM judge runs only for tokens the
tables can't classify** (the ambiguous middle), returning a severity the tables fold in — exactly
the dimension-space "objective→code, subjective→LLM" split and the Claude-Code two-stage shape.

## TDD plan (failure-paths-first, per protocol)

### L2 — `services/governance/shell_severity.py` (Protocol B, contract-driven)
- **Pattern 11 Failure-Mode Matrix** parametrized over `(command → expected_band)`: a row per
  severity incl. every BLOCKED token (the rejection rows first). Assert the *band/severity*, not
  the model — deterministic, no LLM (Anti-Pattern 3/5). Real classifier, ≤3 mocks (Anti-Pattern 2).
- **Degrade test:** judge unavailable → classifier still returns a band for table-coverable
  commands; ambiguous command → conservative default (HIGH/ask, fail-closed), never silent LOW.
- **Anti-tautology (TAP-1):** assert behavior ("`rm -rf /` is CRIT/deny") via known vectors, not
  by re-deriving the table in the test.

### L4 — the three-band PEP + interrupt (Protocol D, simulation)
- **D1 gate matrix** (mirror `test_trust_gate_outcomes`): parametrize
  `(severity_band, approval_decision) → outcome` — auto→executed; deny→`error_class="gating"`,
  never executed; ask+approve→executed; ask+edit→executed-with-edited-cmd; ask+reject→not
  executed, `gating`; ask+timeout→**deny** (fail-closed). Assert **exactly one**
  `GUARDRAIL_CHECKED` carrier per decision (governance: one carrier per fact), and the subprocess
  ran 0 times on every non-approve branch (idempotency: side-effect strictly after interrupt).
- **Pattern 6 mock provider** for the interrupt/resume: a scripted runtime that yields the
  interrupt then resumes with a `Command(resume=...)` decision — no live LLM, no live subprocess.
- **Resume-idempotency test:** node re-executes from top on resume (LangChain gotcha) → assert the
  classifier may re-run but the subprocess executes exactly once and only post-approval.

### Adapter ring — `ApprovalRequested` event (Protocol B / translator unit)
- `to_ag_ui(ApprovalRequested)` emits the Custom approval event with `trace_id` (reuse the
  `TaskUnderstood` translator test shape); missing-`trace_id` refusal test (existing invariant).

### Frontend — approval card (component test)
- `useHumanInTheLoop` card renders Approve/Edit/Reject from the event; the edit path returns the
  modified command; assert the resolve payload shape. (Mirror existing `ToolCard` tests.)

### Architecture conformance (Pattern 7)
- `tests/architecture/` assertion: `shell_severity.py` imports only stdlib/Pydantic/`Severity`
  (no components/orchestration/langgraph) — the dimension-space invariant #7, like
  `injection_classifier.py`.

## Governance carrier design (one fact, one carrier — fail-closed)

Per the audit skill: every gate decision emits **exactly one** `EventType.GUARDRAIL_CHECKED` with
`details = {guardrail:"shell_severity", tool:"shell", command:<capped>, severity, band, decision,
approver?, would_enforce, policy_version}`. Shadow mode sets `outcome:"alert"`/`would_enforce`
without blocking (the carrier-gate Phase-1 precedent). A deny still emits one carrier (no
double-emission). The subprocess-execution outcome stays on the existing tool carrier. **Fail
closed**: classifier error, audit-write failure, or approval timeout → deny + carrier.

## Rollout (shadow-first)

`AgentConfig`: `shell_approval_enabled: bool = False`, `shell_approval_severity_threshold:
Literal["low","medium","high","critical"] = "high"`, `shell_approval_timeout_seconds: int = 120`,
`shell_approval_enforce: bool = False`. **Phase A (shadow):** classify + emit carriers + widen the
auto allowlist (LOW band), but do NOT interrupt — observe severities on real traffic. **Phase B
(enforce):** flip `shell_approval_enforce`; the "ask" band now fires the interrupt/card. Both
phases ship together but Phase B is flag-gated dark, matching the carrier-gate enforce-dark
pattern.

## Critical files

| Purpose | Path |
|---|---|
| New: severity classifier (L2) | `services/governance/shell_severity.py` |
| Reuse: Severity enum | `services/governance/guardrail_validator.py:32` |
| Reuse: judge cascade shape | `services/guardrails.py:383` (`InputGuardrail.decide` / `_call_judge`) |
| Shell tables to tier | `services/tools/shell.py:13-16` |
| New: three-band PEP + `interrupt()` | tool-exec path in `orchestration/react_loop.py` (model on `verify_authorize_log_node:2135`) |
| New: `ApprovalRequested` DomainEvent (+union) | `agent_ui_adapter/wire/domain_events.py` (14th member) |
| New: `to_ag_ui` mapping | `agent_ui_adapter/translators/domain_to_ag_ui.py` (mirror `TaskUnderstood`) |
| Reuse: resume path (already exists) | `agent_ui_adapter/adapters/runtime/langgraph_runtime.py:148-165` |
| Reuse: pause/resume route precedent | `middleware/app_prod.py:539` (`register_understanding_edit_route`) |
| New: approval card | `frontend/components/tools/` (peer to `ToolCard.tsx`) |
| New: config flags | `services/base_config.py` |
| Carrier | `EventType.GUARDRAIL_CHECKED` (no schema change) |

## Verification (end-to-end)

```bash
# Unit/sim (no live LLM, no live subprocess) — must be green:
.venv/bin/python -m pytest tests/services/governance/test_shell_severity.py \
  tests/orchestration/test_shell_approval_gate.py \
  tests/architecture -q

# Adapter + frontend:
.venv/bin/python -m pytest tests/.../test_domain_to_ag_ui.py -q
cd frontend && pnpm test -- shell-approval-card

# Live E2E (reuse Part-1 localhost live-LLM probe harness): add probes
#   P-SHELL-low  (echo → auto-run, no card),
#   P-SHELL-ask  (mkdir → approval card appears → approve → runs),
#   P-SHELL-edit (rm foo → card → edit to `ls foo` → runs edited),
#   P-SHELL-deny (rm -rf / → hard-deny, no card, one gating carrier),
#   P-SHELL-timeout (no response → fail-closed deny)
# then analyze GUARDRAIL_CHECKED carriers via the Part-1 analyzer + governance-trace-audit skill.
```

**Pass criteria:** the severity matrix is green incl. all rejection rows; the PEP matrix proves
the subprocess never runs on deny/reject/timeout and runs exactly once on approve/edit; exactly
one `GUARDRAIL_CHECKED` carrier per decision; the approval card renders+resolves end-to-end on
localhost live; `git diff` shows no `TraceEvent`/`EventType` edits and no new cross-layer imports
in `services/`. Then run the governance-trace-audit skill on a live approval trace as the
post-implementation review (Validation + Reasoning pillars must show the gate decision honestly).

## Risks / guardrails

- **Resume re-executes the node from top** (LangChain gotcha): keep the subprocess strictly after
  `interrupt()`; the classifier re-running is harmless (pure). Explicit idempotency test above.
- **Widening the allowlist increases blast radius** even in the auto band: the CRIT hard-deny
  ceiling is non-promptable and table-driven (FP-free), and Phase A is shadow — observe before
  enforcing. Keep `shell=False` subprocess (no shell metachar execution) unchanged.
- **Don't let the judge become a trigger-word shortcut** (dimension-space InjecGuard caveat): the
  LLM only runs on table-ambiguous tokens, and its output is a severity the tables bound — it can
  raise severity, never silently lower a HIGH/CRIT table verdict.
- **Scope:** this is the shell-approval workstream only; it reuses Part-1's harness for live E2E
  but does not depend on Part-1 shipping first.
