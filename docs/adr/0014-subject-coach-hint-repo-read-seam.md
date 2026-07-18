---
type: decision-record
title: 'ADR-0014: Subject-Coach hint content-family read seam (HintRepo port + hint table)'
status: accepted
created: 2026-07-02
updated: 2026-07-02
owner: Rajnish Khatri
related: 0006-subject-coach-component-protocols.md, 0011-subject-coach-engine-learner-read-port.md, 0012-subject-coach-context-contract-hint-ladder.md, 0013-subject-coach-test-mode-blueprint-generation-integrity.md, subject-coach-agent.plan.md
tags: [decision-record]
---

# ADR-0014: Subject-Coach hint content-family read seam

**Status:** Accepted — 2026-07-02. Amends [ADR-0006](0006-subject-coach-component-protocols.md)
(the amendment window [ADR-0012](0012-subject-coach-context-contract-hint-ladder.md)
§Consequences committed the hint family to). Phase-6's `test_blueprint` seam rides this
same window but its decision is already carried by
[ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md) — per the
ADR-0011 precedent, this ADR freezes **no** port shape for it.
**Related:** [ADR-0006 component protocols](0006-subject-coach-component-protocols.md) ·
[ADR-0011 learner read port](0011-subject-coach-engine-learner-read-port.md) ·
[ADR-0012 context contract + hint ladder](0012-subject-coach-context-contract-hint-ladder.md) ·
[Phase-4 plan section](../plan/subject-coach-agent.plan.md)
**Audience:** anyone adding an engine content family, wiring the quiz hint panel, or
building the Phase-4 generator/verifier cascade.

---

## Context

ADR-0012 pinned the hint-ladder contract (rungs 1..3 probe→conceptual→directive, **no
assertion rung**, pre-submit hint content only from `reviewed = true` leak-checked rows —
spec FR-12/FR-20) and committed the serving surface — `hint` table + wire entity +
read seam — to the next ADR-0006 amendment, shipping authored interim rungs as a
backend-readable data asset (`components/subject_coach_hints.py`) until then.

Phase 4 (the generator milestone) is that amendment's trigger: generated rows need a
review-gated home, and TWO consumers now exist for reads — the quiz hint panel
(FR-D5's `socraticHint()` placeholder at `app/(coach)/learn/quiz/page.tsx`) and the
coach persona's context render (FR-20: paraphrase a reviewed rung, never free-generate).
The four-layer "build on the second consumer" rule is satisfied.

---

## Decision

1. **One new read-only engine port — `HintRepo`** (`frontend/lib/ports/engine/hint_repo.ts`,
   F-R3 one interface per module): `list(subject, questionId): Promise<Hint[]>` returning
   **`reviewed = true` rows only**, ordered by `rung` ascending. No write surface on the
   port: rows are written by the generator/importer path (composition-side), mirroring
   `QuestionRepo`'s posture where serving code can never flip the gate.
2. **`hint` table in BOTH dialects** (`schema.sqlite.ts` + `schema.pg.ts`, added to
   `ENGINE_TABLE_NAMES`): `{id, subject, question_id, rung (1..3), body_md, reviewed
   (default false), generated_by}` — spec §data table row. **Unique on
   `(question_id, rung)`**: the ladder has exactly one rung per level, so the assembler
   never has to disambiguate.
3. **`Hint` Zod wire entity** (`frontend/lib/wire/engine_entities.ts`), following the
   `Question` conventions exactly: snake_case fields, `HintSchema` + inferred `Hint`
   co-export, rung as `z.union([z.literal(1), z.literal(2), z.literal(3)])` so the
   assertion rung stays **unrepresentable** at the wire (the ADR-0012 posture, matching
   the Python `HintRung Literal[1,2,3]`).
4. **Provenance is a row fact:** `generated_by` is `"authored"` for the interim ladder
   rows and `"<model>@<run_id>"` for generator output (plan Phase 4). `reviewed = true`
   is **earned by the verifier cascade** (schema-parse → deterministic per-rung leakage
   check → duplicate/similarity), never asserted by the generator; imported/authored rows
   seed `reviewed = true` only because the authored ladder was already leak-checked
   under ADR-0012.

The dual-literal defense stays: the Python plane keeps its own leakage/answer-field
literals (`components/coach_context.py`); nothing imports across the language boundary.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **`getHints` on `QuestionRepo`** | Couples two content families behind one port; the hint family has its own review/provenance lifecycle and its own consumers. Violates the single-responsibility seam that made `Grader` separate. ❌ |
| **Rungs as a JSON column on `question`** | No per-rung `reviewed`/`generated_by` — breaks FR-12's row-level gate and quarantine (a failed rung would poison the whole question's review state). ❌ |
| **Serve via `ContentRepo`** | That port is objective-plane UI strings (labels, locales), not review-gated learner content. ❌ |
| **Bundle `TestBlueprintRepo` now** | ADR-0011's amendment precedent: don't freeze a port shape before its consumer lands (Phase 6). ADR-0013 already carries the blueprint decision; its seam arrives with Phase 6. ❌ |
| **Write surface on the port (`save(Hint)`)** | Serving code must never be able to flip `reviewed`; writes belong to the generator/importer at the composition boundary, like the seed path. ❌ (revisit if an in-app review UI ever lands) |

---

## Rationale

This is the smallest surface that satisfies FR-12 (row-level review gate), FR-20
(reviewed-rungs-only serving), and FR-D5 (the quiz hint panel), while applying — not
inventing — the ADR-0006 pattern: one narrow port per responsibility, mock+real
conformance bundle, SDKs confined to adapters, composition-root injection. Read-only
port + unique `(question_id, rung)` gives both consumers a deterministic ladder with no
serving-time policy logic.

---

## Consequences

**Commits us to:**
- `frontend/lib/ports/engine/hint_repo.ts` + in-memory and Drizzle adapters + the
  conformance test bundle (mock + real), wired through `buildEngineAdapters()`.
- The FR-12 regression: an **ungated (`reviewed = false`) row is never served** — pinned
  at the adapter conformance level, mirroring `nextReviewed`'s double-enforcement.
- Phase-4 generator writes rows `reviewed = false` and only the verifier cascade
  (deterministic leakage check first; judge assist only after the ADR-0008 cond#1 κ
  floor certifies) flips them.
- The authored ladder (`components/subject_coach_hints.py`) becomes the table's seed
  content (`generated_by = "authored"`); the Python asset stays authoritative for the
  backend persona render until the backend reads generated rows by another decided path.

**Accepted risks / mitigations:**
- *Two serving planes (frontend table, backend Python asset) can drift* → the seed is
  generated FROM the Python asset (single source), and the Phase-4 cascade re-verifies
  every row on import; a parity test compares the seed to the asset.

  > **Amendment (2026-07-07, coach-bank-hints).** The source direction above is
  > INVERTED for generated bank ladders: the canonical source is now the
  > cascade-earned corpus `docs/plan/coach-bank-hints.seed.json`, from which
  > `scripts/emit_hint_bank.py` deterministically emits BOTH serving planes —
  > `frontend/lib/adapters/engine/_hint_bank.ts` and
  > `components/subject_coach_bank_hints.py` (parity-pinned to the JSON on each
  > side). The hand-authored `AUTHORED_RUNGS` stay in place (their `q-*` ids are
  > inert since ADR-0021 removed the dev questions); `rungs_for_question` serves
  > AUTHORED + BANK. The two-plane drift risk is closed by construction (one
  > source, two generated artifacts) rather than by the retired parity pin.
  > See [coach-bank-hints spec](../plan/coach-bank-hints.spec.md) FR-B1..B3/D1.

  > **Amendment (2026-07-17, ADR-0031).** Unique key is now
  > `(question_id, choice_letter|null, rung)` with nullable `choice_letter` on
  > the wire/table/`HintRung`. `list()` defaults to the item-level
  > (`choice_letter IS NULL`) ladder. Rung 4 remains unrepresentable at the
  > wire; the emitter strips it. See [ADR-0031](0031-hint-choice-letter-uniqueness.md).
- *`generated_by` free-text* → format pinned by the wire entity's regex-free string but
  asserted in the cascade ("authored" | "model@run_id"); tighten to a union if a third
  producer appears.
