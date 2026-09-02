---
type: decision-record
title: 'ADR-0040: Exam module — official-rules runs on the ADR-0038 seam + computed analytics read model'
status: proposed
created: 2026-09-01
updated: 2026-09-02
owner: Rajnish Khatri
related: exam-module-official-rules.spec.md, exam-module-official-rules.plan.md, 0038-durable-engine-seam.md, quiz-attempt-elapsed-timing.spec.md, test01-practice-split.spec.md
tags: [decision-record]
---

# ADR-0040: Exam module — official-rules runs on the ADR-0038 seam + computed analytics read model

**Status:** Proposed (Stage-2 plan gate) — 2026-09-01.
**Related:** [spec](../plan/exam-module-official-rules.spec.md) · [plan](../plan/exam-module-official-rules.plan.md) · [ADR-0038](0038-durable-engine-seam.md) (the seam this rides) · [quiz-attempt-elapsed-timing.spec.md §2.1](../plan/quiz-attempt-elapsed-timing.spec.md) (the "Test mode persists nothing" consent gate) · [test01-practice-split.spec.md FR-1](../plan/test01-practice-split.spec.md) (test exclusivity)
**Audience:** anyone touching `components/exam/`, the `exam_*` tables, the `EngineDb` method set, or `/learn/progress`'s exam panel — and anyone tempted to "just persist Test Mode".

---

## Context

The learner needs a full-length practice exam that behaves like the official ACT / PreACT
sitting: timed sections taken one at a time, official navigation rules, per-question time
and mark-for-review flags, results that survive reloads and devices, and a
strength/weakness analysis that points at what to practise next (spec §1).

What exists is `/learn/test` — a deliberately ephemeral, English-only, single-section
timer whose page header says it "shares NOTHING" with the quiz and whose persistence is
explicitly zero, recorded as a **consent gate** in the elapsed-timing spec §2.1. The
durable engine seam from ADR-0038 (`EngineDb` 32 methods → `HttpEngineDb` →
`/api/engine/db/<method>` dispatcher → `pgEngineDb`, dual-dialect schema, migrations
`0000–0004`) exists and is the paved road for any new learner-scoped persistence. The
practice bank already uses the words "exam item" for its governed content rows
(`test_item`, ADR-0015), and the FSRS `skill_state` mastery model is the practice
scheduler's input — timed-test results must never leak into either.

Two `⚠️ Ask first` triggers fire: a **new horizontal repo seam** (three tables, nine
`EngineDb` methods, a new port) and a **new abstraction** (an analytics read model).
This ADR covers both.

---

## Decision

Ship a **new `exam` module** (route `/learn/exam`, `components/exam/`, `lib/wire/exam_entities.ts`,
port `ExamRunRepo`) that persists **runs / section attempts / run items** in three new
`exam_*` tables through the existing ADR-0038 seam — nine `learnerId`-first `EngineDb`
methods dispatched by the generic `/api/engine/db/<method>` handler — and derives
strengths, weaknesses, pacing and recommendations as a **pure, computed `ExamAnalytics`
read model** over run items (never stored, never written to `skill_state`). Test Mode is
left untouched; the phase-1 form is the Test-01 English section behind a section-agnostic
form registry that is the landing zone for the privately ingested official forms.

**Communication posture (recorded 2026-09-02 — arch-lifecycle stage-3 handover).** Item
writes are **async-buffered** (debounced, offline-tolerant, flushed on nav / submit /
reconnect) specifically to keep the latency- and availability-sensitive live section
**decoupled** from store availability — a synchronous per-write dependency would collapse
the live-run and the store into one quantum and make the section inherit the store's
availability (Dynamic Quantum Entanglement). `beginSection` / `finishSection` are the two
**synchronous** round-trips; `beginSection` is an accepted **hard durability point** — a
section cannot begin without a server-recorded `started_at`, so it cannot begin fully
offline (cold-start exposure tracked as a risk). This trades *service availability during a
section* for *durability + local resilience* — the same trade recorded as the
Availability-rejected-driver in the exam-module characteristics worksheet.

---

## Options considered & rejected

| Option | Why it lost |
|---|---|
| **A. Extend Test Mode in place** (add persistence, flags, timing to `components/test/`) | Test Mode's contract is single-section and ephemeral by explicit consent gate; official rules (section attempts, deadlines, review-after-submit, composite) need a different state machine and a form model. Retrofitting rewrites it anyway while breaking its pinned e2e. Building beside it keeps the old surface green until superseded. |
| **B. Reuse `quiz_session` / `attempt` with a `mode: "exam"` discriminator** | `Attempt` is one-shot (`first_try`/`coached`, `used_hint`) with no flags, visits, first-answer fields or change counts; every learner-scoped read (`listByLearner`, summary, FSRS) would need a `mode` filter — one missed filter leaks exam results into practice mastery (violates test exclusivity FR-1). Nullable-column creep on the hottest table. |
| **C. Materialise analytics rows** (`exam_facet` table updated on finish) | Derived data over a few hundred rows per learner; recompute is O(n) and pure, so there is nothing to invalidate. Stored rows add a write path, a migration, and a second source of truth for thresholds that will be tuned. |
| **D. localStorage-only persistence** | Cross-device revision lists and multi-sitting analysis are the point; ADR-0038 already paid for the durable seam. |
| **E. Dedicated `/api/engine/exam/*` route handlers** | Nine handlers duplicating `engine_guard` boilerplate. The generic dispatcher already overrides the learner argument from the server claim; making every exam method `learnerId`-first gives FR-3 isolation in the adapter with zero new handlers. |
| **F. Name the namespace `sitting`/`mock`** | Considered for the "exam item" (= bank content, ADR-0015) collision. `exam_run*` names runs, not content, and reads unambiguously in code; the collision is documented here rather than paid for with an awkward learner-facing name. |

---

## Rationale

- **Simplest thing that satisfies the criteria (A1).** Every piece plugs into an existing
  pattern: tables like `quiz_session`/`attempt`, methods like `insertAttempt`, the
  dispatcher's learner-arg override, one-port-per-file repos, `EnginePortBag` wiring.
  No new process, package, SDK or route family.
- **What the two abstractions buy (G1).** The `ExamRunRepo` seam is the only way to
  get durable, learner-scoped, idempotent item writes without polluting practice data.
  The `ExamAnalytics` read model isolates thresholds and rules (a data table) in a pure
  function the UI and `/learn/progress` both consume — the alternative is duplicated
  ad-hoc aggregation in two screens.
- **Honesty by construction.** Scale = `null` without a table; composite = `null` until
  all composite sections finish; facet labels need ≥ 5 items; recommendations are
  rule-tied with evidence or absent (AP-6, no fabricated readings, no filler advice).
- **Deterministic first (demand-side lens).** No LLM anywhere; narratives are a gated
  later add on top of the same read model.
- **Business value.** *User satisfaction* — a durable, honest, cross-device practice exam
  that guides what to study next, where today's Test Mode measures nothing and remembers
  nothing; *strategic positioning* — the section-agnostic form registry is the landing zone
  for the privately-ingested official forms, the product's differentiator; *time to market*
  — reuses the paved ADR-0038 seam, so it ships without new infrastructure.

---

## Consequences

- **Commits us to:** three new tables (`exam_run`, `exam_section_attempt`,
  `exam_run_item`), pg migration `0005_exam_runs.sql` (the runner is Postgres-only;
  sqlite parity via `schema.sqlite.ts` + `schema.parity.test`), `EngineDb` 32 → 41
  methods with disposition entries and conformance rows, and the `learnerId`-first
  signature convention for run-scoped methods.
- **New guard:** `tests/architecture/test_exam_isolation.test.ts` — no import edge
  between `components/exam/**` / `exam_run_repo` and the quiz/scheduler/FSRS modules in
  either direction; no `skill_state` write from exam code. This is a *new* enforced
  boundary (nothing enforces component-to-component isolation today).
- **Accepted risks:** (1) the ADR-0038 dispatcher's totality tests (method count,
  disposition keys, conformance table) will all need edits — intentional friction;
  (2) dwell timing is client-measured and therefore advisory, mitigated by monotonic-max
  upserts and server-anchored section deadlines; (3) phase 1 has one section of one form
  — the module's value is unlocked by the follow-up specs (Test-01 remaining sections;
  private official forms + Math/Reading/Science rendering; 5-choice wire change).
- **Follow-on work:** Test Mode retirement decision once `/learn/exam` supersedes it;
  hoisting `format_clock`/countdown into a shared timing module if a third consumer
  appears (today `components/exam/` imports the siblings — recorded in `decisions.md`).

---

## Supersedes / related

- Makes canonical: [exam-module-official-rules.spec.md](../plan/exam-module-official-rules.spec.md),
  [exam-module-official-rules.plan.md](../plan/exam-module-official-rules.plan.md).
- Exercises the consent gate in [quiz-attempt-elapsed-timing.spec.md §2.1](../plan/quiz-attempt-elapsed-timing.spec.md)
  **for a new module only** — Test Mode itself still persists nothing.
- Inherits test exclusivity from [test01-practice-split.spec.md](../plan/test01-practice-split.spec.md) FR-1.
- Rides [ADR-0038](0038-durable-engine-seam.md); does not supersede it.
