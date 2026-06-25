# Model A/B — Phase A1/A3 Offline Sweep Plan

**Date:** 2026-06-25
**Depends on:** F1/F2/F8 fixes (done, tests green), the offline-first strategy
(`model_ab_phased_strategy.plan.md`), the pipeline review
(`model_selection_pipeline_design.md` rev 2).
**Goal:** convert the frozen `model_ab_corpus.json` (31 rows) into a harness-
scorable `ui_batch.jsonl`, seed the GEN-L1 workspace files, then run the full
8-arm offline sweep and produce the cross-model report. No deploy, no browser.

---

## Grounding facts (verified from live code/data this session)

- **Source corpus:** `frontend/e2e/fixtures/model_ab_corpus.json` — a JSON **list
  of 31 rows**. Distribution: family = {general:19, multi-turn:6, memory:6};
  difficulty = {L1:10, L2:18, L3:3}; only **22 rows carry `want_answer`**; some
  rows (multi-turn/memory) have **no flat `prompt`** key.
- **Source row shape:** `case, gj_id, family, difficulty, trace_id, session_id,
  prompt, rationale, want_answer`.
- **Harness contract** (`scripts/model_ab_eval.py`):
  - `load_corpus` reads jsonl rows; `_drive_arm` reads `row["case"]`,
    `row["prompt"]`, `row.get("gj_id")`, `row.get("phase")`, `row["trace_id"]`.
  - `score_run` (via `_build_events_by_row` / `analyze_planning_traces`) **requires
    `row["phase"]`** — a missing `phase` raises `KeyError: 'phase'` (confirmed).
  - The drive keys recordings by `uuid5(NAMESPACE_DNS, case.id).hex` (= workflow_id);
    the scorer's `wf_candidates` already starts with that (fixed `771933b`).
  - `_drive_arm` seeds `WORKSPACE_DIR = <repo>/workspace` and `os.environ
    .setdefault(...)` — so file-IO tools resolve under the **repo workspace**, NOT
    the literal `/workspace`.
- **GEN-L1 gap (RUN2 §3):** 10 general rows reference absolute paths like
  `/workspace/nums/a.txt`, `/workspace/contact.txt`, `/workspace/log.txt`,
  `/workspace/scores.csv`, etc. None of these files exist → the L1 cases test
  file-absence, not the intended read+compute.

---

## A1 — Corpus conversion + workspace seed

### A1.1 Conversion: `model_ab_corpus.json` → `cache/model_ab/corpus/ui_batch.jsonl`
A small, idempotent converter (new `scripts/convert_model_ab_corpus.py` OR a
function in the existing `build_model_ab_corpus.py`). Per row:
- **Add `phase`** (the score_run partition key). Map from the source fields:
  `phase = family` is the natural choice (general/multi-turn/memory are the
  behavior partitions). Confirm `score_run` tolerates arbitrary phase strings (it
  partitions by phase; unknown phases just don't hit the depth/replan/etc.
  matchers — they score as a generic behavior bucket). If score_run hard-codes a
  phase enum, fall back to mapping general→"depth", multi-turn→"replan",
  memory→"compaction" (the existing planning phases) — **VERIFY which before
  writing**, do not assume.
- **Carry through** `case, gj_id, trace_id, session_id, prompt`.
- **Rows with no flat `prompt`** (multi-turn/memory): either (a) flatten the
  first turn's text into `prompt` (single-shot drive can't replay multi-turn),
  or (b) EXCLUDE them from the offline single-shot sweep and note it — the
  offline harness runs `run_case` once per row (no multi-session replay). DECISION
  NEEDED: the offline harness is single-shot, so multi-turn/memory rows can't be
  faithfully driven offline. **Recommend: split** — drive the 19 general rows
  offline (single-shot faithful); defer multi-turn/memory to the deployed Phase B
  (the Playwright driver replays turns). Document the split in the report.
- **Preserve `want_answer`** as an extra field for the A4 report (not used by
  score_run, but useful human context).

### A1.2 Seed the GEN-L1 workspace files
The 10 GEN-L1 prompts hardcode absolute `/workspace/...` paths but `_drive_arm`
sets `WORKSPACE_DIR=<repo>/workspace`. Two reconciliation options:
- **Option A (rewrite paths):** in the converter, rewrite `/workspace/` →
  `${WORKSPACE_DIR}/` literal repo path in the prompt. Brittle (absolute path in
  prompt) and couples the corpus to a machine path.
- **Option B (seed at the path the prompt names):** create the files under the
  repo `workspace/` dir at the same RELATIVE structure (`workspace/nums/a.txt`,
  `workspace/contact.txt`, …) AND verify the file-IO tool resolves a prompt's
  `/workspace/x` against `WORKSPACE_DIR` (i.e. treats `/workspace` as the tool
  root, not the OS root). **VERIFY the file-IO tool's path resolution** (does it
  sandbox `/workspace/*` to `WORKSPACE_DIR`?) before choosing. If the tool
  sandboxes, Option B with a seed function is clean and machine-independent.
- A `seed_genl1_workspace()` helper writes deterministic fixture files
  (nums a/b/c = e.g. 3/4/5 → sum 12; contact.txt with a known email; log.txt
  with N non-empty lines; scores.csv; etc.) matching each L1 prompt's `want_answer`.
  Idempotent (overwrite each run) so the corpus is reproducible.

### A1.3 Tests (L1, no live LLM)
- converter: every output row has `phase` + `prompt` + `trace_id`; row count
  matches the inclusion rule; want_answer preserved.
- seed: `seed_genl1_workspace()` writes each referenced file; nums sum to the
  documented `want_answer`.
- a converted corpus loads cleanly through `load_corpus` with no `KeyError`.

---

## A2 — Analyzer empty-output ⇒ HOLD guard (sharpened by F9)
Carry the rev-2 finding: the guard must trip on `answer=="" REGARDLESS of token
count`, distinguishing:
- `answer=="" && tokens==0` → "budget/silent" empty (F3 class).
- `answer=="" && tokens>0` → "all-thinking / no-answer" (F9 class).
Both ⇒ HOLD (never PROMOTE), reported as distinct outcomes. Add to the verdict
path in `diff_summaries` / `decide_verdict`; unit-test both shapes.

---

## A3 — Full offline sweep (real LLM, local, no deploy)
- **Baseline:** `gpt-4o` (current capable default of the openai set) OR the set
  arm `--baseline-set openai`. Pin arms vs the baseline:
  - cheap/full-corpus: `gpt-4o-mini`, `claude-haiku-4-5`, `claude-sonnet-4-6`,
    `deepseek-v4-flash`.
  - reasoning-eligible-rows-only (cost control): `claude-opus-4-8`, `gpt-5`,
    `gpt-5-mini`, `deepseek-v4-pro` — restricted to `difficulty ∈ {L2,L3}` rows
    (the `isReasoningEligible` predicate; mirror it in the harness row filter).
- **Set arms:** `--baseline-set openai` vs `--candidate-set anthropic` and vs
  `--candidate-set deepseek` — the "should Auto flip?" question. (F2 guard blocks
  `--*-set all`.)
- **Cost discipline:** start with `--limit 3` smoke per new arm to confirm
  non-empty + integrity-clean BEFORE the full corpus; then full.
- **Exit criteria:** every arm answers (no empty output — A2 guard green),
  integrity clean (model identity matches pin), verdicts produced.

## A4 — Cross-model report
Per arm: cost/task, tokens, latency p50/p95, outcome, routing correctness,
PROMOTE/HOLD/CONTAMINATED. The artifact the model decision rests on. Document the
single-shot limit (multi-turn/memory deferred to Phase B) and the F6 Langfuse-join
limit.

---

## Resolved decisions (verified in code 2026-06-25)
1. **`score_run` is a PLANNING-phase scorer (RESOLVED).** `per_phase` is a
   `defaultdict`, so an arbitrary phase string does NOT KeyError — but only
   `phase ∈ {depth, replan, reflexion, escalation, fanout, compaction}` have hit
   matchers. A `phase="general"` row scores `n+=1, hits=0` → reads as a TOTAL
   regression. So `model_ab_corpus` (a GAIA-shape ANSWER corpus with `want_answer`,
   NOT `want_depth`/`want_replan`) **must NOT be forced through score_run as-is.**
2. **File-IO sandbox (RESOLVED).** `services/tools/file_io.py:21` resolves paths
   against `WORKSPACE_DIR` (default `/workspace`) and rejects anything not
   `is_relative_to(workspace)`. A prompt's literal `/workspace/nums/a.txt`
   resolves to the OS `/workspace/...`, which is OUTSIDE the repo `WORKSPACE_DIR`
   → rejected. So A1.2 Option A (rewrite paths) is WRONG. Correct: **set
   `WORKSPACE_DIR` to a real dir and seed the files at the path the prompt names**
   (either `WORKSPACE_DIR=/workspace` + seed `/workspace/nums/...`, or rewrite the
   harness drive to export `WORKSPACE_DIR=<repo>/workspace` AND seed there AND the
   prompts must use that path — simplest: seed under the dir `_drive_arm` already
   sets, `<repo>/workspace`, and the L1 prompts must reference that root).
3. **Multi-turn/memory rows** — single-shot offline `run_case` can't replay
   multi-session; drive the 19 general rows offline, defer multi-turn/memory to
   the deployed Phase B Playwright driver. (Confirmed.)

## DECISION (user, 2026-06-25): BOTH corpora, two reports
- **A3a — planning corpus** (`cache/planning_stress_phase9/ui_batch.jsonl`, the
  harness default): score_run scores it CORRECTLY today (it has `phase` +
  `want_depth`/`want_replan`/…). This is the planning-BEHAVIOR verdict and runs
  with ZERO new scorer code. **Start here** — fastest path to a real cross-model
  verdict.
- **A3b — answer corpus** (`model_ab_corpus.json` → converted): needs a NEW
  answer-correctness scorer (a `general` phase or sibling `score_answers`) that
  checks the final answer vs `want_answer` (exact/substring/numeric for L1;
  GoalJudge for fuzzy). This is the answer-QUALITY verdict. Built after A3a, with
  its own tests, then run + reported separately.

## Sequencing (revised)
**A3a first** (planning corpus, works now): smoke `--limit 3` per arm → full
sweep → A4a planning-behavior report.
**Then A3b** (answer corpus): A1.1 conversion + A1.2 seed (+ A1.3 tests) → new
answer scorer + A2 empty-output guard (+ tests) → smoke → full → A4b answer-
quality report.
Pure-local throughout; the only cost is the real-LLM calls, gated smoke-first.

---

## STATUS — A3b COMPLETE (updated 2026-06-25, end of session)

**A3a (planning corpus) — done earlier this session: HOLLOW PROMOTE, abandoned as the
verdict.** `score_run` measures planning-CONTROL, not answer quality; on single-shot
general rows the phase hit-rates are mostly 0.0 floors, so "parity" read as
non-measurement (design doc §6 RC1–RC3). A3a is NOT a model-quality signal — kept only
as the planning-behavior cross-check.

**A3b (answer corpus) — BUILT + RUN + verdict in hand.** This is the real instrument.

Built (all uncommitted, tests green on `.venv`):
- `scripts/seed_model_ab_workspace.py` — deterministic GEN-L1 fixtures + `EXPECTED_BY_CASE`.
- `scripts/convert_model_ab_corpus.py` — corpus → `cache/model_ab_answer/ui_batch.jsonl`
  (general family, adds `phase="answer"`).
- `scripts/model_ab_answer_score.py` — answer-correctness scorer: numeric any-match +
  list token-set membership + **failure-phrase guard** (no prompt-leak false-positives) +
  **provider-error guard** (`errored` outcome → run CONTAMINATED, never fake 0.0).
- `scripts/model_ab_eval.py` — `--answer-score`: verdict is **L1-deterministic ONLY**;
  L2/L3 reported UNGRADED (GoalJudge informational only); provider-contamination forces
  CONTAMINATED.
- `scripts/run_a3b_repeats.sh` — paced (30s) L1-only N=3 sweep, 6 drives.
- `tests/scripts/test_model_ab_answer_corpus.py` — 28 tests (seed/convert/scorer/guards).

**N=3 L1 VERDICT (10 deterministic GEN-L1 rows, paced):**
| arm | mean L1 acc | range | verdict |
|---|---|---|---|
| claude-haiku-4-5 | **1.00** | 0 (zero variance, 3/3) | PROMOTE |
| deepseek-v4-flash | **0.90** | 0.80–1.00 | PROMOTE |
| gpt-4o-mini (baseline) | **≈0.44** | 0.30–0.50 (5 clean runs) | — |
*(1 of 6 runs CONTAMINATED on a real `OpenAIException - Connection error`, correctly
excluded — guard validated live.)*

**KEY FINDING:** baseline spread is a **reproducible tool-use gap**, not noise —
gpt-4o-mini abandons file I/O ("I attempted to read… but I was unable…"), graded WRONG.
Stable fail set: read-sum-01 / convert-unit-05 / write-readback-06 / bool-check-15 (5/5),
sort-list-14 (4/5). Candidates execute the same tools cleanly. Story = tool-use
reliability, exactly what Part I predicted Haiku wins.

**L2/L3 — DEFERRED** to `model_ab_l2l3_blind_adjudication.plan.md` (blind + human-review
gold-set bootstrap). Neither automated grader is an oracle (substring FP / GoalJudge FN).

## REMAINING (all await explicit go-ahead)
1. Commit the A3b work to `feat/model-picker-registry-routing` (not main).
2. Reasoning arms (opus-4-8 / gpt-5 / gpt-5-mini / deepseek-v4-pro on reasoning rows).
3. Execute the L2/L3 blind-adjudication plan → seed gold set.
4. Deployed-revision live A/B (`model_ab_extensive_e2e.plan.md`) — final pre-flip gate.
