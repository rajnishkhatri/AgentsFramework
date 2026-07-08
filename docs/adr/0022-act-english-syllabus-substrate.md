---
type: decision-record
title: 'ADR-0022: ACT-English syllabus-as-data substrate — canonical corpus, two-plane converter, rises-only coverage ratchet'
status: accepted
created: 2026-07-07
updated: 2026-07-07
owner: Rajnish Khatri
related: 0014-subject-coach-hint-repo-read-seam.md, 0015-subject-coach-test-item-bank-blueprint-read-seam.md, 0021-bank-backed-practice-scheduler.md, act-english-syllabus-substrate.spec.md
tags: [decision-record]
---

# ADR-0022: ACT-English syllabus-as-data substrate

**Status:** Accepted — 2026-07-07 (ratified at the design-spec human gate, all
three D-specs approved; the full-converter scope was an explicit gate override
of the lean recommendation).
**Related:** [spec](../plan/act-english-syllabus-substrate.spec.md) ·
[brainstorm + extraction table](../plan/act-english-full-bank.brainstorm.md) ·
[ADR-0014](0014-subject-coach-hint-repo-read-seam.md) (single-source corpus
seam precedent) · [ADR-0015](0015-subject-coach-test-item-bank-blueprint-read-seam.md)
(cascade/promotion the tag rides) · [D4 taxonomy spec](../plan/act-english-topic-taxonomy.spec.md)
(the TS plane's future consumer).
**Audience:** anyone changing the syllabus corpus, the coverage floors, the
seed pre-flight, or wiring standards into the product (read this BEFORE D4).

---

## Context

The ACT-English bank initiative reframed the product goal to **topic-by-topic
mastery**, but "topic" existed nowhere as data: the 12pp IXL skill plan
(`docs/ACT-syllabus/act-english.pdf`) was hand-extracted at the brainstorm
gate into a validated 32-standard table (5 score bands × 3 reporting
categories, each standard mapped to exactly one app practice skill), and the
8-item bank covered ~7 of 32 standards with no way to *measure* that. Three
forces:

1. **"Full" must be measurable, not vibes** — Phase B authors ~192 seed rows
   against a per-standard allocation matrix; without a machine-readable
   syllabus and a coverage count over the promoted corpus, the matrix is
   unenforceable prose.
2. **Tags must survive promotion.** D4 schedules per-standard; if the tag
   dies at promotion (the original draft had promotion *stripping* a
   seed-only `topic` field), every bank row would need re-promotion — a full
   re-run of live solver calls — the day D4 lands.
3. **Two consumers, one truth.** The frontend (D4 scheduler/dashboard) and
   the Python side (generation targeting, coverage tooling) both need the
   standard list; duplicated lists drift.

## Decision

Ship the syllabus **as data with a build-ahead converter**:

- `docs/plan/act-english-syllabus.seed.json` — the canonical 32-standard
  corpus (`standard_id`, `name`, `category`, `bands`, `app_skill`), the ONLY
  hand-edited artifact, byte-matching the gated extraction table.
- `scripts/emit_syllabus.py` — deterministic, stdlib-only, fail-closed
  converter (the `emit_hint_bank.py` two-plane pattern) emitting
  `frontend/lib/adapters/engine/_act_english_syllabus.ts` (data-plane only
  until D4) and `components/act_english_syllabus.py`; a drift test re-emits
  and byte-compares both planes in CI (FR-10).
- Seed rows carry `standard_id` (born with that name — the `topic` draft
  field never shipped); `_reviewed_row` carries it **verbatim** through
  promotion and never invents one (FR-5).
- `scripts/bank_seed_preflight.py` — fail-closed tag validation (unknown id,
  band-membership, skill-contradiction, retired `topic` key), run in CI over
  the canonical seed.
- `docs/plan/act-english-coverage-floors.json` + a **rises-only ratchet**
  (`tests/architecture/test_syllabus_coverage_ratchet.py`): promoted-corpus
  per-cell (standard × band) counts must meet recorded floors, and floors are
  compared against their own committed history (`git show HEAD:`) so lowering
  or deleting one fails. Baseline floors = `{}` (pre-Phase-B corpus is
  untagged); Phase B T7 raises them.

## Options considered & rejected

1. **Lean substrate — canonical JSON now, emitters deferred to D4** (the
   original recommendation). *Rejected at the human gate (2026-07-07):*
   build-ahead chosen so D4 lands against an existing, already-drift-guarded
   plane, and because Phase B's own tooling (coverage report, generation
   targeting) needs the Python plane before D4 exists.
2. **Tag at promotion time** (map rows → standards during the promotion run
   or backfill from a mapping file). Rejected: promotion must never invent
   or default a tag (AP-6 fail-closed posture; FR-5) — authoring owns the
   intent, the cascade only verifies and carries.
3. **Fixed-target coverage tests** (hardcode per-cell minimums in test
   code). Rejected: floors-as-data + a monotonicity guard makes raising the
   bar a reviewable one-line data diff and lowering it mechanically
   impossible without failing CI — a code-edit ratchet has neither property.
4. **Wire the TS plane into the product now.** Rejected: wire-kernel and
   scheduler changes are D4's own ⚠️ Ask-first triggers with their own ADR;
   shipping the plane as inert data keeps D3 single-commit reversible.
5. **Parse the PDF programmatically.** Rejected: one-time extraction of 32
   rows, already human-validated at the gate; a parser is machinery with no
   second use (the PDF stays a citation).

## Rationale

The single-source-corpus seam is the repo's proven shape for governed data
(ADR-0014 hints; ADR-0015 bank): one hand-edited JSON, deterministic
emission, CI drift-pinning, provenance carried verbatim. Extending it to the
syllabus makes coverage a *measured, monotone* property — the ratchet turns
"the bank is full" into `floor_violations == []` — while the fail-closed
pre-flight moves tagging errors to authoring time, before any LLM spend.
Carrying the tag through promotion now (vs stripping) costs one allowlist
line and saves a full re-promotion when D4 needs it.

## Consequences

- **Floors only rise.** Deliberate friction: shrinking the bank (or
  re-authoring away from a covered cell) requires failing CI and a reviewed
  floors change. Accepted.
- **Emitted planes are never hand-edited** — the drift test fails any manual
  touch; every syllabus change is seed-edit → re-emit → re-gate.
- The TS plane sits **unconsumed until D4** (small accepted dead weight;
  documented in the file header).
- `standard_id` stays corpus-side until D4 declares it on the wire — the Zod
  kernel default-strips it from served rows, so no schema/UI change ships
  here.
- The syllabus is versioned by ordinary git history; a future syllabus
  revision (IXL updates their plan) is a seed diff + floors review, not a
  code change.
- Follow-on: Phase B T7 records post-promotion floors; D4 consumes the TS
  plane (its own ADR); the coverage report is the honest artifact for "what's
  still empty".

## Supersedes / related

Supersedes nothing. Realizes
[act-english-syllabus-substrate.spec.md](../plan/act-english-syllabus-substrate.spec.md);
amends the Phase B bank spec's FR-8 field semantics
([act-english-bank-phase-b.spec.md](../plan/act-english-bank-phase-b.spec.md));
prerequisite for [D4](../plan/act-english-topic-taxonomy.spec.md).
