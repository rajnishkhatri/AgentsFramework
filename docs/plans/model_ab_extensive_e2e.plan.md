# Extensive Model A/B Testing via Playwright Agentic E2E

**Status:** PLAN (not started). Created 2026-06-24.
**Skill:** `docs/skills/playwright-agentic-e2e` (tier model, settle-poll, trace verification)
**Companion code (already shipped):** `scripts/model_ab_eval.py` (the offline diff/verdict engine —
[[model-ab-eval-harness]]), the model picker UI ([[model-picker-ui-redesign]]), the 3-set registry
([[model-registry-home-llm-config]], [[deepseek-v4-profile-set-tiering]]).

## Goal

Run **all newly-added models** (Anthropic 3-tier + DeepSeek V4) against **OpenAI baselines** over
**general, multi-turn, and stress** synthetic task suites, driving each model through the **real UI
model picker** on a **deployed Cloud Run** revision. For every (model × task) cell capture: a
**screenshot**, the **Langfuse trace** (to analyze routing/reasoning), **token burn**, **cost**, and
**response time**. Produce a cross-model comparison report.

This is the **executable, full-stack form** of `scripts/model_ab_eval.py`'s local pre-deploy gate:
that harness pins models via the graph input and scores black-box recordings locally; THIS plan pins
via the UI dropdown against the live stack and scores from authentic Langfuse traces + DOM evidence.

## Locked decisions (2026-06-24)

| Axis | Decision |
|---|---|
| **Pin mechanism** | **UI dropdown pin** — the spec selects each model in the Composer dropdown before sending (`input.pinned_model` rides through). One deployed revision serves all arms; no per-arm redeploy. Tests the full real path UI→wire→router pin. |
| **Model matrix (8 arms)** | `Auto` · `gpt-4o-mini` · `gpt-4o` · `claude-haiku-4-5` · `claude-sonnet-4-6` · `claude-opus-4-8` · `deepseek-v4-flash` · `deepseek-v4-pro` |
| **Opus/Pro eligibility (cost control)** | **`claude-opus-4-8` and `deepseek-v4-pro` are RESTRICTED to reasoning/complex cases only** — `difficulty ∈ {L2,L3}` **or** `family ∈ {stress, multi-turn}`. They NEVER run on routine `L1` general cases (that is what those models are *for* — see [[deepseek-v4-profile-set-tiering]] "Pro-on-escalation", and the registry where reasoning tier is escalation-only). |
| **Opus/Pro sampling** | The reasoning arms run `REPEAT=1` (vs `MODEL_AB_REPEAT=3` for the cheap arms) **and** a **seeded ~30–50% sample** of their eligible cases. Cheap arms keep full repeats + full case coverage for tight stats; the pricey arms get a representative, bounded read. |
| **Corpora** | **Reuse existing** (GoalJudge 50-case = general; planning-stress = stress; memory-multisession = multiturn) **AND add** a GAIA/τ²/LoCoMo-shaped new synthetic set. Every row carries a `difficulty` (L1/L2/L3) + `family` so the eligibility filter is data-driven. |
| **Run target** | **Deployed Cloud Run** (T3 full-stack) — authentic Langfuse traces, real cost panels, real pgvector. Skill's release-gate tier. |

### Per-model coverage matrix (who runs what)

| Model | Tier | Routine `L1` general | Reasoning/complex (`L2`/`L3`/stress/multi-turn) | Repeats |
|---|---|---|---|---|
| `Auto` | router | ✅ all | ✅ all | 3 |
| `gpt-4o-mini` | fast | ✅ all | ✅ all | 3 |
| `gpt-4o` | capable | ✅ all | ✅ all | 3 |
| `claude-haiku-4-5` | fast | ✅ all | ✅ all | 3 |
| `claude-sonnet-4-6` | capable | ✅ all | ✅ all | 3 |
| `deepseek-v4-flash` | fast/capable | ✅ all | ✅ all | 3 |
| **`claude-opus-4-8`** | **reasoning** | ❌ skipped | ✅ **seeded 30–50% sample** | **1** |
| **`deepseek-v4-pro`** | **reasoning** | ❌ skipped | ✅ **seeded 30–50% sample** | **1** |

This mirrors how the runtime actually uses these models: Opus/Pro are the **escalation/reasoning tier**,
reached only on hard cases — pinning them on routine L1 work would both waste money and measure them
on tasks they're not meant for. The A/B reflects the real routing intent, not a uniform grid.

## Benchmark grounding (external research, 2026)

The new synthetic corpus is **shaped after** the public agentic benchmarks (synthetic prompts, so no
dataset license entanglement — same approach as `build_planning_stress_corpus.py`):

- **GAIA / Gaia2** — general assistant tasks, 3 levels by step/tool count (L1 ≤5 steps, L2 5–10,
  L3 complex). Our **general** family mirrors L1–L2 multi-step tool tasks.
- **τ²-bench (Sierra)** — tool-agent-**user** interaction over multiple dynamic turns with policy
  adherence (retail/airline/telecom). Our **multi-turn** family mirrors the dual-control,
  info-gathered-over-turns shape.
- **SWE-bench Verified / WebArena / AgentBench** — referenced for task-shape realism; we do NOT host
  repos/browsers, so these inform prompt *shape* (multi-step, verifiable) not literal tasks.
- **LoCoMo / LongMemEval** — multi-session memory (LoCoMo ~300 turns/35 sessions; LongMemEval 5
  abilities: extraction, multi-session reasoning, temporal, knowledge-update, abstention). Our
  **multi-session memory** family reuses the existing repo corpus (already LongMemEval/LoCoMo-shaped,
  [[memory-multisession-e2e-corpus]]).
- **Evaluation methodology** (the standard the report follows): report **judge-based answer quality
  alongside input/reasoning tokens and p50/p95 latency**; quantify **per-run stochasticity** (multiple
  runs per cell — single-run numbers are inflated 5–15 pts per the 2026 surveys).

Sources: [GAIA](https://towardsdatascience.com/gaia-the-llm-agent-benchmark-everyones-talking-about/),
[Gaia2](https://huggingface.co/papers/2602.11964),
[τ²-bench](https://github.com/sierra-research/tau2-bench) ·
[Sierra τ-bench](https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents),
[Agent benchmarks 2026](https://benchmarkingagents.com/agent-benchmarks/),
[Tool Decathlon](https://arxiv.org/pdf/2510.25726),
[LoCoMo](https://www.emergentmind.com/topics/locomo),
[Mem0 memory benchmarks 2026](https://mem0.ai/blog/ai-memory-benchmarks-in-2026),
[Stochasticity in agentic evals](https://arxiv.org/pdf/2512.06710).

---

## What already exists (REUSE — do not rebuild)

| Asset | Path | Role in this plan |
|---|---|---|
| T3 stress driver | `frontend/e2e/full-stack/planning-stress.spec.ts` | The **template** — per-case loop, fresh-trace-id-per-run (no Langfuse superposition), evidence screenshot, JSONL capture, settle-poll. The new model-A/B spec is a generalization of this. |
| TTFT benchmark | `frontend/e2e/full-stack/ttft-benchmark.spec.ts` | Latency-measurement pattern (submit→first-token, p50 of N runs). |
| Settle-poll + send | `frontend/e2e/fixtures/helpers.ts` | `sendMessage`, `waitForResponse` (settle, not "finished"). |
| Auth fixture | `frontend/e2e/fixtures/auth.fixture.ts` + `global-setup.ts` | `authenticatedPage`, WorkOS storageState (gated on `E2E_AUTHENTICATED`). |
| Corpus builder idiom | `scripts/build_planning_stress_corpus.py` | Python source-of-truth → FE JSON; deterministic `uuid5` trace-id namespace. |
| Trace analyzer | `scripts/analyze_planning_traces.py` | `_load_langfuse_events`, `score_run` (per-phase), `_load_blackbox_events`. The model-A/B analyzer extends its Langfuse pull + adds cost/token/latency aggregation. |
| Offline diff engine | `scripts/model_ab_eval.py` | `diff_summaries`, `check_arm_integrity`, `decide_verdict`, report writers — **reused** to turn two arms' summaries into PROMOTE/HOLD and to assert each arm ran the model it claimed. |
| General-task corpus | `tests/fixtures/goaljudge/case_registry.py` (50 LIVE_CASES, strata×domains) | The **general** family. |
| Multi-session corpus | memory-multisession corpus ([[memory-multisession-e2e-corpus]]) | The **multi-turn / memory** family. |
| Stress corpus | `frontend/e2e/fixtures/planning_stress_corpus.json` | The **stress** family. |
| UI pin path | `frontend/lib/translators/ui_input_to_agent_request.ts` (`AUTO_MODEL`, `input.pinned_model`) | What the dropdown selection rides through. |
| Model carriers | `orchestration/react_loop.py` STEP_EXECUTED `details{model,tokens_in,tokens_out,cost_usd}`; `total_cost_usd` in state; `model.selected` reasoning carrier | The token/cost/model-identity source — **no new instrumentation**. |

---

## Plan — phased

### Phase 0 — Prereqs & guards (no runs yet)

0.1 **Stable dropdown selectors.** The Composer picker trigger is `aria-label="Choose model"` and
   items are `role="menuitemradio"` with the model name as text — drivable by accessible name, but
   add a `data-testid="model-option-{name}"` per item + `data-testid="model-picker-trigger"` on the
   trigger for robust, locale-proof selection (one small edit to `Composer.tsx` + its test).
   ⚠ The picker label is hidden in a narrow composer slot (`@[20rem]/composer`) — the spec must open
   the menu by the trigger, never assert on the chip label width.

0.2 **Deployed revision has all three provider keys.** The Cloud Run revision under test must have
   `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` + `DEEPSEEK_API_KEY` live (else pinned arms 401 mid-run).
   `MODEL_PROFILE_SET` is irrelevant for UI-pin arms (pin bypasses Auto-set selection) EXCEPT that
   `/models` must list every matrix model so the dropdown offers it — confirm the revision's
   `/models` returns all 8 names (it will only list ONE set's models). **Decision needed at run time:**
   either (a) deploy a revision whose set lists the union, or (b) the spec types the model via a
   future free-text pin. **Recommended:** add a `MODEL_PROFILE_SET=all` meta-set to the registry
   that lists every model (pin-only union) so `/models` offers all 8 — a 1-row registry change,
   mirrors the existing sets. (Captured as task 0.2a.)

0.3 **Cost/latency are already on the wire** — confirm on one smoke trace that STEP_EXECUTED carries
   non-zero `tokens_in/out` + `cost_usd` for an Anthropic and a DeepSeek pin (the token-seam incident
   — verify, don't assume). If empty, fix the usage_metadata plumbing BEFORE the full matrix.

### Phase 1 — Corpora

1.1 **Reuse three existing families** unchanged:
   - **general** = export the 50-case GoalJudge registry to the FE JSON shape
     (`export_goaljudge_registry_json.py` exists) — general single/multi-step tool tasks.
   - **stress** = `planning_stress_corpus.json` (depth/replan/reflexion/escalation/fanout/compaction).
   - **multiturn/memory** = the memory-multisession corpus (multi-session recall).

1.2 **Author the new benchmark-shaped set** — `scripts/build_model_ab_corpus.py` (mirrors
   `build_planning_stress_corpus.py`: Python source-of-truth, `uuid5` trace-id namespace, emits
   `frontend/e2e/fixtures/model_ab_corpus.json`). ~30–40 rows across three families:
   - **general (GAIA L1–L2 shape)** — multi-step tool tasks with a verifiable answer (e.g. "read
     these 3 files, compute X, write the summary"), ≤5 and 5–10 step variants.
   - **multi-turn (τ²-bench shape)** — dual-control, info-over-turns customer-service-style tasks
     with a policy constraint (the spec sends a SCRIPTED multi-message sequence per case; the
     existing single-shot driver is extended to a turn list — see 2.2).
   - **memory (LoCoMo/LongMemEval shape)** — covered by reusing 1.1's multisession corpus; the new
     builder adds a few temporal/knowledge-update rows if coverage gaps appear.
   Each row carries a `family`, `prompt` (or `turns[]`), optional `want_*` expectation, and a
   `difficulty` (L1/L2/L3) for the report's by-difficulty cut.

1.3 **`difficulty` is the eligibility key — every row must carry one.** The Opus/Pro restriction is
   data-driven off `difficulty` + `family`, so:
   - The new builder (1.2) sets `difficulty` per row at authoring time.
   - The **reused** families (1.1) predate this field → backfill it:
     - **stress** (`planning_stress_corpus.json`) — already phase-tagged; map
       `phase ∈ {replan, reflexion, escalation, fanout, compaction}` → reasoning-eligible
       (`difficulty=L2`), `phase=depth` L0/L1 rows → `L1`. (`family=stress` already makes the whole
       set eligible, but the depth-L1 rows are the routine ones — keep them L1 so the report's
       by-difficulty cut is honest.)
     - **general** (GoalJudge 50-case) — map `stratum`: `representative`/simple `domain` → `L1`;
       `boundary`/`composite`/`impossible`/`red_team` → `L2` (these are the reasoning-heavy general
       cases Opus/Pro SHOULD see). A 1-time tagging pass in the export step.
     - **memory/multiturn** — `family=multi-turn` makes the whole set reasoning-eligible; tag
       `difficulty=L2` (multi-session reasoning is inherently complex).
   - A row is **Opus/Pro-eligible** iff `difficulty ∈ {L2,L3}` OR `family ∈ {stress, multi-turn}`.
     The eligibility predicate lives in ONE place (the typed corpus reader, Phase 2) so the driver,
     the cost estimator, and the analyzer all agree.

1.4 **Corpus hash** recorded per run (governance: reproducible decision artifact — reuse
   `model_ab_eval.corpus_hash`).

### Phase 2 — The Playwright driver (`frontend/e2e/full-stack/model-ab.spec.ts`)

A generalization of `planning-stress.spec.ts`. The matrix is **model × case**; each cell is one test.

2.0 **Matrix construction — eligibility + sampling (the cost-control core).** The cell list is
   NOT a uniform 8×N grid; it is built per-model from the corpus:
   - **Eligibility filter.** For `claude-opus-4-8` and `deepseek-v4-pro`, drop every case that is NOT
     reasoning-eligible (`difficulty ∈ {L2,L3}` OR `family ∈ {stress, multi-turn}`). All other models
     + Auto take every case. The predicate is the single `isReasoningEligible(case)` helper from the
     typed corpus reader (Phase 1.3) — driver, cost estimator, and analyzer import the same one.
   - **Sampling (Opus/Pro only).** From each reasoning arm's *eligible* cases, take a **seeded
     deterministic sample** of `MODEL_AB_REASONING_SAMPLE` (default `0.4` = 40%). Seed =
     `hash(model + run_id)` so the sample is reproducible and the report can name exactly which cases
     each pricey arm ran. The cheap arms are NOT sampled (full coverage).
   - **Repeats.** Cheap arms: `MODEL_AB_REPEAT` (default 3). Opus/Pro: forced to `1` (override
     `MODEL_AB_REASONING_REPEAT`, default 1). So an Opus cell is `1 run`, a Haiku cell is `3 runs`.
   - **Result:** the matrix is dense for the cheap/Auto arms and a bounded, seeded, reasoning-only
     slice for Opus/Pro — directly encoding "don't burn the pricey models on routine work."

2.1 **Per-cell flow** (settle-poll, never "finished"):
   1. fresh `runTraceId` (per-run, `freshTraceId()` — no Langfuse superposition);
   2. install the thread-bridge route (`gj:{gj_id}:{runTraceId}` thread_id) so the server-side
      trace_id is deterministic and the analyzer can pull it from Langfuse;
   3. `page.goto("/")`, new thread;
   4. **open the model picker → select the arm's model** (or Auto) via the 0.1 testid;
   5. `sendMessage(prompt)`; `waitForResponse` (settle); record submit→first-token (TTFT) and
      submit→settle (total latency);
   6. assert ONLY that a non-empty answer rendered (T3 is non-deterministic — aggregate scoring is
      the analyzer's job);
   7. `captureEvidence` screenshot (tool cards + reasoning expander force-opened) →
      `{model}/{case}.png`;
   8. append a JSONL capture row: `model`, `family`, `case`, `gj_id`, `trace_id` (per-run),
      `corpus_trace_id`, `prompt`, `response_text` (truncated), `response_chars`, `tool_card_count`,
      `ttft_ms`, `latency_ms`, `screenshot_path`, `outcome`, `difficulty`, `finished_at`, `base_url`,
      + `want_*`.

2.2 **Multi-turn extension.** For τ²-shaped cases the row carries `turns: string[]`; the spec sends
   them sequentially in ONE thread (each turn settle-polled), capturing per-turn latency and a final
   screenshot. The model stays pinned across turns (the pin persists via the checkpoint — confirms
   the multi-step pin path too).

2.3 **Repetition for stochasticity.** `MODEL_AB_REPEAT=3` (cheap arms) runs each cell N times with a
   fresh trace-id (the 2026 stochasticity finding — single runs are unreliable). Opus/Pro run
   `MODEL_AB_REASONING_REPEAT=1` (the sampling trade-off — fewer cells but bounded spend). The report
   reduces to per-cell median + variance, and flags the reasoning arms' wider CI (n=1) explicitly so
   no one over-reads a single Opus run.

2.4 **Env knobs** (mirror the stress spec): `MODEL_AB_MODEL_FILTER`, `MODEL_AB_FAMILY`
   (general|stress|multiturn), `MODEL_AB_LIMIT`, `MODEL_AB_SMOKE=1` (one case per family per model),
   `MODEL_AB_REPEAT`, **`MODEL_AB_REASONING_REPEAT` (default 1)**, **`MODEL_AB_REASONING_SAMPLE`
   (default 0.4)**, **`MODEL_AB_REASONING_BUDGET`** (optional absolute hard cap on total Opus/Pro
   runs — the sampler fills it from L2/L3 cases first if set, overriding the fraction),
   `MODEL_AB_JSONL`, `MODEL_AB_SCREENSHOT_DIR`. Artifact rotation per batch (one file == one batch,
   the Stage-B report-integrity rule).

2.5 **Cost guard.** Opus/Pro are the expensive axis, so the matrix is structured to never spend them
   on routine work (2.0 eligibility + sampling). On top of that: the spec logs a **running estimated
   token/cost tally** broken out per model, and `MODEL_AB_MODEL_FILTER` lets the matrix run
   **incrementally** — cheap arms first, then review the tally, then run Opus/Pro last. A pre-run
   **dry-run mode** (`MODEL_AB_DRY_RUN=1`) prints the constructed matrix (cell count + projected runs
   per model + a coarse cost estimate from the registry per-1k rates × an assumed tokens/task) WITHOUT
   any LLM call, so the spend is reviewable before committing. Recommend the **SMOKE pass first**
   (`MODEL_AB_SMOKE=1`, ≤8 models × ≤3 families × 1 case; Opus/Pro only on their eligible smoke case)
   before the full matrix.

### Phase 3 — The analyzer (`scripts/analyze_model_ab.py`)

Extends `analyze_planning_traces.py`'s Langfuse pull; reuses `model_ab_eval.diff_summaries` /
`check_arm_integrity`.

3.1 **Per-cell trace pull** — `_load_langfuse_events(trace_id)` for every JSONL row → the trace's
   STEP carriers (model, tokens_in/out, cost_usd), the `model.selected` **reasoning** carriers
   (routing rationale + alternatives), task_completed verdict.

3.2 **Integrity (governance).** For every row assert the trace's STEP `model` == the pinned arm
   (Auto arm: ∈ the registry). A mismatch ⇒ that cell is CONTAMINATED and excluded from the model's
   aggregate (the `model_ab_eval` posture: an arm that didn't run what it claimed is not scored).
   An empty `model` (token-seam) is also CONTAMINATED.

3.3 **Metrics per (model, family)** — the comparison table:
   - **answer quality** — reuse the GoalJudge/`score_run` per-phase rates where the case carries a
     `want_*`; for the general/τ²/memory families with no per-phase want, an **LLM-judge** pass
     (reuse the GoalJudge judge profile) scores correct/complete vs the case's success criteria.
     (Quality gate is OPT-IN — `--judge` — same as the harness's v2 GoalJudge flag; default is
     behavior + cost + latency only.)
   - **token burn** — mean/median input + output tokens per task (sum of STEP carriers).
   - **cost** — mean/median `total_cost_usd` per task; projected $/1k-tasks.
   - **latency** — TTFT p50/p95 and total-latency p50/p95 (from the DOM capture rows).
   - **tool usage** — mean tool calls per task (tool_card_count).
   - **reasoning shape** — from `model.selected`: escalation rate, planning depth distribution (does
     this model trigger replan/reflexion more?), Auto-arm tier mix.

3.3a **Fair comparison on the SHARED case set (sampling correction).** Opus/Pro ran only a sampled,
   reasoning-only slice — so a naive "Opus cost vs Haiku cost" compares different case sets and is
   apples-to-oranges. The report therefore produces TWO views:
   - **Full view** — every model on every case it ran (the absolute numbers, with each pricey arm's
     `n` and sampled-case list shown so the small sample is explicit).
   - **Matched view (the headline comparison)** — for any Opus/Pro-vs-X comparison, restrict BOTH
     arms to the **intersection** of cases they both ran (i.e. Opus's sampled reasoning cases). This
     is the only honest head-to-head: same cases, same difficulty. `diff_summaries` runs on the
     matched subset. The report states the matched-set size and that the reasoning arms are NOT
     compared on routine L1 cases by design.

3.4 **Report writers** — `cache/model_ab_live/<run-id>/`:
   - `model_ab_live_report.md` — the headline cross-model table (rows = models, cols = quality |
     tokens | cost/task | TTFT p50 | latency p50 | tool calls), then per-family breakdowns, a
     by-difficulty cut, a per-cell stochasticity (variance) note, the screenshot index, and the
     CONTAMINATED-cell list. **Verdict banner per model vs the gpt-4o baseline** (PROMOTE/HOLD via
     `diff_summaries`).
   - `model_ab_live_report.json` — machine-readable: per-(model,family) summaries, the diffs vs
     baseline, corpus hash, every trace_id, contamination list.
   - The honest-limit note (this IS the deployed path, so the local-only caveat is dropped — but
     stochasticity + single-revision caveats are stamped).

### Phase 4 — Governance audit (`docs/skills/governance-trace-audit`)

Per the model-picker plan's governance contract: after the matrix runs, run the
`governance-trace-audit` skill on a sample of traces (one pinned run per model + one Auto run) and
confirm the four pillars hold across providers:
- **Reasoning** — `model.selected` rationale reads `user-pinned:{model}` (not an Auto-looking reason)
  for pinned cells; the Auto cells name the tier reached.
- **Recording** — STEP `model` matches the pin on `step.executed` (this is also 3.2's integrity gate).
- **Identity / Validation** — unchanged; the audit confirms no `carrier_gate` alert fires on the new
  DeepSeek/Anthropic provider values.
Any alert ⇒ a runtime-confirmed seam defect to fix before trusting the comparison.

### Phase 5 — Execute & report

5.1 SMOKE pass (`MODEL_AB_SMOKE=1`) — 24 runs, ~minutes, confirms wiring + the cost/token carriers
   are non-empty for every provider. Review the smoke `model_ab_live_report.md`.
5.2 Incremental full matrix — cheapest models first (`MODEL_AB_MODEL_FILTER` per arm), Opus/Pro last,
   reviewing the running cost tally between arms. `MODEL_AB_REPEAT=3`.
5.3 Final analyzer + governance audit pass. Deliver the cross-model report + screenshot gallery +
   Langfuse trace links.

---

## Test tiers (skill taxonomy)

- **T1 (per-commit CI):** the driver's **wiring** — a mocked-stream spec proving the picker selection
  sets `input.pinned_model` and the capture row shape is correct. NO live model. This is the only
  tier in CI (skill golden rule).
- **T3 (on-demand / this plan):** the live matrix. Real models, real cost, deployed Cloud Run. Never
  in CI.
- The `scripts/analyze_model_ab.py` unit tests (no live LLM) cover the metric aggregation, the
  integrity exclusion, the eligibility/sampling matrix construction, and the matched-subset
  comparison (3.3a) on synthetic fixtures (mirrors `test_model_ab_eval.py`).

## Critical files

- **New:** `frontend/e2e/full-stack/model-ab.spec.ts`, `scripts/build_model_ab_corpus.py`,
  `frontend/e2e/fixtures/model_ab_corpus.json`, `scripts/analyze_model_ab.py`,
  `tests/scripts/test_analyze_model_ab.py`, `frontend/e2e/fixtures/model_ab_corpus.ts` (typed reader).
- **Edited (small):** `frontend/components/chat/Composer.tsx` (per-item `data-testid`),
  `services/llm_config.py` (optional `"all"` union meta-set for `/models`, task 0.2a).
- **Reused unchanged:** `planning-stress.spec.ts` (template), `helpers.ts`, `auth.fixture.ts`,
  `analyze_planning_traces.py` (`_load_langfuse_events`, `score_run`), `model_ab_eval.py`
  (`diff_summaries`, `check_arm_integrity`, report writers), GoalJudge judge profile.

## Risks / honest limits

- **Cost.** Opus/Pro are the expensive axis. Mitigated structurally: they run ONLY on
  reasoning-eligible cases (`L2/L3` or stress/multi-turn — never routine L1), a seeded 30–50% sample
  of those, at `REPEAT=1`. Plus SMOKE-first, a `MODEL_AB_DRY_RUN` matrix preview, incremental per-arm
  runs with a running cost tally, and an optional `MODEL_AB_REASONING_BUDGET` hard cap.
- **Sampled reasoning arms have a small `n`.** `REPEAT=1` + a 40% case sample means each Opus/Pro
  number rests on few runs — the report flags the wide CI and only compares them on the **matched
  shared case subset** (3.3a), never on the full grid. Raise `MODEL_AB_REASONING_SAMPLE`/`REPEAT` if
  a specific Opus-vs-Sonnet question needs tighter stats.
- **`/models` lists one set.** The dropdown only offers the deployed set's models unless the `"all"`
  union meta-set (0.2a) is wired — REQUIRED prereq for an 8-arm UI-pin sweep.
- **Stochasticity.** Single runs are unreliable (2026 surveys); the `MODEL_AB_REPEAT=3` median +
  variance is the mitigation, but 3 is still small — the report states the CI is wide.
- **LLM-judge quality gate is opt-in** (`--judge`) — default report is behavior + cost + latency
  (no quality gate in v1), matching the `model_ab_eval` v1 stance; quality is the v2 add.
- **Langfuse join** must use the per-run fresh trace-id bridge (the superposition defect,
  [[stress-harness-traceid-superposition]]) — reused verbatim from the stress spec.
```
