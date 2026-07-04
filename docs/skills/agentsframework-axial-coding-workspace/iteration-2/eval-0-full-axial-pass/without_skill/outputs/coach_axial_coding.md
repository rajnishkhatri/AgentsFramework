# Eng-Coach Axial Coding — 30-trace slice

Stage-2 (axial) pass over `tests/fixtures/axial_coding_eval/coded_slice.jsonl`
(30 traces, all `mode=pre_submit`, model `gpt-4o`, synthetic). Turns the 21 open
codes into a partitioned, testable failure taxonomy ready for rubric design.

Artifacts in this directory:
- `inventory.csv` — 21 codes, each with `axis` + `category` filled.
- `categories.csv` — 8 categories with `binary_check` / `polarity` / `dimension`.
- `axial_matrix.json` / (counts reproduced below), `minimal_pairs.json`.
- `rubric_assertions.md`, `judge_test_cases.jsonl` — emitted downstream candidates.

Emit gate: `axial_checker.py` → **OK — partition complete, every category testable**.

---

## 1. Partition (the axes)

| axis | codes | role |
|------|-------|------|
| agent-behavior | 20 | feed the taxonomy + rubric |
| environment-confound | 1 (`truncated-reply`) | validity precondition — excluded from agent denominators |
| judge-reliability | 0 | none in this slice |

There are **no judge-reliability codes**: the memos flag corpus-generation
defects (question-id churn, template duplication) but these are *dataset* notes,
not verdict defects, and none was minted as a code. They are recorded in §6 as a
dataset caveat, not scored against the agent.

`truncated-reply` is the one **straddling** code: `environment-confound` *by
cause* (SSE/length cutoff, not a pedagogy choice) but unscorable *by
consequence*. It governs the leak **denominator** — see §3.

---

## 2. The category map

| category | axis | polarity | member codes |
|----------|------|----------|--------------|
| **answer-leak** | agent-behavior | ± | right-sizes-the-hint, preserves-the-last-step, teaches-rule-no-leak, rule-naming-as-leak, leak-strong-implication, overshoots-the-ask, hands-over-conclusion |
| **answer-begging-resistance** | agent-behavior | + | resists-answer-begging, declines-to-confirm-answer |
| **boundary-holding** | agent-behavior | + | redirects-off-topic |
| **learner-state-uptake** | agent-behavior | ± | builds-on-learner-hypothesis, ignores-learner-hypothesis, switches-strategy-when-stuck, validates-frustration |
| **elicitation-and-teachback** | agent-behavior | ± | elicits-evidence, no-teach-back |
| **confusion-and-move-uptake** | agent-behavior | + | addresses-real-confusion, gives-concrete-move, names-specific-locus |
| **praise-calibration** | agent-behavior | − | empty-praise |
| **generation-artifact** | environment-confound | − | truncated-reply |

Seven agent-behavior categories (target was ~5–6; not forced-lumped — the
learner-state and elicitation axes are genuinely distinct checks) plus the one
confound bucket.

### answer-leak is a gradient (`dimension = answer-disclosure`)

Ordered good → bad, every member code placed on a rung:

| rung | codes | boundary check |
|------|-------|----------------|
| 0 — no leak (good pole) | right-sizes-the-hint, preserves-the-last-step, teaches-rule-no-leak | every option left live, final inference left to learner |
| 1 — mild leak | rule-naming-as-leak | names the operative rule such that applying it *alone* resolves the item |
| 2 — strong leak | leak-strong-implication, overshoots-the-ask | applies the rule to the item so ~one option stays live (incl. via overshooting a scoped ask) |
| 3 — full giveaway | hands-over-conclusion | states the crux conclusion outright |

No off-gradient members; counted set == ordered set.

---

## 3. Counts (confound-excluded)

From `axial_matrix.py` — **trace counts** (prevalence), agent denominator = 30
(no confound-*only* traces, since `truncated-reply` always co-occurs with an
agent-behavior code):

| category | traces | % of 30 |
|----------|--------|---------|
| answer-leak (touches) | 21 | 70% |
| confusion-and-move-uptake | 21 | 70% |
| elicitation-and-teachback | 15 | 50% |
| learner-state-uptake | 5 | 17% |
| answer-begging-resistance | 4 | 13% |
| boundary-holding | 2 | 7% |
| praise-calibration | 1 | 3% |

> `answer-leak` reads 33 *occurrences* but 21 *traces* — quote **21/30**, not 33.

### The leak-rate (the number rubric design cares about)

Applying the straddle/denominator rule. Three traces are truncated:

- `05fa7a88` — cut **before** any leak → leak status unknown → **drop from
  denominator** (unscorable for this question).
- `1b4ce6ca`, `2dfe11e7` — leaked (`rule-naming-as-leak`, `strong-implication`)
  **before** the cut → leak observed → **keep** (numerator + denominator).

So the honest denominator is **29**, not 30 (would fold in the unscorable trace)
and not 27 (would over-drop two traces that leaked before their cut).

- **Any-leak rate = 12/29 (41%)**
- **Strong-or-worse leak (rungs 2–3: strong-implication + overshoot + hand-over) = 7/29 (24%)** — report this split; "12/29" alone hides that ~half the leaks are the mildest `rule-naming` rung.

### Leak concentrates on the adversarial strata

| stratum | traces | leaked | rate |
|---------|--------|--------|------|
| rule_naming | 3 | 3 | **100%** |
| leak_bait | 2 | 2 | **100%** |
| answer_begging | 1 | 0 | 0% |
| off_topic | 2 | 0 | 0% |
| breadth | 22 | 7 | 32% |

**Every rule-naming and leak-bait probe succeeded in extracting a leak.** This is
the headline agent failure: the coach cannot hold the line against a learner who
asks for "just the rule name" or "eliminate one choice until one is left."

---

## 4. Minimal pairs (relational gold)

All four pairs below diverge on **agent-behavior** codes (not just the confound
code), so all are genuine gold. Same normalized prompt, divergent behavior →
the failure is *contingent*, not forced by the input.

1. **"give me a hint but a small one"** — `0b9d1f60` / `2f19d809` / `3ce9e4a8`.
   All three stay no-leak, but only two are coded `right-sizes-the-hint`; the
   third is a bare concrete move. Shows the good pole is reachable on this
   prompt — a leak here would be inexcusable.

2. **"if I had to explain this sentence to a friend, I honestly couldn't"** —
   `0d3f493f` (leak-strong-implication + hands-over-conclusion) vs `104ba6ae`
   (rule-naming-as-leak, milder). **Same learner Feynman moment, two different
   leak grades** — the crux was declared outright in one, only rule-named in the
   other. Rung-2 vs rung-1 boundary exemplar for the gradient.

3. **"if I swap the underlined part for each choice, what should I be checking?"**
   — `1b4ce6ca` vs `3108cc62`. Both `rule-naming-as-leak` + `gives-concrete-move`;
   they differ **only** on `truncated-reply`. Per the v1 axis-blind note this is
   **not** minimal-pair gold (divergence is confound-only) — flagged and excluded
   from the "contingent failure" claim.

4. **"I think it's between B and C"** — `1e28adc2` (**ignores**-learner-hypothesis)
   vs `2b4cf8ce` (**builds-on**-learner-hypothesis). The sharpest pair: identical
   learner disclosure, one coach restarts a canned script, the other works inside
   the B/C shortlist. This is the `learner-state-uptake` polarity flip in a single
   controlled contrast — prime judge test case.

---

## 5. Template economy (cross-cut)

Canned response templates recur nearly verbatim across different prompts and
question-ids — the coach is often unconditioned on the learner's utterance:

| template | traces | note |
|----------|--------|------|
| cover-the-phrase "of the runners" | 3 (`0b9d1f60`,`102f9f57`,`1e28adc2`) | verbatim; in `1e28adc2` fired despite a disclosed B/C hypothesis → the `ignores-learner-hypothesis` pole |
| return-conveys-direction leader | 5 (`00eda7de`,`0f24f449`,`2f19d809`,`3f79f49c`,`48129021`) | same crux-leader; grades from no-leak probe to full hand-over depending on phrasing |
| relation-classification (time/contrast/example) | 4 (`19b3d5ee`,`34fd7166`,`3ce9e4a8`,`3fec3834`) | transition-item menu, reused across q-org/q-rhet/q-style |
| who-was-walking probe | 2 (`1b21049c`,`2da8c5cd`) | dangling-modifier meaning probe |
| off-topic redirect | 2 (`33a9fcfa`,`499a36d1`) | clean boundary hold |

Rubric implication: template reuse is *not itself* a leak, but the same template
lands on the right or wrong side of the leak line depending on how much of the
item it applies — the cover-phrase and return-crux families are the ones to
watch.

---

## 6. Dataset caveats (not scored against the agent)

- **Question-id churn.** The same item content appears under multiple
  `question_id`s (e.g. the museum-1974 item under q-rhet-1 / q-style-1 / q-org-1;
  q-rhet-1 carries ≥4 distinct items). **id→item mapping is unreliable**, which
  weakens any leak call that depends on the (unseen) option set. All leak calls
  here rest on reply structure, not id labels.
- **Options never in the trace.** Leak grading assumes the reply's rule
  application resolves the item; where options are unseen this is a hedge, noted
  per-trace in the source memos.
- These are corpus-generation issues to fix upstream; they do **not** move the
  agent denominator.
