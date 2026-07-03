# Spec — Coach Test Mode governed plane (Phase 6: FR-23..FR-27)

**Status:** Draft — 2026-07-03
**Owner:** Rajnish Khatri
**Related:** [subject-coach-agent.plan.md](subject-coach-agent.plan.md) (Phase 6, §11 step 7) ·
[subject-coach-agent.spec.md](subject-coach-agent.spec.md) (parent spec; §FR-23..27 deferral note at
its "Test Mode" blockquote, FR-28 BUILT) ·
[ADR-0013](../adr/0013-subject-coach-test-mode-blueprint-generation-integrity.md) (ratified decision this
spec implements — never re-decides) · [ADR-0014](../adr/0014-subject-coach-hint-repo-read-seam.md)
(the port/cascade precedent mirrored here) ·
[ADR-0006](../adr/0006-subject-coach-component-protocols.md) (engine ports; this spec rides its
amendment window) · design doc §8/§11
([SUBJECT_COACH_AGENT_DETAILED_DESIGN.md](../Architectures/SUBJECT_COACH_AGENT_DETAILED_DESIGN.md)).

---

## 1. Goal

Give Test Mode a **governed content plane**: test items exist only as rows whose
`reviewed=true` was **earned by a verifier cascade** (never self-stamped), test forms are
assembled **deterministically from a blueprint + seed** (reproducible, auditable), and the
existing ungoverned `convert:test01` self-stamping path is demoted to a seed importer.
Outcome: a learner-facing test can never contain an unverified item, and any form is
byte-reproducible from `(blueprint_id, seed)` within a single bank state (reproducibility
across bank growth is a serving-time concern deferred to the ADR-0013 delivery re-open).

## 2. Context

Phases 1–4 shipped the coach identity, judge plane, and the ADR-0014 hint plane (9th
read-only engine port, deterministic leakage cascade, `reviewed=true` earned in
`components/hint_generation.py`). Phase 6 is the last governed-generation family and rides
Phase 4's ADR-0006 amendment window "where schema additions overlap" (design §11 step 7).
ADR-0013 is **accepted** with its acceptance condition MET (FR-28 posture flag +
`tests/architecture/test_no_client_served_test_keys.py`). Today's gap: the Test-01 corpus
(`frontend/lib/adapters/engine/_test01_english_corpus.ts`) is produced by a converter that
**self-stamps `reviewed:true`** (ADR-0013 clause 4 calls this retroactively unearned), and
no `TestBlueprint` contract, seeded assembler, or test-item cascade exists.

**Ratified constraints this spec implements, never re-opens:**
- **Option A stays** (keys in client bundle; client-side grading). A flag flip is a
  reviewed code diff + ADR-0013 re-open — out of scope here.
- **Delivery tripwire discipline (ADR-0013):** moving the *served* corpus off the static
  `.ts` bundle to DB/sync-served rows fires the delivery tripwire. Phase 6 therefore
  builds the governed bank/assembler **without rewiring the `/learn/test` serving path**;
  wiring assembled forms into the UI is a separate, tripwire-evaluating product step.

## 3. Functional requirements (EARS)

Numbers continue the parent spec's ratified identities (FR-23..FR-27). Failure paths
first within each family (TAP-4).

### FR-23 — Governed test-item generator family

- **FR-23.1** IF any cascade stage (schema-parse → answer-key consistency → duplicate/
  similarity) fails for a candidate item THEN THE SYSTEM SHALL write a quarantine row
  `{stage, violations, raw}` and record the failure via `eval_capture`
  (`target="test_item_generator"`), and SHALL NOT mark the item `reviewed=true`.
- **FR-23.2** IF the answer-key consistency check is undecidable (empty/malformed solver
  reply) THEN THE SYSTEM SHALL quarantine the item (undecidable → quarantine, never a
  fabricated pass — AP-6).
- **FR-23.3** THE SYSTEM SHALL confirm each candidate's declared `answer_letter` by an
  **independent solver pass** (the item's stem + choices only — the declared key is never
  shown to the solver) compared via **exact-letter match mirroring `ExactLetterGrader`
  semantics** (Python-side pure function; the TS grader is not importable). Mismatch →
  quarantine. *(Critical gate — design §8.1.)*
- **FR-23.4** WHEN the generator job runs THE SYSTEM SHALL run as a governed `build_graph`
  job under the `subject-coach-english` identity and capability gate (think/file_io only),
  with its own eval stream (`eval_capture_target="test_item_generator_llm"` — never
  polluting the coach shadow corpus) and the learner-domain guardrail dropped for
  first-party template input (mirror of `scripts/generate_hints.py` overrides).
- **FR-23.5** WHEN a candidate passes all cascade stages THE SYSTEM SHALL stamp
  `reviewed=True` **inside the cascade only**, with a deterministic content-hash id
  (idempotent re-runs) and provenance `generated_by="<model>@<run_id>"`.

### FR-24 — TestBlueprint contract + read seam

- **FR-24.1** IF a blueprint fails validation (skill-mix weights that do not sum to 1.0
  within tolerance, `count <= 0`, unknown skill id, empty/malformed `scale_band_table`,
  missing `seed`) THEN THE SYSTEM SHALL reject it at parse (Zod/Pydantic `ValidationError`)
  — never a silently clamped or partially applied blueprint.
- **FR-24.2** THE SYSTEM SHALL define `TestBlueprint`
  `{id, subject, skill_mix, difficulty_dist, count, minutes, scale_band_table,
  pass_criteria?, seed}` as a Zod wire entity (`frontend/lib/wire/engine_entities.ts`) and
  a `test_blueprint` table in **both dialects** (`schema.sqlite.ts` + `schema.pg.ts`).
- **FR-24.3** THE SYSTEM SHALL expose the governed plane through two new **read-only
  engine ports** (ADR-0006 third amendment, mirroring ADR-0014's `HintRepo` posture — no
  write surface; writes happen at the composition boundary): `TestBlueprintRepo.get(id)`
  (10th) and `TestItemRepo.listReviewed(subject)` (11th, `reviewed=true` rows only),
  both wired in `composition_engine.ts`.

### FR-25 — Seed importer (convert:test01 demotion)

- **FR-25.1** IF an imported row carries a self-stamped `reviewed:true` THEN the importer
  SHALL demote it to `reviewed=false` on entry — `reviewed` is earned by the FR-23
  cascade, never asserted by a converter.
- **FR-25.2** WHEN Test-01 rows are imported into the governed bank THE SYSTEM SHALL enter
  every row at `reviewed=false` with provenance `generated_by="test01-import"`, and
  promotion SHALL occur only via the FR-23 cascade (re-verification, including the
  solver key-consistency gate). On promotion THE SYSTEM SHALL re-stamp
  `generated_by="<model>@<run_id>"` (ADR-0013 clause 1) — so `"test01-import"` never
  appears on a `reviewed=true` row; the demotion→promotion transition is recorded in the
  cascade `eval_capture` stream (import lineage lives there, not in a persisted column).
- **FR-25.3** THE SYSTEM SHALL leave `_test01_english_corpus.ts` in place as the frozen
  e2e fixture and the `/learn/test` serving source (design §8.3) — the importer feeds the
  governed bank, not the client bundle.

### FR-26 — Deterministic seeded assembler

- **FR-26.1** IF the reviewed bank cannot satisfy the blueprint (any skill × difficulty
  stratum short of its required count) THEN the assembler SHALL fail closed with a typed
  error naming the short stratum — never emit a short, padded, or silently re-stratified
  form.
- **FR-26.2** WHEN assembling with a fixed `seed` over a frozen bank THE SYSTEM SHALL emit
  a **byte-identical form** across runs (10× determinism audit; stratify by skill_mix →
  difficulty_dist → count, order included).
- **FR-26.3** IF the `seed` differs THEN the assembled form SHALL differ (wrong-seed
  test asserted alongside determinism — guards against a seed-ignoring implementation).
- **FR-26.4** THE SYSTEM SHALL implement the assembler as a **pure, offline, client-side
  engine function** (Option A home per design §8.2) taking `(blueprint, bank_rows)` —
  no I/O inside the function.

### FR-27 — Reviewed-only selection

- **FR-27.1** IF a `reviewed=false` item exists in the bank THEN no assembled form SHALL
  ever include it (ungated-item-never-served: enforced at **both** the repo query and an
  assembler-level filter, each independently tested).
- **FR-27.2** WHILE ADR-0013 Option A holds, THE SYSTEM SHALL NOT change the `/learn/test`
  client serving source (the static bundle) — the delivery tripwire stays unfired and
  `tests/architecture/test_no_client_served_test_keys.py` stays green unmodified.

## 4. Data model / contracts

| Contract | Kind | Home | Notes |
|---|---|---|---|
| `test_item` table | NEW, both dialects | `frontend/lib/adapters/engine/db/schema.{sqlite,pg}.ts` | Question-shaped fields + `difficulty`, `skill_id`, `reviewed` (default false), `generated_by`, content-hash `id`. **Separate from `question`** so unreviewed/test items can never leak into practice scheduling (`DrizzleQuestionRepo.nextReviewed`). |
| `test_blueprint` table | NEW, both dialects | same | Fields per FR-24.2; `seed` stored on the row (reproducibility). |
| `TestItem`, `TestBlueprint` Zod entities | NEW | `frontend/lib/wire/engine_entities.ts` | Mirror hint precedent; no CI TS↔Python parity gate exists for engine entities — parity held by seed-generated-from-Python + parity-pin tests (ADR-0014 accepted-risk pattern). |
| `TestBlueprintRepo` port | NEW (10th, read-only) | `frontend/lib/ports/engine/test_blueprint_repo.ts` | `get(id)`; ADR-0006 amendment → **ADR-0015** (sibling of ADR-0014). |
| `TestItemRepo` port | NEW (11th, read-only) | `frontend/lib/ports/engine/test_item_repo.ts` | `listReviewed(subject)` — `reviewed=true` only (FR-27.1 repo-level gate); same ADR. |
| Python cascade + types | NEW | `components/test_item_generation.py` (+ `components/schemas.py` additions if needed) | Mirrors `hint_generation.py`: stages, quarantine rows, content-hash ids, `reviewed` earned in-cascade. |
| Generator job | NEW | `scripts/generate_test_items.py` | Mirrors `scripts/generate_hints.py` (identity, capability gate, eval-stream override, guardrail drop). |
| Importer | CHANGED | `frontend/scripts/convert_test01_english.ts` (parse stays TS) + NEW Python promotion path | Converter emits a neutral `reviewed=false` seed; the Python cascade re-verifies and emits the promoted seed. `_test01_english_corpus.ts` untouched. |
| No `trust/` changes | — | — | Instance/config only; no kernel re-sign. |

## 5. Invariants & security boundaries

- **#3 Components framework-agnostic:** `components/test_item_generation.py` imports no
  langgraph/langchain; the LLM solver is injected (same seam as `hint_generation.py`).
- **#5 No peer imports:** the cascade does not import router/evaluator.
- **#6 Thin nodes / no new graph node:** the generator is a `scripts/` job reusing
  `build_graph` with config overrides — no `react_loop.py` change.
- **No live LLM in CI:** generator + solver gates run on-demand; CI tests use mock
  providers (`ErrorMockProvider`/`TextOnlyMockProvider` patterns). `make check` stays
  deterministic.
- **ADR ratchet (⚠️ Ask first):** new engine port + two tables ⇒ **new ADR** riding the
  ADR-0006 amendment window (mirror ADR-0014's structure), OKF frontmatter + `index.md` +
  `log.md`. ADR-0013 itself is referenced, never re-opened.
- **Security boundary (ADR-0013):** answer keys remain client-visible **only** via the
  existing static bundle (Option A). The governed bank is not a new client key-delivery
  channel in this phase; `test_no_client_served_test_keys.py` is not weakened or modified.

## 6. Edge cases

- Solver returns an empty reply or a non-letter → quarantine (FR-23.2), mirroring the
  hint generator's live-verified empty-reply quarantine.
- Solver returns the right letter with extra prose ("The answer is C because…") → the
  exact-letter comparator extracts/normalizes exactly as `ExactLetterGrader` does; a
  non-extractable reply is undecidable → quarantine.
- Generator re-run over the same question set → content-hash ids make writes idempotent
  (no duplicate rows, no double-promotion).
- Near-duplicate of an existing bank item (Jaccard ≥ threshold, hint precedent 0.85) →
  quarantine at the duplicate stage even if key-consistent.
- Blueprint `skill_mix` naming a skill with zero reviewed items → FR-26.1 fail-closed at
  assembly (not at blueprint parse — the bank is not known at parse time).
- Import source `PreAct/practice-tests/Test-01.md` absent (untracked) → importer skips
  gracefully (existing `skipIf` oracle pattern); the committed corpus fixture keeps CI
  coverage.
- Two blueprints sharing a seed → fine (seed is per-blueprint row data, not global).
- `pass_criteria` absent (optional field) → form assembles; no default invented.

## 7. Non-functional requirements

- **Determinism:** assembler is L1-exact (byte-identical, 10× audit). Cascade
  deterministic stages (schema, duplicate, comparator) are L1; the solver pass is L2
  (live, on-demand only).
- **Cost:** solver gate = 1 extra LLM call per candidate item; runs only in the
  on-demand generator/importer jobs, never CI, never the learner hot path.
- **Reversibility:** all-additive (new tables/port/files); rollback = drop seed +
  revert. No behavior change to `/learn/quiz` or `/learn/test` serving.
- **Auditability:** every generated/imported item carries provenance; every quarantine
  carries stage + violations; every LLM call recorded with `user_id`+`task_id`.

## 8. Test plan

Failure-path tests first. All L1/L2 rows run in `make check` / `pnpm test`; L2-live rows
are on-demand scripts.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-23.1 | `tests/components/test_test_item_generation.py::test_stage_failure_quarantines_never_reviews` (per-stage matrix, Pattern 11) | L1 | yes |
| FR-23.2 | `::test_undecidable_solver_reply_quarantines` (ErrorMock/empty) | L2 mock | yes |
| FR-23.3 | `::test_key_mismatch_quarantines` before `::test_key_match_passes`; comparator parity-pinned to `exact_letter_grader.ts` fixtures | L1/L2 | yes |
| FR-23.4 | `tests/scripts/test_generate_test_items_config.py` — identity, capability set, eval target, guardrail override asserted on the built config | L2 | yes |
| FR-23.5 | `::test_reviewed_earned_only_in_cascade` + content-hash idempotency (10× audit) | L1 | yes |
| FR-24.1 | Zod + Pydantic rejection pairs (Protocol A1) — invalid blueprints first | L1 | yes (vitest + pytest) |
| FR-24.2/3 | `drizzle_test_blueprint_repo.test.ts` roundtrip both dialects; port barrel + composition wiring test | L2 | yes (vitest) |
| FR-25.1 | importer demotes self-stamped `reviewed:true` → `false` (failure path first) | L1 | yes (vitest) |
| FR-25.2 | imported rows enter `reviewed=false`; promotion only via cascade; promotion re-stamps `generated_by` to `<model>@<run_id>`; roundtrip = Python-emitted promoted row parses under Zod `TestItem` | L2 | yes |
| FR-25.3 | `_test01_english_corpus.ts` byte-unchanged + `/learn/test` page still imports it (lock test) | L1 | yes (vitest) |
| FR-26.1 | short-stratum fail-closed with named stratum, before any happy path | L1 | yes (vitest) |
| FR-26.2 | fixed seed + frozen bank ⇒ byte-identical, 10× | L1 | yes (vitest) |
| FR-26.3 | wrong seed ⇒ different form | L1 | yes (vitest) |
| FR-27.1 | ungated-item-never-served at repo layer AND assembler layer (two tests) | L1 | yes (vitest) |
| FR-27.2 | `tests/architecture/test_no_client_served_test_keys.py` untouched + green | L1 | yes |
| e2e | existing learn-e2e suite stays green (no serving change) | L4 | e2e tier |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was *seen to fail first*.
- [ ] `make check` green (baseline 2026-07-03: 4784 passed, 52 skipped).
- [ ] Frontend `pnpm test` + learn-e2e green (no `/learn/test` behavior change).
- [ ] Invariants in §5 unbroken (`tests/architecture/` green; `test_adr_ratchet` satisfied
      by the new ADR).
- [ ] New ADR (TestBlueprint/test-item read seam + governed bank) accepted, OKF-complete
      (frontmatter, `index.md`, `log.md`); ADR-0006 header gains the amendment pointer;
      small choices → `docs/adr/decisions.md`.
- [ ] Generator live-verified on ≥5 questions with at least one observed quarantine path
      (mirror of the Phase-4 hint-generator live check), evidence pasted.
- [ ] Parent spec's FR-23..27 deferral note updated to point here.
