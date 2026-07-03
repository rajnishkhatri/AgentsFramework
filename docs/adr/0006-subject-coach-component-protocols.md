---
type: decision-record
title: 'ADR-0006: Subject-Coach component protocols (seven Frontend-Ring ports)'
status: accepted
created: 2026-06-30
updated: 2026-06-30
owner: Rajnish Khatri
related: SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md, 0005-subject-coach-engine-home-and-substrate.md, FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md, preact-english-coach-ui.spec.md
tags: [decision-record]
---

# ADR-0006: Subject-Coach component protocols

**Status:** Accepted — 2026-06-30. **Amended by [ADR-0011](0011-subject-coach-engine-learner-read-port.md)**
(2026-07-01) — adds an eighth engine port, the read-only `LearnerReadRepo` (the seven ports
below are unchanged). **Amended by [ADR-0014](0014-subject-coach-hint-repo-read-seam.md)**
(2026-07-02) — adds a ninth read-only port, `HintRepo` (the hint content-family read seam:
`hint` table both dialects + `Hint` wire entity; ADR-0012's committed amendment window).
**Related:** [data & protocols design doc](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md) · [ADR-0005 engine home](0005-subject-coach-engine-home-and-substrate.md) · [ADR-0011 learner read port](0011-subject-coach-engine-learner-read-port.md) · [Frontend ports deep dive](../Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) · [UI spec](../plan/preact-english-coach-ui.spec.md)
**Audience:** anyone implementing or changing an engine port signature, the `Verdict` shape, or the coach stream contract.

---

## Context

ADR-0005 places the learner-facing engine in the Frontend-Ring, local-first. The engine
must talk to its subject (taxonomy, content, grading) and its infrastructure (DB, FSRS,
coach stream) through **contracts**, not concrete classes — so that (a) English ships
against in-repo/local adapters, (b) Math is added by new adapters without touching the
engine, and (c) tests inject mocks (every port ≥1 mock + 1 real, per the deep-dive).

The existing Frontend-Ring already prescribes the shape this must take:
- **F-R3: exactly one interface per `ports/` module.** Eight existing ports = eight files.
- **SDKs confined to `adapters/`** (CopilotKit, LangGraph, Drizzle); never in `ports/`.
- **Composition root injects** the adapter; conformance is checked by a test bundle, not
  the structural type system alone.

The open question this ADR settles: **what are the engine's ports, their exact
responsibilities and boundaries, and how does grading stay subject-extensible** — given the
"English-concrete, seams only" stance (no premature generic machinery).

---

## Decision

Introduce **seven engine ports** (one interface per module under `frontend/lib/ports/`),
plus one **client-side renderer registry** (not a port). The ports:

| # | Port | Contract (intent, not final TS) | Boundary |
|---|---|---|---|
| 1 | `SkillTaxonomy` | `list(subject): Skill[]` · `get(subject, skillKey): Skill` | read-only; no mastery (that's `Scheduler`/`skill_state`) |
| 2 | `QuestionRepo` | `nextReviewed(subject, skillId): Question?` · `get(id)` · `save(Question)` | **returns `reviewed=true` only**; never grades |
| 3 | `AttemptRepo` | `record(Attempt)` · `misses(subject, learner): Attempt[]` | write attempts; read for "review my misses" |
| 4 | `SessionRepo` | `open(subject, learner, mode, focus?)` · `close(id, score)` · `get(id)` | session lifecycle + scoring tally only |
| 5 | `Scheduler` (FSRS) | `next(subject, learner): {skillId, questionId}` · `review(attempt): SkillState` | **only writer of `skill_state`**; subject-agnostic algorithm |
| 6 | `Grader` | `grade(question, answer): Verdict` | **pure**, deterministic, canonicalizing; no I/O |
| 7 | `ContentRepo` | `text(subject, key, locale): string` · `bundle(subject, locale)` | objective-plane UI strings; no business logic |
| + | `CoachAgentClient` | `subscribe(ctx): AsyncStream<CoachToken>` over the BFF SSE | the one online port; reuses the AG-UI transport, **not** a new stream stack |

`Verdict` (the grading contract — generic enough for Math without being abstract now):
```
Verdict = {
  correct: boolean,
  correctLetter?: string,        // English MC canonical answer
  canonicalAnswer?: string,      // future: normalized numeric/symbolic form
  rationaleKey?: string,         // which per-choice rationale to surface
}
```

**Grading is verifier-first** (the 2026 consensus + the repo's own GoalJudge cascade
habit): `Grader` is *deterministic and canonicalizing*. English = exact-letter-match. A
future Math grader implements the *same interface* with symbolic-equivalence
canonicalization; an LLM, if ever used to grade free-response, sits **behind** a
deterministic verifier, never in front of the learner-facing verdict.

**Renderer registry (client-side, not a port):** the Quiz screen renders
`registry[question.item_type]`. English registers `underlined-span-mc`. This is the
React-OCP twin of `Grader` — new item *types* are registered, the screen is never edited.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **One fat `EngineService` interface** (all reads/writes/grading on one object) | Violates F-R3 (one interface per module) and the single-responsibility seam; makes the Math extension a god-object edit. ❌ |
| **No `Grader` port — grade inside `QuestionRepo`** | Couples persistence to subject logic; Math's symbolic grader would force a repo change. Grading must be a pure, swappable strategy. ❌ |
| **Generic `ItemType` port + plugin loader now** | The brainstorm's Option C1 / the four-layer doc's anti-pattern: building the abstraction before the second consumer. We keep `item_type` a column + a registry entry; the *loader* waits for Math. ❌ (documented-open) |
| **A new coach stream transport** | A new SSE stack would duplicate the AG-UI transport already confined to `adapters/`. The coach is a `CoachAgentClient` adapter over the *existing* transport. ❌ |
| **Subject as a separate service per subject** | Over-isolation; subject is a *row discriminator* + adapter set, not a microservice. ❌ |

---

## Rationale

Seven narrow ports map 1:1 to the engine's responsibilities and obey the F-R3 rule the
Frontend-Ring already enforces, so this is *applying* the existing pattern, not inventing
one. The `Grader`/registry split is the precise pair of seams that makes Math an
*extension* (a new grader adapter + a new registry entry + new rows) with **zero** engine
edits — satisfying OCP exactly where subjects diverge (item shape + answer checking) while
leaving everything subject-invariant (flow, scheduling, sessions, attempts) un-abstracted.
Keeping `Grader` pure and verifier-first inherits the repo's proven correctness-cascade
discipline and keeps grading deterministic for L1 tests (no live LLM in CI).

---

## Consequences

**Commits us to:**
- Seven new `frontend/lib/ports/*.ts` modules (one interface each) + matching
  `frontend/lib/adapters/*` (Drizzle repos, ts-fsrs scheduler, exact-match grader, in-repo
  content bundle, AG-UI coach client), wired in the composition root.
- A **conformance test bundle** per port (mock + real), matching the existing port testing
  convention — the structural type check is not sufficient on its own.
- The `Grader` stays **pure** (no I/O) so it is trivially L1-testable and reusable on the
  generation side as the gate that sets `reviewed`.
- Translators map repo rows → the UI view-models (spec §4); the UI never imports a port’s
  row types directly.

**Accepted risks / mitigations:**
- *`Verdict` under-fits a future subject* → it already reserves `canonicalAnswer`; a
  genuinely new field is an additive change behind the port (non-breaking). Decision
  trigger: first non-MC subject → review `Verdict` with that grader's needs.
- *Registry sprawl* → one entry per item-type; an architecture/review-template check (the
  repo's "template-as-enforcement" tactic) flags any `switch(subject)` that bypasses it.
- *Coach client drift from AG-UI* → `CoachAgentClient` is a thin adapter over the existing
  transport; it adds subject context as a param, not a new protocol.

---

## Supersedes / related

Makes canonical the protocol section of
[SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md).
Pairs with [ADR-0005](0005-subject-coach-engine-home-and-substrate.md) (engine home + substrate).
Conforms to [FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](../Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) (F-R3, SDK confinement, composition root).
