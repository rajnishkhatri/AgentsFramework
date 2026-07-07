---
type: brainstorm
title: 'Brainstorm — live hint ladders for the ADR-0021 test_item bank'
status: gate-passed
created: 2026-07-07
owner: Rajnish Khatri
related: 0021-bank-backed-practice-scheduler.md, 0014-subject-coach-hint-repo-read-seam.md, 0012-subject-coach-context-contract-hint-ladder.md, coach-item-bank-live.spec.md
---

# SDD Stage 1 — Brainstorm: hint ladders for bank-served practice items

**Problem (as posed).** ADR-0021 made the governed `test_item` bank the sole
practice-quiz source and deleted `DEV_HINTS` with the dev questions. Bank items
ship without hint ladders, so the iPad CoachPanel falls back to its generic
nudge. "We don't have live/accurate hints for each question — plan to implement
hints for the question bank."

---

## Premise audit (checked against the working tree, not memory)

| # | Premise | Status | Evidence |
|---|---------|--------|----------|
| P1 | ADR-0021 removed `DEV_HINTS`; bank items have no hint ladders | **verified** | `frontend/lib/adapters/engine/_dev_seed.ts:14-19` (removal + "generic nudge" note); ADR-0021 §Consequences risk bullet; the browser dev path seeds skills/states + bank but **never calls `db.seedHints`** (`composition_engine_browser.ts:163-168` — `seedHints` fires only on the e2e `window` injection path, line 159) |
| P2 | The CoachPanel/quiz degrade to a generic fallback on an empty ladder | **verified** | `use_quiz.ts:102-104` (ladder loads with the item; `[]` → generic nudge), `CoachPanel.tsx:40-44` (two-tier nudge = rungs 2/3), `app/(coach)/learn/quiz/page.tsx:188` (rung-1 falls back to answer-free `socraticHint()`) |
| P3 | "No hint capability exists — we must plan/build hint generation" | **REFUTED (re-posed below)** | The full governed pipeline already exists end-to-end: `scripts/generate_hints.py` (governed `build_graph` job, quarantine → `eval_capture target=hint_generator`), `components/hint_generation.py::run_hint_cascade` (schema → deterministic per-rung leakage → duplicate; content-hash ids, idempotent), `components/hint_leakage.py`, `prompts/hint_generator.j2`. ADR-0021's "deferred to a later `scripts/generate_hints.py` run" refers to an **existing** script, not a to-be-built one |
| P4 | (implicit) The backend coach persona still has a working hint source | **REFUTED** | `components/subject_coach_hints.py::AUTHORED_RUNGS` is keyed to the deleted dev ids (`q-punc-1`, `q-gram-1`, …); `orchestration/react_loop.py:2332` calls `rungs_for_question(question_id)` with the live `ti-gen-*` ids → always `[]`. The authored Python asset is now **orphaned content on both planes** |
| P5 | Bank rows carry everything the hint generator needs as input | **verified** | `hint_generator.j2` reads `id / stem_md (or stem) / choices / answer_letter / why_correct_md`; every `_test_item_bank.ts` row carries all of them (ADR-0021 teaching-fields extension). 8 reviewed items, ids `ti-gen-*`, 6/6 skill coverage (`_test_item_bank.test.ts`) |
| P6 | The serving seam is ready — only content is missing | **verified** | `ports/engine/hint_repo.ts` + `DrizzleHintRepo` (reviewed-only FR-12 pin) wired in **both** composition roots (`composition_engine_browser.ts:111`, `composition_engine.ts:132`); `db.seedHints` exists; `hint` table in both dialects with unique `(question_id, rung)` |
| P7 | Existing guards will cover a new checked-in hint seed | **REFUTED** | `tests/architecture/test_test_item_provenance_confinement.py:38-43` matches only `stem_md`-bearing rows — hint rows are *invisible* to it. A checked-in generated hint seed ships **unguarded** unless a hint-provenance sensor is added. (The old two-plane parity pin was retired as a G8 tombstone: `tests/components/test_hint_seed_parity.py`) |

**Re-posed framing (P3/P4 corrected).** This is not "build hint generation."
The generation + verification machinery is built and governed. The increment is:
**(a)** run the existing cascade over the 8 bank items, **(b)** build the missing
*serving-side seed path* for reviewed hint rows (the frontend hint table is empty
in dev), **(c)** decide the *single source of truth* now that the two-plane
parity discipline is retired and the Python asset is orphaned, and **(d)** add
the guards (provenance + coverage) the retirement left behind.

No D0: the generic-nudge fallback is a documented degradation, not a live defect.

---

## Directions

### High-probability (follow existing repo patterns)

**D1 — Batch-generate + checked-in `_hint_bank.ts` seed (LEAD).**
Pattern: `_test_item_bank.ts` (ADR-0021) + `scripts/generate_hints.py` (ADR-0014
Phase 4). Export the 8 bank rows to `questions.json` (they are already the dict
shape the script expects), run the governed job (cascade earns `reviewed=true`;
`generated_by="<model>@<workflow_id>"`), emit a checked-in
`frontend/lib/adapters/engine/_hint_bank.ts`, load it in the browser dev path
next to `seedTestItemBank(db)` (+ pg-root parity), and add a hint-provenance
sensor (P7).
*Tradeoffs:* static content — regeneration needed whenever the bank grows (D4
closes that class). *What breaks if chosen:* nothing structural; read-only
posture preserved. *Invariants stressed:* none of the 8; composition-root-only
wiring (C1/C2). *ADR:* the run itself was anticipated by ADR-0021 (no new ADR);
the checked-in-seed + guard shape is a `decisions.md` entry.

**D2 — Fuse hint emission into test_item generation.**
Extend `test_item_generator.j2` + the item cascade so each generated item
carries its ladder; promotion writes both tables. *Why attractive:* hints can
never lag the bank. *Why suspect:* ADR-0014 deliberately gave the hint family
its own review/provenance lifecycle ("a failed rung would poison the whole
question's review state" — the rejected-JSON-column rationale applies to fused
*generation* too: one quarantined rung shouldn't block an item's promotion, and
vice versa). Needs an ADR (deviates from the ADR-0014 separation). ❌-leaning.

**D3 — Re-key the backend plane / unify the hint source (P4 fix).**
`react_loop.py:2332` renders reviewed rungs into the coach context (FR-20:
paraphrase, never free-generate) — today it always gets `[]`. Options inside
this direction: (a) generated JSON becomes the single source consumed by both
the TS seed emitter and `subject_coach_hints.py` (replacing the orphaned
`AUTHORED_RUNGS` for bank ids), or (b) frontend-only now, backend deferred.
Note (a) *inverts* ADR-0014's "seed is generated FROM the Python asset" — the
generated corpus becomes upstream of both planes → short ADR-0014 amendment or
`decisions.md` entry at spec time.

### Exploratory (different abstraction / integration)

**D4 — Class-level coverage ratchet (do-regardless hygiene).**
The defect *class* is "bank grows; a dependent content family silently lags →
generic fallback" (this is its first occurrence; the seed-parity retirement was
the enabling event). Mechanical sensor: a seed-level test asserting every
`reviewed=true` bank item has a full reviewed 3-rung ladder (or carries an
explicit waiver token), plus the P7 provenance guard. Cheap, independent once
D1 lands, prevents the recurrence instead of patching the instance.

**D5 — Demand-side: deterministic rung derivation, LLM as fallback.**
The bank rows already carry *reviewed teaching content*: `rule_md` is "the
underlying rule named in general terms" — structurally rung-2's definition
(ADR-0012). A pure-function deriver (`rule_md` → rung-2 candidate; skill-level
probe templates → rung-1) gated by the **existing** deterministic
`check_rung_leakage` would cover part of every ladder with zero LLM calls;
`generate_hints.py` fills only the residue (rung 3, failed derivations).
Repo precedent: the guardrail regex→classifier→LLM cascade. *Honest cost
framing:* at N=8 the LLM run is minutes — demand-side pays off only at
full-ACT-bank scale. *Risk:* derived text from `why_correct_md` /
`per_choice_rationale` is high leakage risk (those fields are withheld from the
solver precisely because they reveal the key); `rule_md`-only derivation keeps
the gate honest. Tag: revisit at scale; not the lead now.

**D6 — Live on-demand hint generation by the coach agent. ❌ as-stated.**
"When the ladder is empty, let the live coach free-generate a hint." This
crosses the deliberately-maintained ADR-0012/FR-20 discipline — pre-submit hint
content **only** from `reviewed=true` leak-checked rows; the persona
paraphrases a reviewed rung, never free-generates. Surfaces that discipline
protects: the FR-12 row gate, the no-assertion-rung wire literal (`1|2|3`),
the deterministic leakage check, the quarantine/eval-capture loop, and the
Test-Mode leak posture next door. Every one is bypassed by live generation.
Rejected unless the reviewed-only contract is re-decided by ADR.

---

## Hypotheses for the lead (D1 + D3-a + D4) — validated

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Works because bank rows are already generator-shaped input | **PASS** | P5: `hint_generator.j2` field list ⊆ `TestItem` row fields |
| Safe because `reviewed=true` is *earned*, never asserted | **PASS** | `run_hint_cascade` stages (schema → `check_rung_leakage` per rung → Jaccard dup); quarantine → `eval_capture target=hint_generator` |
| Serving stays read-only / leak-safe | **PASS** | `HintRepo` has no write surface; `DrizzleHintRepo` serves `reviewed=true` only (FR-12 conformance pin); ladder loads with the item, rung ascending |
| The seed seam exists — one call to add | **PASS** | `db.seedHints` implemented + already exercised by the e2e injection path (`composition_engine_browser.ts:159`); dev default path needs the parallel of `seedTestItemBank` |
| Existing provenance guard covers hint rows | **FAIL → D4 scope** | P7: the scan keys on `stem_md`; hint rows pass unseen |
| Backend persona benefits automatically | **FAIL → D3 decision** | P4: `rungs_for_question` is id-keyed; needs the generated rows (or stays `[]`) |

## Dependency structure

- **Sequenced:** everything stacks on the ADR-0021 branch
  (`feat/coach-item-bank-live`, PR #132 pending) — hints key to `ti-gen-*` ids
  that only exist there. Land after (or on) that branch, not parallel to it.
- **Independent once D1 lands:** D4 (ratchet), D3 (backend plane).
- **Cost axes:** engineering time is small (one script run + one seed module +
  wiring + tests). The load-bearing wait is a **live LLM run** (minutes, 8×~4
  graph runs) — never in CI, needs `.venv` + keys (repo-venv note applies).

## Human gate (Stage 1 → sdd-spec)

- **Q1 — direction:** D1 (recommended) vs D2 (fused generation, ADR required)
  vs D5 (deterministic-first hybrid).
- **Q2 — backend plane:** D3-a unify source now (ADR-0014 amendment note) vs
  D3-b frontend-only, defer backend.
- **Q3 — ratchet:** include D4 in the same increment (recommended) or defer.
- **Q4 — landing:** stack on `feat/coach-item-bank-live` pre-merge vs follow-up
  branch after PR #132 merges.

### Gate decision (2026-07-07) — advance to sdd-spec

- **Q1: D1** — batch-generate via the existing `scripts/generate_hints.py`;
  checked-in `_hint_bank.ts` seed on the `_test_item_bank.ts` pattern.
- **Q2: D3-a** — the generated hint corpus becomes the single source for both
  planes (TS seed + `subject_coach_hints.py` bank-id rungs); spec must carry
  the ADR-0014 amendment / `decisions.md` note for the inverted source
  direction. D5 (deterministic derivation) deferred to full-bank scale; D6
  rejected (crosses the FR-20 reviewed-only discipline).
- **Q3: yes** — D4 coverage ratchet + hint-provenance guard in the same
  increment.
- **Q4:** PR #132 is **merged**; this lands on a fresh follow-up branch off
  `main`.
