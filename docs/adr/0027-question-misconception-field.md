---
type: decision-record
title: 'ADR-0027: Question.misconception — nullable authored one-line field on the item-bank cascade'
status: accepted
created: 2026-07-10
updated: 2026-07-10
owner: Rajnish Khatri
related: docs/plan/preact-parity-C2-summary-payoff.spec.md, docs/plan/preact-parity-sprint-board-C.md, docs/adr/0021-bank-backed-practice-scheduler.md, docs/adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md
tags: [decision-record, epic-c, summary-payoff, wire, item-bank]
---

# ADR-0027: `Question.misconception` — nullable authored one-line field on the item-bank cascade

**Status:** Accepted — 2026-07-10 (ratified at the C2 tasks→implement human gate).
**Related:** [C2 summary-payoff spec](../plan/preact-parity-C2-summary-payoff.spec.md), [Epic C sprint board](../plan/preact-parity-sprint-board-C.md), [ADR-0021 (bank-backed practice)](0021-bank-backed-practice-scheduler.md), [ADR-0015 (`test_item` bank)](0015-subject-coach-test-item-bank-blueprint-read-seam.md).
**Audience:** Anyone extending Summary payoff copy, the item-bank cascade, or the `Question` / `TestItem` wire shape.

---

## Context

Epic C sprint C2 closes the Summary "misconception payoff" gap
([spec §1](../plan/preact-parity-C2-summary-payoff.spec.md)): turn
`/learn/summary` into the prototype's coaching payoff surface — framed
title, misconception accent card when authored, drill recommendation, and
the three-actions row.

The Stage-1 brainstorm
([preact-parity-epic-C.brainstorm.md](../plan/preact-parity-epic-C.brainstorm.md))
**refuted** the naïve premise that misconception "comes from the coach."
No engine seam produces it today. Direction **D4** landed: carry
misconception as author-captured metadata on the item the learner missed,
not as a runtime coach synthesis.

Three forces:

1. **Honesty (C-4 / AP-6).** Summary must never claim "I spotted a
   misconception" without an author signal. Absent → no card (honest-absent).
2. **Determinism.** The payoff must derive from the session's misses +
   authored fields — no LLM on the Summary render hot path.
3. **Cascade precedent (ADR-0021 / ADR-0015).** Practice items already flow
   `test_item` → `TestItem` wire → `TestItemQuestionRepo` → `Question`. A
   new nullable field rides that same cascade; inventing a parallel home
   would split the content contract.

G1 fires: new wire field + new corpus contract = new derivation path. This
ADR is the required record.

---

## Decision

Add a **nullable string** field `misconception` to:

1. The `Question` Zod wire entity (`frontend/lib/wire/engine_entities.ts`).
2. The `TestItem` Zod wire entity (same file — bank storage shape).
3. The `test_item` Drizzle column (both dialects) — `text("misconception")`,
   nullable, no default required.
4. The item-bank emit cascade (`promoted.json` → `emit_test_item_bank.py` →
   `_test_item_bank.ts`) so every row carries the key (`null` or string).

Summary derives the card from the **most-recent session miss on the
recommended-next skill** whose `Question.misconception` is non-null after
empty-string normalization. No new port method; no new abstraction beyond
the field itself.

---

## Options considered & rejected

| # | Option | Verdict | Why it lost |
|---|--------|---------|-------------|
| (a) | LLM-synthesize misconception at Summary render time | Rejected | Violates C-4 honesty (would claim "I spotted…" with no author signal); puts an LLM call on the render hot path. |
| (b) | Attach to `Skill` | Rejected | Skill-level blurs item-specific copy ("conciseness overrode punctuation") back to the skill name. |
| (c) | Attach to `Attempt` at grade time | Rejected | Post-hoc; no author signal; invents a write on the grade path for display copy. |
| (d) | D5 Coach-runtime marker | Rejected (Stage 1) | Only fires when the learner used the coach — adoption gap vs "everyone who missed." Keep as future variant if D4 falters. |
| (e) | `Question.misconception_id` FK → separate `misconception` table | Rejected | Over-abstracted; a nullable TEXT column suffices for the one-line prototype copy. |

---

## Rationale

D4 wins because it is **author-honest**, **deterministic**, and **cascade-native**.
The prototype's payoff copy is item-specific one-liners; a nullable TEXT on
the bank row is the smallest change that preserves C-4 and reuses ADR-0021's
`TestItem` → `Question` mapping. Rejected alternatives either invent honesty
debt (a/c), blur specificity (b), under-serve the audience (d), or over-build
(e).

---

## Consequences

- **Additive wire + column.** Existing rows parse with `misconception: null`;
  migration is `ALTER TABLE … ADD COLUMN misconception text` (nullable).
- **Content pass is probe-gated.** C2 authors K rows where `why_tempted_md`
  already implies a one-line misconception; K==0 → code-only ship, content
  follow-up track (spec §12 Q2).
- **No new port.** Hook derives via existing `AttemptRepo.misses` +
  `servedQuestionIds` + `QuestionRepo.get` (G1 abstraction-introduction
  upheld).
- **Accepted risk.** Until content authors fill rows, the card is honestly
  absent for most sessions — correct under AP-6, not a bug.
- **Follow-on.** D5 coach-runtime marker remains a named future variant if
  authored coverage stays thin.

---

## Supersedes / related

- Realizes [preact-parity-C2-summary-payoff.spec.md](../plan/preact-parity-C2-summary-payoff.spec.md).
- Extends the ADR-0021 bank → Question cascade; does not supersede ADR-0015
  table separation.
- Companion small decisions (threshold 0.6, half-split self-correction,
  FLAG-5 soft-gate, probe K) land in `docs/adr/decisions.md` at C2 T8.3.
