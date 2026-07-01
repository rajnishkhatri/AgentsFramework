# Spec — Subject-Coach Agent (the governed ReAct coach + judges)

> **Scope discipline.** This is the **agent** spec — the *subjective/dynamic plane* of the
> Subject-Coach engine. It is the testable *what* of the **LLM-driven coach** and the
> **offline question generator**, spun as a governed ReAct agent from the existing
> pipeline. It does **not** re-spec the engine (the
> [engine spec](preact-english-coach-engine.spec.md) owns adaptivity, FSRS, the `reviewed`
> gate, persistence) nor any UI screen. Where the coach *produces* what the UI consumes
> (streamed replies, generated questions), this spec owns the agent contract; the engine
> spec owns delivery and the UI spec owns rendering.
>
> This spec *implements* decisions ratified in its ADRs — it does **not** re-decide them:
> - [ADR-0007](../adr/0007-subject-coach-agent-tool-capability-gating.md) — `AgentFacts.capabilities` load-bearingly gate the `ToolRegistry`; English-only input guardrail. **Proposed.**
> - [ADR-0008](../adr/0008-subject-coach-judges-grader-and-pedagogy.md) — the three-judge split (MC Grader / Grader Judge / Pedagogy GoalJudge) + homes. **Proposed.**
> - [ADR-0009](../adr/0009-subject-coach-reflexion-not-on-live-path.md) — inline T2 Reflexion stays OFF for the coach; reflection is offline (judge layer). **Proposed.**
>
> Two `⚠️ Ask first` triggers fire here and are carried by the ADRs above: the
> capability-gated `ToolRegistry` (a new governance mechanism) and the judge additions.
> The **coach-agent fork** uses the *prompt-param* path (no new graph node), so the
> new-graph-node trigger does **not** fire (ADR-0007 §Decision).
>
> Acceptance criteria use **EARS** so each is directly testable:
> - **Ubiquitous:** `THE SYSTEM SHALL <behavior>.` · **Event-driven:** `WHEN <trigger> THE SYSTEM SHALL <behavior>.`
> - **State-driven:** `WHILE <state> …` · **Unwanted:** `IF <condition> THEN …` · **Optional:** `WHERE <feature> …`

**Status:** Draft — 2026-06-30
**Owner:** Rajnish Khatri
**Related:**
- Brainstorm (the *why* survey): [`subject-coach-agent.brainstorm.md`](subject-coach-agent.brainstorm.md)
- ADRs (the *why* decided): [ADR-0007](../adr/0007-subject-coach-agent-tool-capability-gating.md), [ADR-0008](../adr/0008-subject-coach-judges-grader-and-pedagogy.md)
- Engine sibling: [`preact-english-coach-engine.spec.md`](preact-english-coach-engine.spec.md) · Design doc: [`SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md`](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md)
- Governance narratives: [`03_agentfacts_governance.md`](../../governanaceTriangle/03_agentfacts_governance.md), [`04_guardrails_validation_pii.md`](../../governanaceTriangle/04_guardrails_validation_pii.md)
- Template: [`_spec_template.md`](_spec_template.md)

---

## 1. Goal

Deliver a **governed English-coaching ReAct agent** — an identity-bound, tool-restricted,
domain-guardrailed instance of the existing `build_graph()` pipeline — plus the **three
judges** that grade learner answers (correctness) and the coach's own generated content
(faithfulness + pedagogy, including answer-leakage). For the learner: a Socratic coach
that scaffolds without handing over answers. For the platform: a least-privilege agent
whose declared contract is *enforced*, not merely documented.

## 2. Context

The engine ADRs (0005/0006) settled the objective plane and the frontend engine home. The
[agent brainstorm](subject-coach-agent.brainstorm.md) surveyed the subjective plane and
chose to **spin a ReAct agent from the pipeline** rather than build a bespoke service. The
pipeline already provides AgentFacts, the input-guardrail cascade, model routing, prompts,
and an injectable GoalJudge (all verified as live code). Two gaps motivate the ADRs: (a)
**no per-agent tool allow-list exists** — `AgentFacts.capabilities` don't gate the
`ToolRegistry` today; (b) the **general GoalJudge cannot grade English answers or
pedagogy** — its verdict schema lacks correctness/leakage axes. 2026 tutoring research
makes **answer-leakage** the #1 failure mode to penalize and converges on **rubric-anchored,
criterion-separated, calibrated** judges.

## 3. Functional requirements (EARS)

### 3.1 Identity & contract (AgentFacts)
- **FR-1.** THE SYSTEM SHALL register the coach as an `AgentFacts` record `subject-coach-english`
  declaring `capabilities = [think, file_io]` (each with input/output schemas) and
  `policies = [domain=english-teaching, no-code-execution, answer-leakage-prohibited, rate-limit]`,
  HMAC-signed at registration.
- **FR-2.** WHEN the coach graph starts THE SYSTEM SHALL verify the AgentFacts signature at
  `guard_input` and, IF verification fails, THEN reject the run before routing (no LLM call).

### 3.2 Tool restriction (load-bearing — ADR-0007)
- **FR-3.** THE SYSTEM SHALL bind to the coach LLM **only** the tools named in its
  `AgentFacts.capabilities` — i.e. `think` and `file_io` — by filtering the `ToolRegistry`
  at the graph-build boundary.
- **FR-4.** IF a tool exists in the process-wide `ToolRegistry` but is **not** in the
  agent's capabilities (e.g. `web_search`, `shell`, `python`) THEN THE SYSTEM SHALL NOT
  expose its schema to the coach LLM and SHALL NOT execute it for this agent.
- **FR-5.** IF an `AgentFacts.capability` names a tool absent from the `ToolRegistry` THEN
  THE SYSTEM SHALL fail fast at graph-build with a clear error (declared-but-unavailable is
  a configuration bug, not a silent no-op).
- **FR-6.** THE SYSTEM SHALL be covered by an architecture test asserting *declared =
  bound*: the set of tools bound to the coach equals its declared capabilities.

### 3.3 Domain input guardrail (English-only — ADR-0007)
- **FR-7.** WHEN input reaches `guard_input` THE SYSTEM SHALL evaluate it against an
  injectable English-learning `accept_condition` via the existing 3-stage cascade
  (deterministic precheck → optional ONNX → LLM judge).
- **FR-8.** IF the input is off-topic for English learning THEN THE SYSTEM SHALL refuse at
  `guard_input` (route to the rejected→END edge) without calling the coach LLM.
- **FR-9.** THE SYSTEM SHALL admit the **full breadth** of English learning — grammar,
  usage, mechanics, rhetoric/style, reading comprehension, vocabulary, and test strategy —
  not only narrow "ACT English" phrasing (FP-rate guard; see §7).

### 3.4 Persona & generation
- **FR-10.** THE SYSTEM SHALL render the coach system prompt from
  `prompts/subject_coach_system_prompt.j2`, parameterized by subject, injected via
  `AgentConfig.additional_instructions`, instructing scaffolding-first + Socratic behavior,
  **teach-back** (ask the student to explain their reasoning — Feynman), **analogy-first**
  over re-explanation, and **naming why** a skill is being revisited (Oakley/FSRS).
- **FR-11.** WHILE coaching THE SYSTEM SHALL prefer hints, probing questions, and faded
  guidance over revealing the answer, and SHALL **preserve productive struggle** (not rescue
  too early — Holt) (the persona encodes the anti-leakage stance the Pedagogy judge measures).
- **FR-12.** WHERE the offline generator runs THE SYSTEM SHALL emit typed
  `question`/`tutorial` rows and SHALL set `reviewed = false` until a verifier gate passes
  (no learner sees an ungated item — mirrors the engine spec's `reviewed` invariant).

### 3.5 Judges (ADR-0008)
- **FR-13.** WHEN a learner submits a multiple-choice answer THE SYSTEM SHALL grade
  correctness **deterministically** (letter exact-match) on the **frontend** (client-side,
  offline-capable), with **no LLM call** on the MC correctness path.
- **FR-14.** WHEN the coach produces dynamically generated content (a hint, explanation, or
  mini-question) THE SYSTEM SHALL grade it with the **Grader Judge** (backend LLM rubric)
  on the dimensions **faithfulness, correctness, justification, actionability** — reference-free.
- **FR-15.** WHEN a coaching turn completes THE SYSTEM SHALL score it with the **Pedagogy
  GoalJudge** on **mistake-identification, mistake-location, actionability, coherence**, a
  first-class **answer-leakage** axis, and the learning-science axes **productive-struggle
  preservation** (Holt — did it resist rescuing too early?) and **illusion-of-competence
  detection** (Oakley — did it test recall rather than accept false confidence?).
- **FR-16.** IF the Pedagogy judge detects answer-leakage THEN THE SYSTEM SHALL flag the
  turn (the leakage axis is recorded distinctly, never averaged into a single quality score).
- **FR-17.** THE SYSTEM SHALL reuse the existing general `GoalJudge` **unchanged** for
  session-goal completion (`goal_met`), overlaying — never replacing — the deterministic
  process floor.
- **FR-18.** WHERE a judge runs THE SYSTEM SHALL pass every evidence/content line through the
  `GuardRailValidator` redactor before it reaches the judge prompt (PII/secret hygiene).

## 4. Data model / contracts

| Contract | Shape (sketch) | Notes |
|---|---|---|
| `AgentFacts` (reuse) | `agent_id, capabilities[], policies[], signature` | `trust/models.py`; **no type change** → no re-signing of the kernel. New *instance*, not new field. |
| Coach `ToolRegistry` (filtered) | `{think, file_io}` | derived from capabilities at build time (ADR-0007). |
| `GraderVerdict` (new) | `{correct: bool}` (MC) ⊕ `{faithfulness, correctness, justification, actionability}` (generated content) | frontend MC = bool; backend Grader Judge = per-criterion. Composes into ADR-0006 `Grader` port `Verdict`. |
| `PedagogyVerdict` (new) | `{mistake_identification, mistake_location, actionability, coherence, answer_leakage: flag}` | dimensions from the AI-tutor taxonomy; leakage is distinct. |
| `GoalVerdict` (reuse) | `{goal_met, criteria_met, unmet_conditions}` | unchanged (`components/schemas.py`). |

The new verdict types live in `components/` (framework-agnostic) alongside `GoalJudge`.
**No `trust/models.py` change** — so no kernel re-sign trigger.

## 5. Invariants & security boundaries

- **Invariant #2 (trust purity):** untouched — no new `trust/` types; the contract reuses
  existing `AgentFacts`. **No re-signing.**
- **Invariant #3/#4 (framework-agnostic components/services):** the new judges live in
  `components/`, import only `services/` + `trust/`, **no langgraph/langchain** — same as
  `GoalJudge`.
- **Invariant #6 (thin nodes):** the capability-gating is a **graph-build-boundary** filter
  + composition-root wiring, not domain logic in a node. The coach uses the *existing*
  nodes via prompt-param (no new node → invariant #1 upward-import risk not introduced).
- **Security boundary — least privilege:** the whole point of ADR-0007 is that the agent
  *cannot* call `shell`/`python`/`web_search` — enforced, not documented. The English-only
  guardrail is an input-trust boundary.
- **Live-LLM-in-CI:** all three LLM judges are flag-gated and mockable (reusing the
  `GoalJudgeRuntimeConfigReader` pattern); the deterministic MC Grader and the keyword
  fallback are the CI path. **No live LLM on the CI hot path.**

## 6. Edge cases

- **Empty / whitespace learner input** → guardrail precheck rejects; no LLM call.
- **On-topic-but-adversarial** (asks the coach to "just give the answer") → admitted by the
  guardrail (on-topic) but the persona refuses to leak; the Pedagogy judge confirms no leak.
- **Capability names a non-existent tool** → fail fast at build (FR-5), not a silent empty
  tool set.
- **Generated content the Grader Judge can't score** (undecidable) → return `None`, never a
  fabricated `0.0` (AP-6); fall back to the deterministic/heuristic floor.
- **Off-topic but benign** (a math question) → refused politely with a redirect, not an error.
- **Mixed-language input** → treated as on-topic if English-learning intent is present;
  otherwise refused (FP-rate guard in §7 bounds over-refusal).

## 7. Non-functional requirements

- **MC grading:** deterministic, **L1 exact**, client-side, sub-millisecond, offline. No
  network, no LLM.
- **Backend judges:** **L2 sampled** (5–10%) live + **L3** rubric evals nightly; calibrated
  against human raters with **κ** reusing the GoalJudge calibration-cert harness. Target:
  the Pedagogy judge's answer-leakage detection meets the same TPR/TNR floor discipline as
  ADR-0003's GoalJudge gate.
- **Guardrail FP rate:** the English-only condition SHALL admit a held-out set of legitimate
  English-learning prompts at ≥ a stated threshold (over-refusal is the named failure mode
  in the research; the threshold is the acceptance criterion).
- **Reversibility:** every governance addition is **flag-gated** (registry, guardrail
  condition, each judge) so the coach can run shadow-first (flags OFF) like prior workstreams.

## 8. Test plan (maps FRs → tests)

| FR | Test (level) |
|---|---|
| FR-1, FR-2 | AgentFacts register+verify; tampered-signature rejection at guard_input (L2 mock) |
| FR-3, FR-4, FR-6 | **architecture test**: tools bound == declared capabilities; `shell`/`web_search` not bound (L1) |
| FR-5 | build fails fast on capability-without-tool (L1) |
| FR-7–FR-9 | guardrail accepts breadth of English prompts; refuses off-topic; **FP-rate** over held-out set (L2/L3) |
| FR-10, FR-11 | persona renders; red/green: a "just tell me the answer" prompt yields no leak (L2 mock + L3 rubric) |
| FR-12 | generator emits `reviewed=false`; verifier gate flips to true; ungated item never served (L2) |
| FR-13 | deterministic letter-match grader, frontend unit (L1) |
| FR-14–FR-16 | Grader Judge + Pedagogy Judge rubric evals; answer-leakage flag fires on a leaking sample (L3) |
| FR-17 | general GoalJudge unchanged regression (L2/L3) |
| FR-18 | redactor scrubs PII before judge prompt (L2) |

**Red/green discipline:** the answer-leakage and off-topic-refusal tests are written
**failure-first** (TAP-4) — watch them fail before the persona/guardrail lands.

## 9. Out of scope (deferred — OCP)

- A second subject pack (Math) — built when Math is real; the subject-param seam is here.
- The LLM-rubric grader for *learner free-response essays* — the Grader Judge grades the
  *coach's generated content* now; learner-essay grading arrives with free-response items.
- A dedicated topic-classifier ONNX head (guardrail C2) — only if the LLM-judge stage's
  FP/FN rate proves insufficient.
- A new graph node / sub-graph for the coach — the prompt-param path (B1) avoids it.
- **Inline T2 Reflexion for the live coach** — `reflexion_enabled` stays **OFF**; reflection
  lives in the offline judge layer (the Pedagogy judge *is* turn-reflection). T2 is a
  per-task retry that converges toward the answer (counter-pedagogical) and is latency-heavy
  on a chat UX. Decision + the `reflections` cross-turn-leak prerequisite →
  [ADR-0009](../adr/0009-subject-coach-reflexion-not-on-live-path.md).
