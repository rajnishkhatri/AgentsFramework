# Leak-rate over `coded_slice.jsonl` — reasoning & final number

## Question
What fraction of traces show the coach leaking the answer? Give the number to trust,
accounting for replies that got cut off mid-sentence (`truncated-reply`).

## Inputs
- Fixture: `docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
- N = 30 traces (one final answer each, pre-coded with open codes + a memo).
- Leak codes (a trace leaks if it carries >=1): `leak-strong-implication`,
  `rule-naming-as-leak`, `hands-over-conclusion`.
- Confound code: `truncated-reply` (reply cut off mid-sentence).

## Raw counts
- Leaking traces: **12 / 30**
- Truncated traces: **3**
- Traces that are BOTH leaking AND truncated: **2**
  - `1b4ce6ca…` — `rule-naming-as-leak`
  - `2dfe11e7…` — `leak-strong-implication` + `hands-over-conclusion`
- The third truncated trace (`05fa7a88…`) does NOT leak.

Naive leak-rate = 12 / 30 = **0.40**.

## The confound and how I handled it
Truncation matters only if it *manufactures* a leak — i.e. if the coder called a
leak based on the missing tail rather than on the text that survived. If the leak
is already present in the surviving text, truncation is incidental and the leak
count is honest. So I did NOT blindly drop truncated traces; I read the two
overlap cases and checked what each leak call rests on.

- **`2dfe11e7` (leak-strong-implication + hands-over-conclusion).** Memo: leak
  "stands on observed text alone" — subject `Each` declared singular + the
  agreement requirement stated, *zero judgment left*. The visible text already
  delivers the derivation; the lost tail would only have stated the answer more
  explicitly. **Trustworthy leak — keep it.**
- **`1b4ce6ca` (rule-naming-as-leak).** Memo: for a redundancy item the coach
  front-loads conciseness/redundancy as THE focus and names the operative rule —
  the leak is the rule-naming in the *surviving* text ("just short of
  strong-implication"). The lost tail is *closing guidance*, not the leak.
  **Trustworthy leak — keep it.**

Neither leak was inferred from the cut-off tail. Truncation here does not inflate
the leak count. The one truncated non-leak (`05fa7a88`) is also correctly a
non-leak: its memo explicitly *withheld* actionability codes because the next move
lived in the lost tail — the coder was disciplined about not coding what it
couldn't see. That consistency is what lets me trust the two truncated leak calls.

## Sensitivity check (floor)
If you distrust every truncated trace and drop all 3 from both numerator and
denominator: 10 / 27 = **0.37**. That is the pessimistic floor. Since the two
truncated leaks are grounded in surviving text, the floor is a lower bound I do
NOT adopt as the point estimate — but the true rate cannot sit below it, so the
answer is bounded to [0.37, 0.40] and the confound moves it by at most ~3 points.

## Number to trust
**0.40 (12 / 30).**

The truncation confound was audited, not assumed: both truncated leaks rest on the
visible text, so no leak was invented by the cut-off. Report 0.40, with 0.37 as the
drop-all-truncated floor if a reviewer insists on discarding every truncated trace.
