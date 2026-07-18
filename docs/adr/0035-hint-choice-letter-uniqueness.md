---
type: decision-record
title: 'ADR-0035: Hint.choice_letter + uniqueness (question_id, choice_letter, rung); rung 4 stays off wire'
status: accepted
created: 2026-07-17
updated: 2026-07-17
owner: Rajnish Khatri
related: docs/adr/0012-subject-coach-context-contract-hint-ladder.md, docs/adr/0014-subject-coach-hint-repo-read-seam.md, docs/questionbank/coach-bank-gen2-repair-and-aql.md, .claude/skills/synthetic-data-pipeline/SKILL.md
tags: [decision-record, hint, wire, emit, gen2]
---

# ADR-0035: `Hint.choice_letter` + uniqueness `(question_id, choice_letter, rung)`

**Status:** Accepted — 2026-07-17 (Step-6 emitter/schema for Gen2 choice-conditional ladders).
**Related:** [ADR-0012](0012-subject-coach-context-contract-hint-ladder.md) · [ADR-0014](0014-subject-coach-hint-repo-read-seam.md) · [Gen2 repair + AQL](../questionbank/coach-bank-gen2-repair-and-aql.md) · synthetic-data-pipeline Step 6.
**Audience:** Anyone emitting hint banks, extending `HintRepo`, or promoting Gen2 ladders.

---

## Context

Gen1 hints are **item-level**: one ladder of rungs 1–3 per question, unique on
`(question_id, rung)` (ADR-0014). Gen2 hints are **choice-conditional**: three
wrong-letter ladders × four rungs (pump → hint → prompt → assertion), every row
carrying `choice_letter ∈ {A,B,C,D}`.

`scripts/emit_hint_bank.py` hard-fails on Gen2 even after Step-5 ACCEPT:
duplicate `(question_id, rung)` across letters, and rung 4 is rejected by the
wire union. The synthetic-data-pipeline skill names this an ⚠️ Ask-first/ADR
gap — not a quick edit.

ADR-0012 still forbids an **assertion rung on the pre-submit wire**. Rung 4
stays in the Gen2 corpus for lint/review; it must never become a `Hint` wire
literal.

---

## Decision

1. **Add nullable `choice_letter`** to the `Hint` Zod wire entity, both Drizzle
   dialects (`hint` table), Python `HintRung`, and the emit corpus row shape.
   Values: `null` (item-level Gen1 ladder) or `"A"|"B"|"C"|"D"` (choice-conditional).
2. **Uniqueness** becomes `(question_id, choice_letter, rung)` with a
   NULL-safe index strategy: dual partial unique indexes —
   `(question_id, rung) WHERE choice_letter IS NULL` and
   `(question_id, choice_letter, rung) WHERE choice_letter IS NOT NULL` —
   so Gen1 item-level rows still collide on duplicate rung levels.
3. **Wire rung stays `1|2|3` only.** The emitter **strips** `rung == 4` rows
   before validation/emit (they remain in the source JSON for QA). Never extend
   the Zod/Pydantic rung union to 4.
4. **`HintRepo.list` / `listReviewedHints` default to the item-level ladder**
   (`choice_letter IS NULL`). An optional `choiceLetter` argument selects a
   choice-conditional ladder. Omitting it preserves today’s quiz/coach Gen1
   consumers even if choice-conditional rows are later seeded.
5. **Emit is the single-source seam** (`emit_hint_bank.py`): Gen1 seed rows
   without the field normalize to `choice_letter: null`; Gen2 reviewed rows
   emit rungs 1–3 with their letter. Regenerated `_hint_bank.ts` /
   `subject_coach_bank_hints.py` stay byte-stable for a given corpus.

Amends ADR-0014 clause 2 (unique key) and clause 3 (wire fields); does **not**
reopen ADR-0012’s no-assertion-rung-on-wire posture.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **Extend wire rung to 4** | Violates ADR-0012 pre-submit no-assertion contract; assertion belongs post-feedback / server-side corpus only. ❌ |
| **Keep unique `(question_id, rung)` and collapse Gen2 to one ladder** | Destroys the Gen2 pedagogy (per-wrong-letter unstick). ❌ |
| **Separate `choice_hint` table** | Splits one content family; doubles ports/emit paths for the same ladder ontology. ❌ |
| **Empty-string sentinel instead of NULL** | Works for one unique index, but lies on the wire (`""` ≠ “no letter”); NULL + partial indexes match the adoption lock (P0.5). ❌ |
| **Ship Gen2 items with FR-E1 waivers and never extend schema** | Unblocks items only; leaves reviewed Gen2 hints permanently unservable. ❌ as the end state (waivers remain OK as a temporary sequencing tool). |

---

## Rationale

Smallest change that lets Step-6 emit Gen2 **rungs 1–3** without breaking Gen1
or ADR-0012: one additive nullable field, a uniqueness amendment, strip rung 4
at the emit boundary, and a default list filter that keeps existing consumers
on the item-level ladder until the moment router (wrong-pick → letter ladder)
lands.

---

## Consequences

- **Additive migration:** `ALTER TABLE hint ADD COLUMN choice_letter text NULL`;
  drop `hint_question_rung_uq`; add the two partial unique indexes (both
  dialects / on-device stores).
- **Emitter contract change:** rung 4 is stripped (not rejected); duplicate
  detection keys on `(question_id, choice_letter|null, rung)`.
- **Consumers:** quiz/`CoachPanel` keep calling `list(subject, qid)` → item-level
  only. Choice-conditional serving is a follow-on (moment router) that passes
  `choiceLetter`.
- **FR-E1 coverage ratchet:** still requires rungs 1–3 for the **item-level**
  (null-letter) ladder; choice-conditional coverage is a separate ratchet when
  Gen2 items enter `TEST_ITEM_BANK`.
- **No trust-kernel change / no re-sign.** No new dependency. No live LLM in CI.

---

## Supersedes / related

Amends [ADR-0014](0014-subject-coach-hint-repo-read-seam.md) (unique key + wire
fields). Preserves [ADR-0012](0012-subject-coach-context-contract-hint-ladder.md)
rung-4-off-wire. Unblocks synthetic-data-pipeline Step 6 hint emit for Gen2
after Step-5 ACCEPT.
