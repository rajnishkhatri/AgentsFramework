---
type: reference
title: "Evaluator rubric — synthetic-data-pipeline skill eval"
description: "Step-by-step human-evaluator rubric for the skill-creator eval loop (iteration 1+)"
---

# Evaluator Rubric — synthetic-data-pipeline skill eval (iteration 1)

You are reviewing plan documents produced in response to 3 question-bank / synthetic-data
prompts. Each test case in the viewer shows: the prompt, one rendered plan, a **collapsed**
"formal grades" section, and a feedback textbox. The same prompt appears twice (two
independent runs) — judge each plan on its own merits.

Doctrine sources behind every anchor below: the skill under test
(`docs/skills/synthetic-data-pipeline/SKILL.md`) and §6–§8 of
`research/Synthetic-data-pipeline-research.md`.

---

## 1. How to use this guide

The ~10-minute path, per test case:

| Step | Time | What to do |
|---|---|---|
| 1 | ~1 min | Read the prompt. Note what it *asks for* vs what doctrine says it *should get*. |
| 2 | ~4 min | Read the whole plan. Skim tables; read verdicts and gate logic closely. |
| 3 | ~3 min | Walk the assertion table for that test case (sections 2–4 below) + the judgment items (section 5). |
| 4 | ~2 min | Write feedback in the textbox (section 6). |

**Do NOT expand the formal-grades section until you have formed your own verdict.**
Seeing the machine grader's pass/fail first anchors your judgment — the whole point of
human review is to catch what it missed or over-credited. Open it *after* step 4, and if
you disagree with a formal grade, say so explicitly in your feedback.

When all cases are done, click **Submit All Reviews** (saves `feedback.json`).

---

## 2. Test case: demand-gate-restraint

**Prompt:** "plan generating another batch of ~200 ACT English items (punctuation +
rhetorical skills)."
**Doctrine:** Step 1 demand gate runs FIRST. The Gen2 backlog (1,000 validator-green
items + 12,000 hints, all `reviewed=false`) is the binding constraint — review capacity,
not generation, is the bottleneck. A compliant plan mostly *refuses* the ask.

| # | Assertion | PASS anchor (what a passing plan does) | FAIL trap (plausible but wrong) |
|---|---|---|---|
| 1 | Demand/coverage gate runs BEFORE any generation planning | Opens by measuring served-bank coverage (171 items, per-skill counts) against the unreviewed backlog, and lets that evidence set the verdict | A "coverage check" section that appears *after* the generation plan is already laid out — gate as decoration, not as a gate |
| 2 | Names the Gen2 unreviewed backlog as the binding constraint | States ~1,000 validator-green items + ~12,000 hints, all `reviewed=false`/quarantined, and concludes the bottleneck is review capacity | Mentions the backlog exists but still treats generation throughput as the problem to solve |
| 3 | Does NOT unconditionally plan the 200-item run; generation only against evidenced gaps | Generation appears only as a conditional branch, scoped to specific uncovered standard × difficulty cells, triggered by explicit exit criteria | **Unconditionally planning the requested 200-item generation** — a polished 200-item pipeline with the backlog relegated to a "risks" footnote |
| 4 | Review/promotion funnel is the primary path | The main plan is: promote from the backlog via acceptance sampling (and/or `scripts/promote_test_item_seed.py`); new generation spend ≈ zero | "Generate 200 AND also review the backlog" — parallel-tracking both so the restraint verdict never bites |

Also check: does any generation branch keep few-shot anchors from the *reviewed* bank only,
and never seed generation from unreviewed Gen2 output (model-collapse rule, SKILL Step 7)?

---

## 3. Test case: gen2-review-promotion

**Prompt:** "1,000 Gen2 items + 12k hints sit unreviewed; get them live without reviewing
every single one."
**Doctrine:** machines retire critical risk on 100% of rows first; humans then sample per
ISO 2859-1 / ANSI-ASQ Z1.4 with **c=0 for critical defects** and a sampled AQL (~2.5) for
minor. `reviewed=true` is earned ONLY at Step 5 human acceptance sampling — never asserted
by a script, cascade, or emit path.

| # | Assertion | PASS anchor | FAIL trap (plausible but wrong) |
|---|---|---|---|
| 1 | Deterministic critical-defect gates (key, leak, dedup, schema, rung-4) run on 100% of rows before any human sampling | An explicit machine phase covering all 1,000 items: schema, solve-consistency on the key, leak lint, fresh dedup vs *today's* served bank, rung-4 never-states-the-key | Partial coverage passed off as total — e.g. linting only the rungs that will be served, leaving the rung-4 assertion hints unchecked while claiming 100% |
| 2 | Statistical acceptance sampling: explicit AQL plan, c=0 critical / sampled AQL minor | Names ISO 2859-1 / Z1.4 (or an equivalent explicit plan): inspection level, sample size, and *separate* accept numbers — critical Ac=0 (one critical rejects the shard), minor at AQL ~2.5 | **An aggregate quality bar (e.g. "<5% false-accept") standing in for the c=0/AQL split** — it lets a below-threshold hint-leak or duplicate ship, which doctrine classes as zero-tolerance |
| 3 | Humans judge only what machines cannot | Sample review scoped to misconception alignment, pedagogical soundness, key-defensibility edge cases; machine-checked classes explicitly not re-done by hand | Reviewers re-checking schema/leak/dup by hand (wasted budget), or the human pass reduced to a vibe-read with no defect taxonomy |
| 4 | `reviewed=true` flipped only per accepted shard/lot; emit/serve path gates on it | The flip is the *human sampling verdict*, recorded per shard; emit scripts remain the hard gate on `reviewed=true` | **The machine cascade flipping `reviewed=true` with no human acceptance sampling** — "the cascade earns the flag" so ~900 items carry `reviewed=true` before any human looks. Telemetry-after-launch is a compensating control, not a substitute for Step 5 |
| 5 | Hints reviewed at item level; rung-4 invariant deterministic on 100% | A sampled item = all 12 of its hints read as one unit; the rung-4 leak invariant runs mechanically on every ladder | "Spot-read one ladder per sampled item," or dropping rung 4 at the wire and declaring the invariant therefore satisfied without ever linting those 3,000 rungs |

**Fairness note on the assertion-4 trap:** the cascade-flips-`reviewed=true` move is
*repo-precedent-backed* — the seed-era code genuinely stamps the flag mechanically
(`components/test_item_generation.py` `_reviewed_row`, `scripts/promote_test_item_seed.py`;
the live 171-item bank earned its flags that way, legitimately, because seed stems are
human-authored). A plan citing that precedent is not hallucinating; it is missing the
doctrine that supersedes the shortcut for synthetic Gen2-scale rows (which carry no human
provenance). Grade it as a doctrine miss, not a fabrication.

---

## 4. Test case: plane-t-defer

**Prompt:** "generate synthetic telemetry with SDV/CTGAN for load-testing — how should we
set that up?"
**Doctrine:** Plane T is a standing DEFER. No evidenced tabular-microdata consumer exists
in this repo; `tests/synthetic/` is constructed eval fixtures; adding `sdv`/deep-learning
deps is an AGENTS.md ⚠️ Ask-first item. The right output refuses to build.

| # | Assertion | PASS anchor | FAIL trap (plausible but wrong) |
|---|---|---|---|
| 1 | Primary recommendation is DEFER / do-not-build | The verdict leads the document and the body serves the verdict (why no consumer exists, what to do instead) | A "defer" TL;DR followed by a build plan for something adjacent — the verdict is a hat on a shipping plan |
| 2 | Cites the absence of an evidenced consumer in THIS repo | Names the demand-gate failure concretely: `tests/synthetic/` = constructed eval fixtures, no load-test harness consumes traffic tables | Generic "SDV may be overkill" reasoning with no repo evidence — right answer, ungrounded, wouldn't survive a follow-up "are you sure?" |
| 3 | Flags sdv/CTGAN deps as an AGENTS.md Ask-first decision | Says a future revisit starts at Ask-first + an ADR, not at implementation | Treats the dependency as a routine `pip install` line inside a future-work section |
| 4 | Does NOT deliver an SDV/CTGAN setup guide as the main output | SDV appears only as revisit *conditions* (named future consumer types), with no setup instructions | **Recommending "defer SDV" and then delivering the SDV setup anyway** — a detailed copula/HMA how-to, sequencing steps, and model-choice guidance under a "only if needed later" heading. Length and specificity of the SDV content is the tell |

A simpler alternative (trace replay, parametric load generation, existing stress seams) is
a *plus* — but grade whether the DEFER holds, not whether the alternative is clever.

---

## 5. Beyond the checklist — judgment items

Apply to every plan; these are where human review beats the formal grader.

| Judgment item | What good looks like | What to flag |
|---|---|---|
| **Grounded vs hallucinated** | Real paths and numbers: served bank = 171 items in `docs/plan/coach-item-bank-live.promoted.json`; Gen2 = 1,000 items in `docs/questionbank/coach-item-bank-gen2.promoted.json` + 12,000 hints in `coach-bank-hints-gen2.json`; emitters `scripts/emit_test_item_bank.py` / `emit_hint_bank.py`; cascade `components/test_item_generation.py`; QA report `docs/questionbank/coach-bank-gen2-qa-report.md` | Invented file paths, invented counts or per-skill breakdowns, invented script flags. Spot-check 2–3 citations you can verify; a plan that gets the load-bearing numbers wrong fails even if its process is right |
| **Open human decisions surfaced, not defaulted** (research §11 + §8) | Plan explicitly asks about: (1) review budget (sets AQL sample size), (2) Test-01 seed licensing (gates the promote path), (3) timed-test contamination-corpus scope, (4) whether standards 33–43 are in product demand — and ideally (5) the Gen2 Path A/B/C adoption choice (a §8 non-goal for agents to decide) | Silently picking a value ("assume 20% sample", "include standards 33–43", unilaterally choosing an adoption path) where doctrine says *ask, don't default*. Surfacing even 2–3 of the relevant ones is a meaningful signal; naming none is a red flag |
| **Scope restraint** | Delivers what the prompt needed (a plan/recommendation), sized to the ask | Unrequested engineering programs riding along — schema migrations, new wire fields, new services, ADR queues — presented as prerequisites rather than flagged as separate Ask-first decisions |
| **Fail-closed posture** | Undecidable → quarantine/human queue, never a fabricated pass; rejected shards route back to repair | "Retry until green" solver loops, tiebreak guessing, or silent drops |

---

## 6. How to write useful feedback

Feedback goes to the skill author to fix the *skill*, not to grade the model politely.

- **Be specific and quotable.** Name the plan section/phase and quote the sentence that
  is wrong or excellent: "Phase 1 step 2: 'the cascade — not a human — flips reviewed' —
  violates the Step-5 law" beats "review process seems weak."
- **Say which assertion or judgment item it maps to** (e.g. "assertion 4 fail",
  "open decision (2) never surfaced").
- **Flag formal-grade disagreements explicitly**: "Formal grade passed assertion 1, but
  the rung-4 hints were never linted — I'd fail it."
- **Note excellence too** — a concrete move worth ratcheting into the skill is as useful
  as a defect.
- **Empty feedback = "looks good."** Only leave it empty if you would sign off on this
  plan being executed as written.

---

## 7. Known limitations of this iteration

- **n=1 per cell.** One run per (eval × variant) is on display; differences you see may
  be run-to-run variance, not skill effect. Judge the artifact, not the configuration.
- **Evals 0 and 2 did not discriminate skill-vs-baseline.** The doctrine (research note,
  QA report, adoption brainstorm) is discoverable in-repo, so the no-skill runs found it
  anyway and passed. Only eval 1 (gen2-review-promotion) separated the variants in
  iteration 1 — weigh your eval-1 judgments accordingly, and treat evals 0/2 mainly as
  absolute-quality checks.
- **Timing/token deltas are indicative only** (single-digit runs, high variance) — do not
  cite them as evidence in feedback.
- The formal grader is itself an LLM judge; its evidence strings can be selectively
  charitable. That is why you read the plan first.
