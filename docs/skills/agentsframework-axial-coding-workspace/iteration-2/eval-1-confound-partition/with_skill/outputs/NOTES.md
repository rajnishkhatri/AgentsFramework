# Axial coding — coach answer-leak rate (iteration-2, eval-1 confound-partition)

**Source:** `tests/fixtures/axial_coding_eval/coded_slice.jsonl` (30 open-coded coach traces)
**Skill:** `agentsframework-axial-coding` — loop steps 0→6.
**Question:** what fraction of traces show the coach leaking the answer, given some replies were truncated mid-sentence?

## Answer

**Leak-rate = 12/29 = 41.4%.**

The load-bearing move is the **denominator**, not the numerator. `12/29` — not `12/30`, not `12/27`.

## How I got there

### 1. Partition (axis column)
All 21 non-truncation codes are `agent-behavior`. `truncated-reply` is `environment-confound`
(a sandbox/harness cut, assigned **by cause** per the straddle rule) with its scorability
**consequence** recorded per-trace (below). Gate `axial_checker.py` → **exit 0** (partition
complete, every category testable).

### 2. What counts as a leak (numerator)
Bad-pole leak codes only: `leak-strong-implication`, `rule-naming-as-leak`,
`hands-over-conclusion`. The good-pole members of the same `answer-leak` gradient
(`preserves-the-last-step`, `right-sizes-the-hint`, `teaches-rule-no-leak`,
`declines-to-confirm-answer`) are **not** leaks — they are the no-leak rungs of the graded
dimension. 12 distinct traces carry a bad-pole leak code.

### 3. The truncation / scorability call (denominator — the sharp move)
`truncated-reply` is a confound *by cause*, but its consequence **for the leak question** is
decided per trace:

| trace | truncated? | leak code before the cut? | call |
|-------|-----------|---------------------------|------|
| `05fa7a88` | yes | **no** (cut before any leak; codes = names-specific-locus, addresses-real-confusion) | **DROP** — leak status *unknown*, not "no" → unscorable, out of denominator |
| `1b4ce6ca` | yes | **yes** — `rule-naming-as-leak` observed in the visible text | **KEEP** — leak already observed; the lost tail can't un-leak it |
| `2dfe11e7` | yes | **yes** — `leak-strong-implication` + `hands-over-conclusion` observed | **KEEP** — leak already observed |

So exactly **1** truncated trace is unscorable for this question.

- Numerator = 12 observed leaks.
- Denominator = 30 total − 1 unscorable = **29 leak-scorable traces**.
- Honest rate = `observed_leaks / leak-scorable = 12/29 = 41.4%`.

### 4. Why not the naive numbers
- `12/30 = 40.0%` — folds the 1 unscorable trace in as an implicit "no leak"; it isn't a no,
  it's unknown. Understates.
- `12/27 = 44.4%` — drops *all three* truncated traces, but two of them **leaked before the
  cut**. Over-drops → overstates.
- `12/29 = 41.4%` — drops only the trace whose leak status is genuinely unknown. Correct.

### 5. Graded split (bonus, per the skill's "report the split, not just the collapse")
Most leaks are the mildest/near-answer rungs. The **severe** rungs alone
(`leak-strong-implication` + `hands-over-conclusion`) = **6/29 = 20.7%**. A rubric author
should see both: 41% "some leakage" but only 21% "handed over / strongly implied the answer".

## Files
- `inventory.csv` — 21 codes, axis + category filled.
- `categories.csv` — 6 categories; `answer-leak` is `±` with an ordered dimension.
- `NOTES.md` — this file.

## Number to stand behind
**Leak-rate = 12/29 ≈ 41% (95% of traces scorable; 1 dropped as truncated-before-leak).**
Severe-only leak-rate = 6/29 ≈ 21%.
