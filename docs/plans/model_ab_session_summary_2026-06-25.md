# Model A/B Session Summary — 2026-06-25

**Branch:** `feat/model-picker-registry-routing` · **Status:** all work UNCOMMITTED, tests green on `.venv`.
**Scope of this session:** finish the offline model-A/B instrument, fix the pipeline-honesty defects it exposed,
and produce a trustworthy cross-model verdict. No deploy, no commit (both await explicit go-ahead).

This doc is the hand-off for subsequent sessions. Companion docs:
`model_ab_A1_A3_offline_sweep.plan.md` (the executable plan + final status),
`model_selection_pipeline_design.md` (the pipeline review, rev 2 + §6),
`model_ab_l2l3_blind_adjudication.plan.md` (the deferred L2/L3 process).

---

## 1. What we set out to do
Decide, offline and cheaply, whether a model swap (Haiku / DeepSeek-Flash vs the gpt-4o-mini baseline)
is safe — without a deploy. The existing harness scored **planning behavior**, which turned out to be
the wrong instrument for answer quality. So the session became: build the right instrument, prove the
old one was hollow, and run it honestly.

## 2. The three pipeline fixes (F1/F10, F2, F8 — all DONE, tests green)
Found during a full-path re-audit (UI dropdown → `input.pinned_model` → `state["pinned_model"]` →
router `select_model()` → `state["selected_model"]` → `call_llm` → `get_llm` → litellm dispatch).

- **F1/F10** — `RoutingConfig.default_model` now reads `MODEL_PROFILE_SET` (one registry read), with an
  explicit pass at the cli/batch builders. A bare `RoutingConfig()` no longer pins a stale `gpt-4o-mini`.
  Files: `components/routing_config.py`, `cli.py`, `scripts/run_goaljudge_synthetic_batch.py`.
- **F2** — harness rejects `--baseline-set all` / `--candidate-set all` (`all` is pin-only; Auto under
  `all` escalates to opus). `scripts/model_ab_eval.py`.
- **F8** — `call_llm_node` KeyError fallback now emits a `model_resolution_fallback` PARAMETER_CHANGED
  carrier AND truths-up the `selected_model` channel via `result["selected_model"]`, so the synthesize
  node records the model that actually RAN. `orchestration/react_loop.py`.

**Two state keys (do not confuse):** `pinned_model` = the input pin the router reads; `selected_model`
= the per-step route write-back / UI display. The offline harness pins via
`graph_input_extra={"pinned_model": arm_model}`.

## 3. The instrument problem (why A3a was abandoned)
`analyze_planning_traces.score_run` is a **planning-CONTROL** scorer (credits phase hits for
depth/replan/reflexion/escalation/fanout/compaction). On single-shot general rows those phases mostly
don't fire → 0.0 floors → "parity" reads as **non-measurement**, producing a hollow PROMOTE. Documented
as RC1–RC4 in `model_selection_pipeline_design.md` §6. **A3a is not a model-quality signal.**

## 4. The answer-quality instrument (A3b — BUILT)
A separate, deterministic answer-correctness path:
- `scripts/seed_model_ab_workspace.py` — idempotent GEN-L1 fixtures under `<repo>/workspace` +
  `EXPECTED_BY_CASE` (numeric/substring expectations, per-case tolerance).
- `scripts/convert_model_ab_corpus.py` — `model_ab_corpus.json` → `cache/model_ab_answer/ui_batch.jsonl`
  (general family only, adds `phase="answer"`; excludes multi-turn/memory).
- `scripts/model_ab_answer_score.py` — grades the final `call_llm` answer (read from the per-arm
  `evals.log` snapshot, keyed by `task_id = uuid5(NAMESPACE_DNS, case).hex`):
  - numeric **any-match** within tol (scans ALL numbers — avoids the last-number false-negative),
  - list **token-set membership** (handles reformatted lists),
  - **failure-phrase guard** — an answer admitting non-completion can't grade correct even if it
    contains the expected token (kills the prompt-leak false-positive),
  - **provider-error guard** — `litellm`/`InternalServerError`/`Cannot connect`/rate-limit → outcome
    `errored` → run **CONTAMINATED**, never a fake 0.0.
- `scripts/model_ab_eval.py --answer-score` — verdict is **L1-deterministic ONLY**; L2/L3 reported
  UNGRADED (GoalJudge shown as informational cross-check, never a verdict input); provider-contamination
  forces CONTAMINATED with a banner.
- `scripts/run_a3b_repeats.sh` — paced (30s between drives) L1-only N=3 sweep.
- `tests/scripts/test_model_ab_answer_corpus.py` — 28 tests.

## 5. The verdict (N=3 paced L1 sweep — 10 deterministic rows)

| arm | mean L1 accuracy | range | verdict |
|---|---|---|---|
| **claude-haiku-4-5** | **1.00** | 0 (zero variance, 3/3) | PROMOTE |
| **deepseek-v4-flash** | **0.90** | 0.80–1.00 | PROMOTE |
| gpt-4o-mini (baseline) | **≈0.44** | 0.30–0.50 (5 clean runs) | — |

- 1 of 6 runs (`a3b_l1_claudehaiku45_v3r2`) tripped **CONTAMINATED** on a genuine transient
  (`OpenAIException - Connection error` on 5 gpt-4o-mini cases) — guard validated in production, excluded
  from the mean.
- Reports: `cache/model_ab/a3b_l1_*_v3r*/model_ab_report.{md,json}`.

### Key finding — the headline, keep it honest
The baseline's 0.30–0.50 spread is **genuine, reproducible weakness, not provider noise.** gpt-4o-mini
repeatedly **gives up on file I/O** ("I attempted to read… but I was unable…"), correctly graded WRONG by
the failure-phrase guard. Stable fail set: `read-sum-01` / `convert-unit-05` / `write-readback-06` /
`bool-check-15` (5/5 clean runs), `sort-list-14` (4/5), `extract-field-13` (2/5). The candidates execute
the same tools cleanly (Haiku 10/10 every run). **The story is tool-use reliability, not raw answer
cleverness** — exactly what the Part I plan predicted Haiku would win (BFCL / SWE-bench tool-calling).

## 6. Meta-lessons (carry forward)
- **Neither automated grader is an oracle.** The deterministic scorer had both false-negatives
  (last-number, contiguous-list — fixed) and false-positives (prompt-leak — fixed via failure guard);
  GoalJudge has false-negatives (over-decomposes one instruction, e.g. `lookup-format-02` `goal_met=False`
  on a correct answer). **Always eyeball per-case misses against raw data — an aggregate can be wrong in
  either direction.**
- **Separate contamination from regression.** A provider outage is CONTAMINATED (re-run), not a 0.0 model
  miss. The guard enforces this.
- **The planning pipeline can't measure answer A/B** (RC1–RC4). Use the deterministic answer scorer for the
  verdict; defer fuzzy L2/L3 to a real gold-set process.

## 7. Where it stands & what's next (all await explicit go-ahead)
1. **Commit** the A3b work to `feat/model-picker-registry-routing` (NOT main) — uncommitted: the 3 fixes
   + the 5 new scripts + tests + the docs.
2. **Reasoning arms** — opus-4-8 / gpt-5 / gpt-5-mini / deepseek-v4-pro on reasoning-eligible rows (future).
3. **L2/L3 blind-adjudication** — execute `model_ab_l2l3_blind_adjudication.plan.md` to bootstrap a seed
   gold set (then, and only then, fix GoalJudge's criteria-split, measured against the labels).
4. **Deployed-revision live A/B** — `model_ab_extensive_e2e.plan.md`; the final gate before flipping
   `MODEL_PROFILE_SET` in prod. Default stays `"openai"` until that passes.

## 8. Operational notes
- **Interpreter:** `.venv/bin/python` only (anaconda has broken opentelemetry → fails collection).
- **Langfuse** is independent of LangSmith; `LANGSMITH_TRACING` is off in `.env` (user-set), tracing unaffected.
- **Security constraints honored:** no secret values printed/committed, no `.env`/tfvars touched, no live
  LLM in CI, no deploy/live phases run.
