---
type: decision-record
title: 'ADR-0015: Subject-Coach test-item content family — governed bank + TestBlueprint read seam (test_item/test_blueprint tables + two read-only ports)'
status: accepted
created: 2026-07-03
updated: 2026-07-03
owner: Rajnish Khatri
related: 0006-subject-coach-component-protocols.md, 0013-subject-coach-test-mode-blueprint-generation-integrity.md, 0014-subject-coach-hint-repo-read-seam.md, subject-coach-agent.plan.md
tags: [decision-record]
---

# ADR-0015: Subject-Coach test-item bank + TestBlueprint read seam

**Status:** Proposed — 2026-07-03. Amends [ADR-0006](0006-subject-coach-component-protocols.md)
(third amendment — the window [ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md)
§Consequences committed the `test_blueprint` schema to: "rides the ADR-0006 amendment
train, never a silent add"). This ADR **realizes** ADR-0013's ratified decisions in
schema/port shape; it re-decides nothing — the integrity stance (Option A + tripwires),
the cascade stages, and the seeded-assembler contract are all carried by ADR-0013.
**Related:** [ADR-0006 component protocols](0006-subject-coach-component-protocols.md) ·
[ADR-0013 Test Mode integrity + blueprint](0013-subject-coach-test-mode-blueprint-generation-integrity.md) ·
[ADR-0014 hint read seam](0014-subject-coach-hint-repo-read-seam.md) (the structural precedent) ·
[Phase-6 spec](../plan/coach-test-mode-governed-plane.spec.md) ·
[Phase-6 plan section](../plan/subject-coach-agent.plan.md)
**Audience:** anyone building the test-item generator/importer, the seeded assembler, or
a future assembled-form serving path.

---

## Context

ADR-0013 (accepted 2026-07-02, condition MET) ratified test items as the generator's
**second content family** (cascade: schema-parse → answer-key self-consistency, the
critical gate → duplicate/similarity; hint-leakage rung N/A), a `TestBlueprint` +
deterministic seeded assembler over the `reviewed=true` bank, and the demotion of
`convert:test01` to a seed importer whose rows enter `reviewed=false`. It deliberately
left the port/table shape to this amendment (ADR-0011 build-on-consumer precedent —
ADR-0014 explicitly declined to bundle it).

Phase 6 is the consumer arriving: the assembler needs a reviewed-only bank read, and the
generator/importer need a review-gated home for rows. The clarified Phase-6 spec
([coach-test-mode-governed-plane.spec.md](../plan/coach-test-mode-governed-plane.spec.md))
pins the scope: **governed plane only** — `/learn/test` keeps serving the frozen
`_test01_english_corpus.ts` fixture, so ADR-0013's delivery tripwire stays unfired.

---

## Decision

1. **Separate `test_item` table** in BOTH dialects (`schema.sqlite.ts` + `schema.pg.ts`,
   added to `ENGINE_TABLE_NAMES`) — Question-shaped fields (stem, choices, the four
   answer-bearing fields) + `{subject, skill_id, difficulty, reviewed (default false),
   generated_by}`, with a deterministic content-hash `id` (idempotent generator re-runs,
   the `hint_generation.py` precedent). **NOT rows in `question`**: the practice plane's
   `DrizzleQuestionRepo.nextReviewed` scheduling must be structurally unable to serve an
   exam item — separation by table, not by a filter every query must remember.
2. **`test_blueprint` table** in BOTH dialects: `{id, subject, skill_mix,
   difficulty_dist, count, minutes, scale_band_table, pass_criteria?, seed}` (the
   ADR-0013 §8.2 shape verbatim; `seed` on the row so a form is byte-reproducible from
   `(blueprint_id, seed)` **within a single bank state**). Byte-identity holds for a fixed
   seed over a fixed bank (FR-26.2's 10× audit runs over a frozen fixture bank); a bank
   append changes the reviewed set and so may change the draw for the same seed. There is
   no `bank_version` field: reproducibility-*across* bank growth is a serving-time concern
   (record the assembled item content-hash ids on the served form), owned by the future
   ADR-0013 delivery-tripwire re-open — not a schema commitment Phase 6 makes for a serving
   path it deliberately does not build.
3. **Two new read-only engine ports** (ports 10 + 11; F-R3 one interface per module; no
   write surface — the ADR-0014 posture: serving code can never flip `reviewed`):
   - `TestBlueprintRepo.get(id): Promise<TestBlueprint | null>`
   - `TestItemRepo.listReviewed(subject): Promise<TestItem[]>` — **`reviewed=true` rows
     only**, the FR-27 repo-level gate (the assembler filters again, independently).
4. **`TestItem` + `TestBlueprint` Zod wire entities** (`frontend/lib/wire/engine_entities.ts`),
   following the `Question`/`Hint` conventions: snake_case, Schema + inferred-type
   co-export, validation rejecting malformed blueprints at parse (skill-mix weights
   summing to 1.0, `count > 0`, non-empty `scale_band_table`).
5. **`reviewed=true` is earned in the Python cascade only** (`components/test_item_generation.py`,
   mirroring `hint_generation.py`): the answer-key gate is an **independent LLM solver
   pass** (stem + choices only; the declared key withheld) confirmed by a Python
   exact-letter comparator mirroring `ExactLetterGrader` semantics (the TS grader is not
   importable across the language boundary — the dual-literal defense stays). Mismatch or
   undecidable → quarantine, never a fabricated pass.
6. **Importer path = TS parse → Python promotion:** `convert_test01_english.ts` keeps its
   oracle-tested parser but emits a neutral `reviewed=false` seed
   (`generated_by="test01-import"`); a Python job runs the same FR-23 cascade over the
   seed and emits the promoted rows. On promotion the cascade **re-stamps
   `generated_by="<model>@<run_id>"`** (ADR-0013 clause 1: "`generated_by = "<model>@<run_id>"`
   replaces `"test01-convert"`") — so `"test01-import"` lives **only on `reviewed=false`
   seed rows**, and the served (`reviewed=true`) bank carries exactly the two
   generator-family values. Import lineage is not lost: the demotion→promotion transition
   is recorded in the cascade `eval_capture` stream (spec §7 auditability is satisfied by
   the eval record, not by a persisted origin column). One cascade implementation for
   generated and imported items alike. `_test01_english_corpus.ts` stays byte-frozen (e2e
   fixture + the Option-A serving source).

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **Test items as `question` rows + discriminator column** | Every practice-path query must filter correctly forever; one missed filter serves an unreviewed exam item into quiz scheduling. Table separation makes the leak unrepresentable. ❌ |
| **Wire assembled forms into `/learn/test` now** | Moving the served corpus off the static bundle **is** ADR-0013's delivery tripwire — it drags the whole Option-B key-delivery migration into Phase 6. Serving is a separate, tripwire-evaluating product step. ❌ |
| **Deterministic-only answer-key gate** (key ∈ choices, well-formed) | Cannot catch a plausible-but-wrong declared key — the exact failure class the "critical gate" exists for (engine FR-E2). Structural checks stay, in the schema stage. ❌ |
| **TS twin of the cascade for the importer** | Two cascade implementations to hold in parity — the drift risk ADR-0014 already flagged for two serving planes, now on the *gate* itself. ❌ |
| **One combined port (`TestModeRepo`)** | Blueprint and item have different consumers and lifecycles (config vs review-gated content); F-R3 one-interface-per-module, same reason `Grader` is separate. ❌ |
| **Write surface on either port (`save(...)`)** | Serving code must never flip `reviewed`; writes belong to the generator/importer at the composition boundary (ADR-0014 precedent). ❌ (revisit if an in-app review UI lands) |
| **Python-side bank (backend asset, like the interim hint ladder)** | The bank's only consumer (assembler) is client-side under Option A (design §8.2); the generator writes THROUGH the seed path like hints. A backend-authoritative bank buys nothing until Option B moves assembly server-side. ❌ |

---

## Rationale

Smallest surface satisfying FR-23..27: the two tables give generated/imported rows a
review-gated home; the two read-only ports apply — not invent — the ADR-0006 pattern
(narrow port per responsibility, mock+real conformance, composition-root injection); the
single Python cascade keeps `reviewed` provable at one seam. Scope discipline (no serving
change) keeps ADR-0013's Option A posture and its code-enforced tripwire untouched.

---

## Consequences

**Commits us to:**
- `frontend/lib/ports/engine/test_blueprint_repo.ts` + `test_item_repo.ts`, in-memory +
  Drizzle adapters with conformance bundles, wired through `buildEngineAdapters()`.
- The FR-27 regression pinned at BOTH layers: adapter conformance (repo never returns
  `reviewed=false`) and assembler unit tests (independent filter).
- `components/test_item_generation.py` cascade + `scripts/generate_test_items.py`
  governed job (identity/capability/eval-stream/guardrail overrides mirroring
  `scripts/generate_hints.py`), quarantine rows + `eval_capture`
  (`target="test_item_generator"`).
- The assembler as a pure client-side engine function over `(blueprint, bank_rows)` —
  deterministic: internally sorts bank rows by content-hash id before the seeded
  stratified draw, so byte-identity never depends on query order.
- A **write-confinement arch test** (mirroring `test_no_client_served_test_keys.py`'s
  shape): every `reviewed=true` `test_item` row in any checked-in seed MUST carry a
  `generated_by` matching the `<model>@<run_id>` cascade format. This is the code-enforced
  backstop for "`reviewed=true` is earned in the cascade only" (the ADR-0011 lesson: a
  prose-only integrity claim rots). It works *because* promotion re-stamps provenance
  (clause 6) — a hand-authored or migration-written `reviewed=true` row would carry a
  non-conforming `generated_by` and fail the test. (The check must allow the legitimate
  non-cascade producers already in `_dev_seed.ts` — `"dev-seed"`/`"authored"` — for the
  `question`/`hint` families; the `test_item` family admits only the cascade format.)
- ADR-0006 header gains the third amendment pointer on acceptance.

**Accepted risks / mitigations:**
- *Solver gate is a live LLM call* → on-demand jobs only (never CI, never the learner hot
  path); undecidable → quarantine; cost is 1 call per candidate item.
- *Solver–generator shared misconception* → the gate is prompt-independent (declared key
  withheld) but not automatically model-independent: a generator and solver of the same
  family can share a wrong key. The solver SHOULD be a different model/tier than the
  generator; a different family *reduces* (does not eliminate — correlated training
  corpora) the shared-misconception residual, which is a named accepted risk.
- *Schema duplication `question`↔`test_item`* → `test_item` duplicates most MC-item
  columns; a future answer-bearing field lands in two tables. Accepted: the leak-
  unrepresentable separation (clause 1) dominates DRY here.
- *Write path is indirect* → promoted rows reach the DB as Python cascade → seed file →
  frontend composition-time Drizzle insert (the hint precedent), never a live backend
  write. `_test01_english_corpus.ts` is untouched.
- *Cold-start / thin bank* → blueprints are authored against actual reviewed coverage; a
  skill_mix naming a zero-reviewed skill fails closed at assembly (FR-26.1), by design.
- *TS↔Python `TestItem` shape drift* (no CI parity gate exists for engine entities) →
  the seed crosses the boundary as data validated on BOTH sides (Zod at import, Pydantic
  in the cascade); the FR-25.2 seed-roundtrip test asserts a Python-emitted promoted row
  parses under the Zod `TestItem` schema (shape closure across the boundary), and a
  separate parity-pin test compares comparator fixtures to `exact_letter_grader.ts`
  behavior (grader-semantics closure).
- *Bank staleness vs the frozen fixture* → the fixture is the serving source of truth
  under Option A; the bank is generation-plane state. Divergence is expected and
  harmless until the delivery tripwire evaluation, which re-opens ADR-0013 by design.
