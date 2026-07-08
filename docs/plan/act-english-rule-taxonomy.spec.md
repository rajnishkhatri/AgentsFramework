# Spec — ACT-English item `rule_type` taxonomy (D5)

**Status:** Draft — 2026-07-08
**Owner:** Rajnish Khatri
**Related:** [act-english-bank-phase-b.spec.md](act-english-bank-phase-b.spec.md) ·
[act-english-topic-taxonomy.spec.md](act-english-topic-taxonomy.spec.md) (D4 — the
emitter reopening this piggy-backs on) ·
[coach-item-bank-live.spec.md](coach-item-bank-live.spec.md) ·
ADR-0014 (single-source-corpus emitter seam) · ADR-0015 (cascade provenance)

---

## 1. Goal

Give every bank item's `rule_md` a machine-readable **type** — `fact`, `procedure`, or
`meta` — so the coach agent can decide *when* in a student's error to surface the rule,
instead of always dumping the same prose at the same moment. For the item author and the
coach, not the test-taker.

## 2. Context

External review of the Phase B bank (2026-07-08) observed that the `rule_md` field is
"doing real pedagogical work — essentially a worked heuristic — a strength most banks
lack," but that the rules are **inconsistent in type**: some are procedures ("strip the
prepositional phrase first"), some are facts ("rise-rose-risen"), and some are
meta-strategy ("goal questions aren't grammar questions"). A local classification pass
confirmed the types **cluster by skill** (s-punc → mostly fact, s-rhet → mostly meta,
s-style → mostly procedure) and are today only implicit in the prose.

Why the type matters for a *coach* (the reviewer's load-bearing point): the three types
answer three different student failures, and a good coach surfaces them at different
moments in the error —

| Rule type | Student gap it addresses | When the coach should surface it |
|-----------|--------------------------|----------------------------------|
| **fact** | recall gap — didn't know the pattern | *after* a wrong answer (remediation) |
| **procedure** | method gap — knew the fact, didn't apply the test | *at the decision point*, as a hint before committing |
| **meta** | framing gap — misread what the question is asking | *before* reading the choices (pre-empt the trap) |

This builds on the D3 syllabus substrate (each item already carries `standard_id`) and
should ride the **D4** emitter change, which already reopens the two-plane emitter to add
`standard_id` + FSRS `StandardState` to the wire — so the emitter grows both new fields
once, not twice (per the gate decision 2026-07-08).

**Non-goal.** This spec does *not* build the coach surfacing logic (which hint fires
when). It defines the typed field + the authoring discipline + the emitter carry. The
consuming coach feature is downstream and gets its own spec.

## 3. Functional requirements (EARS)

- **FR-1.** THE SYSTEM SHALL define `rule_type` as a closed enum with exactly three
  members: `fact`, `procedure`, `meta`.
- **FR-2.** THE SYSTEM SHALL require every canonical seed row to carry a `rule_type`
  drawn from that enum.
- **FR-3.** IF a seed row is missing `rule_type` or carries a value outside the enum,
  THEN the seed pre-flight SHALL fail, naming the offending row.
- **FR-4.** WHERE the D4 emitter emits an item to the serving plane, THE SYSTEM SHALL
  carry `rule_type` verbatim onto the emitted row (alongside `standard_id`).
- **FR-5.** THE SYSTEM SHALL classify each `rule_type` against a written rubric (§7) so
  that two authors tag the same rule identically — the enum member is determined by the
  rule's dominant *teaching move*, not by the item's skill.
- **FR-6.** IF a single `rule_md` mixes types (e.g. states a fact *and* prescribes a
  test), THEN the author SHALL either split the rule to its dominant move or tag it by
  the move the coach should surface *first* (procedure > meta > fact tie-break — the
  most actionable move wins), and this precedence SHALL be documented in the rubric.
- **FR-7.** THE SYSTEM SHALL back-classify all pre-existing bank rows (the 164 Phase B
  rows + any promoted corpus) so no row ships untyped once D5 lands.

## 4. Data model / contracts

New field on the canonical seed row and the emitted serving row:

```jsonc
{
  // ...existing item fields...
  "standard_id": 17,          // D4 (already specced)
  "rule_md": "Strip the prepositional phrase to find the true subject...",
  "rule_type": "procedure"    // D5 — NEW: "fact" | "procedure" | "meta"
}
```

- **Wire (TS) plane:** the emitted `_test_item_bank.ts` row gains `ruleType:
  'fact' | 'procedure' | 'meta'` (Zod enum in the wire kernel). No SDK type crosses the
  adapter boundary — it is a plain string-literal union.
- **Zod default-strip parity:** like `standard_id`, if the field is declared on the wire
  but a consumer doesn't need it yet, it stays corpus-side until a coach feature reads
  it. It SHALL NOT be stripped from the *canonical seed* (the seed is the source of
  truth; the wire is derived).
- The two-plane emitter's `_ROW_FIELDS` allowlist SHALL add `rule_type`; the CI drift
  test re-emits and byte-compares, so the field is carried deterministically.

## 5. Invariants & security boundaries

- **Invariant #3/#4 (framework-agnostic components/services):** `rule_type` is a plain
  enum string; no framework type introduced. Holds.
- **Frontend Ring:** the wire enum lives in `frontend/lib/wire/` (pure Zod kernel, zero
  outward deps); `ruleType` never originates in the browser. Holds.
- **ADR-0014 single-source seam:** the field is authored ONCE in the canonical seed and
  flows through the deterministic emitter to both planes — no second source of truth.
- No secrets, no live-LLM-in-CI, no trust-kernel type change. `rule_type` is bank
  metadata, not a `trust/models.py` type, so **no re-signing** triggered.

## 6. Migration steps

1. Land D4 first (it opens the emitter for `standard_id` + `StandardState`).
2. Add `rule_type` to the pre-flight schema assertion (red first: assert every row
   typed; watch 164 rows fail; then back-fill).
3. Author the §7 rubric; back-classify all rows (FR-7) via an authoring pass — human or
   Claude-assisted with the rubric, but every tag is author-owned, not auto-inferred at
   emit time (the classification is pedagogical judgment, not a regex).
4. Extend the emitter `_ROW_FIELDS` + wire Zod enum; re-emit; byte-compare drift test.
5. Update the emitter golden fixtures to include `ruleType`.

## 7. Classification rubric (the taxonomy definition)

The enum member is chosen by the rule's **dominant teaching move**, independent of skill:

- **`fact`** — a declarative pattern to *recall*. Recognizable as something a student
  either knows or doesn't; no in-the-moment test to run. *Examples:* "rise-rose-risen;
  helpers take the third form" · "loose rhymes with goose, lose with snooze" · "City,
  State takes a closing comma."
- **`procedure`** — an imperative *test or step* to run at the point of doubt.
  Recognizable by an action verb the student performs on the sentence. *Examples:*
  "Strip the prepositional phrase to find the true subject" · "Test with he/him: HE →
  who, HIM → whom" · "Expand 'it is' in the slot; if it fails, write its."
- **`meta`** — a strategy about *the question type itself*, surfaced before the student
  even evaluates choices. Recognizable because it reframes what's being asked rather than
  operating on the sentence. *Examples:* "Goal questions aren't grammar questions — grade
  each choice against the stated purpose" · "Identify the passage's register first" ·
  "Read the body before choosing a topic sentence."

**Tie-break (FR-6):** a rule carrying more than one move is tagged by the move the coach
should surface *first* — **procedure > meta > fact** (most actionable first). Prefer
splitting the rule over stacking moves.

## 8. Acceptance tests (map 1:1 to FRs)

- **T-1 (FR-1,2,3):** pre-flight fails a row with missing/invalid `rule_type`, passes a
  fully typed seed. *(red-first: assert on the current 164-row seed → all fail untyped)*
- **T-2 (FR-4):** emitter fixture round-trip carries `ruleType` byte-identically to the
  TS plane; drift test green.
- **T-3 (FR-5,6):** rubric-conformance spot check — a fixed sample of rules, each with
  its expected tag, re-derived by a second reader matches (the "unit test for the
  taxonomy"); documented tie-break precedence honored.
- **T-4 (FR-7):** zero untyped rows in the shipped bank (`count(rule_type is None) == 0`).

## 9. Definition of done

- [ ] `rule_type` enum defined; pre-flight asserts it (FR-1–3).
- [ ] All 164+ rows back-classified per the §7 rubric (FR-7); zero untyped.
- [ ] Emitter carries `ruleType` to the wire; drift + golden tests green (FR-4).
- [ ] Rubric committed; a second-reader conformance sample agrees (FR-5).
- [ ] `docs/adr/decisions.md` entry recording the three-type taxonomy + tie-break.
- [ ] Spec Status → Implemented.

## 10. Open questions

- Does the coach surfacing feature want a *fourth* type for the `why_tempted_md`
  distractor-diagnosis (an "error-pattern" type), or is that field's job orthogonal to
  `rule_type`? (Defer to the coach-surfacing spec.)
- Should `rule_type` influence the **cascade dup-gate** — i.e. are two items with
  identical `(standard_id, rule_type)` and high stem-Jaccard *more* redundant than the
  Jaccard alone suggests? (The Q33/Q35 redundancy that motivated this was exactly a
  shared-rule cluster.) Possible T7 promotion refinement; out of scope here.
