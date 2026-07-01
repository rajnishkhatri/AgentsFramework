---
type: decision-record
title: 'ADR-0007: Subject-Coach agent — capability-gated tools + English-only input guardrail'
status: accepted
created: 2026-06-30
updated: 2026-06-30
owner: Rajnish Khatri
related: subject-coach-agent.spec.md, subject-coach-agent.brainstorm.md, 0008-subject-coach-judges-grader-and-pedagogy.md, 03_agentfacts_governance.md
tags: [decision-record]
---

# ADR-0007: Subject-Coach agent — capability-gated tools + English-only input guardrail

**Status:** Accepted — 2026-06-30 (was Proposed — 2026-06-30). **Acceptance condition MET — 2026-06-30**: the enforcement is implemented and green ([PR #110](https://github.com/rajnishkhatri/AgentsFramework/pull/110), merge `e160148`).
**Related:** [agent spec](../plan/subject-coach-agent.spec.md) · [agent brainstorm](../plan/subject-coach-agent.brainstorm.md) · [ADR-0008 judges](0008-subject-coach-judges-grader-and-pedagogy.md) · [AgentFacts governance narrative](../../governanaceTriangle/03_agentfacts_governance.md)
**Audience:** anyone wiring the coach into `build_graph`, or reconsidering how per-agent resource limits are enforced repo-wide.

> **Acceptance condition (2026-06-30) — ✅ MET (2026-06-30).** The *decision* was ratified;
> the enforcement it commits us to is now **implemented and green** — merged in
> [PR #110](https://github.com/rajnishkhatri/AgentsFramework/pull/110) (`e160148`):
> - the capability-gating filter at the graph-build boundary — `components/capability_gating.py`
>   (`derive_bound_tools` / `filter_registry_schemas`), wired in `orchestration/react_loop.py::build_graph`;
> - the `tests/architecture/test_capability_gating.py` test asserting **declared = bound**
>   (`shell`/`web_search` excluded) — the hard gate;
> - the fail-fast on a missing-tool capability (`CapabilityToolMissingError`, FR-5) at build;
> - the injectable `InputGuardrail.accept_condition` (`AgentConfig.input_guardrail_accept_condition`, FR-7).
>
> The gate mechanism is landed; the coach **still stays shadow-first** — the flags
> (`capability_gating_enabled`, `input_guardrail_accept_condition`) default OFF/empty, so today's
> behavior is byte-identical. This unblocks ADR-0007-dependent work (Phase 2 of the frontend UI plan);
> the *coach persona*, its `AgentFacts` instance, and the ADR-0008 judges remain to be wired before the
> coach flag flips live.

---

## Context

The Subject-Coach agent is spun from the existing `orchestration/react_loop.py::build_graph()`
pipeline. The governanceTriangle intent (the AgentFacts pillar) is that an agent's
**declared contract** — its capabilities (what resources it may use) and policies — is
*enforced*. For the English coach the intended resource limit is **`think` + `file_io`
only**: no `web_search`, no `shell`, no `python` (a Socratic coach reasons over provided
content; code-execution is pure attack surface with no pedagogical use).

But a read of the live code surfaces a gap: **there is no per-agent tool allow-list today.**
`AgentFacts.capabilities` is verified at `guard_input` and propagated into graph state, but
it only gates *sub-agent delegation* (`services/tools/task_tool.py`). Nothing filters the
process-wide `ToolRegistry` (`services/tools/registry.py`) by agent identity. The only
existing restriction is the middleware `ToolAclProvider`, which gates by **WorkOS user
role**, not by **agent contract**. So today "the contract declares `think`+`file_io`" and
"the runtime can only call `think`+`file_io`" are two *different* facts — the contract is
documentary, not load-bearing.

Separately, the coach must accept **English-teaching input only**. The existing
`services/guardrails.py::InputGuardrail` is a 3-stage cascade (deterministic precheck →
optional ONNX classifier → LLM judge) but its `accept_condition` is **hardcoded** inside
`build_graph` to the prompt-injection check ("The input is a legitimate user query").

Both changes are `⚠️ Ask first` triggers (a new governance mechanism + a `build_graph` API
change), so they are recorded here rather than decided in a PR.

---

## Decision

1. **Make `AgentFacts.capabilities` load-bearingly gate the `ToolRegistry`.** At the
   graph-build boundary, derive the agent's bound tool set by **filtering the process-wide
   `ToolRegistry` to exactly the tools named in its capabilities**. Only those schemas are
   bound to the coach LLM; only those executors are reachable. An **architecture test**
   asserts *declared = bound*. A capability naming a tool absent from the registry
   **fails fast at build** (declared-but-unavailable is a config bug, not a silent no-op).

2. **Make the `InputGuardrail.accept_condition` injectable** via a `build_graph` parameter
   and set the coach's to an **English-learning** condition (broad: grammar, usage,
   mechanics, rhetoric, reading, vocabulary, test strategy — not narrow "ACT English").
   Off-topic input is refused at `guard_input` before any coach LLM call.

3. **Fork the coach by prompt-param, not a new graph node.** The coach is a *configured
   instance* of the existing graph (persona via `AgentConfig.additional_instructions`,
   restricted tools via #1, domain via #2). This deliberately **avoids** the new-graph-node
   `⚠️ Ask first` trigger.

All three are **flag-gated** so the coach runs shadow-first (OFF by default).

---

## Options considered & rejected

### Tool restriction
| Option | What | Why it lost |
|---|---|---|
| **A1. Construction-time only** | Pass a 3-tool `ToolRegistry` to `build_graph`; leave capabilities documentary | Cheapest, but the AgentFacts contract stays **non-load-bearing** — "declared ≠ enforced." The governanceTriangle identity pillar becomes a comment. Rejected: it doesn't close the gap, it hides it. |
| **A2. Capabilities gate the registry** *(chosen)* | Capabilities filter the registry at build; arch-test asserts declared=bound | More work + an arch test, but the contract becomes **real enforcement**. The mechanism generalizes to every future agent, not just the coach. |
| **A3. Middleware ACL by agent** | Extend `ToolAclProvider` to key on agent id, not user role | Conflates two boundaries (per-user authz vs per-agent contract); the ACL is a middleware concern, the contract is a trust/governance concern. Wrong layer. |

### Input domain restriction
| Option | What | Why it lost |
|---|---|---|
| **C1. Re-target `accept_condition`** *(chosen)* | Make the condition injectable; reuse the 3-stage cascade | Minimal; reuses a proven cascade; one parameter. |
| **C2. New topic-classifier stage** | Add an ONNX topic head / second guardrail instance | Premature — only justified if C1's LLM-judge FP/FN proves insufficient. Deferred (OCP). |

### Coach fork shape
| Option | What | Why it lost |
|---|---|---|
| **B1. Prompt-param on existing graph** *(chosen)* | Persona + restricted tools + domain on the existing topology | No new node → no new-graph-node trigger; reuses the whole stack. |
| **B2. Distinct coach node / sub-graph** | A dedicated node in `react_loop.py` | New-graph-node is its own `⚠️ Ask first`; unnecessary for v1. |

---

## Rationale

The governanceTriangle's whole claim is that an agent's identity *governs* it. A contract
the runtime ignores is theatre. A2 is the only option that makes "this agent may use
`think`+`file_io` and nothing else" a property the code *guarantees* — which is exactly the
least-privilege posture a coaching agent with no compute needs should have. The arch test is
the same "template-as-enforcement" tactic the repo already uses: the behavior that would
otherwise regress (an agent quietly gaining `shell`) becomes a mechanical gate.

C1 reuses a cascade that already exists and is already on the `guard_input` path; the only
change is making one prose condition injectable. B1 keeps the change inside the existing
topology, so no node is added and invariant #6 (thin nodes) is untouched.

Fail-fast on a missing-tool capability (FR-5) follows the repo's "undecidable → surface it,
don't fabricate" discipline: a contract that names a tool the registry can't provide is a
deployment error that should stop the build, not degrade to an empty tool set the operator
never notices.

---

## Consequences

**Commits us to** (✅ = delivered in [PR #110](https://github.com/rajnishkhatri/AgentsFramework/pull/110)):
- ✅ A new capability-gating filter at the graph-build boundary + an architecture test in
  `tests/architecture/` asserting *declared = bound* (the hard enforcement) —
  `components/capability_gating.py` + `tests/architecture/test_capability_gating.py`.
- ✅ A `build_graph` signature change (injectable `accept_condition`; capability-derived tool
  set — `bound_capabilities`). This is the recorded `⚠️ Ask first` API change.
- ⏳ An `AgentFacts` *instance* for `subject-coach-english` in the registry (no `trust/models.py`
  type change → **no kernel re-sign**). *Deferred with the coach wiring — the gate mechanism
  shipped first; the coach instance lands when the persona/judges are wired.*

**Accepted risks / mitigations:**
- *Over-refusal* by the English-only guardrail (the named research failure mode) →
  mitigated by the breadth requirement (FR-9) + an FP-rate acceptance criterion over a
  held-out prompt set (spec §7).
- *The gate becomes a choke-point for all agents* once generalized → mitigated by keeping it
  flag-gated and defaulting non-coach agents to their current (unfiltered) behavior until
  they declare capabilities.
- *Capability/registry drift* (a renamed tool silently dropped) → the fail-fast (FR-5) +
  arch test (FR-6) catch it at build/CI, not in production.

**Follow-on:** generalize the gate to other agents once the coach proves it; measure the
guardrail FP rate before flipping the flag on.

---

## Supersedes / related

Makes canonical the agent [spec](../plan/subject-coach-agent.spec.md) §3.2–3.3 and the
[brainstorm](../plan/subject-coach-agent.brainstorm.md) §6 Decisions A/B/C. Pairs with
[ADR-0008](0008-subject-coach-judges-grader-and-pedagogy.md) (the judges that grade what
this agent produces). Builds on the engine ADRs
[0005](0005-subject-coach-engine-home-and-substrate.md)/[0006](0006-subject-coach-component-protocols.md)
(the frontend engine the coach feeds). Supersedes nothing.
