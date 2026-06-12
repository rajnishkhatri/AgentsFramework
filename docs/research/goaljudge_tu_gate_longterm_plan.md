# TaskUnderstanding gate — critical session analysis + long-term ≥95% plan

**Date:** 2026-06-12 · **Inputs:** round-1/round-2 shadow reports
(`goaljudge_stage2a_shadow_round1.md`, `goaljudge_stage2a_shadow_round2.md`),
a fresh **local regeneration corpus** (70 samples, exact deployed prompt,
deploy `tierA-prod-2026.06.0-e72920c` == local HEAD), an offline gate-variant
simulation, an evidence-quote prototype, and external best-practice research.
Evidence archived in `goaljudge_tu_gate_longterm_plan/`.

**Decisions locked with the user (2026-06-12):** round 3 gates on the **full
101-row goldset**; round-3 production fix is **punctuation-strip only**; stage
B pursues **evidence-quotes first, then a local NLI checker**.

---

## 1. What the two rounds established

| Metric | Round 1 | Round 2 | Threshold |
| --- | --- | --- | --- |
| Gate-pass (source=generated) | 73.3% | 83.3% | ≥95% |
| Branch coverage (multi-branch) | 50% | 77.3% | ≥80% |
| Shadow invariant (judge consumes deterministic) | 30/30 | 30/30 | 100% |

Round 2 shipped retry-with-feedback + a mechanical vocabulary rule in the
prompt; both worked as built (retry recovered case 16 live), yet 5 cases kept
failing with the **same condition index rejected on both attempts**.

## 2. The new finding: the gate failures are a tokenizer artifact

The rejected condition text was never captured (telemetry bug #2), and the
TU generator's LLM calls are not exported as Langfuse generations (verified:
the failed traces contain a single `llm.call` observation — the executor's),
so round-2's root-cause was inferred blind — and it was **wrong**.

Regenerating all 5 failed tasks locally with the **exact deployed prompt**
(local HEAD == deployed commit) exposed the real mechanism. `_content_tokens`
tokenizes with `[a-z0-9][a-z0-9._/-]*` — the `.` needed to keep `status.txt`
intact also **glues sentence-final punctuation onto the last token** of the
task text. Every failed task ends in its single most important noun:

| Case | Task-final token (as tokenized) | Rejected condition's token |
| --- | --- | --- |
| 01 | `data.` | `data` (≠) |
| 10 | `total.` | `total` (≠) |
| 14 | `source.` | `source` (≠) |
| 17 | `authorization.` | `authorization` (≠) |
| 18 | `ok.` / `workspace/status.txt.` | `ok` / `workspace/status.txt` (≠) |

The model **did quote the task verbatim** — e.g. case 01's rejected
"provides a reason for the refusal related to **data** integrity" — and the
gate's feedback ("shares no word with the task") was factually false, which is
why retry could not converge: the model was already complying.

**Decomposed simulation on the local corpus (20 failed-case samples):**

| Variant | Failed-sample recovery | Notes |
| --- | --- | --- |
| V0 current (exact tokens) | 0/20 | reproduces the live failures |
| **Punct-strip only** | **20/20** | one-line fix, strictly monotone |
| + light stemming | 20/20 | adds nothing on this corpus |
| + path segments / N−1 | 20/20 | adds nothing on this corpus |

Monotonicity: stripping `"._/-"` from both sides of the comparison can only
add matches, so all 25 live-passing cases stay passing (verified 48/50 local
passing samples accept; the 2 rejections are case-16-style **genuinely
invented requirements** — "answer presented in a single, uninterrupted line"
for an echo task — which the gate *should* reject and retry recovered live).

**Erratum applied** to `goaljudge_stage2a_shadow_round2.md` §root-cause:
completion-style conditions were *not* inherently ungroundable; N−1
relaxation and completion-exemptions are **withdrawn** as unnecessary.

## 3. Critical findings beyond the bug

1. **Telemetry gaps cause mis-diagnosis, not just blind spots.** Bug #2 (no
   rejected text) directly produced a wrong root-cause in a shipped report and
   nearly steered the program into relaxing a gate that needed *repairing*.
   Rule going forward: **no diagnosis without the artifact text.**
2. **The gate itself was never meta-evaluated.** We built retry + prompt
   tightening (a full TDD cycle + redeploy + 30-run drive) to compensate a
   validator whose false-positive rate had never been measured against a
   single real model output. Five minutes of feeding it one live generation
   would have caught `data.` ≠ `data`. Every deterministic gate needs its own
   labeled mini-benchmark (L4) before it gates production.
3. **Feedback quality bounds self-correction.** The retry loop is sound, but
   it forwarded the gate's false claim to the model. This matches the
   literature: LLMs cannot reliably self-correct on unreliable feedback
   ([Huang et al., ICLR 2024](https://arxiv.org/abs/2310.01798)); correction
   works when external feedback is *accurate* (tools, executors, verifiers).
   Our empirical ceiling (~83%) was the gate's FP rate, not a model limit.
4. **A lexical gate is a topicality filter, not an anti-fabrication gate.**
   Adversarial probe: "The agent emails the quarterly report to Bob" grounds
   against case 10 (token `report`) under **every** lexical variant including
   the current gate. On-vocabulary fabricated requirements always pass; only
   semantic checks (entailment) or downstream agreement (2b α) can catch them.
   This bounds how much trust the lexical gate should ever carry.
5. **n=30 cannot resolve a 95% bar.** Needing 29/30: a true-97% generator
   passes only 77% of the time; true-95% is a 55/45 coin flip. At n=101
   (need ≥96): true-97% → 92%, true-98% → 98%. Gate decisions must quote
   binomial power at the chosen n.
6. **What round 2 proved that survives:** component-owned retry works
   (recovers genuine inventions); the shadow invariant held 30/30; the
   deterministic fallback never left the judge without conditions; and
   gpt-4o-mini quotes task spans **perfectly verbatim** when asked (16/16
   samples, 0 non-verbatim quotes) — the foundation for stage B.

## 4. External best practices (June 2026)

- **Small grounding verifiers beat lexical proxies.**
  [MiniCheck](https://www.researchgate.net/publication/386205259_MiniCheck_Efficient_Fact-Checking_of_LLMs_on_Grounding_Documents)
  (770M) and [AlignScore](https://arxiv.org/pdf/2406.00975) (355M,
  RoBERTa-based) match GPT-4-level fact-checking at local-model cost;
  [NeMo Guardrails ships AlignScore as a production fact-checking
  rail](https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/guardrail-catalog/fact-checking.html)
  with best accuracy near threshold **0.7**. Our
  `services/governance/injection_classifier.py` (ONNX, three-band, optional
  extra, graceful degrade) is the exact integration pattern.
- **Evidence-span generation is the cheap attribution upgrade.** Industry
  practice for citation reliability is to require **verbatim quotes** and
  validate them by substring check ([INRA](https://www.inra.ai/blog/citation-accuracy),
  [RankStudio](https://rankstudio.net/articles/en/ai-citation-frameworks)) —
  hallucinating is hard when the artifact must carry a copy-paste span.
  Matches our prototype result exactly.
- **Self-correction:** intrinsic self-correction degrades without reliable
  external signal ([Huang et al.](https://arxiv.org/abs/2310.01798));
  RL-trained self-correction (SCoRe, ICLR 2025) exists but is far beyond our
  needs once the gate tells the truth.
- **Checklist generation is a validated paradigm.** Our D1 design follows
  [TICK](https://arxiv.org/html/2410.03608v1); newer work
  ([AutoChecklist](https://arxiv.org/pdf/2603.07019),
  [AdaRubric](https://arxiv.org/pdf/2603.21362)) adds contrastive/deductive
  generation strategies and task-adaptive weighting — relevant at distillation
  time, not before.

## 5. The staged plan to ≥95% (and past it)

### R3 — fidelity + truthful telemetry (days; redeploy)

> **Status 2026-06-12: items 1–3 + 5 IMPLEMENTED on main-tree (TDD,
> failure-first); items 4 (redeploy + 101-row drive) pending.**
> Gate meta-benchmark: `tests/fixtures/task_understanding/gate_benchmark_v1.json`
> (68 must-accept / 2 must-reject / 30-pair adversarial matrix; builder +
> provenance in `goaljudge_tu_gate_longterm_plan/build_gate_benchmark_fixture.py`)
> replayed by `tests/components/test_task_understanding_gate_benchmark.py`.
> RED confirmed exactly as projected: 22 must-accept failures under the live
> tokenizer (20 failed-case + 2 passing-case dot-victims = the sim's 46/50
> stability), 0 after the one-line fix; both must-rejects (case-16 resamples,
> "single, uninterrupted line") rejected before AND after.

1. **Fix `_content_tokens`**: strip `"._/-"` from token edges (one line;
   interior dots/slashes preserved, so `workspace/status.txt` survives).
   TDD: the archived 70-sample corpus becomes **static L4 regression
   fixtures** (real model outputs, deterministic, CI-safe, TAP-2-compliant) —
   the gate's first meta-benchmark: 20 must-accept rejected-sample artifacts,
   the case-16 invention as must-reject, adversarial on-vocab set documented
   as known-pass (topicality bound). ✅ done — stopword-filter-then-strip
   order preserved exactly as simulated (the monotonicity proof depends on
   it; pinned by `test_stopword_filter_runs_before_edge_strip`).
2. **Fix telemetry bug #1** (`attempts` off-by-one on the fallback path) and
   **bug #2** (callback carries rejected condition *text*, so every future
   round can be re-simulated offline — this analysis required regeneration
   because round 2 didn't capture it). ✅ done — `on_gate_rejection(issues,
   attempt, conditions)`; GUARDRAIL_CHECKED and `tu_ai_response.
   rejected_conditions` carry the text; `attempts` = attempts actually made
   (`len(tu_rejections)` on gate exhaustion, else `len+1` — exact on the
   reject-then-parse-error edge `max(len,1)` would miscount).
3. Keep retry exactly as is (it now receives only *true* feedback). ✅
   untouched.
4. Redeploy; **drive the full 101-row goldset** on a fresh namespace
   (`shadow-2a-r3-{000..100}`, ~2–2.5h sequential, shardable); gate at
   ≥96/101. The 30-row subset is embedded for r1/r2 comparability (the
   comparison anchor is the generator's output, not the gate verdict — the
   gate itself changed in R3). Projection: corpus shows 100% recovery +
   ~98–99% true rate (occasional case-16-style inventions, retry-recoverable)
   → pass probability ≥98%. Caveat: the corpus only covers the 30-row
   subset's tasks; the other 71 goldset rows are unseen — the gate decision
   rests on the live n=101 run, not this projection. ⏳ pending.
5. Coverage reads through the same fixed tokenizer (the metric imports
   `_content_tokens`); expect ≥80% as trailing-dot branch mismatches vanish.
   Thresholds stay ≥95%/≥80% (locked); shadow flag stays ON. ✅ automatic —
   verified the only production consumer of `_content_tokens` is
   `validate_conditions`; the coverage metric and quality eval import it.

### 2b — consume gate (week; unchanged design)

Goldset replay α (judge-with-generated vs frozen deterministic baseline vs
0.50). The `plan_builder` floor was untouched by R3 (verified: only
`validate_conditions` consumes `_content_tokens` in production), so the
frozen-baseline discipline holds. Flip `success_conditions_source=generated`
only after 2b; monitor per-attempt GUARDRAIL dashboards post-flip.

### Stage B — attribution upgrade (2–4 weeks, behind 2b)

**B1. Evidence-quotes in shadow.** Schema per condition: `{text, evidence}`,
`evidence` a verbatim task span, **≤1 null** (the declared-generic budget).
Deterministic gates: case-insensitive substring, null budget, existing
count/length/dupe. Prototype baseline: quotes 100% verbatim; failures are
null-budget over-declaration (8/16 with a naive prompt — the model
*under-claims* grounding, the safe direction). Iterate the prompt + budget in
shadow (both verdicts recorded in `tu_ai_response`) until shadow FP/FN are
known and ≥95% holds; then promote to replace lexical grounding. Retry
feedback names the offending quote — *exact, verifiable feedback*.

**B2. Local NLI/entailment checker.** ONNX AlignScore/MiniCheck-class model
via the `injection_classifier.py` pattern (optional extra, artifact dir,
graceful degrade, three-band: entailed ≥0.7 accept / ≤0.3 reject / else
retry). Catches what no lexical or quote check can: on-vocab fabricated
requirements (finding #4). Same checker is reusable **judge-side** at verdict
time (condition-vs-answer entailment) — one asset, two consumers.

### Stage C — post-flip hardening (1–2 months)

- Production `_extract_branches` junk-fragment fix (only after 2b's baseline
  is retired as the comparison anchor) + coverage metric to production parity.
- Wave-2 goldset (~150 prompts) → all future gates at n≥150 with explicit
  binomial power; report Wilson lower bounds alongside point estimates.
- Corpus flywheel: every round's accepted/rejected conditions (now captured
  by the bug-#2 fix) accrete into the L4 gate benchmark.
- Distillation/encoder-decoder generator and AutoChecklist-style strategies:
  revisit only if fast-tier cost or quality demands it.

## 6. Process rules adopted

1. **No diagnosis without artifacts** — telemetry must capture the full
   rejected artifact, not just issue strings.
2. **Gates get gated** — a deterministic validator ships with a labeled
   must-accept/must-reject L4 benchmark before it can discard production
   artifacts.
3. **Quote the power** — any pass/fail decision states n, the bar, and
   P(pass | plausible true rates).
4. **One variable per round** — R3 changes tokenization only; stemming,
   N−1, quotes, NLI each wait their turn.

## 7. Evidence index (`goaljudge_tu_gate_longterm_plan/`)

- `r2_local_sample.py` / `r2_local_samples.json` — 70 local regenerations
  (5 failed × k=4, 25 passing × k=2), exact deployed prompt.
- `r2_gate_sim.py` / `r2_gate_sim_results.json` — 6-variant simulation
  (recovery / stability / adversarial leakage).
- `r2_dot_verify.py` — trailing-punct proof, fix decomposition, binomial
  power table.
- `r2_evidence_proto.py` / `r2_evidence_proto.json` — evidence-quote
  prototype (16 samples, 0 non-verbatim quotes, 8/16 naive pass).
- `build_gate_benchmark_fixture.py` — one-shot R3 conversion of
  `r2_local_samples.json` into the frozen gate meta-benchmark
  `tests/fixtures/task_understanding/gate_benchmark_v1.json` (labeling
  transform inlined as verified, source sha256 in `_meta`).
