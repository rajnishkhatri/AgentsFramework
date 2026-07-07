# Spec — Reviewed hint ladders for the governed test_item bank (both planes)

> EARS acceptance criteria; failure paths first. The *why* is recorded in the
> gate-passed brainstorm ([coach-bank-hints.brainstorm.md](coach-bank-hints.brainstorm.md))
> and the ADRs it consumes; the ADR-0014 source-direction inversion is captured
> as an amendment note (§5).

**Status:** Implemented — 2026-07-07 (evidence: [coach-bank-hints.impl.md](coach-bank-hints.impl.md))
**Owner:** Rajnish Khatri
**Related:** [brainstorm](coach-bank-hints.brainstorm.md) ·
[ADR-0021 bank-backed practice scheduler](../adr/0021-bank-backed-practice-scheduler.md) ·
[ADR-0014 hint read seam](../adr/0014-subject-coach-hint-repo-read-seam.md) ·
[ADR-0012 context contract + hint ladder](../adr/0012-subject-coach-context-contract-hint-ladder.md) ·
[coach-item-bank-live.spec.md](coach-item-bank-live.spec.md) (predecessor increment)

---

## 1. Goal

Every `reviewed=true` bank item served by the `/learn` practice quiz has a full,
cascade-verified 3-rung hint ladder, served on **both** planes: the iPad
CoachPanel two-tier nudge (frontend `HintRepo`) and the coach persona's FR-20
context render (backend `rungs_for_question`). Closes the ADR-0021 accepted
risk "bank items ship without hint ladders" and the discovered orphaning of the
backend authored asset.

## 2. Context

ADR-0021 deleted `DEV_HINTS` with the dev questions; the bank's `ti-gen-*` ids
match nothing in either hint plane. Frontend: the dev hint table is empty
(`db.seedHints` fires only on the e2e injection path), so the CoachPanel always
falls back to its generic nudge. Backend: `AUTHORED_RUNGS` is keyed to the
deleted `q-*` ids, so `orchestration/react_loop.py:2332` always renders an
empty ladder — and per its own comment, *"without rungs the persona
free-generates (the Stage-0 rule-naming leak class)"*. The generation machinery
already exists end-to-end (`scripts/generate_hints.py` →
`components/hint_generation.py::run_hint_cascade` → deterministic
`check_rung_leakage`); this increment produces content, builds the serving seed
path, unifies the source for both planes, and adds the guards whose absence let
the gap ship silently (brainstorm P3/P4/P7).

Gate decisions this spec realizes: **D1** (batch-generate + checked-in seed),
**D3-a** (one canonical corpus feeds both planes; JSON canonical + two
generated modules; authored rows kept), **D4** (full-ladder ratchet + hint
provenance guard; explicit waiver token as escape hatch).

## 3. Functional requirements (EARS)

### Feature A — generation run + canonical corpus

- **FR-A1 (failure path).** IF a generator reply is not a parseable rungs-JSON
  object, or a rung fails the deterministic leakage check, or a rung body is a
  near-duplicate (Jaccard ≥ 0.85), THEN the row SHALL be quarantined by
  `run_hint_cascade` (never served) and recorded via `eval_capture` with
  `target="hint_generator"` — the existing cascade behavior, unchanged.
- **FR-A2 (completeness bar).** THE checked-in corpus SHALL contain a full
  reviewed ladder (rungs 1, 2, 3 — exactly one row per rung) for EVERY
  `reviewed=true` item in `TEST_ITEM_BANK`, produced by iterating
  `scripts/generate_hints.py` (bounded: ≤3 generation attempts per item) with
  `--existing` accumulating accepted bodies across attempts.
- **FR-A3 (escape hatch).** IF an item cannot earn a full ladder within the
  attempt bound, THEN it SHALL be listed in an explicit waiver table in the
  corpus module (id + missing rungs + reason), and the FR-E1 ratchet SHALL
  accept only waivered gaps.
- **FR-A4.** THE canonical corpus SHALL be a checked-in JSON file
  (`docs/plan/coach-bank-hints.seed.json`, the item-bank seed precedent) whose
  rows are exactly the `run_hint_cascade` PASS dicts
  (`id "h-gen-<hash16>"`, `subject`, `question_id`, `rung`, `body_md`,
  `reviewed: true`, `generated_by: "<model>@<workflow_id>"`).
- **FR-A5.** THE generation run SHALL make live LLM calls **on-demand only**
  (developer machine, `.venv/bin/python`, real keys) — never in CI or
  `make check`.

### Feature B — dual-module emission + parity (single source)

- **FR-B1.** THE SYSTEM SHALL provide a deterministic converter
  (`scripts/emit_hint_bank.py`, no LLM, no network) that reads the canonical
  JSON and emits BOTH generated modules:
  `frontend/lib/adapters/engine/_hint_bank.ts` (rows as `Hint` wire shapes +
  `seedHintBank(db)`, the `_test_item_bank.ts` pattern) and
  `components/subject_coach_bank_hints.py` (`BANK_RUNGS: Final[list[HintRung]]`
  literal data asset — no import-time I/O).
- **FR-B2 (failure path — drift pin).** IF either generated module disagrees
  with the canonical JSON (row count, ids, bodies, rung levels, reviewed flags),
  THEN a parity test SHALL fail: one vitest parity check for `_hint_bank.ts`
  and one pytest parity check for `subject_coach_bank_hints.py`, each comparing
  module content against the JSON.
- **FR-B3 (field mapping).** THE Python emission SHALL map the wire
  `generated_by` onto `HintRung.authored_by` verbatim (the model@run stamp is
  the provenance value in both planes); rungs stay within the
  `Literal[1, 2, 3]` / `z.union` bounds so the assertion rung remains
  unrepresentable on both wires.

### Feature C — frontend serving (CoachPanel two-tier nudge)

- **FR-C1.** WHEN the browser composition root builds the dev-default engine
  (no e2e injection), THE SYSTEM SHALL seed the hint table via
  `seedHintBank(db)` alongside `seedTestItemBank(db)` — dev-guard only; the
  production branch stays an empty substrate, and the e2e injection path is
  unchanged.
- **FR-C2.** WHEN the quiz opens a bank item, THE served `hintLadder` SHALL be
  that item's reviewed rungs ascending (rung 1 → item-card Get-a-hint; rungs
  2/3 → CoachPanel two-tier nudge), via the existing `hintRepo.list` load — no
  quiz/CoachPanel code changes.
- **FR-C3 (failure path — reviewed gate).** IF a hint row has
  `reviewed=false`, THEN it SHALL never be served (`DrizzleHintRepo` FR-12 pin,
  unchanged and still covered by its conformance tests).

### Feature D — backend persona plane (FR-20 restored for bank items)

- **FR-D1.** WHEN `rungs_for_question(question_id)` is called with a bank id,
  THE SYSTEM SHALL return that item's reviewed bank rungs ascending:
  `components/subject_coach_hints.py` serves `AUTHORED_RUNGS + BANK_RUNGS`
  (authored rows kept; id-keyed lookup keeps them inert for bank ids). No
  change to `orchestration/react_loop.py` — the call site already exists.
- **FR-D2 (failure path).** IF a question id matches neither asset, THEN
  `rungs_for_question` SHALL return `[]` (existing behavior — the formatter's
  empty-ladder path), never a fabricated rung.

### Feature E — guards (the D4 ratchet)

- **FR-E1 (coverage ratchet).** THE vitest seed suite
  (`_hint_bank.test.ts`) SHALL fail IF any `reviewed=true` item in
  `TEST_ITEM_BANK` lacks a full 3-rung reviewed ladder in `_hint_bank.ts`,
  UNLESS that (item, rung) gap is in the FR-A3 waiver table — so the next bank
  promotion cannot silently ship hint-less items.
- **FR-E2 (provenance confinement).** THE architecture suite SHALL fail IF a
  `reviewed=true` hint row in a seed file lacks cascade provenance
  (`generated_by` matching `<model>@<hex-run-id>` or the literal `"authored"`)
  — extending `tests/architecture/test_test_item_provenance_confinement.py`'s
  approach to hint-shaped rows (`body_md`+`rung` discriminator; the current
  scan keys on `stem_md` and cannot see them).
- **FR-E3 (leakage re-verification).** THE pytest suite SHALL re-run the
  deterministic `check_rung_leakage` over every corpus row against its bank
  item (pure functions, no LLM) — the checked-in content stays leak-free even
  if hand-edited later.

## 4. Data model / contracts

- **No table or wire-entity changes.** `hint` table (both dialects), `Hint`
  Zod entity, `HintRepo` port, `HintRung` Pydantic model all already exist and
  are unchanged. Cascade PASS dicts are field-identical to `Hint`; the only
  mapping is `generated_by → authored_by` on the Python side (FR-B3).
- **New artifacts:** `docs/plan/coach-bank-hints.seed.json` (canonical corpus,
  ~24 rows: 8 items × 3 rungs), `_hint_bank.ts` + `subject_coach_bank_hints.py`
  (generated, checked in, header comments marking them generated + the
  regeneration command), `scripts/emit_hint_bank.py` (converter).
- **No trust-kernel types touched.**

## 5. Invariants & security boundaries

- **#3 components framework-agnostic / purity:** `subject_coach_bank_hints.py`
  is a literal data module (stdlib + Pydantic only, no I/O); its import by
  `subject_coach_hints.py` follows the existing data-asset import precedent
  (`hint_generation` → `hint_leakage`; schemas), not a peer *decision* import
  (#5 untouched).
- **#6 thin orchestration:** zero orchestration changes (FR-D1 reuses the
  existing `react_loop.py:2332` call).
- **Leak discipline (ADR-0012/FR-20/FR-12):** all served content is
  cascade-earned `reviewed=true`; read-only ports unchanged; rung `4`
  unrepresentable on both wires; FR-E3 re-verifies leakage deterministically
  in CI.
- **No live LLM in CI:** generation (FR-A5) is on-demand; converter and all
  tests are deterministic.
- **ADR posture:** no new abstraction, port, node, or dependency → no new ADR.
  The D3-a source-direction inversion (generated corpus now upstream of the
  Python asset, reversing ADR-0014's "seed is generated FROM the Python
  asset") SHALL be recorded as a dated amendment note in ADR-0014
  §Consequences + a `docs/adr/decisions.md` entry referencing this spec. If
  the ADR-ratchet path check fires on touched seams, the commit carries
  `ADR-OK: ADR-0014 amendment note — no new abstraction` only if the amendment
  note itself doesn't satisfy it.

## 6. Edge cases

- **Item ungeneratable after 3 attempts** → FR-A3 waiver row; ratchet accepts
  the explicit gap; CoachPanel falls back per-rung (existing behavior).
- **Bank re-promotion changes `ti-gen-*` ids** → FR-E1 fails on the orphaned
  ladder/missing coverage; regeneration is the documented fix (header comment).
- **Cross-item near-duplicate rungs** (same skill → similar phrasing) →
  `--existing` accumulates all accepted bodies so the Jaccard stage rejects;
  iterate with FR-A2's bound.
- **e2e injected corpora** (practice-table oracles) → unchanged: injection
  replaces the seed entirely; `injected.hints` stays optional.
- **Production substrate** → still empty (no dev seed); real DB rows are the
  ADR-0005/0010 path; nothing in this spec ships content to prod.
- **Hand-edit of a generated module** → FR-B2 parity fails (drift pin); a
  hand-edited *corpus* row that leaks → FR-E3 fails.

## 7. Non-functional requirements

- **Determinism:** converter output is byte-stable for a given JSON (sorted by
  `(question_id, rung)`); cascade row ids are content hashes (idempotent
  re-runs).
- **Cost/latency:** one-time live run ≈ 8–24 graph calls on the fast profile;
  minutes, developer-machine only. CI additions are pure/deterministic (L1).
- **Reversibility:** deleting the two generated modules + the seed call
  restores today's generic-nudge behavior; no migrations.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-A1 | existing `tests/components/test_hint_generation.py` (cascade quarantine paths) — unchanged, re-run | L1 | yes |
| FR-A2/A3 | `_hint_bank.test.ts::full ladder per bank item (or waivered)` — same assertion as FR-E1 | L1 | yes (vitest) |
| FR-B1 | `tests/scripts/test_emit_hint_bank.py::test_emits_both_modules_deterministically` (tmp JSON → byte-stable outputs) | L1 | yes |
| FR-B2 | `_hint_bank.test.ts::parity with seed JSON` + `tests/components/test_subject_coach_bank_hints.py::test_parity_with_seed_json` | L1 | yes |
| FR-B3 | `tests/components/test_subject_coach_bank_hints.py::test_authored_by_carries_generated_by` | L1 | yes |
| FR-C1 | `composition_engine_browser` seed test (dev path seeds hints; prod path empty) — extend the existing root test | L1 | yes (vitest) |
| FR-C2 | existing `use_quiz` ladder-load tests + one bank-id fixture case | L1 | yes (vitest) |
| FR-C3 | existing `drizzle_hint_repo` conformance (reviewed gate) — unchanged | L1 | yes (vitest) |
| FR-D1 | `tests/components/test_subject_coach_hints.py::test_bank_id_returns_bank_rungs` (red first: `[]` today) | L1 | yes |
| FR-D2 | `tests/components/test_subject_coach_hints.py::test_unknown_id_returns_empty` | L1 | yes |
| FR-E1 | `_hint_bank.test.ts` coverage ratchet (fails on synthetic gap fixture) | L1 | yes (vitest) |
| FR-E2 | `tests/architecture/test_hint_provenance_confinement.py` (or extension of the test_item scan) — red on a hand-authored reviewed row | L1 | yes |
| FR-E3 | `tests/components/test_hint_bank_leakage.py::test_corpus_rows_pass_leakage_check` | L1 | yes |

Live generation run (FR-A5) is evidence-logged in the `.impl.md` (verbatim
output, the item-bank precedent), not a CI test.

## 9. Definition of Done

- [ ] All FRs implemented; each mapped test *seen to fail first* where a red
      state is constructible (FR-D1, FR-E1, FR-E2 explicitly).
- [ ] `make check` green + frontend vitest green (`pnpm test`), incl.
      `tests/architecture/` (provenance + ratchet).
- [ ] Live run evidence pasted verbatim in `coach-bank-hints.impl.md`
      (per-item PASS/quarantine counts, waiver table if any).
- [ ] ADR-0014 amendment note + `decisions.md` entry landed (§5).
- [ ] CoachPanel verified against a bank item in the dev preview (two rungs
      visible via "One more nudge", rung-1 on the item card).
