# Tasks — Reviewed hint ladders for the governed test_item bank

> Executes [coach-bank-hints.plan.md](coach-bank-hints.plan.md) (Approved
> 2026-07-07). Red/green TDD per task; each task ends by checking its own
> pass/fail criterion (mapped 1:1 from the spec's EARS FRs). `[P]` = may run
> in parallel within its phase once its dependency line is satisfied.

## Phase 0 — Branch + baseline (no code)

- **T0.1** Branch `feat/coach-bank-hints` off updated `main`; commit the
  untracked docs (`coach-bank-hints.{brainstorm,spec,plan,tasks}.md`) and the
  leftover G8 tombstone `tests/components/test_hint_seed_parity.py` (analyze
  finding AF-1 — it is NOT on merged main).
  *Pass:* `git log --oneline -1` on the new branch; tombstone tracked.
- **T0.2** Baseline: `make check` + `pytest tests/architecture/ -q` +
  `cd frontend && pnpm vitest run` green BEFORE any edit (paste output).
  *Pass:* all green (vitest arch-suite flake note: re-run isolated if the
  ts-morph suites time out under load).

## Phase B — Converter + generated-module shape (deterministic; do FIRST) → FR-B1..B3

- **T B.1 (red)** `tests/scripts/test_emit_hint_bank.py`: with a 2-row fixture
  JSON — (a) two runs emit byte-identical `.ts`/`.py` outputs; (b) `.py` rows
  are valid `HintRung`s with `authored_by == generated_by`; (c) a rung outside
  1..3 in the JSON → converter exits non-zero. Watch it fail (no script).
  *Pass:* red for the right reason (ModuleNotFoundError/usage error).
- **T B.2 (green)** `scripts/emit_hint_bank.py`: JSON → `_hint_bank.ts`
  (`HINT_BANK` JSON-quoted rows + `HINT_BANK_WAIVERS` + `seedHintBank(db)`)
  and `components/subject_coach_bank_hints.py` (`BANK_RUNGS` literal), sorted
  `(question_id, rung)`, generated-file headers with the regeneration command.
  *Pass:* T B.1 green; `make check` green.
- **T B.3 [P]** Parity tests against the FIXTURE (they re-point at the real
  seed in Phase A): `tests/components/test_subject_coach_bank_hints.py`
  (module ↔ JSON row-for-row; `authored_by` stamp) and the vitest side
  `_hint_bank.test.ts::parity` skeleton.
  *Pass:* FR-B2 tests green on the fixture.

## Phase A — Live generation run → canonical corpus (on-demand; needs keys) → FR-A1..A5

- **T A.1** Export the 8 `TEST_ITEM_BANK` rows to scratchpad `questions.json`
  (read-only extraction — rows are JSON-quoted in the TS literal).
  *Pass:* 8 objects, each with id/stem_md/choices/answer_letter/why_correct_md.
- **T A.2** Run `.venv/bin/python scripts/generate_hints.py --questions … --out …`;
  iterate per item (≤3 attempts, `--existing` accumulating accepted bodies)
  until every item has rungs {1,2,3} or is waivered (FR-A3). Record every
  attempt verbatim in `coach-bank-hints.impl.md`.
  *Pass:* FR-A2 bar met (or explicit waiver rows); quarantines visible in the
  eval_capture log (FR-A1 evidence).
- **T A.3** Freeze `docs/plan/coach-bank-hints.seed.json`; run the converter;
  check in both generated modules; re-point the T B.3 parity tests at the real
  seed.
  *Pass:* parity green on the real corpus; `git diff --stat` shows only the
  three data artifacts + test re-point.

## Phase E — Guards (red-first where constructible) → FR-E1..E3

- **T E.1 (red→green)** `tests/architecture/test_hint_provenance_confinement.py`:
  scans `_hint_bank.ts` for `reviewed=true` hint-shaped rows (`body_md`+`rung`,
  no `stem_md`) whose `generated_by`/provenance is neither `<model>@<hex>` nor
  `"authored"`. Red via a synthetic bad row in a tmp copy (test fixture), then
  green on the real seed.
  *Pass:* fails on the synthetic row; green on `_hint_bank.ts`.
- **T E.2 (red→green)** `_hint_bank.test.ts::coverage ratchet`: every
  `reviewed=true` item in `TEST_ITEM_BANK` has rungs {1,2,3} in `HINT_BANK`
  unless `(item, rung)` ∈ `HINT_BANK_WAIVERS`. Red first against a mutated
  in-test fixture (not the shipped seed).
  *Pass:* FR-E1 semantics demonstrated red, then green.
- **T E.3 [P]** `tests/components/test_hint_bank_leakage.py`: load seed JSON +
  bank items (from A.1's extraction logic, made a test helper);
  `check_rung_leakage(body_md, item)` returns `[]` for every row.
  *Pass:* green (pure L1; in `make check`).

## Phase D — Backend persona plane (red-first) → FR-D1..D2

- **T D.1 (red)** `tests/components/test_subject_coach_hints.py`:
  `rungs_for_question("<real ti-gen id>")` returns 3 rungs ascending — watch
  it fail (returns `[]` today); plus unknown-id → `[]` (already-green guard,
  keep as regression).
  *Pass:* red on the bank-id case.
- **T D.2 (green)** `components/subject_coach_hints.py`: default source =
  `AUTHORED_RUNGS + BANK_RUNGS` (import the generated data asset). No other
  behavior change; no existing assertion weakened (no G8).
  *Pass:* T D.1 green; `make check` green.

## Phase C — Frontend serving wire (after A; one line) → FR-C1..C3

- **T C.1 (red→green)** Extend the browser composition-root seed test: dev
  default path serves a non-empty ladder for a bank id; prod branch stays
  empty. Then add `seedHintBank(db);` + import in
  `composition_engine_browser.ts` dev branch only.
  *Pass:* test red before the wire, green after; e2e-injection branch
  untouched (existing tests stay green).
- **T C.2** Manual dev-preview verification on a bank item: item-card
  Get-a-hint shows rung 1; CoachPanel "One more nudge" reveals rungs 2 then 3
  (`panel-nudge-2/3` testids). Screenshot/snapshot evidence into `.impl.md`.
  *Pass:* FR-C2 observed; evidence pasted.

## Phase G — Governance docs

- **T G.1** ADR-0014 §Consequences dated amendment note (source direction
  inverted for bank ids; link this spec) + `docs/adr/decisions.md` entry
  (JSON-canonical, two generated modules, authored rows kept inert, waiver
  bar). `ADR-OK:` waiver in the commit message only if the ratchet fires.
  *Pass:* `pytest tests/architecture/test_adr_ratchet.py -q` green.

## Phase V — Verify end-to-end (no new code)

- **T V.1** Full gates: `make check` + `pytest tests/architecture/ -q` +
  `cd frontend && pnpm vitest run` — paste outputs into `.impl.md`.
- **T V.2** DoD cross-check against spec §9 (every box, with evidence links).

## Dependency graph

```
T0.1 → T0.2 → TB.1 → TB.2 → TB.3[P]
                        └──→ TA.1 → TA.2(live) → TA.3 → TE.1[P] TE.2[P] TE.3[P]
                                                   ├──→ TD.1 → TD.2
                                                   └──→ TC.1 → TC.2
TE.*, TD.2, TC.2 → TG.1 → TV.1 → TV.2
```

## Definition-of-Done cross-check (spec §9)

- [ ] Every FR (A1–A5, B1–B3, C1–C3, D1–D2, E1–E3) has a task + a test seen
      red first where constructible (TB.1, TE.1, TE.2, TD.1, TC.1).
- [ ] Live-run + preview evidence verbatim in `coach-bank-hints.impl.md`.
- [ ] ADR-0014 amendment + decisions.md entry landed; adr-ratchet green.
- [ ] All gates green with pasted output (TV.1).
