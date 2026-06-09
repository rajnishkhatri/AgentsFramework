# LLM Eval Grounded-Theory Pipeline — Reference

Detailed metrics, thresholds, bias catalog, and bibliography. Read when calibrating judges, setting IAA bars, or designing monitoring.

---

## IAA decision table

| Situation | Metric | When to use |
|-----------|--------|-------------|
| Two fixed annotators, nominal labels | Cohen's κ | Gold-set double-labeling with exactly 2 raters |
| ≥2 annotators, missing data, ordinal scales | Krippendorff's α | Multi-rater, partial coverage, or ordinal rubrics |
| Raw percent agreement | Report alongside κ/α | Never alone — inflated by class imbalance |

### Threshold conventions (set before annotating)

| Coefficient | Interpretation | Typical use |
|-------------|----------------|-------------|
| ≥ **0.80** | Reliable | Consequential gates, gold-set acceptance |
| **0.667–0.80** | Tentative | Pilot instruments; refine guidelines |
| **≥ 0.60** | Acceptable for subjective judge tasks | Judge–human calibration gate (looser than label IAA) |
| < **0.667** | Unreliable | Revise guidelines, retrain annotators, do not gate |

**Rule:** Higher stakes → higher bar. A downgrade/block action argues for α ≥ 0.80 on human labels; judge–human κ ≥ 0.6 is a deliberately looser prerequisite before trusting class-specific P/R.

---

## Metric formulas

### Class-specific P/R/F1 (action-triggering negative class)

For binary gate field `G` where `G=False` triggers an action (downgrade, block, escalate):

- **Precision on G=False:** TP / (TP + FP) — fraction of triggered actions that were deserved
- **Recall on G=False:** TP / (TP + FN) — fraction of true failures caught
- **F1 on G=False:** harmonic mean of precision and recall

Report **per failure_mode** breakdown when strata are large enough.

**Do not gate on global accuracy.** An always-pass judge scores ~90% on a 10%-fail set while missing every failure.

### False-action rate (population harm)

Over a held-out set of **clean successes** (human-labeled `G=True`):

```
false_action_rate = (# successes where judge says G=False) / (# successes)
```

Stricter than precision alone — bounds harm on the success population.

### Expected Calibration Error (ECE)

Diagnostic only. LLM-judge confidence is systematically overconfident and ECE is bin-sensitive. Report ECE; **never gate deployment on it**. Prefer κ/α and class-specific P/R.

### CoT-gaming red-team flip rate

Inject trajectories where chain-of-thought is manipulated (narration claims success; tool outputs unchanged). Measure fraction of verdicts that flip from fail→pass vs human baseline.

---

## Enable-policy template

Adapt thresholds to product stakes. Example profile for a **precision-first downgrade gate**:

| Gate | Example threshold | Purpose |
|------|-------------------|---------|
| Precision on action-trigger class | ≥ 0.90 | ≤10% of actions undeserved |
| False-action rate on clean successes | ≤ 2% | Population-level harm bound |
| Recall on action-trigger class | ≥ 0.70 | Gate catches enough real failures |
| Red-team verdict-flip rate | ≤ 5% (soft 10%) | Gaming exposure ceiling |
| Judge–human κ vs gold labels | ≥ 0.6 | Labels trustworthy enough to gate |
| ECE | Reported, not gated | Overconfidence diagnostic |
| Default posture | **Shadow/off until all met** | Record `would_act`; do not change outcomes |

### Rollout stages

1. **Shadow** — judge runs; log `would_act` without changing outcomes
2. **Dev eval** — enable on dev/staging with monitoring
3. **Production enable** — flip action gate only after all thresholds clear on frozen test split

**Held-out discipline:** Never iterate rubric/prompt on the test split. Refresh gold set quarterly; alert if κ drops below floor.

---

## Judge bias catalog

| Bias | Symptom | Mitigation in rubric/pipeline |
|------|---------|-------------------------------|
| **Position bias** | Prefers first/last option in pairwise | Shuffle option order; pointwise scoring |
| **Verbosity bias** | Longer answers score higher | Explicit length-neutral rules; penalize fluent evasion |
| **Self-preference** | Model favors its own style | External judge model; jury-of-3 + abstain |
| **CoT-gaming** | Narration claims success; evidence contradicts | Evidence-grounded criteria; red-team stratum |
| **Style attacks (BITE)** | Semantics-preserving style edits flip verdict | Ground on observable spans, not prose |
| **Halo/conflation** | One strong dimension inflates others | Analytic (per-criterion) rubric |
| **Criteria drift** | Graders redefine criteria while grading | Budget re-coding loops; co-construct rubric with labels |

---

## Synthetic data anti-patterns

| Anti-pattern | Why it fails | Fix |
|--------------|--------------|-----|
| Re-roll until target code appears | Selection bias; confirms priors | Record mismatches; fix dimension spec |
| Generate outputs, not inputs | Leaks generator blind spots | Generate user inputs only; run through real system |
| Synthetic in held-out test | Contamination | Synthetic → dev split only |
| "Give me test queries" prompt | Generic, repetitive cases | Structured dimensions (domain × behavior × stratum) |
| Same team authors rubric + red-team | Tests only anticipated attacks | Independent double-labeling on gold set |

---

## Gold set sizing and stratification

| Parameter | Guideline |
|-----------|-----------|
| Size | ~200–300 items (~250 validates ~80% agreement at 95% CI) |
| Split | ~60/40 dev/test; never tune on test |
| Stratification | Taxonomy defines strata; oversample action-trigger class |
| Mix (starting point) | ~40% representative / 30% boundary / 20% edge / 10% impossible |
| Labeling | Double-label + adjudicate; α ≥ 0.80 on primary gate field |
| Provenance | Tag `production` vs `synthetic`; report metrics on production-only test subset |
| Versioning | `gold-v1`, `gold-v2`; label changes are production risk |

### Three-tier rollout

1. **Pilot (~50)** — validate labeling instrument
2. **Confirmation** — κ + behavioral shadow before full set
3. **Full gold set** — calibration against frozen test

---

## Seed failure codes (bootstrap only)

Use as open-coding seeds; let real codes emerge and rename/split/merge:

| Seed code | Observable signal | Typical verdict |
|-----------|-------------------|-----------------|
| `fabricated-progress` | Narrates success; no tool/state support | Fail; red-team stratum |
| `premature-impossible` | Declares impossible without exploration | Fail; graceful only if exploration evidenced |
| `partial-counted-as-full` | Subgoal done; presented as complete | Fail; record partial metadata |
| `right-answer-wrong-process` | Correct output; invalid trajectory | Per evidence; flag process |
| `tool-error-misread` | Misinterprets tool error as success | Fail |
| `fluent-evasion` | Polite non-answer as resolution | Fail |
| `criteria-mismatch` | Satisfies wrong goal | Fail |
| `goal-met-but-unsafe` | Achieved via unsafe path | Pass goal; flag in metadata |

---

## Continuous monitoring stack

### Offline regression

- **CI/PR:** Run golden dataset; block deploy on regression
- **Scheduled:** Daily/weekly gold re-run against current judge prompt/model
- **Trace-to-dataset:** Every production failure → candidate golden entry after human review

### Online production

| Layer | Coverage | Purpose |
|-------|----------|---------|
| L1 — Sync checks | 100% traffic | Schema, tool validators, deterministic guards |
| L2 — Async LLM judge | 5–10% sample | Quality drift, new failure modes |
| L3 — Statistical drift | Aggregated scores | CUSUM / control charts on judge metrics |

### Operational loops

- **Per-category fail rates** — not a single global threshold (categories have different costs)
- **Quarterly gold refresh** — re-check κ; add new strata from production
- **Criteria drift** → re-open-code (Stage 1)
- **New failure mode in prod** → axial update → rubric → gold stratum

---

## Judge creation paths

| Approach | When | Requirements |
|----------|------|----------------|
| **Prompt + rubric calibration** (default) | Starting out; <250 labels | Gold set; few-shot from human corrections |
| **Few-shot iteration loop** | After initial calibration | Human corrections → exemplars; track agreement |
| **Fine-tuning / distillation** | Prompt path plateaus | Larger labeled set; hold-out discipline |

Target **75–90% judge–human alignment** on pilot before scaling annotation (Arize practitioner guidance).

---

## Open-code quality diagnostics (no ground truth yet)

When codes are emerging without a gold set, track:

- **Coverage** — traces with at least one code vs blank
- **Novelty** — new unique codes per batch (saturation signal)
- **Coherence** — LLM-cluster stability across exports

Use to detect hallucinated or overly broad codes before axial clustering.

---

## Bibliography

| # | Title | URL | Used for |
|---|-------|-----|----------|
| R1 | AI Evals Step-by-Step: Hamel Husain & Shreya Shankar Masterclass | https://www.aakashg.com/hamel-shreya-ai-evals-step-by-step/ | Open/axial coding terms; error analysis primacy |
| R2 | Hamel — evals-FAQ: error analysis | https://hamel.dev/blog/posts/evals-faq/why-is-error-analysis-so-important-in-llm-evals-and-how-is-it-performed.html | First-failure; saturation; axial taxonomy |
| R3 | Field Guide to Rapidly Improving AI Products | https://hamel.dev/blog/posts/field-guide/ | Traces prerequisite; one judge for biggest issue; synthetic principles |
| R4 | EvalGen (Shankar et al., UIST 2024) | https://arxiv.org/abs/2404.12272 | Criteria drift; co-construct rubric |
| R5 | Autorubric | https://arxiv.org/abs/2603.00077 | Analytic vs holistic; per-criterion κ |
| R6 | Masood — Rubric-Based Evals & LLM-as-a-Judge | https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80 | Anchor examples; regression root-cause |
| R7 | Krippendorff — Computing Alpha-Reliability (2011) | https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf | α thresholds |
| R8 | Brenndoerfer — IAA Metrics & Implementation | https://mbrenndoerfer.com/writing/inter-annotator-agreement-kappa-alpha-reliability | κ vs α choice |
| R9 | Agent-as-a-Judge (ICML 2025) | https://arxiv.org/abs/2410.10934 | Trajectory-aware judging |
| R10 | Gaming the Judge (Jan 2026) | https://arxiv.org/abs/2601.14691 | CoT-gaming; evidence grounding |
| R11 | BITE — Style Manipulation Attacks | https://arxiv.org/abs/2605.26156 | Style-only judge attacks |
| R12 | LLM Evals Lesson 2: Error Analysis | https://thingsithinkithink.blog/posts/2025/06-21-llm-evals-lesson-2-error-analysis/ | Emergent categories; card sort |
| R13 | Langfuse — Scores Overview | https://langfuse.com/docs/evaluation/scores/overview | TEXT scores for open coding |
| R14 | SPADE (VLDB 2024) | https://arxiv.org/abs/2401.03038 | Prompt deltas encode taxonomy |
| R15 | Galtea / Arize / LangChain judge guidance | https://galtea.ai/blog/llm-evaluation-complete-guide | Class P/R; validate before gating |
| R16 | Hamel — synthetic data FAQ | https://hamel.dev/blog/posts/evals-faq/what-is-the-best-approach-for-generating-synthetic-data.html | Structured dimensions |
| R17 | Langfuse — Annotation Queues | https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues | Human scoring workflow |
| R18 | Overconfidence in LLM-as-a-Judge | https://arxiv.org/abs/2508.06225 | ECE diagnostic-only |
| R19 | How to Correctly Report LLM-as-a-Judge | https://arxiv.org/abs/2511.21140 | Sample sizing; asymmetric allocation |
| R20 | Appen — Krippendorff's Alpha | https://www.appen.com/blog/krippendorffs-alpha | α interpretation bands |
| R21 | GATOS / LOGOS — LLM-assisted coding | https://arxiv.org/abs/2509.24294 | Assisted codebook; human validation required |
| R22 | Open-code quality metrics | https://arxiv.org/abs/2411.12142 | Coverage/novelty/coherence without ground truth |
| R23 | Ensemble-LM axial coding | https://arxiv.org/abs/2601.15338 | Clustering + intrinsic metrics |
| R24 | LangChain Align Evals | https://docs.langchain.com/langsmith/align-eval | Human corrections → few-shot loop |
| R25 | VentureBeat — offline/online eval split (2026) | https://venturebeat.com/ai/ | Golden regression + production sampling |
