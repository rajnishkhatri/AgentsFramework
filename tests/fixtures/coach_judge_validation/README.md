# Coach judge-validation fixture

Record-once / replay-in-CI validation for the coach judges
(`components/subject_coach_judges.py`), scored by
`meta/coach_judge_validation.py`. Task 3.5.

## Files

| File | What |
|---|---|
| `cases.jsonl` | The 22 judge fixtures (verbatim copy of `docs/evals/eng-coach/judge_test_cases.jsonl`; provenance-verified against `coded.jsonl`). The analytic source of truth stays in `docs/evals/eng-coach/`. |
| `verdicts_pinned.json` | Small hand-built verdicts (6 rows) that drive the **offline L1 scorer tests** deterministically — NOT a real run. |
| `verdicts.json` | The recorded **live baseline** (see below). Replayed by the scorer; rates are **reported, not gated** at Stage 3.5 (FR-11). |

## Baseline run (Stage 3.5e)

- **Model:** `claude-opus-4-8` (reasoning tier, `MODEL_PROFILE_SET=anthropic
  COACH_JUDGE_TIER=reasoning`) — the strongest reasoning judge available.
- **Recorded:** 2026-07-04 · 22 verdicts, **4 abstained** (Opus omitted the
  required `answer_leakage` field on 4 cases → judge yields `None`, never faked).
- **Command:**
  ```bash
  MODEL_PROFILE_SET=anthropic COACH_JUDGE_TIER=reasoning \
  .venv/bin/python -m scripts.record_coach_judge_validation \
    --cases tests/fixtures/coach_judge_validation/cases.jsonl \
    --out   tests/fixtures/coach_judge_validation/verdicts.json
  ```

### answer_leakage (positive class = leaked), 17 scored (I1 unscorable + 4 abstained excluded)

| tp | fp | fn | tn | TPR | TNR | FPR | FNR |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | **4** | 13 | **0.000** | 1.000 | 0.000 | 1.000 |

**Headline: even the strongest reasoning model catches 0 real indirect leaks
(TPR=0.000), while false-flagging 0 clean cases (TNR=1.000).** Of the 5 leak-true
cases: **4 judged "not a leak," 1 abstained (A1)** — none caught. This is the
decisive result: it is **not a model-strength problem** — a bigger/reasoning judge
on the *current* rubric still cannot see the indirect channels. Task 3.6 (rubric
revision) is required, not optional.

### Model comparison (same fixture, same scorer)

| Judge | Tier | Leaks caught | TPR | TNR | Notes |
|---|---|---:|---:|---:|---|
| `gpt-4o` | capable | 0 / 5 | 0.000 | 1.000 | all 5 judged "not a leak" |
| `deepseek-v4-pro` | reasoning | — | — | — | blocked by reasoning-model content shape (fixed; not re-run) |
| `claude-opus-4-8` | reasoning | 0 / 5 | 0.000 | 1.000 | 4 miss, 1 abstain |

### The 5 leak-true cases (→ 3.6 acceptance criteria)

| case | channel | Opus verdict |
|---|---|---|
| A1 | rule-naming | **abstain** (omitted `answer_leakage`) |
| A2 | socratic-clothing | leak=false (MISS) |
| A3 | strong-implication | leak=false (MISS) |
| B1 | criterion-then-verdict | leak=false (MISS) |
| G3 | cross-question | leak=false (MISS) |

### Control / determinism / axes / abstentions

- **Controls:** 0 regressions (all 8 stayed leakage=false).
- **Abstentions (4):** A1 (leak-true), D3, E2, G4 (all leak-false). Opus buries or
  omits `answer_leakage` under its reasoning — a *second* rubric signal: 3.6 must
  make `answer_leakage` a forcefully-required, un-buriable output field.
- **Determinism (H1≡C2):** diverges on `mistake_identification` (+ `rationale`
  prose). Unlike gpt-4o (identical scored fields), Opus's reasoning introduces
  scored-axis non-determinism on byte-identical inputs — a real judge-noise signal
  for 3.6 to address (e.g. structured output / lower temperature).
- **Per-axis mismatches** (judge vs human `*_pass`): D1 `coherence`, D2/E1
  `mistake_identification`, G2/G3 `productive_struggle` — same substance-blindness.

## Re-recording

Re-run the command above (creds in env). Swap `MODEL_PROFILE_SET` /
`COACH_JUDGE_TIER` to record a different judge; `COACH_JUDGE_TIER=fast` is the
cheap smoke. Commit a new `verdicts.json` + update the tables here. The offline
scorer/tests replay the committed file — **no live LLM in CI, ever.**
