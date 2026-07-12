---
type: decision-record
title: 'ADR-0028: Lesson content read path — Tutorial teaching fields + TutorialRepo/ProgressRepo read ports + authored-seed provenance'
status: proposed
created: 2026-07-11
updated: 2026-07-11
owner: Rajnish Khatri
related: preact-parity-epic-E1a.spec.md, 0005-subject-coach-engine-home-and-substrate.md, 0014-subject-coach-hint-repo-read-seam.md, 0015-subject-coach-test-item-bank-blueprint-read-seam.md, 0021-bank-backed-practice-scheduler.md, 0027-question-misconception-field.md
tags: [decision-record]
---

# ADR-0028: Lesson content read path — Tutorial teaching fields + TutorialRepo/ProgressRepo read ports + authored-seed provenance

**Status:** Proposed — 2026-07-11.
**Related:** [preact-parity-epic-E1a.spec.md](../plan/preact-parity-epic-E1a.spec.md) (the *what*); design contract [`PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md`](../../eng-coach-ui-design/e1-learn-skill-delivery/specs/PreACT-English-Coach-v2-E1-LearnSkill-Implementation-Spec.md); amends the ADR-0005 engine substrate; mirrors the ADR-0014 / ADR-0015 read-seam pattern.
**Audience:** anyone reconsidering where lesson content lives, how the `/learn/skill` surface reads it, or how it earns `reviewed=true`.

---

## Context

Epic E1a ships `/learn/skill`, the adaptive-lesson surface. It renders one skill's
content in a different ordered block sequence per learner **context** (`newSkill` /
`returning` / `refresher`). Three Ask-first triggers fire and each needs a *why* on the
record (root `AGENTS.md`: new persistence surface, new abstraction, deviation from an
invariant):

1. **Where does the durable lesson content live?** The design contract's D5 says: add
   *optional typed teaching fields* to skill content, and do **NOT** persist
   `blocks[]`/`zone`/`role`/`context`/`beats` — block order is a render-time output, not
   authored content. The existing `Tutorial` wire type (`frontend/lib/wire/engine_entities.ts:273-282`)
   carries only `body_md` + `examples[]`; the six teaching blocks (`ground`, `pitfall`,
   `question`, `workedExample`, `completionTry`, `selfExplainPrompt`, `annotatedExample`)
   have nowhere to bind.
2. **How does the surface read it?** `EngineDb.getTutorial`/`listProgressPoints` exist
   (`engine_db.ts:160-161`, both InMemory + Drizzle) but are the **only unwired engine
   reads** — absent from `EnginePortBag` (`composition_engine.ts:64-87`); no repo/port
   surfaces them.
3. **How does lesson content earn `reviewed=true`?** The hint (`hint_generation.py`) and
   item-bank (ADR-0021, `test_item_generation.py`) families earn the reviewed gate by a
   verifier cascade — never self-assertion. Lesson content needs the same discipline
   without forging a stamp.

Stage-2 grounding (workflow `wf_659b0811-763`, verified at HEAD) refuted three premises
carried into this decision from the Stage-1 brainstorms, each of which shaped the option
set below:

- **The D5 change is a Drizzle-schema change, not a Rule-W2 cross-language change.**
  `Tutorial` is explicitly exempt from the Python↔TS wire mirror (ADR-0005 local-first;
  the file header says so; it is absent from `baseline_drift.test.ts` `schemaIndex` and
  `__python_schema_baseline__.json`). The mechanical W2 gate does **not** fire.
- **No scheduler-pin work is needed** (so it is not in this ADR). `?focus=<skillId>`
  already pins drill mode via a separate path (`use_quiz.ts:177-225` → `questionRepo.nextReviewed`),
  bypassing the subject-agnostic `Scheduler.next()`. The "Practice this skill →" CTA is a
  plain link — zero engine change.
- **`accuracyStat` has no honest data source yet**, so its per-skill accuracy read is a
  follow-up, not part of this read path (`Attempt` carries no `skill_id`; no aggregation,
  chart primitive, or ≥6-session fixture exists). The block self-omits (D7).

---

## Decision

Ship the lesson content read path as one coherent unit:

1. **Add optional typed teaching fields to `Tutorial`** (candidate set: `ground_md`,
   `pitfall_md`, `question_md`, `self_explain_prompt`, and typed sub-objects
   `worked_example`, `completion_try`, `annotated_examples`), plus the matching Drizzle
   columns (`schema.pg.ts` + `schema.sqlite.ts`) and a migration. All fields **optional**
   — content without them is unaffected. Do **not** persist `blocks[]`/`zone`/`role`/
   `context`/`beats`; block order is composed at render time.
2. **Add two read-only ports** — `TutorialRepo.getTutorial(subject, skillId)` and
   `ProgressRepo.list(subject, learnerId)` — mirroring `HintRepo`/`DrizzleHintRepo`
   (single-method, read-only, `@throws EngineRepoError`), wired into `EnginePortBag`.
   Reads only; no write surface.
3. **Earn `reviewed=true` by a hand-authored + human-leak-checked seed** for the first
   drop, stamped `generated_from="hand:<author>@<date>"`, gated by a
   `test_tutorial_provenance_confinement.py` that mirrors `test_hint_provenance_confinement.py`
   (accepts `hand:<author>@<date>` | `llm:<model>@<promptrev>`, never a bare unstamped
   `reviewed=true`). The LLM generator cascade is the scale-up path, not this drop.

---

## Options considered & rejected

**Where lesson content lives (trigger 1):**

| Option | Verdict |
|---|---|
| **Optional teaching fields on `Tutorial` (chosen)** | Matches the in-file `Verdict` optional-field precedent (`engine_entities.ts:303-309` — fields added incrementally, absent when unused); zero W2-gate work (Tutorial is out of scope for `baseline_drift.test.ts`); matches D5's "durable artifact stays close to existing content." |
| New `LessonPlan` wire type | Rejected: zero code precedent; the wrong shape for D5-as-ratified (no `blocks[]`/`beats` persisted); would force a new-file/new-abstraction decision for no gain. |
| Persist `blocks[]`/`zone`/`role`/`context`/`beats` | Rejected by D5: block order is a render-time composer output, not authored content (`DATA-BLK-6`). Persisting it couples the content store to one UI's composition. |

**How the surface reads it (trigger 2):**

| Option | Verdict |
|---|---|
| **`TutorialRepo` + `ProgressRepo` read ports (chosen)** | Mirrors the ADR-0014 `HintRepo` and ADR-0015 read-seam pattern exactly (read-only, single-method); reads existing `EngineDb` methods; no schema change on the read side. |
| Call `db.getTutorial` directly from the surface | Rejected: bypasses the port layer every other capability uses; leaks the DB seam into components (Rule F-R1/A). |
| Add `insertTutorial` write method now | Rejected for E1a: no write path exists (`insertTutorial` = 0 grep hits; only `seedTutorial` on the test fake); the content-authoring write seam is a separate, larger decision (governed reviewed-gate vs. plain insert) and is deferred — E1a reads pre-seeded content. |

**How it earns `reviewed=true` (trigger 3):**

| Option | Verdict |
|---|---|
| **Hand-authored + reviewed single-skill seed (chosen)** | The hint family already treats `"authored"` as a legitimate non-cascade provenance (`test_hint_provenance_confinement.py:58-59`); honest, buildable today, zero new runtime components. |
| Full B2 generator cascade now (`tutorial_generation.py` + `.j2` + quality judge) | Rejected for the first drop: three Ask-first triggers at once (new component + new prompt + new judge), and **no lesson-prose quality/leakage lint exists** (`hint_leakage.py` is answer-leakage-specific to hint rungs; "leakage" is undefined at the skill-copy level). Correct **scale-up** path once the quality-judge question is resolved on its own ADR track. |
| Stamp `reviewed=true` on generated content without a cascade | Rejected: a forged provenance stamp — the exact anti-pattern the hint/item-bank confinement tests exist to prevent (AP-6 / "never forge a stamp"). |

**Adjacent decisions folded in (with their rejected alternatives):**

- **`accuracyStat` — build the accuracy read now?** Rejected: no per-skill accuracy read
  exists (`Attempt` has no `skill_id`), no chart primitive, no ≥6-session fixture to test
  against. Building it would mean an untestable or fabricated render — a D7/`GUARD-ACC-1`
  violation. The block **self-omits** (honest absence); the accuracy read + chart +
  fixtures are a follow-up.
- **Misconception callout "newest due miss" — new port?** Rejected: a client-side pure
  translator (`AttemptRepo.misses()` × `listSkillState()` `due_at`) mirrors the proven
  `use_summary.ts` `deriveMisconception` binding with no new port/DB method.
- **Bundle vs. split the ADR.** One bundled ADR chosen (human gate) over separate
  schema-fields and read-seam ADRs — the three triggers are one coherent "lesson content
  read path" decision and read better as one intent record.

---

## Rationale

The three triggers are a single seam: content shape → how it is read → how it is trusted.
Splitting them would fragment one decision across three records that must be read
together anyway. Each chosen option is the *smallest honest* move: the optional-field
extension reuses an in-file precedent and dodges the W2 gate entirely; the read ports
copy a pattern the codebase has ratified twice (ADR-0014/0015); the authored seed earns
the reviewed gate by the same confinement mechanism the hint family already trusts,
without standing up a generator + judge under time pressure. The grounding refutations
matter here precisely because they *shrink* the ADR: no scheduler-pin, no W2 baseline
work, no accuracy engine, no generator — the intent debt is in remembering *why* those
were correct to leave out.

---

## Consequences

**Commits us to:**
- A Drizzle migration (both dialects) adding the optional teaching columns; existing rows
  read back with the new fields absent (safe — all optional).
- Two new read ports + adapters + composition wiring + conformance coverage, following
  the `HintRepo` template.
- A `test_tutorial_provenance_confinement.py` architecture test; every checked-in tutorial
  seed row must carry a valid `generated_from` stamp or fail CI.
- Authoring the first skill's lesson content by hand and leak-checking it — the honest
  cost of not building the generator yet.

**Accepted risks / follow-on (honest downsides):**
- `accuracyStat` renders nothing until the per-skill accuracy read + chart + fixtures
  land — the `returning`/`refresher` rail is thinner than the design prototype until then.
  Mitigation: the block's render path exists and self-omits; it activates when data
  arrives, no re-architecture.
- Hand-authoring does not scale past a few skills. Mitigation: the confinement test
  already accepts the `llm:<model>@<promptrev>` stamp, so the B2 generator drops in behind
  the same gate without changing the read path.
- The lesson→coach seed contract (design OQ-3) is unresolved; `coachEntry` ships as a
  seam (button only). Mitigation: the seam is inert; the seed contract is its own decision.

**Not re-signing** (no `trust/` type change), **no new dependency**, **no new graph
node**, **no live LLM in CI** (content is authored offline as data).

---

## Supersedes / related

Realizes the [E1a spec](../plan/preact-parity-epic-E1a.spec.md). Amends the ADR-0005
engine substrate (adds a content read seam to the Frontend-Ring local-first engine).
Mirrors the [ADR-0014](0014-subject-coach-hint-repo-read-seam.md) /
[ADR-0015](0015-subject-coach-test-item-bank-blueprint-read-seam.md) read-seam pattern
and the [ADR-0021](0021-bank-backed-practice-scheduler.md) provenance cascade. Consumes
the [ADR-0027](0027-question-misconception-field.md) `misconception` field for the
`returning` callout. Ratification = the tasks→implement human gate.
