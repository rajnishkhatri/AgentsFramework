---
type: decision-record
title: 'ADR-0013: Subject-Coach Test Mode — test blueprint, governed test generation, and the client-integrity stance'
status: accepted
created: 2026-07-02
updated: 2026-07-02
owner: Rajnish Khatri
related: SUBJECT_COACH_AGENT_DETAILED_DESIGN.md, SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md, subject-coach-agent.spec.md, preact-english-coach-engine.spec.md, preact-english-coach-ui.spec.md, 0005-subject-coach-engine-home-and-substrate.md, 0006-subject-coach-component-protocols.md, 0012-subject-coach-context-contract-hint-ladder.md
tags: [decision-record]
---

# ADR-0013: Subject-Coach Test Mode — test blueprint, governed test generation, and the client-integrity stance

**Status:** Accepted — 2026-07-02, **with conditions** (was Proposed — 2026-07-02, spawned
by the agent design doc's §10 adjudication pattern, the ADR-0012 precedent; the ride-along
design-doc sections land with this ADR's execution pass). Ratified conditionally at the
build-sequencing human gate: the integrity stance — **Option A now, Option B as the
committed evolution behind three named, independently-sufficient tripwires** (delivery /
stake / proctoring) — is the ratified answer to "may answer keys ship in the client bundle
on a timed test surface?" The condition — that the tripwire be **implemented in code, not
just guarded in docs** — was **met the same day** (see Acceptance conditions below). Integrity stance = Option A now
with B as the committed evolution behind **three named, independently-sufficient decision
triggers** (delivery / stake / proctoring), each with a mechanical detector or named owner
— see "Decision triggers — migration to Option B" below.

> **Acceptance condition (2026-07-02) — ✅ MET (same day).** The condition required the
> tripwire to be implemented in code, not just guarded in docs:
> 1. **The `COACH_TEST_KEYS_CLIENT_SERVED` posture flag is now a real code switch** —
>    `services/governance/coach_test_mode_posture.py` (agent spec FR-28): a literal
>    `Final[bool]` constant, **deliberately not env-overridable** so flipping it is always
>    a reviewed code diff paired with re-opening this ADR (an env override would let a
>    deploy invert the tripwire silently — the exact failure the flag exists to prevent).
>    `tests/architecture/test_no_client_served_test_keys.py` now **keys off the actual
>    flag state**: flag `True` ⇒ the Option-A posture assertions run (the four
>    answer-bearing fields ARE in the Test-01 fixture); flag `False` ⇒ the gate
>    **mechanically inverts** and asserts keys are NOT shipped client-side — the inverted
>    branch is already implemented, not added later. The docs-integrity assertion (the
>    three triggers, the flag name, this detector, the "third ADR-0012 mode" landing spot
>    all remain present in this ADR) runs under both postures. At ratification the test
>    guarded prose + as-built posture only; the rewire mirrors ADR-0011's
>    `ReadableEngineDb` lesson (an assert-in-prose posture rots; a code-enforced switch
>    does not) and ADR-0008's "stated, tracked floor before the flag is trusted" shape.
>    Evidence: red (ModuleNotFoundError) → green 3/3, full `make check` 4543 passed.
>
> With the flag landed the tripwire is **code-enforced**: Option A's keys-in-bundle
> posture remains the accepted residual risk (named, tripwired, mechanically watched at
> the flag + fixture + docs layers), and any of the three named triggers firing still
> re-opens this ADR by its own terms — the migration now *cannot* proceed without the
> flag flip, because the unflipped gate fails the moment the fixture posture changes.
**Related:** [agent detailed design](../Architectures/SUBJECT_COACH_AGENT_DETAILED_DESIGN.md) §8 · [component design](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) · [UI spec](../plan/preact-english-coach-ui.spec.md) · [engine spec](../plan/preact-english-coach-engine.spec.md) · [agent spec](../plan/subject-coach-agent.spec.md) · [ADR-0006 ports](0006-subject-coach-component-protocols.md) · [ADR-0012 context contract](0012-subject-coach-context-contract-hint-ladder.md)
**Audience:** anyone generating test content, composing a timed test form, or
reconsidering whether answer keys may ship in the client bundle.

---

## Context

Test Mode (`/learn/test`, commit `a3cb9ef`) is a **BUILT, client-only timed test
surface** — 48-question Test-01 corpus, countdown + auto-submit
(`frontend/components/test/test_runner_reducer.ts:49–130`,
`CountdownTimer.tsx`/`use_countdown.ts`), one-shot idempotent grading via the engine
`Grader` port, results with `englishScaleBand` (`test_scoring.ts:37`), byte-stable e2e
(`frontend/e2e/learn/test-mode.spec.ts`) — that appears in **no spec, design doc, or ADR**.
Three coupled problems:

1. **The content path is ungoverned.** A hand-run `pnpm convert:test01`
   (`frontend/scripts/convert_test01_english.ts`, reading untracked
   `PreAct/practice-tests/Test-01.md`) emits the checked-in corpus
   (`frontend/lib/adapters/engine/_test01_english_corpus.ts`) and **stamps
   `reviewed:true` itself** — bypassing the verifier-cascade discipline (engine spec §E,
   FR-E2) that governs every other content row in the system.
2. **No form definition exists.** Count (48), duration (`TEST01_ENGLISH_MINUTES = 35`),
   and the scale-band table are whatever Test-01.md contained, frozen into corpus
   constants; there is no skill-mix or difficulty-distribution control, no `TestBlueprint`
   entity anywhere.
3. **The integrity hole.** The corpus ships the four answer-bearing `Question` fields
   (`answer_letter`, `per_choice_rationale`, `why_correct_md`, `why_tempted_md`) in the
   client bundle **on a timed test surface** — the exact fields ADR-0012 excludes
   server-side for the coach pre-submit. Test Mode has no server at all: grading is
   client-side, so the key is *needed* on the client today.

Also stated as design surface (not oversights to paper over): no test-session archival,
no attempt writes, no FSRS/mastery feedback, no telemetry, no resume, no per-item timing.

---

## Decision

Four clauses (the agent design doc §8.1–§8.3 are the HOW once this ratifies):

1. **Test items become the second content family of the offline generator** (§8 of the
   agent design doc; hints are the first). The verifier cascade for test items:
   schema-parse → **answer-key self-consistency (the critical gate** — exactly one
   correct letter; rationales reference real choices; the deterministic
   `ExactLetterGrader` confirms the declared key; engine-spec FR-E2 made concrete) →
   duplicate/similarity. The per-rung **leakage check is N/A** for test items (it is
   hint-specific) — stated explicitly so the cascade is not blindly copied.
   Provenance: `generated_by = "<model>@<run_id>"` replaces `"test01-convert"`.
   PASS → `reviewed=true`; FAIL → quarantine + `eval_capture` record.
2. **A `TestBlueprint` entity + a deterministic, seeded assembler** compose test forms
   from the `reviewed=true` bank: selection stratified by skill mix, then difficulty
   distribution, then count; duration + scale-band/pass table carried **on the blueprint**
   (retiring the hardcoded constants as the only sources). Fixed `seed` + frozen bank ⇒
   byte-identical form, preserving the existing e2e byte-stability contract. Sketch:
   `{id, subject, skill_mix, difficulty_dist, count, minutes, scale_band_table,
   pass_criteria?, seed}`.
3. **Integrity stance: Option A now, Option B as the committed evolution behind three
   named decision triggers.** Keys stay in the bundle for the unproctored MVP (an *accepted
   risk with a tripwire*, the ADR-0012 residual-risk-window pattern — accepted risk ≠ gating
   condition). The deferral is safe only because the moment the score *means* something, B
   is already designed. Three independent, any-one-sufficient triggers force a re-opening
   of this ADR and migration to Option B — **delivery** (corpus moves off the static bundle
   onto DB/sync-served rows), **stake** (any downstream consumer attaches significance to
   the score — placement, mastery/FSRS feedback, or reporting), and **proctoring** (the
   surface gains a proctoring signal: camera, lockdown, identity-verified attempt). Each
   carries a mechanical detector or a named owner so the trigger cannot fire silently —
   detailed in the "Decision triggers — migration to Option B" section below. Any future
   Option B lands as a **third `mode` of the ADR-0012 context contract** (pre-submit test
   payload excludes the four fields; key withheld until submit), not a bespoke mechanism.
4. **`convert:test01` becomes a one-time seed importer** into the governed pipeline:
   Test-01 rows enter at `reviewed=false` and are promoted only by the clause-1 cascade
   (the script's self-stamped `reviewed:true` is retroactively unearned). The checked-in
   corpus `.ts` remains a **frozen e2e fixture** until delivery moves to DB-served rows;
   then script and fixture both retire.

---

## Options considered & rejected (the integrity core)

| Option | What | Verdict |
|---|---|---|
| **A. Accept-for-MVP** *(chosen, tripwired)* | Keys stay in the bundle; grading stays client-side | Preserves ADR-0005's local-first/offline posture (a server-delivered test contradicts the engine spec's offline loop, FR-G1); the product is unproctored practice with **zero stakes attached to the score**; zero new server surface. Risk: a motivated student reads the bundle — bounded by the decision trigger above; unearnable the moment scores feed anything. |
| **B. Server-side delivery now** | Test = a third ADR-0012 context-contract mode; pre-submit payload excludes the four fields; key withheld until submit (server grades or releases at submit) | Real integrity, mechanically enforced, reuses a ratified mechanism — **rejected as *primary*** because it breaks offline test-taking and adds a BFF route + server session state for zero current stakes. **Named as the committed evolution** (clause 3). |
| **C. Hybrid split-bundle** | Keys/rationales in a separate module fetched only at submit; grading client-side | Keys remain client-obtainable (the module URL is in the bundle), so it is cost without a real guarantee — a half-measure that still needs B eventually. Rejected. |
| **Two ADRs (split integrity from generation)** | Separate records for the blueprint/generation and the integrity stance | The integrity stance *determines* where the assembler runs, which determines the blueprint's realization home — splitting creates two mutually-dangling Proposed ADRs. ADR-0012 bundled mechanism + content for the same coupling reason. One ADR. |
| **Retire `convert:test01` outright** | Hand-import Test-01 rows, delete the script | Loses the only reproducible parse of the source markdown (lettering normalization, skill mapping, difficulty assignment — all tested in `convert_test01_english.test.ts`). The seed-importer path (clause 4) keeps the machinery and fixes only the governance defect (the self-stamped `reviewed`). Rejected. |

---

## Decision triggers — migration to Option B (the tripwire)

Option A is accepted for the unproctored, zero-stakes MVP only. The choice is **not
silent intent debt**: three named triggers force a re-opening of this ADR and migration
to Option B. They are **independent and any-one-sufficient**, not conjunctive — so no
single team can silently cross the line. Each carries a mechanical detector or a named
owner (the ADR-0011/0012 lesson: a prose assertion rots; a mechanical check or a named
seam does not).

1. **Delivery trigger.** Corpus delivery moves off the static client bundle —
   `test_blueprint` rows (or the item bank) are read from a DB/sync adapter rather than
   from the frozen `_test01_english_corpus.ts` fixture. Once delivery is server-mediated,
   the marginal cost of withholding the answer-bearing fields drops to near-zero and
   Option B becomes the cheaper correct choice. **Detector:**
   `tests/architecture/test_no_client_served_test_keys.py` — keyed off the actual
   `COACH_TEST_KEYS_CLIENT_SERVED` flag state
   (`services/governance/coach_test_mode_posture.py`): while the flag is `True` it
   asserts the four answer-bearing fields **are** present in the Test-01 corpus fixture
   (Option A live); the moment a DB/sync adapter serves test items that premise breaks
   and the test forces the conscious `COACH_TEST_KEYS_CLIENT_SERVED = False` flip, which
   **mechanically inverts the gate** to assert keys are **not** shipped client-side (the
   inverted branch is already implemented).
2. **Stake trigger.** Any downstream consumer attaches significance to the test score.
   Three sub-triggers, each owned by a different seam so no single team can silently
   cross the line:
   - **Placement** — the score influences which course/level a learner is routed to.
     Owner: the agent design doc's §11 step-7 ratifier.
   - **Mastery feedback** — the score feeds FSRS/mastery state (the component design
     doc's §4.9 DEFERRED `AttemptRepo`/`SessionRepo` becomes real). Owner: the engine
     spec's §I archival amendment.
   - **Reporting** — the score is surfaced to any party other than the test-taker
     themselves (parent, teacher, dashboard, export). Owner: the UI spec's §L7 row.
3. **Proctoring trigger.** The surface gains any proctoring signal (camera, lockdown
   browser, identity-verified attempt, supervised session). Bundle-readable keys are
   exploitable under proctoring in a way they are not on a pure self-study surface, so
   Option A's risk model no longer holds. Owner: this ADR's re-opening (no code detector
   — proctoring is a product decision, so the owner is the human gate, named explicitly
   to avoid the "no detector ⇒ silent" failure mode).

**Consequence path on any trigger firing:**
- Option B lands as **a third `mode` of the
  [ADR-0012](0012-subject-coach-context-contract-hint-ladder.md) context contract** — not
  a parallel mechanism. ADR-0012 is amended (its second amendment window) to add the
  `test` mode; the coach's existing mode-dependent injection machinery is reused, not
  duplicated.
- The [ADR-0006](0006-subject-coach-component-protocols.md) amendment machinery opens for
  the `test_blueprint` read seam (the deferred DB adapter) — ride the same amendment
  window if timing aligns, else flag a third ADR-0006 amendment explicitly (never a
  silent schema add, per the agent design doc §9 Ask-first row).
- Both design docs' Test-Mode status rows flip: §2.5/§4.9 BUILT "corpus `.ts`" → RETIRED;
  §4.9 DEFERRED `SessionRepo`/`AttemptRepo` → TO-BUILD where the stake trigger fired;
  §8.3 `convert:test01` script + fixture → RETIRED.
- `COACH_TEST_KEYS_CLIENT_SERVED` flips to `false` (see agent spec FR-28); the
  architecture test above inverts to fail if keys **are** shipped client-side.
- The e2e byte-stability contract re-bases onto fixed-seed + server-served bank rather
  than the frozen static fixture.

**Non-trigger (explicitly out of scope):** a learner inspecting their own bundle to
cheat on a self-study test is the accepted Option-A residual risk, *not* a trigger — it
is the cost of preserving [ADR-0005](0005-subject-coach-engine-home-and-substrate.md)'s
local-first/offline FR-G1 for an unproctored, zero-stakes surface. Naming it here prevents
a future reader from treating a self-reported cheat as grounds to re-open the ADR; only
the three triggers above do.

---

## Rationale

The three questions are one decision because they share one pivot: *where does trust in a
test item come from?* The cascade (clause 1) makes item **content** trustworthy — and the
answer-key self-consistency gate is the test family's precise analog of the hint family's
leakage rung: each family's critical gate targets its own dominant failure (a wrong key
corrupts every downstream grade; a leaking hint corrupts the pedagogy). The blueprint
(clause 2) makes the **form** reproducible — determinism-by-seed preserves the e2e
contract the fixed corpus provides today, so governance does not cost test stability. The
integrity stance (clause 3) is honest about stakes: prompt-side secrecy theater (Option C)
is rejected on the same evidence-first grounds as ADR-0012's Option A (a guarantee you
cannot mechanically enforce is not a guarantee), while full server delivery (Option B) is
deferred — not rejected — because paying an offline-posture regression for a zero-stakes
score protects nothing today. The tripwire makes the deferral safe: the moment the score
*means* something, B is already designed (a third ADR-0012 mode, not a new mechanism).

---

## Consequences

**Commits us to:**
- A **`test_blueprint` table (both dialects) + wire entity + read seam** under the
  ADR-0006 amendment machinery — riding the second-amendment window that lands with the
  generator build where the schedules overlap, or a **third amendment flagged explicitly**
  if timing splits. Never a silent schema add (the agent design doc §9 Ask-first row).
- **Generator family parameterization** (§8.1) + the seeded assembler (§8.2) + the
  seed-import path (§8.3), each red-first per the spec test plans.
- **e2e byte-stability re-based** on fixed-seed + frozen bank (replacing fixed corpus
  order) when the assembler ships.
- Both design docs' Test-Mode statuses + the OKF triple flip on ratification.

**Stays DEFERRED under Option A:** test-session archival / attempt writes / FSRS feedback
/ telemetry — adding **any** of these that makes the score consequential **fires a
clause-3 tripwire** (the **stake** trigger above — they are the "stake attaches" events,
not routine follow-ups; archival specifically is the *mastery feedback* sub-trigger).

**Posture flag:** `COACH_TEST_KEYS_CLIENT_SERVED` (agent spec FR-28) defaults to `true`
under Option A and flips to `false` on any of the three named triggers firing — the
single canonical switch the architecture test
(`tests/architecture/test_no_client_served_test_keys.py`) keys off, so the migration is
mechanically observable rather than prose-only.

**Accepted risks:** bundle-readable keys until the tripwire fires (stated above);
the frozen corpus fixture and the generated bank coexist during migration — the fixture
is e2e-only, never learner-served, once DB delivery starts.

---

## Supersedes / related

Extends [ADR-0006](0006-subject-coach-component-protocols.md) via its flagged amendment
train (the `test_blueprint` read seam). Applies [ADR-0012](0012-subject-coach-context-contract-hint-ladder.md)'s
context-contract machinery as the *designed evolution* (Option B) rather than day-1
scope. Complements [ADR-0005](0005-subject-coach-engine-home-and-substrate.md)'s
local-first ruling (which Option A preserves). Supersedes nothing.
