# Axial clustering — coded_slice.jsonl (NOTES)

**Task as asked:** "just cluster the codes into failure categories — you pick good
names, quick and dirty." So this is a Stage-2 *clustering* pass, stopped at the
taxonomy. I did **not** do selective coding (no core-category storyline) or emit a
full rubric — the user asked for buckets, not a gold set.

## Inputs
- Fixture: `tests/fixtures/axial_coding_eval/coded_slice.jsonl` — **30 traces**, all
  `pre_submit` mode, English-tutoring "coach" replies. **21 distinct open codes.**

## What I ran (the skill runbook, steps 0–4)
1. **Inventory** — `scripts/build_coach_open_code_inventory.py` → `inventory.csv`
   (one row per code, blank `axis`/`category`).
2. **Partition** — filled the `axis` column. 20 codes are **agent-behavior**;
   `truncated-reply` is the one **environment-confound** (harness cut the reply mid-
   word). No **judge-reliability** codes in this slice.
3. **Cluster** — filled `category` and wrote `categories.csv` (with `polarity`,
   `binary_check`, `dimension`). Five buckets (below).
4. **Gate** — `axial_checker.py` → **exit 0** ("emit allowed"). Every code carries an
   axis; every category has a testable check.
5. **Count + pairs** — `axial_matrix.py` (trace counts) + `axial_minimal_pairs.py`.

## The five buckets (my names — the "you pick" part)
| Category | Axis | Polarity | What it captures |
|---|---|---|---|
| **answer-handling** | agent-behavior | ± | How much of the conclusion the reply hands over. This is the money bucket — a graded **leak-severity** gradient, rungs 0→3. |
| **scaffolding-quality** | agent-behavior | + | Does the reply give a concrete, right-sized next move (specific locus + doable action) vs. a vague nudge. |
| **learner-responsiveness** | agent-behavior | ± | Does it engage *this* learner's stated hypothesis / confusion, or ignore it / skip the teach-back. |
| **boundary-holding** | agent-behavior | ± | Under pressure (answer-begging, off-topic, frustration) does it hold the coaching frame without empty praise. |
| **sandbox-artifact** | environment-confound | − | Reply truncated by the harness → behavior unscorable. Kept out of agent quality judgments. |

`answer-handling` is marked `±` and given a **leak-severity dimension** because its
member codes form an ordered gradient, not a flat pass/fail:
- **Rung 0 — no leak:** `teaches-rule-no-leak`, `preserves-the-last-step`,
  `declines-to-confirm-answer` (the good pole).
- **Rung 1 — rule-named-only:** `rule-naming-as-leak` (names the rule, leaves the
  item application to the learner).
- **Rung 2 — strong implication:** `leak-strong-implication`, `overshoots-the-ask`
  (applies the rule to *this* item, ~1 option left live).
- **Rung 3 — hand-over:** `hands-over-conclusion` (states / all-but-states the answer).

## Numbers (trace counts, N=30; quote these, not occurrence counts)
- answer-handling touches **21/30** traces; scaffolding-quality **21/30**;
  learner-responsiveness **14/30**; boundary-holding **6/30**.
- **Leak rate, graded:** any leak (rungs 1–3) = **12/30 (40%)**; but the mild
  rung-1 "rule-named-only" is half of that — the **strong leaks that actually cost
  the learner the last step (rungs 2–3) = 6/30 (20%)**. Report the split, not the
  collapsed 40%; the 20% is the number a rubric author cares about.
- **learner-responsiveness misses** (ignores-hypothesis OR no-teach-back) = 7/30.

## Denominator / confound call
`truncated-reply` is `environment-confound` **by cause**. But all 3 truncated traces
(`05fa7a…`, `1b4ce6…`, `2dfe11…`) *also* carry agent-behavior codes that were
observable **before** the cut, so none is confound-only. `axial_matrix` reports
`confound_only_excluded: 0` — the agent denominator honestly stays **30**, not 27.
(If you later score a question that the truncation makes unknowable for a given
trace, drop *that* trace from *that* question's denominator — per-question, not
globally.)

## Minimal pairs worth a look (agent-behavior divergence, not confound noise)
- **"i think it's between b and c"** — one reply `builds-on-learner-hypothesis`, the
  twin `ignores-learner-hypothesis`. Same prompt, opposite responsiveness → the miss
  is contingent, not forced. Good gold pair.
- **"if i had to explain this sentence to a friend, i honestly couldn't"** — one reply
  `hands-over-conclusion` (rung 3), the twin only `rule-naming-as-leak` (rung 1).
  Same prompt, two rungs apart on leak-severity.

## Caveats I'd flag to the user
- **Quick-and-dirty as requested:** category *names and boundaries are my judgment*,
  not red-teamed. `overshoots-the-ask` (I put it at rung 2) and `empty-praise` (I put
  it in boundary-holding, not answer-handling) are the two placements I'd re-examine
  first.
- **Small slice (30 traces, all one mode):** counts are directional, not statistically
  load-bearing. `switches-strategy-when-stuck`, `validates-frustration`, `empty-praise`
  each appear once — singleton codes, treat as anecdotes.
- **Dataset flag inherited from Stage 1:** a memo on trace `06c2aa…` notes the
  "redundancy" framing recurs across 5/6 question_ids — possible item-bank conflation
  by the synthetic generator. Not a coach failure; worth an item-bank check before
  trusting per-question breakdowns.
- No judge-reliability codes here, so this pass says nothing about verdict drift.
