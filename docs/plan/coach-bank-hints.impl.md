# Implementation evidence — coach-bank-hints

Evidence log per the spec's Definition of Done: verbatim outputs, not summaries.
Executes [coach-bank-hints.tasks.md](coach-bank-hints.tasks.md).

## Phase 0 — branch + baseline (T0.1/T0.2)

- Branch `feat/coach-bank-hints` off `origin/main` (4645d28, PR #132 merge).
  Bundle + AF-1 tombstone committed: `3249bb1`.
- Baseline gates BEFORE any edit:
  - `make check` → `5183 passed, 50 skipped, 72 deselected, 3 warnings in 154.72s`
  - `pytest tests/architecture/ -q` → `162 passed, 4 skipped, 1 warning in 29.83s`
  - `cd frontend && pnpm vitest run` → `Test Files 132 passed (132) · Tests 1392 passed (1392)`

## Phase B — converter (TB.1 red → TB.2 green)

Red (before `scripts/emit_hint_bank.py` existed):

```
E   ModuleNotFoundError: No module named 'scripts.emit_hint_bank'
ERROR tests/scripts/test_emit_hint_bank.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

Green after implementation:

```
.......                                                                  [100%]
7 passed in 0.91s
```

`make typecheck` → `0 errors, 0 warnings, 0 informations`. Commit `276ed36`.

## Phase A — live generation run (TA.1–TA.3)

**TA.1 export** — 8/8 bank rows extracted, every generator field present:

```
8 rows -> …/scratchpad/questions.json
ti-gen-eb8028a2b674681d s-punc reviewed= True missing= none
ti-gen-99e05e271a9f6c92 s-gram reviewed= True missing= none
ti-gen-2fddf2bbbfb1b061 s-gram reviewed= True missing= none
ti-gen-c49644db17cedd1b s-sent reviewed= True missing= none
ti-gen-9fb6fd5eaae7fdf9 s-rhet reviewed= True missing= none
ti-gen-949378b918123353 s-rhet reviewed= True missing= none
ti-gen-abe42cfc107b3d34 s-org reviewed= True missing= none
ti-gen-95b88bbdaeda2910 s-style reviewed= True missing= none
```

**Prompt fixes (plan deviation, precedented).** `prompts/hint_generator.j2`
gained (a) the passage line — bank items carry the tested sentence in
`context_html`, which the template never rendered (the exact solver-blindness
class the item-bank increment hit: its solver needed `context_html` too); and
(b) ladder-discipline rule 5 — "never quote the underlined phrase verbatim" —
added after attempts 1–2 showed the leak class below. Leakage gate consumes
only `answer_letter`/`choices`/`why_correct_md` (verified), so the richer
question dict changes nothing in verification.

**TA.2 run 1** (gpt-4o-mini fast profile, governed graph, live):

```
ti-gen-eb8028a2b674681d: 3 reviewed rung(s), 0 quarantined
ti-gen-99e05e271a9f6c92: 3 reviewed rung(s), 0 quarantined
ti-gen-2fddf2bbbfb1b061: 3 reviewed rung(s), 0 quarantined
ti-gen-c49644db17cedd1b: 3 reviewed rung(s), 0 quarantined
ti-gen-9fb6fd5eaae7fdf9: 1 reviewed rung(s), 2 quarantined
ti-gen-949378b918123353: 3 reviewed rung(s), 0 quarantined
ti-gen-abe42cfc107b3d34: 3 reviewed rung(s), 0 quarantined
ti-gen-95b88bbdaeda2910: 3 reviewed rung(s), 0 quarantined

DONE: 22 reviewed rows -> …/hints_run1.json (2 quarantined -> eval_capture target=hint_generator)
```

Quarantine records (eval_capture `target="hint_generator"`):

```
stage: leakage | violations: ["quotes the correct choice's label"]
raw: {'rung': 1, 'body_md': "What do you think about the phrase 'consensus of opinion'? …"}
stage: leakage | violations: ["quotes the correct choice's label"]
raw: {'rung': 3, 'body_md': "Look closely at the phrase 'consensus of opinion' and think about …"}
```

Root cause: the item's correct choice **"consensus"** is a substring of the
underlined phrase "consensus of opinion" — quoting the tested phrase IS quoting
the answer (deterministic gate fail-closed, working as designed). A whole
revision-item class, hence the template rule 5, not an item-specific hack.

**Attempt 2** (same item, `--existing` run-1 bodies): `0 reviewed, 3 quarantined`
(rungs 1/3 leakage again; rung 2 near-duplicate of the already-earned rung 2 —
the dup gate doing its job).

**Attempt 3** (after rule 5): 

```
ti-gen-9fb6fd5eaae7fdf9: 3 reviewed rung(s), 0 quarantined
1 | What do you think about the phrase that is underlined? How does it convey the committee's agreement?
2 | Consider the concept of conciseness in writing. …
3 | Look closely at the options and compare how each one expresses the idea of agreement. …
```

Within the FR-A2 bound (3 attempts). Merge: run-1's 22 rows + attempt-3 rungs
{1,3} (run-1's rung 2 earned first).

**TA.3 freeze + emit:**

```
corpus frozen: 24 rows, 8 items, full ladders, 0 waivers
emitted …/frontend/lib/adapters/engine/_hint_bank.ts and …/components/subject_coach_bank_hints.py
  from …/docs/plan/coach-bank-hints.seed.json
```

`from components.subject_coach_bank_hints import BANK_RUNGS` → `24 rungs`.
`HINT_BANK_WAIVERS = []` (FR-A3 table empty — no waivers needed).
