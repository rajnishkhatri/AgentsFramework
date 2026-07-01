# Brainstorm — Subject-Coach Agent (the subjective plane: a governed ReAct coach)

> **SDD Stage-1 artifact** (`brainstorm`). Idea-expansion for the *subjective/dynamic
> plane* of the Subject-Coach engine: the **live coach** and the **offline question
> generator**, realized as a ReAct agent spun from this repo's existing pipeline and
> governed end-to-end by the governanceTriangle. It surveys current best practice and
> proposes the seams + candidate options. It does **not** decide (the ADRs do) and
> contains **no code**.
>
> **Status:** Draft — 2026-06-30 · **Owner:** Rajnish Khatri
> **Related:**
> - Engine brainstorm (objective plane + OCP stance): [`subject-coach-engine.brainstorm.md`](subject-coach-engine.brainstorm.md)
> - Engine data/protocols (the `Grader`/`CoachAgentClient` ports): [`SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md`](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md)
> - Decided here-after: [ADR-0007](../adr/0007-subject-coach-agent-tool-capability-gating.md) (tool gating), [ADR-0008](../adr/0008-subject-coach-judges-grader-and-pedagogy.md) (judges)
> - Companion spec (the *what*): [`subject-coach-agent.spec.md`](subject-coach-agent.spec.md)

---

## 1. Intent (restated)

The English coach has **two planes** (from the engine brainstorm): a *deterministic/
objective* plane (UI text, taxonomy, flow — authored data) and a *subjective/dynamic*
plane (questions, coach replies, rationales — LLM-generated). The engine ADRs (0005/0006)
already settled the **objective plane** and the **frontend engine home**. **This brainstorm
owns the subjective plane**: how the LLM-driven coach and generator are built.

The decision is to **spin a ReAct agent from the existing pipeline** (`orchestration/
react_loop.py::build_graph()`) rather than write a bespoke coach service — reusing the
whole governance + telemetry + model-routing + judge stack. Per the governanceTriangle,
this agent gets:

- **An identity + contract** (AgentFacts: capabilities, I/O schemas, policies, signature).
- **A restricted resource set** — tools limited to `think` + `file_io`. **No web_search,
  no shell, no python.** (Least privilege; rationale in §4.)
- **A domain input-guardrail** — accepts English-teaching input only; refuses off-topic.
- **Its own persona prompt**, model tier, and **judges**: a Grader (answer correctness),
  a Grader Judge (grades the coach's *dynamically generated* content), and a Pedagogy
  GoalJudge (did the turn scaffold *without revealing the answer*).

The OCP discipline from the engine brainstorm carries over unchanged: **English-concrete
now, subject seams only.** The agent is `subject-coach`, parameterized by subject; English
is the one binding we build.

---

## 2. What the pipeline already gives us (the reuse inventory)

A read of the live code (not the governanceTriangle tutorials, which are the *design
narrative*) confirms the governance primitives are **real and wired**, not doc-only:

| Capability | Where it lives (verified) | Reuse for the coach |
|---|---|---|
| ReAct graph | `orchestration/react_loop.py::build_graph()` | spin the coach as a configured graph instance |
| AgentFacts registry | `services/governance/agent_facts_registry.py` (HMAC-signed, JSONL audit) | register `subject-coach-english` identity + contract |
| AgentFacts types | `trust/models.py` (`AgentFacts`, `Capability`, `Policy`) | the contract surface (pure, signed) |
| Input guardrail | `services/guardrails.py::InputGuardrail` (3-stage cascade: precheck → ONNX → LLM judge) | re-target `accept_condition` to English-only |
| Output guardrail | `services/governance/guardrail_validator.py` (`pii_rules`, `api_key_rules`) | reuse as the judge-input redactor |
| Tools | `services/tools/` — `think_tool.py`, `file_io.py`, `web_search.py`, `shell.py` | register **only** `think` + `file_io` |
| Tool registry | `services/tools/registry.py` (`ToolRegistry` dict injected into `build_graph`) | the gating surface (see ADR-0007) |
| Model routing | `services/llm_config.py` (tiers: fast/capable/reasoning) | coach = capable; judges = fast/capable |
| Prompts | `services/prompt_service.py` + `prompts/*.j2` | new `subject_coach_*.j2` templates |
| GoalJudge | `components/goal_judge.py` (injectable, H1/H2, correctness cascade) | the *pattern* to fork — not retargetable as-is (see §5) |
| Answer verifier | `components/answer_verifiers.py::verify_answer` | the deterministic stage of the cascade |

**The one real gap** (drives ADR-0007): **there is no per-agent tool allow-list today.**
`AgentFacts.capabilities` is propagated into graph state but only gates *sub-agent
delegation* (`services/tools/task_tool.py`); nothing filters the `ToolRegistry` by agent
identity. So "the contract declares `think`+`file_io`" and "the runtime can only call
`think`+`file_io`" are, today, two different facts. Making the contract *load-bearing* is
the meaty decision.

---

## 3. External research — what current best practice says (2026)

Four research veins feed this design. Each finding is tagged with how it lands here.

### 3.1 Tutoring pedagogy — scaffolding + Socratic, and the answer-leakage trap
- LLM tutors converge on **instructional scaffolding**, **Socratic questioning**, and the
  **zone of proximal development**: provide heavy guidance early, fade to hints, never
  hand over the answer. ([Adaptive Scaffolding theory](https://arxiv.org/pdf/2508.01503),
  [Conversational design — Socratic/narrative](https://arxiv.org/pdf/2509.12107))
  → **Lands as:** the coach **persona prompt** is scaffolding-first + Socratic; the
  pedagogy judge scores *fading* and *guidance-without-revealing*.
- The **#1 measured failure mode is "answer leakage"**: benchmarks (MathTutorBench,
  EduBench) explicitly *penalize* revealing the solution and *reward* targeted help.
  LLMs are RLHF-trained to "be helpful by answering directly" — which **fights**
  pedagogy. ([MathTutorBench](https://arxiv.org/html/2502.18940v1),
  [Rethinking Scaffolding](https://arxiv.org/html/2606.15766v1),
  [Answer-leakage robustness](https://arxiv.org/html/2604.18660v1))
  → **Lands as:** answer-leakage is a **first-class, penalized axis** in the Pedagogy
  GoalJudge — not folded into a generic "quality" score. It is also a **policy** in the
  AgentFacts contract (`answer-leakage-prohibited`).
- Overreliance is a real harm; "accurate diagnosis does not reliably produce
  pedagogically actionable feedback." ([Confirming Correct, Missing the Rest](https://arxiv.org/html/2605.16207))
  → **Lands as:** the judge separates *diagnosis* (did it find the mistake) from
  *actionability* (did the feedback help) — distinct rubric dimensions.

### 3.2 Input guardrails — off-topic / domain restriction
- 2026 guardrail practice: **input guardrails do topic classification** (reject off-topic),
  prompt-injection detection, PII, rate-limiting — as **separable filters** updated
  independently of the model, often a rule-based + ML-classifier + LLM-judge cascade.
  ([Off-topic prompt detection methodology](https://arxiv.org/html/2411.12946v1),
  [LLM guardrails best practices](https://www.datadoghq.com/blog/llm-guardrails-best-practices/))
  → **Lands as:** the repo's existing `InputGuardrail` cascade (precheck → ONNX → LLM
  judge) is *exactly this shape*. We re-target the LLM-judge stage's `accept_condition`
  to "is this a legitimate English-learning request." Off-topic → refuse at `guard_input`.
- The standing caution: **over-strict guardrails frustrate legitimate users** ("a medical
  chatbot that refuses to discuss symptoms is worthless"). False-positive rate matters.
  → **Lands as:** the English-only condition must admit the full breadth of English
  learning (grammar, usage, rhetoric, reading, vocabulary, test strategy) — not just
  "ACT English" narrowly. A spec acceptance criterion guards the FP rate.

### 3.3 Judge architecture — separate the concerns, anchor to rubrics
- The 2026 consensus separates **three judging concerns**: answer **correctness**,
  **pedagogical quality**, and (here) **goal completion** — and warns that *merely*
  splitting judges doesn't help unless each is **rubric-anchored, criterion-separated,
  and calibrated**; a bad judge propagates errors. ([Rubric-based evals methodology](https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80),
  [Confirming Correct, Missing the Rest](https://arxiv.org/html/2605.16207))
  → **Lands as:** three judges (Grader, Grader Judge for dynamic content, Pedagogy
  GoalJudge), each with an explicit `.j2` rubric, calibrated against humans with κ —
  reusing the existing GoalJudge calibration-cert discipline. The general GoalJudge is
  **kept** for session-goal completion.
- A published **AI-tutor evaluation taxonomy** gives ready rubric dimensions: **mistake
  identification, mistake location, revealing-of-answer (penalized), actionability,
  coherence, humanness/tone**. ([Unifying AI Tutor Evaluation](https://arxiv.org/pdf/2412.09416),
  MRBench / Intent Matters)
  → **Lands as:** the Pedagogy judge rubric dimensions, near-verbatim.

### 3.4 Grading correctness + dynamic generated content
- **Grammar/mechanics MC grading is rule-bound and highly reliable** for rubric-based LLM
  grading (reported ICC ≈ 0.92–0.97); deterministic letter-match is even more reliable.
  ([EFL rubric grading reliability](https://bera-journals.onlinelibrary.wiley.com/doi/10.1111/bjet.13494),
  [Criterion-based grading consistency](https://www.nature.com/articles/s41539-024-00291-1))
  → **Lands as:** the MC **Grader's correctness stage is deterministic letter-match** —
  client-side, instant, offline (per ADR-0005's local-first split). Zero LLM, zero leak.
- Grading **dynamically generated tutor content** (hints/explanations tailored to the help
  asked) is **reference-free** rubric grading on **faithfulness/hallucination** +
  **pedagogical correctness** (consistency, clarity, justification, subgoaling). LLM
  explanations score high on clarity but **weaker on justification/subgoaling** — so those
  must be explicit rubric items. Hallucination is mitigated by composing the LLM judge
  with deterministic checks + calibrated prompts. ([Reference-free faithfulness scale](https://arxiv.org/pdf/2410.12222),
  [LLM-Rubric calibrated multidim eval](https://arxiv.org/html/2501.00274v1),
  [Feedback quality dimensions](https://arxiv.org/html/2504.04717v6))
  → **Lands as:** the **Grader Judge** (backend, LLM) grades the coach's *generated*
  output reference-free on **faithfulness + correctness + justification + actionability**.
  This is the consumer that makes the LLM-rubric stage non-speculative *now* (the coach
  generates dynamic content every turn).

### 3.5 Learning-science foundations — Feynman, Oakley, Holt
Three pedagogy sources were studied to ground the persona + judge rubrics in *why* a coach
behaves the way it does (not just *what* the benchmarks score). They converge remarkably.

- **Feynman technique** — learn by *teaching it simply*; explaining in plain words exposes
  exactly where understanding breaks; prefer **analogy to the familiar**; iterate to
  simplify. With an AI tutor the technique inverts: the AI plays the *curious student*
  asking probing questions, surfacing the learner's gaps. A 2024 K-12 study found
  significant learning gains vs. conventional study. ([FS.blog — Feynman technique](https://fs.blog/feynman-learning-technique/),
  [Learn Like Feynman (AI Feynman-bot)](https://arxiv.org/pdf/2506.09055))
  → **Lands as:** a persona move — the coach asks the student to **explain their reasoning
  ("teach it back")** rather than restating the rule, and prefers **analogy over
  re-explanation**. The *gap-surfacing* is the pedagogical engine.
- **Oakley — *Learning How to Learn* / *A Mind for Numbers*** — focused vs. **diffuse**
  modes; **chunking** as the unit of expertise; **active recall > rereading**; the
  **illusion of competence** (re-reading feels like learning but isn't); **spaced
  repetition** and **interleaving** beat massed practice. ([Coursera — Learning How to Learn](https://www.coursera.org/learn/learning-how-to-learn),
  [A Mind for Numbers (notes)](https://www.cs.uni.edu/~jacobson/1025/16/f/MindForNumbers.pdf))
  → **Lands as:** (1) **validates the engine** — FSRS spaced repetition + weakest-skill
  adaptive selection (ADR-0005/0006) *is* Oakley's prescription in code; the coach should
  *name why* a skill is being revisited. (2) The coach **tests recall**, doesn't just
  re-explain, and **flags false confidence** (illusion of competence) — a candidate judge
  signal.
- **Holt — *How Children Learn*** — **learner autonomy**, **intrinsic motivation** over
  coercion/grades, and **productive struggle**: children master concepts by revisiting them
  out of fascination, without external reward/penalty; over-instruction stifles curiosity.
  ([Modulo — John Holt](https://www.modulo.app/all-resources/john-holt),
  [How Children Learn (text)](http://schoolofeducators.com/wp-content/uploads/2011/12/HOW-CHILDREN-LEARN-JOHN-HOLT.pdf))
  → **Lands as:** the **theoretical grounding for the anti-leakage stance** — don't rescue
  too early; let the student own the work. This promotes a new candidate Pedagogy-judge
  dimension: **productive-struggle preservation** ("did the coach resist rescuing too
  early?") alongside the answer-leakage flag.

**Net effect on the design:** the persona (FR-10/11) gains *teach-back*, *analogy-first*,
and *name-the-why-of-revisiting*; the Pedagogy GoalJudge (ADR-0008) gains two candidate
axes — **illusion-of-competence detection** (Oakley) and **productive-struggle preservation**
(Holt) — both pulling the same direction as the answer-leakage flag.

---

## 4. Target architecture (the seams)

The coach is a **configured instance of the existing ReAct graph**, not a new graph. The
governance wraps the same `START → guard_input → route → call_llm → execute_tool →
evaluate` topology.

```
┌──────────────────────────────────────────────────────────────────────┐
│  AgentFacts contract  (trust/models.py + governance registry)         │
│   id: subject-coach-english · capabilities: [think, file_io]          │
│   policies: domain=english-teaching · no-code-execution               │
│             · answer-leakage-prohibited · rate-limit                   │
│   signature: HMAC (verified at guard_input)                           │
└───────────────┬──────────────────────────────────────────────────────┘
                │ gates ▼ (ADR-0007: capabilities filter the ToolRegistry)
┌───────────────┴──────────────────────────────────────────────────────┐
│  ReAct graph instance (orchestration/react_loop.py::build_graph)      │
│   guard_input → English-only InputGuardrail (re-targeted condition)   │
│   route       → capable tier (coach) ; persona via additional_instr.  │
│   call_llm    → bound tools = {think, file_io}  (only these exist)    │
│   evaluate    → Pedagogy GoalJudge (anti-leakage) + general GoalJudge │
└───────────────┬───────────────────────────────────────────────────────┘
                │ grades produced content ▼
┌───────────────┴───────────────────────────────────────────────────────┐
│  Judges (ADR-0008)                                                     │
│   • MC Grader        — deterministic letter-match — FRONTEND, offline  │
│   • Grader Judge      — LLM rubric over coach's GENERATED content — BE │
│   • Pedagogy GoalJudge — scaffolding + answer-leakage — BACKEND        │
│   • general GoalJudge  — session-goal completion (reused as-is) — BE   │
└────────────────────────────────────────────────────────────────────────┘
```

Two flows share the contract:
- **Live coach** (FR-F streaming over the AG-UI SSE / `CoachAgentClient`, ADR-0006): the
  graph instance above, per turn.
- **Offline generator** (engine brainstorm B2): a separate `build_graph` job that emits
  typed `question`/`tutorial` rows, **verifier-gated** (`reviewed=true`) before a learner
  sees them. Same contract, different `accept_condition` and output schema.

---

## 5. The judge question — evaluate the existing GoalJudge first

The user's instinct ("we might need a dedicated grader judge") is correct. Reading
`components/goal_judge.py`:

- It is a **goal-completion** judge — "did this run accomplish what the user asked,"
  reference-free over `final_answer` + trajectory. Its verdict schema (`goal_met`,
  `criteria_met`, `unmet_conditions`) **has no per-criterion or answer-leakage axis.**
- Its **correctness cascade** (`verify_answer` owns `goal_met` when checkable, else the
  LLM rubric) is the right *pattern* — but `verify_answer` is bound to **generic** task
  constraints (topo sorts, etc.), not "is this the correct letter for an English MC item."
- Therefore it **cannot be retargeted to English grading by config alone.** A dedicated
  Grader + Pedagogy judge are justified — but each **reuses GoalJudge's injectable H1/H2
  shape and the cascade pattern**, not a from-scratch judge.

**Decision (→ ADR-0008): three judges, maximal reuse.**

| Judge | Verdict | Home | Reuse |
|---|---|---|---|
| **MC Grader** | correct letter? (bool) | **Frontend** (client, offline) | deterministic letter-match; the `Grader` port's deterministic stage (ADR-0006) |
| **Grader Judge** | faithfulness + correctness + justification + actionability (per-criterion) | **Backend** (`components/`) | GoalJudge H1/H2 shape; new `.j2` rubric; **grades the coach's generated content** |
| **Pedagogy GoalJudge** | scaffolding score + **answer-leakage flag** + mistake-id/location/actionability | **Backend** (`components/`) | GoalJudge shape; new `.j2`; AI-tutor taxonomy dimensions |
| **general GoalJudge** | `goal_met` (session objective) | **Backend** | reused **as-is** |

**Home split** (user decision, matches ADR-0005 local-first): deterministic letter-match
runs **client-side** (instant, offline-capable); LLM grading (Grader Judge + Pedagogy)
calls the **backend** agent over the BFF. Two grader homes is the accepted cost of
local-first.

---

## 6. Candidate options (what the ADRs settle)

### Decision A — tool restriction enforcement (→ ADR-0007)
| Option | What | Verdict |
|---|---|---|
| **A1. Construction-time** | pass a 3-tool `ToolRegistry` to `build_graph`; contract is documentary | ❌ leaves the AgentFacts contract non-load-bearing (declared ≠ enforced) |
| **A2. Capability-gated registry** | `AgentFacts.capabilities` filter the `ToolRegistry` at the graph-build boundary; an architecture test asserts the gate | ✅ **This.** Makes the governance contract real enforcement (user decision) |

### Decision B — the live coach fork (engine brainstorm B1, the ⚠️ new-graph-node flag)
| Option | What | Verdict |
|---|---|---|
| **B1. Prompt-param on the existing graph** | coach = `build_graph` with persona via `additional_instructions` + restricted tools; no new node | ✅ **Lean.** Cheapest; reuses topology; no new graph node = no new-node ADR trigger |
| **B2. Distinct node / sub-graph** | a dedicated coach node in `react_loop.py` | ❌ for v1 — new-graph-node is ⚠️ Ask-first; the prompt-param path avoids it |

### Decision C — input domain restriction (→ ADR-0007 consequence, small)
| Option | What | Verdict |
|---|---|---|
| **C1. Re-target `accept_condition`** | make the existing `InputGuardrail` condition injectable; set English-only | ✅ **Lean.** Reuses the 3-stage cascade; one `build_graph` parameter |
| **C2. New topic-classifier stage** | add a second guardrail instance / ONNX topic head | ⏳ defer — only if the LLM-judge stage's FP/FN rate proves insufficient |

### Decision D — inline Reflexion (T2) for the multi-turn coach (→ ADR-0009)
The pipeline already has a **T2 Reflexion** loop (`reflect` node): on a `failed`/`partial`
GoalJudge verdict it generates a critique and **re-runs the same task** up to 2×, folding the
critique into the system prompt. Gated OFF by default, no quality benchmark. Should the coach
enable it?

| Option | What | Verdict |
|---|---|---|
| **D1. Enable T2 for the coach** | `reflexion_enabled=True` | ❌ **Overkill + counter-pedagogical.** T2 is a *per-task retry* keyed on a task-failure verdict; a coaching turn has no such verdict (the student's next message *is* the loop). It converges toward *the correct answer* — the exact behavior (answer-leakage) the design forbids. Adds 2–3 LLM calls/turn on a latency-sensitive UX with no measured gain. And `reflections` has no `task_id` guard → a prior turn's critique leaks into the next. |
| **D2. Reflection offline, in the judge layer** *(chosen)* | T2 OFF for the coach; the Pedagogy GoalJudge (ADR-0008) *is* reflection-on-the-turn; offline content-improvement uses the same judges | ✅ **This.** Keeps the live turn fast + scaffolding-faithful; puts self-critique where it helps (grading + generation) reusing judges already planned. |

**Research basis:** 2026 reflection guidance reserves the pattern for *checkable single-task
runs* (code-gen/research) and explicitly says to **skip it for quick/latency-sensitive
conversational replies** ([Finding the Sweet Spot](https://arxiv.org/pdf/2510.20653),
[Self-Improving AI Agents](https://www.taskade.com/blog/self-improving-ai-agents-reflection)).
The pedagogy sources (§3.5) reinforce it: Reflexion *rescues the answer*, the coach must *not*.
**Full reasoning + the cross-turn-leak prerequisite → [ADR-0009](../adr/0009-subject-coach-reflexion-not-on-live-path.md).**

---

## 7. The "don't-bake-it-in" checklist (subjective-plane edition)

Carries the engine brainstorm §6 discipline to the agent. A PR that hard-codes the left
column closes an OCP door:

- ❌ "English" hard-coded in the persona prompt → ✅ subject is a prompt/config param.
- ❌ ACT-English-only `accept_condition` → ✅ broad English-learning condition, subject-param.
- ❌ judges import English specifics → ✅ judges take the rubric as injected config/`.j2`.
- ❌ letter-match assumed in the backend Grader Judge → ✅ MC correctness is the frontend
  deterministic stage; backend grades *generated content*, item-type-agnostic.
- ❌ tools hard-wired in the graph → ✅ tools come from the capability-gated registry.

---

## 8. Open questions handed to the ADRs / spec

1. **ADR-0007:** the exact gate point — does `AgentFacts.capabilities` filter the
   `ToolRegistry` inside `build_graph`, or at registry construction in the composition
   root? What architecture test asserts "declared = bound"? What's the failure mode when
   a capability names a tool that doesn't exist?
2. **ADR-0008:** the three verdict schemas; the Pedagogy rubric's answer-leakage scoring
   (binary flag vs. graded); calibration target (κ vs. human raters) reusing the
   GoalJudge cert harness; how the frontend MC Grader and backend judges compose into
   ADR-0006's `Grader` port.
3. **Spec:** the English-only `accept_condition` wording + its FP-rate acceptance
   criterion; the offline generator's `reviewed`-gate verifier per item-type; the persona
   prompt's scaffolding/Socratic/anti-leakage acceptance criteria.

---

## 9. Recommendation (one line)

**Spin the coach as a configured `build_graph` instance (B1) with an AgentFacts contract
whose `capabilities` *load-bearingly* gate a `think`+`file_io` tool registry (A2/ADR-0007),
an English-only re-targeted input guardrail (C1), and three rubric-anchored judges —
deterministic MC Grader on the frontend, LLM Grader Judge + Pedagogy GoalJudge on the
backend, general GoalJudge reused (ADR-0008)** — English-concrete now, subject-param open.

---

### Sources
- Pedagogy / scaffolding / answer-leakage: [Adaptive Scaffolding theory](https://arxiv.org/pdf/2508.01503) ·
  [Conversational design (Socratic/narrative)](https://arxiv.org/pdf/2509.12107) ·
  [MathTutorBench](https://arxiv.org/html/2502.18940v1) ·
  [Rethinking Scaffolding in LLM Tutors](https://arxiv.org/html/2606.15766v1) ·
  [Answer-leakage robustness](https://arxiv.org/html/2604.18660v1) ·
  [Confirming Correct, Missing the Rest](https://arxiv.org/html/2605.16207)
- Guardrails / off-topic: [Off-topic prompt detection methodology](https://arxiv.org/html/2411.12946v1) ·
  [LLM guardrails best practices (Datadog)](https://www.datadoghq.com/blog/llm-guardrails-best-practices/)
- Judge architecture / taxonomy: [Unifying AI Tutor Evaluation taxonomy](https://arxiv.org/pdf/2412.09416) ·
  [Rubric-based evals methodology](https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80)
- Grading correctness + generated content: [EFL rubric grading reliability](https://bera-journals.onlinelibrary.wiley.com/doi/10.1111/bjet.13494) ·
  [Criterion-based grading consistency](https://www.nature.com/articles/s41539-024-00291-1) ·
  [Reference-free faithfulness scale](https://arxiv.org/pdf/2410.12222) ·
  [LLM-Rubric calibrated multidim eval](https://arxiv.org/html/2501.00274v1) ·
  [Feedback quality dimensions survey](https://arxiv.org/html/2504.04717v6)
- Learning science (persona/judge grounding): [FS.blog — Feynman learning technique](https://fs.blog/feynman-learning-technique/) ·
  [Learn Like Feynman — AI Feynman-bot](https://arxiv.org/pdf/2506.09055) ·
  [Oakley — Learning How to Learn (Coursera)](https://www.coursera.org/learn/learning-how-to-learn) ·
  [Oakley — A Mind for Numbers (notes)](https://www.cs.uni.edu/~jacobson/1025/16/f/MindForNumbers.pdf) ·
  [Holt — John Holt overview](https://www.modulo.app/all-resources/john-holt) ·
  [Holt — How Children Learn (text)](http://schoolofeducators.com/wp-content/uploads/2011/12/HOW-CHILDREN-LEARN-JOHN-HOLT.pdf)
- Reflexion / when-not-to-loop: [Finding the Sweet Spot — inference-time reflection trade-offs](https://arxiv.org/pdf/2510.20653) ·
  [Self-Improving AI Agents — the reflection loop](https://www.taskade.com/blog/self-improving-ai-agents-reflection)
