---
type: notes
title: 'Notes on the AgentsFramework Architecture'
description: 'Author: Rajnish Khatri'
tags: [architecture]
---

# Notes on the AgentsFramework Architecture

**Author:** Rajnish Khatri
**Repo:** github.com/rajnishkhatri/AgentsFramework
**Purpose:** A short note on architectural decisions and trade-offs, intended to complement our interview conversation. Platform-agnostic by design. The cloud-specific adapters live in separate deployment documents (AWS, Azure, GCP).

---

## Governing thought

The framework is a four-layer architecture with a pure trust kernel at the core, a hexagonal adapter ring at the outside, and an event-driven governance feedback loop in between. The intent is that orchestration topology, domain logic, infrastructure, and trust types each have exactly one valid home, and that dependency direction is enforced by tests rather than convention.

The driving situation was straightforward. A LangGraph ReAct agent has to combine identity and authorization, dynamic model routing, prompt rendering, defense-in-depth guardrails, tool dispatch, evaluation capture, and offline meta-optimization. Then it has to expose all of that through SSE to a browser front end.

The complication is that naively wiring those concerns produces a graph where everything imports everything else. Framework SDKs leak into domain logic. Prompt strings drift across modules. Governance code circularly depends on orchestration. Any change to the trust schema cascades unpredictably.

The question was where each new concern belongs, and how that placement can be mechanically verified in CI. The answer is the five decisions that follow.

---

## Decision 1: Tests enforce architecture, not conventions

**The decision.** Every architectural rule is enforced by a test that fails the build. Ten test files in `tests/architecture/` guard fourteen invariants.

**Alternatives considered.** Code review only. Linter rules. Documentation conventions in a style guide.

**Why not those.** Conventions decay. Code review depends on the reviewer that day. Linters cannot express layering rules like "services cannot import from components." Architecture tests run in CI on every pull request. They fail with a named violation, a forbidden import, and a file path. No exceptions.

**What gets enforced.** A few examples. The trust kernel cannot import logging, network, or framework code. Components cannot import LangGraph or LangChain. Services cannot import from components, which would create reverse coupling. The adapter ring cannot leak framework SDK code outside one specific subdirectory. The meta-layer cannot call into orchestration.

**The trade-off.** More test infrastructure to maintain. New contributors hit failures before they understand the rules. Reviewer fatigue is real if violations are common. The architecture tests themselves need their own discipline (they are not unit tests, they are structural assertions about the codebase).

**The consequence.** The architecture stays clean as the codebase grows. A regulator or auditor reading the test suite would see governance discipline encoded as executable artifacts, not aspirational text. This is the single decision that, in my experience, most cleanly separates a maintainable agent codebase from one that drifts in six months.

---

## Decision 2: The trust kernel has zero framework dependencies

**The decision.** The `trust/` package imports only Python standard library and Pydantic. No I/O. No logging. No network. No framework imports.

**Alternatives considered.** Allow logging for debugging. Allow optional framework hints for type completeness. Co-locate trust types with infrastructure for convenience.

**Why not those.** Trust types are signed and audited. They are the longest-lived contracts in the system. AgentFacts records persist across deployments. If trust types depended on LangGraph internals, an LangGraph upgrade could invalidate a signed AgentFacts cache. Logging inside a model validator means a logging library version pin becomes part of the trust contract.

**What lives there.** AgentFacts (the signed identity card), Policy, AuditEntry, VerificationReport, TrustTraceRecord, PolicyDecision. Enums for state machines. Hexagonal protocols for IdentityProvider, PolicyProvider, CredentialProvider. Deterministic HMAC over the signed-field set. That is it.

**The trade-off.** Less convenient. You cannot log from inside a validator. You import the type and the formatter separately. Refactors that would naturally pull a logging call into a model class get rejected by the architecture tests.

**The consequence.** The trust kernel can be lifted intact into a successor framework. If a future agent runtime supersedes LangGraph, the trust contracts do not need to change. Signed AgentFacts records from version one of the system remain valid in version five.

---

## Decision 3: Hexagonal adapter ring on top of layered architecture

**The decision.** A four-layer backend (trust → services → components → orchestration) is wrapped in a hexagonal adapter ring where the framework SDK touches the system in exactly one place.

**Alternatives considered.** Pure hexagonal architecture with no internal layering. Pure layered architecture with no adapter ring. Microservices decomposition.

**Why not those.** Hexagonal alone gives clean external boundaries but allows internal coupling. Layering alone gives internal discipline but leaks framework concerns into orchestration. Microservices add operational complexity disproportionate to the use case. The combination of layered internals with a hexagonal outer ring keeps both kinds of discipline.

**What this looks like in practice.** Orchestration uses LangGraph. Components and services do not. The adapter ring (`agent_ui_adapter/`) translates between LangGraph's event model and the system's domain events. The framework SDK appears in exactly one subdirectory (`adapters/runtime/`), and an architecture test enforces that.

**The trade-off.** More files. More indirection. A simple change can require touching three files (a service method, a component that orchestrates the service, an adapter that translates the orchestration's event). Cognitive load is real for new contributors.

**The consequence.** A framework swap does not cascade. If LangGraph were replaced by a successor framework, or by a proprietary orchestrator that a client mandated, the change radius would be bounded to the runtime adapter. Domain logic, governance, and trust types would not move. Most agent codebases I have reviewed cannot survive a framework swap without a rewrite.

---

## Decision 4: The meta-layer is horizontal to orchestration, never below it

**The decision.** The offline governance and optimization layer reads logs and writes config files. It never calls the graph.

**Alternatives considered.** Synchronous governance hooks called from inside orchestration nodes. Inline judge calls during execution. Direct optimizer calls that mutate orchestration state.

**Why not those.** A governance hook that runs synchronously is a runtime dependency. The graph cannot serve a request if the judge is down. Inline LLM judges add latency to every request. Direct optimizer mutations create circular reasoning between the system and its own evaluation.

**What this looks like.** Orchestration emits TrustTraceRecord events at every gate. The trace service persists them to a JSONL sink. The meta-layer consumes the sink asynchronously, runs offline analysis (judge, drift detection, threshold tuning), and writes results back. Results land in three places. Numeric thresholds in a routing config file. Prompt updates as new template versions. New AgentFacts entries for newly-certified agents. None of these write paths goes back through the graph.

**The trade-off.** Feedback latency. Improvements derived from offline analysis cannot land in the next request. They land in the next deployment. There is no real-time policy steering. Drift detection runs on yesterday's traces, not this minute's traffic.

**The consequence.** Governance never blocks production. The same property regulators look for in banking model risk management: validation is separate from production, with its own failure domain. The meta-layer can be offline for a day without the agent going down. The agent can be down without the meta-layer noticing for hours.

---

## Decision 5: Direct method calls today, event bus tomorrow

**The decision.** Governance feedback is implemented today as direct method calls. The architecture documents the path to an in-process event bus (Phase 2) and a distributed bus (Phase 3) but does not build either yet.

**Alternatives considered.** Build the event bus on day one. Skip the bus entirely and assume direct calls forever.

**Why not those.** There is currently one consumer of governance events: the meta-layer judge running over a JSONL sink. A premature event bus adds operational complexity (broker, schemas, dead-letter queues, ordering guarantees) without payoff. Skipping the bus forever fails the second-consumer test. The architecture is committed to swapping the transport when the second consumer arrives, not before.

**What makes this work.** The change radius of the future migration is bounded by a test. `test_mphase2_swap_radius.py` verifies that swapping `services/trace_service.py` from direct dispatch to event-bus subscription touches only that one service file. Emitters and consumers do not change. The test fails today if any other file gains awareness of the transport.

**The trade-off.** A future migration to an event bus is still a migration. There is no free lunch. The architectural promise is only that the migration cost is predictable, not zero. If the second consumer arrives next quarter, that is when the work happens.

**The consequence.** The framework is honest about its current maturity. Phase 1 is direct calls. Phase 2 is in-process bus. Phase 3 is distributed bus. Each phase has a named trigger and a bounded change radius. Most architectures I have reviewed over-promise event-driven posture they have not earned.

---

## What this framework is not

A few honest exclusions matter for context.

It is not a production system. It is a reference implementation. Production deployment requires the cloud-specific adapters detailed in separate documents: a Postgres-based checkpointer instead of SQLite, a blob store for AgentFacts instead of local files, a queue-based trace sink instead of JSONL on disk, a secret manager instead of `.env`. Those translations are documented but the reference runs on a laptop.

It is not a multi-agent system today. The trust kernel supports agent-to-agent patterns (source_agent_id and causation_id are first-class fields in TrustTraceRecord) but the current orchestration is single-agent. The path to multi-agent is the Phase 3 distributed bus.

It is not opinionated about the LLM provider. LiteLLM sits behind a single service wrapper. Switching from one provider to another touches one file. The framework deliberately does not lock in to a specific model family.

It is not feature-rich. The point is to prove the layering works under real constraints, not to ship the largest possible feature set.

---

## Open questions still being worked through

A few items the framework tracks as gaps rather than solved problems.

Three architectural invariants are currently enforced by convention rather than by automated test. The orchestration node thinness rule (nodes must delegate to components or services, not contain logic). The eval_capture coverage rule (every LLM call must route through the recorder). The hardcoded-prompt ban (every prompt must live in a `.j2` file, not as a string literal). Each one has a planned test in the gap analysis and a documented severity. They are named, scoped, and prioritized.

The pyramid-reasoning agent (a structured reasoning mini-stack that lives alongside the main ReAct loop) currently has weaker defense-in-depth than the main loop. It runs the input guardrail but not the output guardrail and not per-tool authorization. The risk is contained while the pyramid agent is CLI-only. The risk escalates if it gets exposed to untrusted input.

The meta-layer assumes a single deployment scope. Multi-tenancy at the meta-layer (one optimizer per client carrier, one judge per business unit) is not addressed in the current design. That is a Phase 3 concern.

---

## Closing note

This is a working framework, not a finished one. The intent of sharing it is to expose the decision-making, not to assert a complete answer. Most agent architectures I see in production were assembled rather than designed. The five decisions above were chosen explicitly. They are revisitable as the framework grows, and the tests will tell us when we have broken one.

Happy to walk through any of these in more depth on a follow-up call.
