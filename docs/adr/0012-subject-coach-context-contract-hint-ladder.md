---
type: decision-record
title: 'ADR-0012: Coach context contract — mode-dependent injection + offline leak-checked hint ladder'
status: accepted
created: 2026-07-01
updated: 2026-07-02
owner: Rajnish Khatri
related: SUBJECT_COACH_AGENT_DETAILED_DESIGN.md, subject-coach-agent.spec.md, 0006-subject-coach-component-protocols.md, 0007-subject-coach-agent-tool-capability-gating.md, 0008-subject-coach-judges-grader-and-pedagogy.md
tags: [decision-record]
---

# ADR-0012: Coach context contract — mode-dependent injection + offline leak-checked hint ladder

**Status:** Accepted — 2026-07-02 (was Proposed — 2026-07-01, proposed by the agent
design doc's §10 adjudication; tightened 2026-07-02 with the residual-risk window,
mechanical mode-spoofing enforcement, the no-assertion-rung decision trigger, and the
Decision §3 advisory-mode clarifier; ratified 2026-07-02 at the design doc's
build-sequencing step-1 human gate — see `log.md`; **amended 2026-07-02 with the
session-state home** — see the Amendment block below).

> **Amendment (2026-07-02) — the session-state home: a minimal BFF coach-session
> marker.** A pre-implementation gap review found Decision §3's "derives the
> authoritative `mode` from session state (the attempt row exists or it doesn't)" had
> **no server-visible state to read**: the engine substrate is Frontend-Ring-local at
> runtime (the live `/learn` surface composes `browserEngineAdapters` /
> `InMemoryEngineDb`; no server API route reads or writes attempts — verified
> 2026-07-02), and the agent design doc §4.1 itself rules "the backend never re-queries
> the engine DB" (ADR-0005). Amended mechanism, smallest store that preserves the
> ratified mechanical claim:
>
> 1. **A minimal BFF-side coach-session marker store** — `{user_id, question_id,
>    submitted_at}` — written fire-and-forget from the client quiz-submit path, read by
>    the coach BFF route (`frontend/app/api/coach/run/stream/route.ts`, BUILT) at
>    context assembly: marker present ⇒ `post_feedback` permitted for that item; absent
>    ⇒ `pre_submit`. Markers are **monotonic** (never deleted within a session scope):
>    once submitted, always post-feedback for that item.
> 2. **Two-layer context assembly.** The BFF derives the authoritative `mode` from the
>    marker store and **strips the four answer-bearing fields from the client-supplied
>    `coach_context` whenever derived mode = `pre_submit`** — the exclusion is enforced
>    server-side *over client-supplied content* (the backend still never queries the
>    engine DB, preserving ADR-0005 local-first). The backend renders the persona from
>    the sanitized context. The client-sent `mode` stays advisory-only (unchanged).
> 3. **Trust model, stated honestly:** the marker write is client-triggered — only the
>    client knows a submit happened, because grading is client-side (ADR-0005). Spoofing
>    the marker is therefore possible but **pedagogically equivalent to actually
>    submitting** (any learner can self-serve the answer by submitting an arbitrary
>    letter — the pre-submit exclusion protects the learner from being *handed* the
>    answer, it is not adversarial security). What the marker buys over trusting the
>    client's `mode` directly: server-side authority + monotonicity + an auditable
>    carrier (the §13.2 trace-audit check reads it), and a single arch-testable seam —
>    the arch test asserts assembly-mode sourcing = the marker store, never
>    `input.coach_context.mode`.
> 4. **Interim hint rungs** (before the `hint` schema lands at the generator build):
>    authored rungs ship as a **backend-readable data asset** (a data file beside
>    `prompts/`, leak-checked at authoring, `reviewed`-equivalent by review) — a
>    frontend fixture cannot serve the backend persona render.
>
> Rejected: a full server-side engine mirror (breaks ADR-0005's no-sync deferral for one
> bit of state); client-derived `mode` with a tripwire (re-opens the ratified mechanical
> claim for no cost saving — the marker store is one table + one read).
**Related:** [agent detailed design](../Architectures/SUBJECT_COACH_AGENT_DETAILED_DESIGN.md) §4/§8/§10 · [agent spec](../plan/subject-coach-agent.spec.md) · [ADR-0006 ports](0006-subject-coach-component-protocols.md) · [ADR-0008 judges](0008-subject-coach-judges-grader-and-pedagogy.md)
**Audience:** anyone assembling the coach's per-run context, building the hint pipeline, or
reconsidering whether the live coach may see the correct answer.

---

## Context

The deepest unresolved design tension in the Subject-Coach: **does the live coach see the
correct answer?** Give it `answer_letter` + rationales and hints are grounded — but
free-generating tutors measurably leak (solution disclosed in **66%** of ChatGPT-style
tutoring interactions; worse under adversarial "just tell me" pressure). Withhold the
answer and leakage from context becomes impossible — but post-answer coaching is crippled
(the coach can't discuss a `why_tempted` it can't see) and *faithfulness* risk appears
(scaffolding toward a wrong answer). Prompt discipline alone is not a mitigation: RLHF
helpfulness actively fights it, and answer-leakage is the #1 penalized failure in the
tutoring benchmarks (ADR-0008's rationale). The proven architectural mitigation is the
**finite-state hint ladder** with per-rung leak checks (MWPTutor lineage: pump → hint →
directive → assertion slots, leakage checked per slot).

Two grounded facts shape the solution space (design doc §4, verified 2026-07-01):
- The `Question` wire entity's answer-bearing fields are exactly four —
  `answer_letter`, `per_choice_rationale`, `why_correct_md`, `why_tempted_md`
  (`frontend/lib/wire/engine_entities.ts:61–79`) — a precise exclusion list exists.
- **No hint table/entity exists anywhere** (`schema.pg.ts`, `engine_entities.ts`) — a
  ladder is a real schema addition, and the UI flow itself already splits the problem:
  the pre-submit surfaces (quiz hint FR-D5, split-panel nudges FR-J3a) forbid revealing;
  the post-feedback surface ("Ask the coach" FR-E5) is entered from a screen where the
  correct answer is **already rendered**.

---

## Decision

**Adopt a mode-dependent context contract, with pre-submit hints served from an offline
leak-checked hint ladder.**

1. **Pre-submit mode** (quiz hint, split-panel nudges): the per-run coach context
   **excludes the four answer-bearing `Question` fields**. Hints come from a per-question
   **hint ladder** — rung 1 *probe*, rung 2 *conceptual*, rung 3 *directive*, deliberately
   **no assertion rung** — generated/authored offline, **leak-checked per rung** in the
   generator's deterministic verifier cascade, and gated behind the same `reviewed` flag
   as questions. The live coach *selects and paraphrases* rungs; it cannot free-generate
   toward an answer it cannot see.
2. **Post-feedback mode** ("Ask the coach"): full `Question` context (answer + rationales)
   is injected — the answer is already on the learner's screen, so leakage is moot by
   construction; judge attention shifts to faithfulness/actionability.
3. **Context assembly is server-side**: the client sends `{question_id, …}` (and
   optionally an advisory `mode` hint) on the existing structured run-input
   (`RunCreateRequest.input`, the `memory_context` precedent); the backend **derives the
   authoritative `mode` from session state** — per the 2026-07-02 Amendment, from the
   **minimal BFF coach-session marker store** (the attempt-submitted marker exists or it
   doesn't; the engine DB itself stays Frontend-Ring-local) — and resolves the
   mode-appropriate field subset by **stripping the four answer-bearing fields from the
   client-supplied context whenever derived mode = `pre_submit`**. The exclusion is
   never trusted to the client, and the client-sent `mode` is **advisory-only —
   ignored/overwritten**, never trusted into the persona render (see the mode-spoofing
   mitigation in Consequences; enforced by an architecture test, not a prose check).

---

## Options considered & rejected

| Option | What | Why it lost |
|---|---|---|
| **A. Always full context + prompt constraints** | Coach sees everything; the persona forbids revealing | Prompt discipline measurably fails (66% leak; adversarial pressure worsens it; RLHF fights it). The Pedagogy judge becomes a smoke detector on a known fire — detection without prevention. |
| **B. Always withheld** | Coach never sees answer-bearing fields | Cripples post-feedback coaching (can't explain `why_tempted` it can't see) and *introduces* faithfulness failures — the coach may scaffold toward a wrong answer, caught only post-hoc. Pays the cost everywhere to solve a problem that exists only pre-submit. |
| **C. Mode-dependent + ladder** *(chosen)* | Exclusion exactly where leakage exists; full context exactly where it's moot; pre-submit content pre-verified offline | Leakage made **structurally hard**, not just detected; reuses the engine's existing `reviewed`-gate machinery; the offline leak check is cheap where the online one is costly. |
| **C′. Mode-dependent, free-generated pre-submit hints** | Same modes, no ladder | Still free-generates in the leakage-critical mode — the 66% failure shape returns with only the exclusion (a coach that doesn't know the answer can still *derive and assert* one, possibly wrongly). The ladder bounds both leakage *and* wrong-hint faithfulness. |

---

## Rationale

The structural insight is that **the UI flow already partitions the risk**: leakage is
only *defined* pre-submit, and the pre-submit surfaces already carry a never-reveal
contract (FR-D5, FR-J3a). Aligning the context contract to that partition buys maximum
grounding quality (post-feedback) at zero leakage cost, and makes the pre-submit path
safe by **construction + verification** rather than by exhortation: the coach cannot leak
what it does not have, and what it *can* say pre-submit has already passed a per-rung
leak check offline — where checking is cheap, repeatable, and doesn't add hot-path
latency. This is the same verifier-first discipline the repo already applies everywhere
else (the GoalJudge cascade, the `reviewed` gate): deterministic prevention in front,
LLM judgment behind (the ADR-0008 Pedagogy judge remains the post-hoc sensor for
paraphrase-level leakage the structural exclusion can't rule out).

---

## Consequences

**Commits us to:**
- A **new `hint` content family**: table (both dialects), wire entity, and a
  `getHints(question_id)` read — executed under the **ADR-0006 second amendment** (the
  same amendment train as `getTutorial`/`listProgressPoints`), landing with the generator
  build. ADR-0006's 7(+1)-port surface is amended *by extension*, per its own OCP stance.
- **Server-side context assembly** as a component function (thin-node rule holds): the
  four-field exclusion list is code, tested, and keyed to the wire entity — a schema
  change to `Question`'s answer-bearing fields must update the exclusion (a lock test).
- **Authored seed rungs** until the generator ships — the ladder mechanism does not wait
  for generation; the seed corpus gets hand-written rungs behind the same `reviewed` gate.
- The Pedagogy judge's `answer_leakage` flag (ADR-0008) stays the post-hoc sensor for
  paraphrase drift; the ladder does not replace it.

**Accepted risks / mitigations:**
- *Rung quality ceiling* — selected-and-paraphrased hints are less tailored than free
  generation → mitigated by rung 1 being a *probe* (the coach personalizes the Socratic
  question around it) and by the content-improvement loop regenerating weak rungs.
- *No-assertion rung is a pedagogical ceiling* — the ladder deliberately drops MWPTutor's
  terminal "assertion" slot (FR-D5/FR-J3a: neither pre-submit tier reveals), so a learner
  who genuinely cannot solve the item **never gets the answer from the pre-submit coach**;
  the post-feedback surface (FR-E5) is the designed release valve. **Decision trigger**
  (recorded so the no-assertion choice is not silent intent debt, mirroring ADR-0011's
  session-resume trigger): revisit a fourth "reveal" rung if either (a) a measured
  productive-struggle floor is crossed — e.g. learners exhaust rung 3 without progress on
  a defined class of items — or (b) a research finding shows never-reveal harms mastery
  for that class. Any reveal rung stays gated behind the post-feedback surface (the answer
  is on-screen) and behind the same `reviewed` gate; it is never a pre-submit assertion.
- *Mode spoofing* — a client claiming `post_feedback` pre-submit → mitigated by
  **mechanical enforcement, not a prose check** (the ADR-0011 lesson: an "architecture
  assertion **or** code-review check" was too weak for the read-only invariant and was
  promoted to a compiler-enforced `ReadableEngineDb` projection). Concretely: the
  server-side context-assembly function accepts `question_id` + session state and
  **derives `mode` itself** (the attempt row exists or it doesn't); a `mode` field
  supplied by the client in `input.coach_context` is **ignored/overwritten**, never
  trusted into the persona render. An architecture test asserts that the assembly
  function's `mode` input is sourced from session-state derivation, not from the client
  run-input — the same "template-as-enforcement" tactic as the capability-gating arch
  test (ADR-0007). This replaces the earlier "flagged as a build-time check" hedge.
- *Per-rung leak check false negatives* (a rung that implies the answer without naming
  it) → deterministic check first (no choice-letter/answer-string references), Pedagogy
  judge assist after its κ floor (ADR-0008 cond#1).
- *Residual-risk window until ADR-0008 cond#1 is certified* — Option C eliminates
  **context** leakage (the 66% free-generation failure) on day 1 by construction, but the
  remaining surface is **paraphrase drift over the constrained rung vocabulary**. Until
  the Pedagogy judge's `answer_leakage` axis is calibrated to the stated floor (TNR ≥ 0.95
  / TPR ≥ 0.90 / κ ≥ 0.75, ADR-0008 cond#1 — still **pending**), the per-rung leak check
  is **deterministic-only** (literal letter/answer-string references) and the
  `answer_leakage` flag stays **telemetry-only** per ADR-0008. The constrained rung
  vocabulary bounds — but does not eliminate — paraphrase drift; there is no calibrated
  backstop until the cert lands. The build-sequencing step-1 gate must read C as
  "context-leakage solved; paraphrase-drift bounded, not yet calibrated," not as
  "leakage solved."

**Follow-on:** `attempt` gains per-rung usage capture (which rung was shown) at
generator-build time — small, decided then.

---

## Supersedes / related

Makes canonical the [agent detailed design](../Architectures/SUBJECT_COACH_AGENT_DETAILED_DESIGN.md)
§4 (context contract + ladder) and §8 (the verifier cascade that leak-checks rungs).
Extends [ADR-0006](0006-subject-coach-component-protocols.md) via its flagged second
amendment (executed with the generator build). Pairs with
[ADR-0007](0007-subject-coach-agent-tool-capability-gating.md) (the gates in front) and
[ADR-0008](0008-subject-coach-judges-grader-and-pedagogy.md) (the judges behind).
Supersedes nothing.
