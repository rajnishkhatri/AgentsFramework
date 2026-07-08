# Implementation evidence — ACT-English bank Phase B

**Date:** 2026-07-08 · **Spec:** [act-english-bank-phase-b.spec.md](act-english-bank-phase-b.spec.md) ·
**Related:** [ADR-0022](../adr/0022-act-english-syllabus-substrate.md) (D3),
ADR-0015 (cascade), ADR-0012 (answer-bearing fields), ADR-0014 (emitter seam).

Evidence log per the spec's Definition of Done (§9): **verbatim outputs, not
summaries.** Red→green seen first for every new gate; live-run `DONE:` lines and
gate results pasted below.

---

## T0–T6 (offline authoring + deterministic gates) — committed earlier

Rail fix (`4ddd7fe`), SDD docs (`8eb5179`), D3 syllabus substrate + ADR-0022
(`2815207`), seed gates red-first (`15c2dfb`), tier knob (`f21e226`), emitter
(`3e36bb7`), D2 split (`ab76ff1`), T5 fold (`241b175`), T6 six tranches to 164
rows (`f76af64`/`7d9fec6`/`6753a71`/`0537e13`), proactive review + key rebalance
+ TAP-4 (`bb12315`/`b683a12`/`1d8442a`), decided-rule verification (`e1cb6c9`),
T5b Test-01 fold to 192 (`e82baf9`/`0c7d4d8`). At T6 end the matrix conformance
test went live-green (marker removed): **197 passed, 1 skipped, 0 xfailed.**

---

## T3 tier-knob DEFECT — found during T7, fixed red→green (`d944b6b`)

The `--capable-difficulty` knob decided the tier from `item.get("difficulty")`
in `_make_tiered_solver`, but the cascade fed the solver `_solver_view(raw_item)`,
which returns only `context_html`/`stem_md`/`choices` — **difficulty stripped**,
so the guard `isinstance(difficulty, int)` never held and every item routed fast.
The unit tests hid it (they called `_make_tiered_solver` with a dict that *had*
difficulty; the cascade integration dropped it).

Red — the new test caught the defect exactly:

```
FAILED tests/components/test_test_item_generation.py::TestTeachingFieldsGate::test_cascade_hands_solver_the_full_item_for_tier_routing
E   AssertionError: solver did not receive difficulty — tier router is blind, capable tier can never fire
E   assert None == 3
```

Fix (route-before-view): the cascade now calls `solver(raw_item)`; each real
solver applies `_solver_view` itself before rendering, so the router sees
difficulty while the model still never sees the key. Three answer-blindness tests
re-pointed onto `_solver_view` directly (stronger). Green: `45 passed`. Offline
wiring proof (stub tiers, `capable_difficulty=4`):

```
d1 -> fast · d2 -> fast · d3 -> fast · d4 -> capable · d5 -> capable · dNone -> fast
PASS: d>=4 routes capable, d<4 + missing routes fast
```

`make check`: **5279 passed**.

---

## T7 — full-corpus promotion (FR-1,2,3,7,10)

Live `--import-seed` cascade (schema → independent-solver key gate → duplicate).
Three runs; the tier defect and the d2/d3 fast-tier weakness are visible in the
run-over-run deltas.

**Run 1 (defective tier) — proves the defect on real traffic:**

```
DONE: 150 reviewed item(s) -> docs/plan/coach-item-bank-live.promoted.json (42 quarantined)
tier calls: capable=0  fast=384        # 82 d>=4 items ALL ran fast
```

**Run 2 (tier fixed, `--capable-difficulty 4`):**

```
DONE: 161 reviewed item(s) -> ... (31 quarantined)
tier calls: capable=82                 # every d>=4 item on gpt-4o
```

Promote-rate by difficulty, run-1 → run-2 (the fix recovered the hard items):

```
       d1    d2    d3    d4    d5
run-1: 87%   72%   79%   87%   63%
run-2: 87%   72%   79%   95%   84%      # d4/d5 lifted; d2/d3 unchanged (fast tier)
```

**Quarantine triage (31 rows, live re-solve + open coding):** ~23 were
fast-tier FALSE-NEGATIVES on *correct* items (gpt-4o-mini weak at d2/d3
parallelism/agreement/modifier/register, and distracted by seeded errors
elsewhere in a passage), 3 genuine defects, ~4 ambiguous, 1 nondeterministic.
Capable-tier re-solve of all 31 recovered **17/31** (incl. all 6 items fixed for
defect/ambiguity). The 6 fixes: `2840ae2`.

**Run 3 (fixed seed, `--capable-difficulty 2` — the clean fold, `a8ca29f`):**

```
DONE: 171 reviewed item(s) -> docs/plan/coach-item-bank-live.promoted.json (21 quarantined)
tier calls: capable=176  fast=208      # every d2+ item graded by gpt-4o
```

**T7 pass criteria (§12) — all met:**

```
[PASS] promoted 171 >= 170
[PASS] capable-tier calls visible for d4-5: 176 total
[PASS] ids stable + unique: 171/171 (content-hash ti-gen-*)
[PASS] standard coverage in PROMOTED: 32/32
       key balance B/C/D = 54/52/49 (no position bias survives promotion)
       items by skill: s-gram 39, s-punc 31, s-rhet 28, s-style 26, s-org 24, s-sent 23
```

---

## T8 — hint ladders (FR-4,5,11) (`665e50c`, `a1ca0fe`)

Live `generate_hints.py` → `run_hint_cascade` (deterministic leakage gate) →
`emit_hint_bank.py`. One graph run per promoted item; each rung must scaffold
without revealing the answer.

**Main run (171 items):**

```
DONE: 502 reviewed rows -> t8_new_hints.json (11 quarantined -> target=hint_generator)
```

The leakage gate worked as designed — a representative catch:

```
{"stage": "leakage"}: {"violations": ["quotes the correct choice's label"],
 "raw": "{'rung': 2, 'body_md': \"Consider the difference between 'could have' and 'could of' ...\"}"}
```

8 items gapped from a mid-ladder quarantine. Unioning across 3 regeneration
attempts closed 4. The other 4 were **atomic** (single irregular-verb swaps
sung→sang / teached→taught / carry→carries; a bare cause-effect transition) whose
missing rung couldn't generate without leaking. Per the **reword-not-waive**
decision: reframed their STEMS (context edits don't help — `_row_id` hashes
stem+answer, and the leak is stem-anchored) and re-promoted through the T7 key
gate (`4 reviewed, 0 quarantined`). 3 closed by regeneration. The last — the
transition item's rung-2 concept, which *is* the answer — traced to
`why_correct_md` **stating the relationship** ("the second is the result of the
first"), which the generator recited (why-correct-recital leak class). Reframing
`why_correct` to method-language ("read what the second sentence does to the
first, then match the transition") produced a clean 3-rung ladder with genuine
cascade provenance — **no waiver, no hand-authored/faked provenance.**

**Landing artifacts:** 513 reviewed hint rows, 0 waivers; wholesale re-emit of
both planes (`_hint_bank.ts`, `subject_coach_bank_hints.py`, `_test_item_bank.ts`).
15 stale shipped-hint rows dropped (ids changed by the earlier key-rebalance /
rework) — no serving regression (every item present under its current id).

**Gates:**

```
ladderGaps == 0 · zero waivers · leakage green
frontend engine suite: 11 files, 80 passed  (provenance confinement FR-B2,
    coverage ratchet FR-E1, serving path FR-C1)
python leakage + emit: 22 passed
```

---

## T9 — landing gate (FR-6,12,13,14) (`a1ca0fe`, `0efe1c3`)

Both serving planes emitted wholesale from the frozen promoted corpus. Full gate:

```
make check:  All checks passed!
             ruff check — All checks passed!
             ruff format — 803 files already formatted
             pyright — 0 errors, 0 warnings, 0 informations
             cite_lint — clean: 10 REVIEW.md file(s), 0 cite violations
             hygiene — end-of-file-fixer / trailing-whitespace / merge-conflicts / large-files: Passed
             pytest — 5279 passed, 49 skipped, 72 deselected in 159s
tests/architecture/ — green (within make check)
frontend vitest (engine) — 80 passed
bank serves 171 items (>= 170); every standard >= 1 item (matrix test green)
```

---

## Definition of Done (§9)

- [x] P0 rail fix committed first (`4ddd7fe`).
- [x] All FRs implemented; each new test seen to fail first (red→green).
- [x] `make check` + `tests/architecture/` green; frontend vitest green
      (ratchet satisfied, **zero waivers**).
- [x] Promotion + hint run outputs pasted above (not summarized).
- [x] `decisions.md` entries: tier-routing defect fix + floor-recovery method +
      reword-not-waive (see newest-first entries dated 2026-07-08).
- [x] Bank serves ≥170 items (171); every topic ≥1 item (32/32, matrix green).

No ⚠️ Ask-first trigger fired during T7–T10 (bug fix + content, no new
abstraction/node/service/dependency) → no new ADR. Deferred: **D4** topic
taxonomy (own spec+ADR) and **D5** `rule_type` (rides D4's emitter).
