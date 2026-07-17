---
name: synthetic-data-pipeline
type: skill
description: >-
  Route ALL synthetic-data and question-bank generation work in THIS repository
  (AgentsFramework `agent` monorepo) through the stage-gated pipeline: demand
  gate → scoped generation → deterministic filter cascade → solve-consistency +
  contamination gate → human acceptance sampling → emit → monitor. Use whenever
  the user wants to generate, expand, review, promote, or serve coach bank
  content (ACT English test items, distractors, rationales, hint ladders), asks
  to "generate more items/hints", "grow the bank", "get Gen2 items reviewed",
  "flip reviewed=true", "promote the backlog", "check for duplicates/leaks",
  set up acceptance sampling, or proposes ANY synthetic data generation
  (including tabular/SDV/telemetry synthesis — this skill owns the DEFER
  decision for that too). Trigger even if the user just says "we need more
  questions" or "let's use the Gen2 items" without saying "synthetic" or
  "pipeline". The generate-or-not demand decision lives HERE even when phrased
  as "how should we approach growing the bank" (use sdd-brainstorm only for
  choosing an implementation direction for new pipeline code). Do NOT use for
  eval gold-set authoring or judge calibration (llm-eval-grounded-theory), for
  adding a continuous-eval probe or drift monitor on an LLM seam
  (agentsframework-eval-probe — Step 7 here is per-job scorecards for
  generation runs, not a registered probe), or for documentation write-ups
  (agentsframework-okf-curator).
---

# Synthetic Data Pipeline — coach question banks

Process-checklist skill distilled from
[research/Synthetic-data-pipeline-research.md](../../../research/Synthetic-data-pipeline-research.md)
(2026-07-17, workspace-grounded; full metric catalog, thresholds, and citations
live there — read it when a gate below needs its evidence or exact source). The
book-chapter background is `docs/SyntheticDataCreation/` (5 chapters).

**The one-sentence law:** generation is easy, evaluation is the moat, and
`reviewed=true` is EARNED at Step 5 — never asserted by a generator, script,
or emit path.

> **Supersession note (read before citing the code against the law).** The
> historical seed pipeline earns `reviewed=true` mechanically: the cascade in
> `components/test_item_generation.py` stamps it when its checks pass, and
> `scripts/promote_test_item_seed.py` promotes rows through that same cascade —
> the live 171-item bank got its flags this way. That was acceptable because
> seed items carry human provenance (a human authored every stem). For
> synthetic Gen2-scale batches this skill SUPERSEDES that shortcut: run the
> cascade, but its output stays `reviewed=false`; the flag is earned only by
> Step 5 human acceptance sampling. (The Gen2 QA report's "flip per item after
> review" wording is likewise superseded by the per-shard AQL flip in Step 5.)
> The flag's provenance is code-enforced, not just convention:
> `tests/architecture/test_test_item_provenance_confinement.py` (ADR-0015)
> fails any `reviewed=true` row whose `generated_by` is not the cascade's
> `<model>@<run_id>` format — a hand-stamped row is caught mechanically.

## Two planes — decide which one you are on first

- **Plane C (LLM educational content):** ACT English items, distractors,
  rationales, hint ladders. Consumer is real and evidenced: the TestItem wire
  schema (`frontend/lib/wire/engine_entities.ts`) and the live served bank
  (`scripts/emit_test_item_bank.py`). This skill's pipeline applies in full.
- **Plane T (tabular/telemetry SDV-style synthesis):** **DEFER.** No evidenced
  consumer in this repo; `tests/synthetic/` is constructed eval fixtures, not
  SDV territory. Adding `sdv`/deep-learning deps is an AGENTS.md ⚠️ Ask-first
  item. If someone asks for tabular synthesis, say DEFER, cite the missing
  consumer, and record the decision — do not build. Make the DEFER
  *falsifiable*: name the reopen conditions (privacy-regulated microdata to
  share; a table contract that can't be replayed; a named ML/analytics
  consumer) plus at most a one-line preferred method (copulas over deep nets)
  — never a setup guide; a growing "only if needed later" method section is
  the drift to watch. (Verify the no-SDV-deps claim by grepping
  `pyproject.toml`, don't assert it from memory.) For load-testing asks
  specifically: load is *requests over time*, not rows — telemetry is an
  output of load, not an input, and its IDs/timestamps must be regenerated
  procedurally anyway; what remains is low-cardinality fields a categorical
  sampler reproduces for free, which is the requests-not-rows argument in
  numbers. Point at the repo's real stress seams instead:
  `frontend/e2e/full-stack/planning-stress.spec.ts` (`pnpm test:e2e:stress`),
  `frontend/e2e/load-profile.ts`, `frontend/e2e/testing.profiles.yml` +
  `scripts/fill_stress_profile_url.py`, and
  `agent_ui_adapter/adapters/runtime/mock_runtime.py` for volume at ~zero
  model cost. Two principles when using them: drive load open-loop (a
  closed-loop driver self-throttles and flatters p99; Playwright is the
  quality-corpus tool, not the throughput tool — full T1 measured as hours
  of serial browser work), and assert on the governance pillars (Langfuse
  trace-count parity with driven requests, hash-chain validity), not just
  latency. Route any future revisit through sdd-brainstorm + an Ask-first
  ADR.

Tabular fidelity metrics (Hellinger, PSS1-3, AUROC distinguishability) do NOT
apply to prose items. Use the Plane C analogs in the gate table below.

## The pipeline (each step gates the next; fail-closed)

### Step 1 — Demand gate (restraint; always run this first)
Input: coverage of the served bank by standard × difficulty + review-capacity
estimate. Decision rule:
- Unreviewed backlog already covers the gap → **do not generate**; go to
  Step 4/5 (review funnel). This is the current state: Gen2 holds 1,000
  validator-green items + 12,000 hints (= 1,000 × 12), all `reviewed=false`
  and quarantined — the binding constraint is review capacity, not generation.
- A gap the backlog does not cover → scoped generation (Step 2) against that
  gap only — and NAME the gap quantitatively: compute served + backlog
  coverage by standard × difficulty and size N to the specific empty cells
  (e.g. d1/d5 holes), not a round number. Split the backlog into
  servable-today vs taxonomy-gated by checking which standards the syllabus
  substrate actually seeds (`docs/plan/act-english-syllabus.seed.json`,
  ADR-0022) — don't count items whose standards aren't servable as coverage.
- No evidenced gap → STOP. Generating into well-covered standards is a
  non-goal.
Probe the ask itself: is the requested N driven by measured serving telemetry
(repeat-exposure rates, served-ids exhaustion) or by round-number instinct?
Ask before sizing. And remember why restraint wins mechanically: emit
hard-gates on `reviewed=true`, so new generation moves the served bank by
ZERO until Step 5 — review throughput, not generation, is what ships items.
Prefer promoting human-provenance seed items
(`scripts/promote_test_item_seed.py`) over net-new generation — seeds reduce
model-collapse risk (and the cascade-stamped `reviewed=true` shortcut is
legitimate there, per the supersession note; synthetic rows get no such
shortcut).

### Step 2 — Scoped generation (only if Step 1 allows)
- Spec: `docs/questionbank/act-english-batch-generation-prompt.md`; schema:
  TestItem in `frontend/lib/wire/engine_entities.ts`; few-shot anchors from the
  *reviewed* bank only — never seed any generation from unreviewed Gen2 output
  (model-collapse rule, Step 7). State this in every generation branch you
  write, even conditional ones.
- Overgenerate N× target (overgenerate-and-rank is the dominant 2024–2026
  pattern), via `scripts/generate_test_items.py` / `scripts/generate_hints.py`
  as an offline governed job — never live LLM calls in CI.
- Model choice per `research/act_english_llm_ranking_for_generation.md` — do
  not re-derive the ranking.
- Record provenance (model IDs + timestamp). Constrained/schema-valid emission
  is table stakes but guarantees *format only* — schema validity ≠ defensible
  key, which is why the cascade exists.

### Step 3 — Deterministic filter cascade, 100% of rows
Two tooling layers — be honest about which is checked in:
- **Checked-in cascade** (`components/test_item_generation.py`): schema
  conformance + per-choice rationales, an answer-blind solver key gate, and
  dedup (exact normalized-stem + token-set Jaccard ≥0.85 — the `_DUP_JACCARD`
  constant, mirrored in the hint cascade) vs batch + existing bank.
  When it passes it stamps `reviewed=true` (seed-era behavior) — for
  synthetic batches keep/reset the output to `reviewed=false` (Step 5 owns
  the flag; see the supersession note). This includes REPAIR loops: re-running
  the cascade after a rejected shard re-stamps the flag, so a rejection must
  reset it again — otherwise "reject" silently leaves rows promoted.
- **Batch shard validator** (Gen2-era): enforced gates 2–7 below, but its code
  is NOT checked in — the gate list survives in
  `docs/questionbank/coach-bank-gen2-qa-report.md`. Before running Step 3 on a
  new batch, re-implement/port those checks; do not assume the checked-in
  cascade covers them.

Per-row gates (c=0 critical — any hit routes the row back to
generation/repair; never emit):
1. Schema conformance vs TestItem — 100%.
2. Exactly one underlined span per span item; exactly one key.
3. Per-choice rationales; 4-rung ladders (pump → hint → prompt → assertion) on
   exactly the 3 wrong letters; rung-4 states the rule but never the key.
4. Leak lint: no key content words, no letter references, no "no change" tell
   on key-A items — zero hits.
5. Dedup within batch AND vs served bank — zero hits. Checked-in threshold:
   exact + Jaccard ≥0.85; the Gen2 shard validator additionally applied
   Jaccard ≥0.75 / difflib ≥0.85 — hold new batches to the stricter pair.

Batch-distribution gates (deterministic and fail-closed at the BATCH level —
a failure rejects/rebalances the batch or its quota plan, not a single row;
Step 5's per-item human sample cannot even observe these, so they must pass
here):
6. Letter balance 25% ±3 (chi-square p≥0.01); NO CHANGE key rate 25–33%.
7. Coverage: per-standard quota ±10%; no target standard at 0.

Output stays `reviewed=false`.

### Step 4 — Solve-consistency + contamination gate
- Multi-sample/multi-model solver must recover exactly one key unanimously —
  use solvers from *different model families* (answer-blind), and require
  unanimous agreement especially on difficulty 4–5 items. Any disagreement →
  human-review queue as suspected key ambiguity; undecidable → quarantine
  (AP-6), never retry-until-green.
- Zero overlap vs the served bank AND any timed-test corpus; contamination
  hit → drop the row. Record provenance + timestamp.
- **Promoting a previously-generated batch (e.g. the Gen2 backlog): re-run the
  FULL Step-3 gate set — including leak lint and the rung-4
  never-states-the-key lint — against *today's* served bank.** Generation-time
  green does not carry over, and rung 4 being unrepresentable at the wire is
  not a substitute for linting it. Say so explicitly in the plan; silently
  scoping lint to servable rungs is the observed failure mode.

### Step 5 — Human acceptance sampling (the ONLY place `reviewed=true` is earned)
ISO 2859-1 / ANSI-ASQ Z1.4 attributes sampling per shard. Worked example for
the Gen2 lot: 1,000 items at General Inspection Level II → code letter J →
n=80; critical Ac=0; minor AQL 2.5 → Ac=5 / Re=6.
- **Critical defects, AQL 0 (zero tolerance) — ALL FIVE classes, not just
  wrong-key:** wrong/indefensible key, hint leaks the answer, schema break,
  duplicate of a served item, rung-4 states the key. One critical in the
  sample → reject the whole shard back to Step 3/repair, and tighten
  inspection on the next shard (Z1.4 switching rules) — a human-found critical
  is a signal to widen scrutiny, never a patch-one-item fix.
- **Minor defects, AQL 2.5, Level-II sample:** stylistic infelicity,
  weak-but-valid distractor, opener repetition.
- **An aggregate quality bar is NOT acceptance sampling.** The authoring
  playbook's "<5% audited false-accept" is the exit-ramp from per-item review
  over time, not a per-lot acceptance criterion — using it as the lot bar is a
  category error that lets a below-threshold hint-leak or duplicate ship.
  c=0 means one critical rejects the lot, full stop.
- **Never invent a sample rate.** "Review 20% per stratum" is a silent default
  of the review-budget decision; the budget (an open human decision) plus the
  Z1.4 table set n — derive, don't assume.
- Efficiency lever — and the why of the ordering: every item machines
  disqualify at Steps 3–4 is an item humans never review. Critical risk is
  retired deterministically on 100% of rows first; humans sample only what
  machines can't judge — misconception alignment, pedagogical soundness,
  defensibility edge cases.
- Hints: sample at the *item* level — a sampled item means ALL 12 of its hints
  (3 wrong-letter ladders × 4 rungs) read as one unit. "One full ladder" is 4
  rungs for a single wrong letter: a 3× under-review. The rung-4 invariant
  runs deterministically on 100% regardless (Step 4).
Sample passes → flip the shard `reviewed=true`.

### Step 6 — Emit to serve
`scripts/emit_test_item_bank.py` / `scripts/emit_hint_bank.py`. Only
`reviewed=true` rows may be emitted — both scripts die fail-closed on
unreviewed rows. Never build a parallel bank path that bypasses the flag.

**Known gap — Gen2 hints cannot flow through the current emitter.**
`emit_hint_bank.py` serves the seed-era shape only: rungs 1–3, one ladder per
question, unique on (question_id, rung). The Gen2 corpus has per-wrong-letter
ladders (3 rows per (question_id, rung)) plus rung 4, so the emitter hard-fails
on it even after review. Serving Gen2 hints requires extending the emitter +
wire schema (a `choice_letter` field; uniqueness on (question_id,
choice_letter, rung)) — an ⚠️ Ask-first/ADR change, not a quick edit. Rung 4 is
deliberately unrepresentable at the wire (ADR-0012/0014) and stays server-side
regardless.

Sequencing consequence: reviewed Gen2 *items* need not wait for the hint-emitter
ADR — but they cannot ship silently hint-less either. The FR-E1 coverage
ratchet (`ladderGaps` in `frontend/lib/adapters/engine/_hint_bank.test.ts`)
hard-fails CI for any reviewed bank item lacking reviewed rungs-1–3 hints, so
"items now, ladders later" is an explicit per-(item, rung) waiver entry in the
seed JSON with a reason — never a silent default. Don't hold accepted items
hostage to hint schema work, and don't waive ladders without saying so.

### Step 7 — Monitor / feed
Per-job scorecards (validation-error rate, label-distribution drift — the Gen2
QA report `docs/questionbank/coach-bank-gen2-qa-report.md` is the reference
shape). Field telemetry (IRT α<0.3 flags, distractor-beats-key anomalies) is a
*compensating control AFTER Step 5* — it can detect escapes and trigger
quarantine, but it never authorizes shipping: "live learners as the last
reviewer" is not a review strategy, and telemetry is never co-equal promotion
authority with the Step-5 human verdict. On any regeneration loop: re-decontaminate vs served + timed corpora
each cycle, and keep a human-authored/real anchor set in every cycle — never
seed generation N+1 purely from unreviewed generation N output (model
collapse: tails of the distribution disappear irreversibly; Shumailov et al.,
*Nature* 2024). Three failed regeneration attempts at the same gap cell →
stop and re-plan (AGENTS.md three-strikes), not a fourth variation.

## Gate quick-reference (Plane C)

| Gate | Threshold | Class |
|---|---|---|
| Schema conformance | 100% | critical |
| Single defensible key (solve-consistency) | unanimous multi-model agreement | critical |
| Hint leak lint | zero hits | critical |
| Rung-4 states the key | zero hits | critical |
| Dedup (batch + served bank) | checked-in: exact + Jaccard ≥0.85 flags; Gen2 shard validator also Jaccard ≥0.75 / difflib ≥0.85 — hold to the stricter pair | critical |
| Contamination vs timed corpus | zero overlap | critical |
| Letter balance | 25% ±3, chi-square p≥0.01 | critical (batch-level, Step 3) |
| NO CHANGE key rate | 25–33% | critical (batch-level, Step 3) |
| Coverage per standard | quota ±10%, none at 0 | critical (batch-level, Step 3) |
| Distractor misconception alignment | each maps to a named error type | human (Step 5) |
| Difficulty calibration | LLM-simulated-student IRT proxy pre-field; field IRT (flag α<0.3) once responses exist | advisory |

## Never / non-goals

- Never flip `reviewed=true` outside Step 5 acceptance sampling.
- Never treat Gen2 JSON (`docs/questionbank/coach-item-bank-gen2.promoted.json`)
  as product fuel — it is quarantined evidence until Step 5 runs.
- Never generate when the demand gate says the backlog covers the need.
- No `sdv`/deep-learning deps, no Plane T build (Ask-first + no consumer).
- No shared dashboard *service* — per-job scorecards only, until a consumer
  exists.
- Human-authored anchors stay in every regeneration cycle (anti-collapse).
- Never pick the Gen2 adoption path (Path A/B/C) unilaterally — it is an open
  product decision; this pipeline informs the review metrics only. Surface the
  choice, don't make it.

## Open human decisions (surface, don't assume)

Review budget (sets AQL sample size), Test-01 seed licensing (gates the
promote path), timed-test contamination corpus scope, and whether new
standards 33–43 are in product demand — all four are decision-shaped questions
in §11 of the research note. The Gen2 adoption path (Path A/B/C) is a fifth:
an open product decision the pipeline explicitly does not make. If a task
depends on one, ask; don't default.
