# Axial clustering — coded_slice.jsonl (quick pass)

**Input:** `tests/fixtures/axial_coding_eval/coded_slice.jsonl` — 30 traces, all `mode=pre_submit`, 21 distinct open codes.
**Ask:** cluster the codes into failure categories, my judgment on names, quick-and-dirty.
**Outputs in this dir:**
- `clusters.json` — the buckets, each with a definition, polarity, member codes, and counts.
- `code_to_cluster.json` — flat `code → bucket-letter` map for downstream tallying.
- `NOTES.md` — this file.

## What this data is

A Socratic tutoring ("Subject-Coach") eval. A learner is working grammar/style multiple-choice
items and asks the coach for help *before submitting* (`pre_submit`). In that mode the cardinal
sin is **giving away which option is correct** — so most of the interesting codes are about *how
much the coach leaked* vs. *how well it coached without leaking*.

## Approach

1. Counted code frequencies (21 codes over 30 traces).
2. Read one representative `memo` per code to get the intended meaning — the memos are rich and
   carry the coder's leak/no-leak reasoning, so I clustered on **semantics**, not just string names.
3. Sanity-checked with a co-occurrence pass: the leak codes travel together
   (`hands-over-conclusion`+`leak-strong-implication`, `rule-naming-as-leak`), and the positive
   coaching codes travel together (`elicits-evidence`+`gives-concrete-move`+`right-sizes-the-hint`).
   That confirmed the buckets rather than inventing them.
4. Assigned **every code to exactly one bucket** (verified programmatically — no code dropped, none double-counted).

## The buckets

| # | Bucket | Polarity | Codes | Annotations |
|---|--------|----------|-------|-------------|
| A | **Answer leakage** — discloses/implies the correct option, or reasons the item down to one live option | FAILURE | 4 | 18 |
| B | **Pedagogy shortfall** — legal on leakage but doesn't teach (no comprehension check, unearned praise) | FAILURE | 2 | 6 |
| C | **Non-responsiveness** — runs its own script, ignores the state the learner disclosed | FAILURE | 1 | 2 |
| D | **Output / mechanical defects** — reply broken as an artifact (mid-word truncation) | FAILURE (env-confound suspect) | 1 | 3 |
| E | **Good coaching** — the target behaviors + minimal-pair contrast cases | POSITIVE | 13 | 61 |

**A. Answer leakage** is the headline failure family: `leak-strong-implication`, `rule-naming-as-leak`,
`hands-over-conclusion`, `overshoots-the-ask`. These are graded severities of the same axis
(name-the-rule → apply-it-to-the-item → state-the-conclusion), which is why several minimal pairs in
the memos contrast a leaking turn against a clean one on the *same item*.

## Caveats (you asked for quick-and-dirty, so read these)

- **This is descriptive clustering, not the full axial pass.** I named buckets and partitioned codes.
  I did **not** do the three-axis partition (agent-behavior / environment-confound / judge-reliability),
  mint rubric assertions, or derive judge test cases. That's what the `agentsframework-axial-coding`
  skill does; this run was the without-skill arm, so I stayed with what you asked for.
- **Bucket E lumps all 13 positive codes together.** It's a legitimate "everything that went right"
  pile and it's ~half the annotations, but it's coarse. If you care about the positive taxonomy
  (elicitation vs. hint-sizing vs. boundary-holding vs. adaptation), E should be split further.
- **`truncated-reply` (bucket D) is probably an environment confound, not a coach decision.** The memo
  says the reply cut off mid-word (`informat…`) and the coder *withheld* the actionability call because
  the next move may have been in the lost tail. Counting it as a coaching failure would poison the
  frequency stats — I flagged it "env-confound suspect" so you can exclude it if you're scoring the agent.
- **Small n.** 30 traces; the long tail (many n=1 codes) is single-occurrence and shouldn't drive
  conclusions. Counts are annotation counts (a trace can carry multiple codes), not trace counts.
- **ID churn noise:** several memos note the same item reappearing under different `question_id`s
  (`q-style-1` / `q-punc-1`, etc.). Doesn't affect the code clustering, but flags that dedup/provenance
  is messy in this slice — worth knowing before you treat item ids as stable.
