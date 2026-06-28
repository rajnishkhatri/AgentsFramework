# The Evals Handbook for Solo Agentic Engineering
### Runbook V — Evaluation as the Discipline That Bridges Building *With* Agents and Building *Systems That Contain* LLMs

## TL;DR
- **Evals are not a dashboard; they are a *process* — error analysis first, automation last.** The single highest-ROI activity is "look at your data": read traces, open-code failures, group them into a taxonomy, and only then build the smallest evaluator that catches each high-frequency failure. Husain & Shankar's evals FAQ states verbatim: *"In the projects we've worked on, we've spent 60-80% of our development time on error analysis and evaluation."*
- **The same discipline serves both targets.** Whether you are measuring how well a coding agent writes/maintains your code (target A) or hardening a production LLM system you ship — a dispute-resolution platform, RAG pipeline, agentic workflow (target B) — the loop is identical: Analyze → Measure → Improve, gated by binary pass/fail criteria, a human-aligned judge, and statistically honest success rates. "Design for verifiability" graduates from ad-hoc tests into measurement when each verification step becomes a scored, regression-tracked eval.
- **Trust the eval before you trust the system.** A judge that is not validated against human labels (via TPR/TNR, not accuracy) is worse than no judge. A 100-example eval at 80% has a ±~8-point 95% confidence interval, so most "improvements" you'll see are noise. Validate the validator, size the set, report intervals, and prune evals that no longer give signal.

---

## Key Findings

1. **Error analysis is the spine of everything.** Husain calls "look at your data" the most important and underrated activity in AI development and "the single most valuable activity... consistently the highest-ROI activity." The canonical method is grounded-theory qualitative coding: **open coding** (free-text notes on each trace) → **axial coding** (group notes into a failure taxonomy) → **iterate to theoretical saturation**. Rule of thumb: review at least 100 traces; if ~20 traces don't reveal a new failure category, you can stop.

2. **Prefer binary pass/fail over Likert/1–5 scales.** Husain: scores like 3.72 vs 4.2 are uninterpretable ("does it really mean your system is better? We don't know"); binary judgments force clarity and are harder to game with verbosity. Pair each pass/fail with a written **critique** (the "Critique Shadowing" method).

3. **LLM-as-judge must itself be evaluated.** Measure the judge against human labels using **True Positive Rate and True Negative Rate**, never raw agreement (a "trap metric": a dumb judge that always says "pass" scores 90% agreement when failures are only 10% of data). Use scoped, per-criterion binary judges, not holistic graders.

4. **Criteria drift is real and unavoidable** (Shankar et al., "Who Validates the Validators?", UIST 2024). You cannot fully specify evaluation criteria a priori; grading outputs is how you discover your criteria. Tooling must support rapid iteration over criteria *and* implementations simultaneously.

5. **The Three Gulfs model** (Husain/Shankar) organizes the whole problem: Gulf of Comprehension (you ↔ your data), Gulf of Specification (your intent ↔ your prompt), Gulf of Generalization (your prompt ↔ behavior across all inputs). Each gulf maps to different practices and is closed by different tools.

6. **Coding agents are the easy case for verification — but "tests pass" is necessary, not sufficient.** Deterministic graders are natural for code (does it run, do tests pass), but METR found roughly half of test-passing SWE-bench Verified PRs would not be merged by maintainers, and a vanilla agent broke an average of 6.5 previously-passing tests per patch. Reliability needs multi-trial measurement (pass^k), regression suites, and code-quality graders.

7. **Generic, off-the-shelf metrics are an anti-pattern.** "Helpfulness," "coherence," BERTScore, ROUGE, cosine similarity create an illusion of confidence. Husain: *"Generic evaluations waste time and create false confidence."* Use custom, application-specific binary failure modes derived from your own error analysis.

---

## Details

### Part 1 — The Mental Model: Three Gulfs + Analyze/Measure/Improve

**The Three Gulfs (Shankar & Husain, AI Evals course; rooted in Shankar's HCI research and the "Who Validates the Validators?" line of work).** Frame every eval problem as bridging three gaps:

- **Gulf of Comprehension** (developer → data): You cannot read every input or output. *Practices:* error analysis, custom trace viewers, clustering/sampling. A "data scientist" hat.
- **Gulf of Specification** (intent → prompt): Your prompt under-specifies what you actually want; the model can't read your mind. *Practices:* explicit prompt structure (role, instructions, examples, reasoning steps), critique-driven criteria refinement. A "PM/communication" hat.
- **Gulf of Generalization** (prompt → behavior across inputs): Even a perfect prompt fails on new data. *Practices:* RAG, task decomposition, pre/post-processing, retries, fine-tuning. The "AI engineering" hat.

Shankar's own framing: people "often mistake specification issues for generalization issues (or vice versa), or try to tackle two gulfs without considering the third." Diagnose the gulf *before* choosing the fix.

**The Analyze → Measure → Improve lifecycle (Husain/Shankar).**
- **Analyze:** Run the system on real or synthetic inputs, log traces, do error analysis (open + axial coding), tag each failure to a gulf. This is where the bulk of effort goes.
- **Measure:** Turn the dominant qualitative failure modes into binary evaluators (code assertions or aligned LLM judges). Quantify how often each happens.
- **Improve:** Fix prompts (specification) or engineering (generalization); fine-tune only when cheaper fixes fail. Re-run. Cycle repeatedly.

### Part 2 — Error Analysis (the core ritual)

The canonical procedure (Husain/Shankar FAQ, updated Jan 15, 2026):
1. **Create a dataset** of representative traces. If you have none, bootstrap with structured synthetic data.
2. **Open coding:** A single domain expert (the "benevolent dictator") writes free-text notes on each trace, akin to journaling, adapted from qualitative research. Focus on the **first failure** in a trace — upstream errors cause downstream noise.
3. **Axial coding:** Group notes into a structured failure taxonomy; count failures per category. Husain calls this "the most important step." An LLM can assist the grouping.
4. **Iterative refinement** to theoretical saturation (~20 new traces with no new category; review ≥100 to start).

A **simple custom data viewer** is described by Husain as "the single most impactful investment I've seen AI teams make" — more than any dashboard: *"Teams with thoughtfully designed data viewers iterate 10x faster than those without them. And here's the thing: These tools can be built in hours using AI-assisted development."* Real example: Nurture Boss discovered their assistant failed 66% of the time on relative-date handling ("two weeks from now") purely by building a viewer and annotating conversations.

### Part 3 — Building Evaluators: code assertions vs LLM judges

**Cost hierarchy (cheapest first):** code-based assertions (regex, schema/structural validation, execution/unit tests) → LLM-as-judge → human review. Husain: *"Start with cheap code-based checks where possible... Reserve complex evaluation for subjective qualities that can't be [checked otherwise]. Only build expensive evaluators for problems you'll iterate on repeatedly."*

**LLM-as-judge done right — "Critique Shadowing" (Husain):**
1. Find the principal domain expert.
2. Create a diverse dataset (start ~30 examples, expand).
3. Expert makes **binary pass/fail** judgments + a **detailed critique** — detailed enough to use as a few-shot example, such that "a new employee could understand it."
4. Fix pervasive errors found before building the judge.
5. Build the judge iteratively, few-shotting with expert critiques.
6. Create specialized per-criterion judges only if needed.

**Validate the judge** on a held-out, human-labeled set using **TPR** (of things that should pass, what % did the judge pass) and **TNR** (of things that should fail, what % did it fail). Husain in the FAQ: *"Focus on achieving high True Positive Rate (TPR) and True Negative Rate (TNR) with your judge on a held out labeled test set. If you struggle to achieve good alignment with human scores, then consider trying a different model."* Never optimize raw agreement — it's a trap metric because "if this failure is only happening 10% of the time, you can have the dumbest judge in the world have 90% accuracy by just always predicting pass." Split data so the judge isn't overfit. Once you know TPR/TNR you can correct the judge's estimate to recover the true failure rate. Using the same model family for the judge is usually fine for scoped binary tasks — what matters is alignment, not model identity.

**Criteria drift (Shankar et al., UIST 2024).** Verbatim: *"to grade outputs, people need to externalize and define their evaluation criteria; however, the process of grading outputs helps them to define those very criteria... it is impossible to completely determine evaluation criteria prior to human judging of LLM outputs."* Expect criteria to evolve as you grade; re-grade earlier examples when criteria shift; keep a versioned record of criteria.

**Assertion synthesis.** SPADE (Shankar et al., arXiv:2401.03038 / VLDB 2024) auto-synthesizes data-quality assertions by analyzing prompt-version histories ("prompt deltas"). Verbatim: *"In testing across nine different real-world LLM pipelines, SPADE efficiently reduces the number of assertions by 14% and decreases false failures by 21%... deployed as an offering within LangSmith... used to generate data quality assertions for over 2000 pipelines across a spectrum of industries."* EvalGen (the "Who Validates the Validators?" system) generates candidate assertions/judges and aligns them to human grades. Treat both as accelerants *after* you understand your failures, not replacements for looking at data.

### Part 4 — Eval Dataset Construction

- **Bootstrap from real traces** whenever possible; synthetic data misses real-user complexity.
- **Structured synthetic data for cold-start (Husain/Shankar):** Don't prompt "give me test queries" — it yields "generic, repetitive outputs." Define **dimensions** (e.g., for a dispute platform: dispute type, claimant emotional state, evidence completeness, jurisdiction), then take the product and generate tuples. Start from explicit **failure hypotheses**.
- **Golden dataset:** a persistent, hand-built set covering core features, regression tests for past bugs, and known edge cases. Keep CI sets small (~100+ curated examples) because they run often and each run costs.
- **Sizing (statistical reality):** A 100-example eval at 80% pass has SE ≈ √(0.8·0.2/100) ≈ 0.04, i.e. a 95% CI of roughly ±8 points. A 4-point "improvement" is less than half the noise. Report confidence intervals, not point estimates ("82% (95% CI: 80–84) is honest; 82% is a coin flip with branding"). For A/B prompt comparisons require non-overlapping CIs (or use paired/bootstrap tests; Anthropic's "statistical approach to model evals" recommends paired-difference analysis as a free variance-reduction technique). Larger deltas need fewer examples; sub-4-point deltas need thousands.

### Part 5 — Target A: Eval Discipline for the Coding-Agent Workflow

This is where "design for verifiability" becomes a measurement methodology. The throughline: **make verification cheap and laddered, then turn every verification step into a scored, regression-tracked eval.**

**Eugene Yan's verification ladder ("How to Work and Compound with AI," May 3, 2026; Yan is on Anthropic's technical staff).** Treat verification as a ladder from cheap+deterministic (bottom) to expensive+judgment (top); catch each issue at the lowest possible rung. Verbatim: *"Shift verification left; catch errors at write time. I think of verification as a ladder. The bottom is cheap and deterministic; the top is expensive and requires judgement. We want to address issues at the lowest possible rung. Near the bottom are post-edit hooks that run `ruff format`, `ruff check --fix`... Higher on the ladder are tests, evals, LLM reviews."* The verification-autonomy link is explicit: *"You can't delegate what you can't verify, so this requires first defining success criteria and metrics."* And give the model its own loops: *"Make it easy for the model to verify the work... If the system produces a metric, let the model run the eval and optimize it... let the model run it and read the error."* **Close the loop** by mining transcripts: *"When I scanned ~2,500 of my past user turns, a sizable percentage contained phrases like 'can you also…', 'did you check…', 'still wrong'... These suggest... I should update the `CLAUDE.md` or skill, or that a verification step is missing or broken."*

**Anthropic's agent-eval framework ("Demystifying evals for AI agents," Jan 9, 2026):**
- Components: **task** (inputs + success criteria), **trial** (one attempt; run multiple due to non-determinism), **grader** (scoring logic with assertions), **transcript/trace** (full record), **outcome** (final environment state — e.g., "a flight-booking agent might say 'Your flight has been booked'... but the outcome is whether a reservation exists in the environment's SQL database"), **harness**, **suite**.
- **Grade the outcome, not the path.** Verbatim: *"it's often better to grade what the agent produced, not the path it took"* — fixed tool-call sequences are "too rigid" and "overly brittle."
- **Capability evals graduate into regression evals.** Verbatim: *"capability evals with high pass rates can 'graduate' to become a regression suite that is run continuously to catch any drift. Tasks that once measured 'Can we do this at all?' then measure 'Can we still do this reliably?'"* Capability evals start low (a hill to climb); regression evals target ~100%.
- Deterministic graders are natural for code: *"does the code run and do the tests pass?"* — binary fail-to-pass and pass-to-pass tests, static analysis (lint, type, security).
- **SWE-bench Verified progress:** *"LLMs have progressed from 40% to >80% on this eval in just one year."* (The same article elsewhere says scores "started at 30%... >80%" — treat the exact baseline as approximate.)
- **Eval-driven development:** *"build evals to define planned capabilities before agents can fulfill them, then iterate until the agent performs well."*

**Reliability measurement: pass@k vs pass^k.**
- **pass@k** = probability of ≥1 success in k tries; rises with k ("shots on goal"). Use when one success matters (e.g., agent finding a solution on the first try → pass@1).
- **pass^k** = probability *all* k trials succeed; falls with k. Use for customer-facing reliability. Concrete hook (Anthropic, verbatim): *"If your agent has a 75% per-trial success rate and you run 3 trials, the probability of passing all three is (0.75)³ ≈ 42%."* Single runs (pass@1) hide reliability problems; "at k=1, they're identical... By k=10, they tell opposite stories: pass@k approaches 100% while pass^k falls to 0%." (pass^k originates in τ-bench, Yao et al., arXiv:2406.12045.) A 0% pass@100 "is most often a signal of a broken task, not an incapable agent."
- **Operational rule:** run ≥3 trials per regression task; if pass@k is high but pass^k drops, you have a reliability problem.

**"Tests pass" is necessary, not sufficient — the empirical case for richer verification.**
- **METR ("Many SWE-bench-Passing PRs Would Not Be Merged into Main," March 10, 2026):** 4 active maintainers from 3 SWE-bench Verified repos (scikit-learn, Sphinx, pytest) reviewed 296 AI-generated PRs, blinded to source. Verbatim: *"roughly half of test-passing SWE-bench Verified PRs written by mid-2024 to mid/late-2025 agents would not be merged into main by repo maintainers, even after adjusting for noise."* And: *"on average maintainer merge decisions are about 24 percentage points lower than SWE-bench scores supplied by the automated grader"* (golden-patch human baseline merge rate ~68%). Rejection reasons, least-to-most serious: **code quality** (bad style, not following repo standards), **breaks other code** (solving the issue but breaking unrelated code), and — relatively rare — **core functionality** failures. One model's time horizon was overstated ~7×. **Crucial caveat (verbatim):** *"Since the agents are not given a chance to iterate on their solution... we do not claim that this represents a fundamental capability limitation."*
- **Pass-to-pass breakage:** a vanilla agent broke an average of 6.5 previously-passing tests per patch across 100 instances (TDAD preprint, arXiv:2603.17973 — a single study on smaller open models; treat as indicative, not authoritative). The SWE-bench harness already records PASS_TO_PASS data; it just isn't surfaced in leaderboards.
- **Implication:** for agent-written code, complement "tests pass" with regression suites (pass-to-pass), code-quality / model-based graders, and a human merge gate.

### Part 6 — Target B: Eval Methodology for Production LLM Systems You Ship

Apply the identical loop to systems you ship (dispute-resolution platforms, RAG, agentic pipelines).

**RAG evals (Jason Liu).** Start the data flywheel with synthetic question generation per chunk; establish retrieval **precision/recall** baselines *before* touching generation — "the biggest mistake I see teams make is spending too much time on complex generation before understanding if their retrieval even works." "There are only 6 RAG evals," organized in tiers: fast retrieval metrics (precision, recall, MAP@K, MRR@K, no LLM needed) → three core relationships (Context|Query, Answer|Context, Answer|Query) → three advanced relationships. The flywheel: implement → synthetic data → fast evals → real-world data → classify/analyze → improve → monitor → user feedback → iterate. Concrete baseline-value: full-text vs embedding recall differed sharply by corpus (≈55% vs ≈65% on repo issues; near-parity on essays) — measure, don't assume.

**Multi-step / agentic traces (Husain FAQ).** Two phases: (1) **End-to-end task success** — treat agent as a black box, define a precise per-task success rule, measure with human or aligned judge; (2) **Step-level diagnostics** — score tool choice, parameter extraction, error handling, context retention, efficiency, and goal checkpoints. Use a **transition failure matrix** (rows = last successful state, columns = first failure state) to localize where most failures occur — e.g., "GenSQL → ExecSQL transitions cause 12 failures while DecideTool → PlanCal causes only 2" (Husain; see also Bryan Bischof's "Failure is a Funnel" text-to-SQL talk, Data Council 2025). Always tag the **first** upstream failure.

**CI vs production (online vs offline).**
- **CI/offline:** small curated dataset (~100+ examples: core features + regression tests + edge cases); favor deterministic assertions over LLM-judges because they run often and cost matters. As the EDD community puts it: "If your evals don't run on every change, they don't exist."
- **Production/online:** sample live traces, run evaluators asynchronously/in batch; feed dashboards, regression tests, and improvement loops; sample interesting traces back into the eval set.

**Guardrails vs evaluators (Husain).** Guardrails run *inline before* the user sees output — fast, deterministic, user-visible when they fire (treat false positives as production bugs; version them, log every trigger, keep conservative). Evaluators run *after*, measure nuanced qualities, feed dashboards/regression, and do **not** block. Inline LLM-judge is feasible "only when the latency budget and reliability targets allow." Don't use off-the-shelf guardrail prompts blindly — "always look at the prompt."

**Drift & monitoring.** Re-run error analysis on significant changes (new features, prompt/model swaps, major fixes); review ≥100 fresh traces per cycle (typically every 2–4 weeks). Between cycles, review 10–20 outlier traces weekly (long conversations, multiple retries, flagged traces). New systems: weekly until patterns stabilize; mature: monthly. Always analyze after incidents and complaint spikes.

---

## Pattern / Rule Catalog (attributed)

Each entry: **Name (attribution) — Problem — Rule(s) — When to use / not.**

**P1. Look At Your Data (Husain).** *Problem:* teams optimize easy-to-measure proxies, not real failures. *Rules:* before any metric, manually read 20–50 outputs on every significant change; spend the majority of dev time here; narrate findings (not "evals") to stakeholders. *When not:* never skip; even mature systems need periodic review.

**P2. Open → Axial Coding to a Failure Taxonomy (Husain/Shankar; grounded theory).** *Problem:* no principled way to decide what to measure. *Rules:* free-text note every trace → group into named failure categories → count → iterate to saturation (≥100 traces; stop after ~20 with no new category). Tag the first failure only. *When not:* tiny/throwaway prototypes.

**P3. Binary Pass/Fail + Critique / Critique Shadowing (Husain).** *Problem:* Likert scores are uninterpretable and verbosity-gameable. *Rules:* every eval is pass/fail; attach a written critique detailed enough to be a few-shot example; have a benevolent-dictator expert label ~30 to start. *When not:* genuinely ordinal product decisions (rare) — even then prefer multiple binaries.

**P4. Validate the Validator with TPR/TNR (Husain; Shankar "Who Validates the Validators?").** *Problem:* an unvalidated judge fabricates confidence. *Rules:* hold out a human-labeled set; report TPR and TNR (never raw agreement); split data to avoid overfitting; correct true failure rate using judge TPR/TNR; if alignment is poor, try another model. *When not:* never trust an unvalidated judge in CI or production.

**P5. Per-Criterion Scoped Judges (Husain/Shankar).** *Problem:* holistic "quality" judges are unalignable and uninformative. *Rules:* one judge = one specific failure mode (e.g., "human handoff failure," "tour scheduling issue"), binary. Add specialized judges only when error analysis demands. *When not:* don't proliferate judges beyond signal.

**P6. Code Assertions Before LLM Judges (Husain; cost hierarchy).** *Problem:* premature, expensive LLM-judges for things a regex catches. *Rules:* climb the cost ladder — regex/schema/execution tests first; LLM-judge only for persistent subjective generalization failures; human review last. *When not:* don't force code assertions onto genuinely subjective qualities.

**P7. Structured Synthetic Data via Dimensions (Husain/Shankar; Liu for RAG).** *Problem:* "give me test queries" yields generic junk. *Rules:* define dimensions (personas/scenarios/edge axes), take the product, generate tuples; start from failure hypotheses; for RAG generate one synthetic Q per chunk. *When not:* prefer real traces once you have them.

**P8. Grade the Outcome, Not the Path (Anthropic).** *Problem:* fixed tool-sequence checks are brittle. *Rules:* assert final environment state/outcome; reserve path checks for step-level diagnostics during debugging. *When not:* when the path itself is the product requirement (e.g., mandated compliance steps).

**P9. Capability Evals Graduate to Regression Evals (Anthropic).** *Problem:* no protection against backsliding. *Rules:* capability evals start at low pass rates; once consistently high, freeze them into a continuously-run regression suite (~100% target). *When not:* don't freeze unstable/flaky tasks.

**P10. pass^k for Reliability (Yao et al. τ-bench; Anthropic).** *Problem:* single runs hide flakiness. *Rules:* run ≥3 trials; track pass^k for customer-facing tasks; if pass@k high but pass^k low, fix reliability; investigate 0% pass@100 as a broken task. *When not:* one-success-matters tasks → use pass@k.

**P11. Verification Ladder / Design for Verifiability (Yan).** *Problem:* expensive late verification, un-delegatable work. *Rules:* shift verification left; cheap deterministic checks at write-time (hooks, linters); define success criteria before delegating; let the model run its own evals and read errors; mine transcripts for missing verification steps. *When not:* exploratory throwaway code.

**P12. Transition Failure Matrix (Husain; Bischof).** *Problem:* multi-step failures are hard to localize. *Rules:* build a matrix of last-good-state × first-failure-state; invest debugging where counts cluster. *When not:* single-step systems.

**P13. RAG Flywheel + 6 Evals (Liu).** *Problem:* teams optimize generation before retrieval works. *Rules:* baseline retrieval precision/recall first; tiered metrics; build feedback collection ASAP; iterate the flywheel. *When not:* non-retrieval systems.

**P14. Guardrails ≠ Evaluators (Husain).** *Problem:* conflating inline safety with async quality measurement. *Rules:* guardrails = fast/deterministic/inline/blocking (version, log, conservative); evaluators = async/nuanced/non-blocking. *When not:* don't put a slow LLM-judge inline unless latency budget allows.

**P15. Pass Rate Is a Product Decision (Husain).** *Problem:* chasing 100% pass. *Rules:* a 100% pass rate means evals are too easy; a ~70% rate often means a meaningfully stressful eval; set per-eval target pass rates from product risk. *When not:* hard safety gates legitimately require ~100%.

---

## Drop-in Directives for AGENTS.md / CLAUDE.md

```markdown
## Evaluation & Verifiability Directives

### Make outputs verifiable
- For every nontrivial function you write or modify, generate or update unit tests
  in the same change. Prefer pure functions and explicit return types.
- After editing any file, run the project formatter, linter, and type checker.
  Treat their output as a blocking gate; fix before proceeding.
- Before submitting, run the full test suite. Report which tests are
  fail-to-pass (newly fixed) and pass-to-pass (must not regress). If any
  previously-passing test now fails, stop and fix it — do not rationalize it.

### Logging & traces (for systems that CONTAIN LLMs)
- Instrument every LLM call, tool call, retrieval, and intermediate result so a
  single user request produces one complete, inspectable trace.
- Log inputs, outputs, tool names, parameters, latency, and token counts. Make
  traces renderable on one screen for human review.
- Emit a stable trace/span ID and the system/prompt version with every trace.

### Write eval-friendly code
- Express success criteria as explicit, binary, code-checkable assertions where
  possible (schema validation, regex, execution checks) before reaching for an
  LLM judge.
- When a task is subjective, write a per-criterion binary judge prompt plus a
  short critique rubric; never a 1–5 holistic score.
- Separate the agent's final natural-language message from the actual outcome
  (environment state); assert on the outcome.

### Regression discipline
- For every bug we fix, add a regression test case to the eval set with the
  failing input and expected pass/fail.
- Run new/changed eval tasks at least 3 trials; report pass@k and pass^k.
- Do not optimize for high eval pass rates. Surface failures honestly.

### Close the loop
- When I correct you for the same class of mistake twice, propose an update to
  this file or a new assertion/eval that would have caught it.
```

---

## Checklists & Gates

**Error-Analysis Checklist (run every significant change):**
- [ ] Gathered ≥100 representative traces (real preferred; structured-synthetic if cold-start).
- [ ] Custom viewer renders the full trace + domain context on one screen.
- [ ] Open-coded each trace with free-text notes; tagged the *first* failure.
- [ ] Axial-coded notes into a named, counted failure taxonomy.
- [ ] Reached saturation (~20 traces, no new category).
- [ ] Prioritized failures by frequency × impact, not by ease of measurement.

**"Before You Trust This Eval" Gate:**
- [ ] Eval is binary and maps to a *specific* failure mode (not "quality/helpfulness").
- [ ] Derived from real error analysis, not an off-the-shelf metric.
- [ ] If LLM-judge: validated on held-out human labels; TPR and TNR both reported (not agreement).
- [ ] Data split so the judge isn't overfit; criteria versioned.
- [ ] Sample size large enough that the reported delta exceeds the 95% CI.
- [ ] Pass-rate target set deliberately from product risk (not assumed 100%).

**LLM-Judge-Alignment Gate (promote a judge to CI only if):**
- [ ] Built via critique shadowing with a single domain expert.
- [ ] TPR and TNR both meet your per-product threshold (see decision rules).
- [ ] You can recover true failure rate from judge TPR/TNR.
- [ ] Re-validated after any prompt/model/criteria change.

**Coding-Agent Output Gate (before merging agent-written code):**
- [ ] Formatter/linter/type checker clean.
- [ ] Fail-to-pass tests pass; pass-to-pass tests unbroken.
- [ ] ≥3 trials run; pass^k acceptable for the task's reliability needs.
- [ ] Human review for code quality / unintended changes (tests-pass ≠ mergeable — METR: ~half of test-passing PRs aren't mergeable).
- [ ] Regression test added for any bug fixed.

---

## Decision Rules & Thresholds

- **How many traces to read:** ≥100 to start error analysis; stop after ~20 consecutive with no new category; review 10–20 outliers/week between cycles; ≥100 fresh per 2–4 week cycle.
- **Code assertion vs LLM-judge vs human:** Deterministic/objective → code assertion. Subjective + persistent + worth iterating → LLM-judge (validated). Novel/high-stakes/ambiguous → human. Climb from cheapest.
- **Judge trust threshold:** Don't ship a judge on raw agreement. Set TPR/TNR targets by asymmetric cost — medical/safety: maximize TNR (catch failures) even at some false positives; creative tasks: protect TPR. Re-validate on every change.
- **Eval set size:** CI ~100+ curated. For A/B claims, ensure the delta exceeds ±~8 pts at n=100 (SE≈0.04 at p=0.8); require non-overlapping 95% CIs or paired/bootstrap significance. Deltas >7 pts tolerate small n; sub-4-pt deltas need thousands.
- **Trials per task:** ≥3 for agentic/regression tasks; report pass@k (one-success tasks) and pass^k (reliability tasks).
- **When an eval has graduated to regression:** consistent high pass rate on a stable task → freeze into continuously-run suite.
- **Pass-rate sanity:** 100% → evals too easy; ~70% often healthy/stressful; set per-eval from risk.
- **Budget:** expect 60–80% of dev time on error analysis + evaluation (Husain/Shankar).

---

## Anti-Patterns & Counters

1. **Generic/off-the-shelf metrics** ("helpfulness," "coherence," BERTScore, ROUGE, cosine sim). *Counter:* custom binary failure modes from error analysis. (Off-the-shelf scores are acceptable only as *exploration signals* to sort/surface interesting traces, never as the eval — an advanced technique.)
2. **Too many metrics / vanity dashboards** — a "buffet of metrics" gives false security. *Counter:* few, specific, decision-driving evals; prune evals that stop giving signal (more evals ≠ better agents).
3. **Likert/1–5 scales.** *Counter:* binary + critique.
4. **Not looking at the data** (tools-first mindset — "the most common mistake in AI development"). *Counter:* notebook/viewer + manual review first.
5. **Premature automation of evals.** *Counter:* fix obvious bugs found in error analysis before building automated evaluators; only automate failures you'll iterate on.
6. **Eval tooling before eval process.** *Counter:* process (analyze→measure→improve) first; tools are interchangeable.
7. **Ignoring the judge's own accuracy.** *Counter:* TPR/TNR validation; agreement is a trap.
8. **Optimizing for high pass rates.** *Counter:* stress-test; treat pass rate as a product decision.
9. **Grading the agent's path / fixed tool sequences.** *Counter:* grade outcomes (final environment state).
10. **Trusting "tests pass" as mergeable for agent code.** *Counter:* pass-to-pass regression + code-quality graders + human merge gate.
11. **Single-run agent evaluation.** *Counter:* multi-trial pass^k.
12. **Prompt auto-optimizers as a substitute for thinking.** *Counter:* write prompts manually early — "good writing is good thinking"; be skeptical of auto-optimizers in early stages.

---

## Staged Adoption Plan (solo, single-operator-plus-agent loop)

**Stage 0 — Instrument (day 1).** Add tracing to every LLM/tool/retrieval call so one request = one inspectable trace. For coding work, wire formatter/linter/type-check/test hooks. Drop the AGENTS.md directives above.

**Stage 1 — Look at data (week 1).** Build a one-screen trace viewer with your coding agent (hours, not weeks). Read 100 traces. Open-code → axial-code → failure taxonomy. Fix obvious bugs immediately (no eval infra needed yet).

**Stage 2 — Cheap evals (week 2).** Convert top failure modes into code assertions. Build a small golden CI set (~100): core features + regression tests for every bug fixed. Wire evals to run on every change.

**Stage 3 — One aligned judge (weeks 3–4).** Pick the single most important subjective failure mode. Critique-shadow ~30 examples. Build a binary per-criterion judge. Validate TPR/TNR on held-out labels. Only then trust it in CI.

**Stage 4 — Reliability & statistics.** Add multi-trial runs (pass@k / pass^k) for agentic tasks. Add confidence intervals to every reported number. Stop shipping deltas inside the noise band.

**Stage 5 — Production loop.** Sample live traces back into eval sets; add guardrails for inline safety (versioned, logged); re-run error analysis every 2–4 weeks; graduate stable capability evals into the regression suite; mine transcripts for recurring corrections and close the loop.

**Benchmarks that change the plan:** if you can't articulate your top 3 failure modes → you're not done with Stage 1. If your judge's TNR is below your risk threshold → don't advance past Stage 3. If A/B deltas keep landing inside the CI → you're in Stage 4 and need a bigger eval set or larger interventions. If production failure patterns shift between cycles → tighten the monitoring cadence in Stage 5.

---

## Caveats

- **Source reliability.** The strongest, most-cited sources here are primary: Husain's blog and the Husain/Shankar FAQ (updated Jan 15, 2026), Shankar et al.'s peer-reviewed papers ("Who Validates the Validators?", UIST 2024; SPADE, VLDB 2024), Eugene Yan's and Jason Liu's practitioner blogs, and Anthropic's engineering posts. Some figures come from single studies or preprints — the TDAD pass-to-pass average (arXiv:2603.17973) uses smaller open models, and the METR merge-rate study (March 2026) gave agents only one shot with no iteration and explicitly declines to claim a fundamental capability ceiling. Treat these as indicative. Note Anthropic's own article states two different SWE-bench baselines (40% and 30%) for the same one-year period.
- **The field moves fast.** Specific tools (Braintrust, Langfuse, Inspect, promptfoo, LangSmith) and model behaviors will change; the durable assets are the *methodology* (error analysis, binary judges, TPR/TNR validation, the three gulfs, statistical honesty), not any tool. Husain himself frames the FAQ as "sharp opinions about what works in most cases... not universal truths."
- **Limits of eval methodology.** Evals are pragmatic, not exhaustive — you prioritize frequent failures, not every possible one (evals aren't free). Criteria drift means you can't fully specify criteria up front. LLM judges inherit the biases of the models they evaluate. Agents can game evals (including detecting eval environments). And as METR shows, passing automated graders can overstate real-world usefulness. Evals reduce uncertainty and catch regressions; they do not prove correctness.
- **Solo scope.** This runbook deliberately treats heavyweight team/org eval-ops lightly. The "benevolent dictator" model — one domain expert owning quality — is well-suited to the single-operator-plus-agent loop and is the recommended default. As Husain notes, "if you feel like you need five subject matter experts to judge a single interaction, it's a sign your product scope might be too broad."
