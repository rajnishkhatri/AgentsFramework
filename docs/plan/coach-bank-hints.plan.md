# Plan — Reviewed hint ladders for the governed test_item bank

> Realizes [coach-bank-hints.spec.md](coach-bank-hints.spec.md) (Approved
> 2026-07-07). Branch: fresh off `main` (PR #132 merged). The generation
> pipeline pre-exists; this plan wires content → corpus → two generated
> modules → two serving planes → guards.

**Related:** [brainstorm](coach-bank-hints.brainstorm.md) ·
[ADR-0014](../adr/0014-subject-coach-hint-repo-read-seam.md) ·
[ADR-0021](../adr/0021-bank-backed-practice-scheduler.md)

---

## 1. Architecture at a glance

```
TEST_ITEM_BANK rows (8 × ti-gen-*)                 [exists]
      │  export → questions.json (already generator-shaped)
      ▼
scripts/generate_hints.py  ──live, iterate ≤3/item──►  cascade PASS rows
      (governed build_graph job)   (run_hint_cascade:   [exists, unchanged]
                                    schema → leakage → dup)
      ▼
docs/plan/coach-bank-hints.seed.json               [NEW — canonical corpus]
      │
      ▼  scripts/emit_hint_bank.py                 [NEW — deterministic converter]
      ├─► frontend/lib/adapters/engine/_hint_bank.ts        [NEW, generated]
      │       └─ seedHintBank(db) ← composition_engine_browser dev path
      │            └─ DrizzleHintRepo (reviewed-only) → use_quiz.hintLadder
      │                 └─ item card rung-1 + CoachPanel rungs-2/3   [exists]
      └─► components/subject_coach_bank_hints.py            [NEW, generated]
              └─ subject_coach_hints.rungs_for_question (AUTHORED + BANK)
                   └─ react_loop.py:2332 → FR-20 persona render     [exists]

Guards: _hint_bank.test.ts (parity + full-ladder ratchet, vitest)
        tests/architecture/test_hint_provenance_confinement.py
        tests/components/test_hint_bank_leakage.py (re-run leakage over corpus)
```

Single source: the JSON. Both modules are generated + parity-pinned; neither is
hand-edited (header comment carries the regeneration command).

## 2. File-level touchpoints

### Feature B first (converter + generated-module shape, testable without LLM)

| File | Change |
|------|--------|
| `scripts/emit_hint_bank.py` | NEW. Read seed JSON → emit both modules, sorted `(question_id, rung)`, byte-stable. JSON-quoted keys in the TS literal (provenance-detector convention). Waiver table (FR-A3) emitted into the TS module as `HINT_BANK_WAIVERS`. |
| `tests/scripts/test_emit_hint_bank.py` | NEW. tmp JSON → both outputs byte-stable across two runs; field mapping `generated_by→authored_by`; rung-bounds rejection. |
| `frontend/lib/adapters/engine/_hint_bank.ts` | NEW (generated). `HINT_BANK: readonly Hint[]`, `HINT_BANK_WAIVERS`, `export function seedHintBank(db)`. |
| `components/subject_coach_bank_hints.py` | NEW (generated). `BANK_RUNGS: Final[list[HintRung]]` literal; stdlib+Pydantic only. |

### Feature A (live run → corpus; after B so emission is ready)

| File | Change |
|------|--------|
| `docs/plan/coach-bank-hints.seed.json` | NEW. Cascade PASS rows verbatim (8 items × rungs 1–3). |
| (scratch) `questions.json` export | From `_test_item_bank.ts` rows — a tiny read-only extractor step inside the run procedure (scratchpad, not checked in). |
| `docs/plan/coach-bank-hints.impl.md` | NEW. Verbatim run evidence: per-item PASS/quarantine counts, attempts, waivers. |

`scripts/generate_hints.py`, `components/hint_generation.py`,
`components/hint_leakage.py`, `prompts/hint_generator.j2`: **unchanged**.

### Feature C (frontend serving)

| File | Change |
|------|--------|
| `frontend/lib/composition_engine_browser.ts` | +1 line in the dev-default branch: `seedHintBank(db);` next to `seedTestItemBank(db)` (+import). e2e injection + prod branches untouched. |
| existing root/seed vitest | Extend: dev path serves a bank ladder; prod path stays empty. |

`use_quiz.ts`, `CoachPanel.tsx`, `quiz/page.tsx`, `drizzle_hint_repo.ts`,
`ports/engine/hint_repo.ts`, both schema dialects: **unchanged**.

### Feature D (backend persona plane)

| File | Change |
|------|--------|
| `components/subject_coach_hints.py` | `rungs_for_question` default source becomes `AUTHORED_RUNGS + BANK_RUNGS` (one import of the sibling data asset — the `hint_generation → hint_leakage` pure-asset precedent). |
| `tests/components/test_subject_coach_hints.py` | +2 tests: bank id → bank rungs ascending (red first — returns `[]` today); unknown id → `[]`. No existing assertions weakened (no G8). |

`orchestration/react_loop.py`: **unchanged** (call site exists).

### Feature E (guards)

| File | Change |
|------|--------|
| `frontend/lib/adapters/engine/_hint_bank.test.ts` | NEW. Parity vs seed JSON; full-ladder ratchet over `TEST_ITEM_BANK` (waiver-aware); reviewed=true only. |
| `tests/architecture/test_hint_provenance_confinement.py` | NEW (sibling of the test_item scan — its `stem_md` keying can't see hint rows). Scans `_hint_bank.ts` (+ any future `_SEED_FILES`-style tuple) for `reviewed=true` hint-shaped rows (`body_md`+`rung`) lacking `<model>@<hex>` / `"authored"` provenance. Red first via a synthetic bad row. |
| `tests/components/test_hint_bank_leakage.py` | NEW. Load seed JSON + bank items; `check_rung_leakage` over every row (pure, L1). |
| `tests/components/test_subject_coach_bank_hints.py` | NEW. Parity vs seed JSON; `authored_by` carries the stamp. |

### Governance / docs

| File | Change |
|------|--------|
| `docs/adr/0014-subject-coach-hint-repo-read-seam.md` | Dated amendment note in §Consequences: source direction inverted — the generated corpus is now upstream of the Python asset for bank ids (this spec). |
| `docs/adr/decisions.md` | 2–4 line entry (JSON-canonical + two generated modules; authored rows kept inert; waiver-token bar). |
| `docs/adr/log.md` / `index.md` | Only if the ratchet requires; no new ADR file. Commit carries `ADR-OK:` waiver if the path-trigger fires spuriously. |

## 3. Migration / sequence

1. **Branch** `feat/coach-bank-hints` off updated `main`; baseline `make check`
   + `pytest tests/architecture/ -q` green before any edit.
2. **B (red→green):** converter + its tests with a hand-written 2-row fixture
   JSON; then generated-module parity tests (against the fixture).
3. **A (live, on-demand):** export bank rows → run `generate_hints.py`
   (iterate, `--existing`) → freeze `coach-bank-hints.seed.json` → run the
   converter → check in both generated modules; evidence into `.impl.md`.
4. **E (red first where constructible):** provenance scan red on a synthetic
   hand-authored row; ratchet red before C wiring? (ratchet is seed-level —
   red via a temporarily-removed rung fixture); leakage re-verification green.
5. **D (red→green):** bank-id test red (`[]`), then the one-line source merge.
6. **C:** dev-path seed call + root test extension; manual dev-preview check
   (CoachPanel two rungs + item-card rung 1 on a bank item).
7. **Docs:** ADR-0014 amendment + decisions.md; `make check` + vitest full run.

Ordering rationale: B before A so the live run's output flows straight through
a tested converter (the item-bank increment ran generation first and paid for
it with ad-hoc TS emission).

## 4. Constitution check

- **#1–#2:** untouched (no trust/, no services/ changes).
- **#3/#5:** new component file is a literal data asset; the
  `subject_coach_hints → subject_coach_bank_hints` import is data-asset reuse
  (existing precedent), not a peer decision import; no langgraph/langchain.
- **#6:** zero orchestration edits.
- **#8:** meta/ untouched.
- **⚠️ Ask-first:** no new dependency, node, service, port, or abstraction —
  converter script + data modules reuse existing seams. ADR-0014 amendment
  note is documentation, not a new ADR.
- **Live-LLM:** step 3 only, developer machine, never CI (`make check` stays
  deterministic).

## 5. Analyze-pass (Stage 4) findings — 2026-07-07

Grounding probes (every referenced file/API opened or grepped, not recalled):

| Probe | Result |
|-------|--------|
| `scripts/generate_hints.py`, `run_hint_cascade`, `check_rung_leakage(body_md, question)` | ✅ exist; cascade PASS dicts field-identical to the `Hint` Zod entity (`engine_entities.ts:104-113`) |
| `HintRung` (`components/subject_coach_hints.py:34-43`) | ✅ has `authored_by: str` — FR-B3 mapping valid |
| `db.seedHints` + `seedTestItemBank` pattern | ✅ (`composition_engine_browser.ts:159`, `_test_item_bank.ts:373`) |
| Test homes (`tests/scripts/`, `tests/components/test_subject_coach_hints.py`, provenance scan) | ✅ all exist |
| New pyproject deps | ✅ none needed (converter = stdlib; tests = existing stack) |
| Baseline `pytest tests/architecture/ -q` | ✅ `162 passed, 4 skipped in 29.83s` (on the pre-branch tree) |

Findings:

- **AF-1 (resolved into T0.1):** the G8 tombstone
  `tests/components/test_hint_seed_parity.py` is **untracked** and NOT on
  merged `main` — the ADR-0021 increment's parity-suite retirement record
  never landed. Carry it on this branch.
- **AF-2 (accepted):** FR-C2's CoachPanel check is manual dev-preview
  evidence (DoD item), not CI — the interaction layer is already covered by
  existing component tests; only the *content* is new.
- **AF-3 (accepted):** FR-A2's ≤3-attempt bound is procedural, verified by
  `.impl.md` run evidence rather than a test (live-LLM stays off CI).
- **Cross-artifact:** every spec FR maps to ≥1 task with a pass/fail check;
  no task references a non-existent file/API; no invariant conflicts
  (constitution check §4). Spec §8 test table ↔ tasks phases are 1:1.
