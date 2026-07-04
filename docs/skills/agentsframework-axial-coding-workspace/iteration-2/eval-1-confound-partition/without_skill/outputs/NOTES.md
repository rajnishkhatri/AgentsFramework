# Leak-rate — confound partition (coded_slice.jsonl, N=30)

**The number to trust: leak-rate = 12/29 = 41.4%.**

Reported alongside the graded split (below), because a single collapsed rate
hides that half the leaks are the mildest rung.

---

## What was asked

Fraction of coach traces that leak the answer. Leak codes:
`leak-strong-implication`, `rule-naming-as-leak`, `hands-over-conclusion`.
Complication: 3 replies were truncated mid-generation (`truncated-reply`), so
the denominator is not obvious.

## Method (Stage-2 axial pass, confound partition)

Followed the `agentsframework-axial-coding` skill. The load-bearing rule here is
the **straddle rule for the denominator**: a truncated reply is
`environment-confound` *by cause*, but whether it counts *for the leak question*
is decided per-trace from the coder's memo:

- leaked **before** the cut → leak is observed → **keep** (numerator + denom);
- cut off **before** any leak → leak status **unknown**, not "no" → **drop from
  the denominator** (unscorable for this question).

So the honest rate is `observed_leaks / leak-scorable-traces`, never
`leaks / all-traces` and never `leaks / (all − every-truncated)`.

### Gate

Built the code inventory (`inventory.csv`, 22 codes — 21 agent-behavior across
11 categories + `truncated-reply` as `environment-confound`), wrote
`categories.csv` (12 categories, each with a binary check; `answer-leak` carries
the ordered dimension `rule-naming-as-leak < leak-strong-implication <
hands-over-conclusion`), and passed `axial_checker.py` (exit 0) **before**
emitting any count. `axial_matrix.py` confirms `answer-leak` touches **12
traces** (trace count; the 16 *occurrence* count is inflated by gradient codes
co-occurring on the same trace — do not quote 16/30).

## The three truncated traces, adjudicated from their memos

| trace | leak code? | memo verdict | scorable? |
|-------|-----------|--------------|-----------|
| `05fa7a88` | none | "Considered rule-naming-as-leak … but item is q-rhet-1 (rhetoric) … next move may be in lost tail" — leak status **unknown** | **DROP** (unscorable) |
| `1b4ce6ca` | `rule-naming-as-leak` | "names the operative rule for a redundancy item, **leak by rule-naming**" — minted on observed text, tail only lost *closing* guidance | KEEP |
| `2dfe11e7` | `leak-strong-implication`, `hands-over-conclusion` | "**leak stands on observed text alone** … subject=Each declared singular + agreement requirement stated, **zero judgment left**" | KEEP |

Exactly **one** trace (`05fa7a88`) is unscorable → denominator = 30 − 1 = **29**.
Both truncated-but-leaked traces stay in the numerator on their observed text.

## The number, and the two wrong numbers it beats

| computation | value | why it's wrong / right |
|-------------|-------|------------------------|
| `leaks / all-traces` | 12/30 = 40.0% | folds the unscorable `05fa7a88` into the denom as an implicit "no leak" |
| `leaks / (all − truncated)` | 10/27 = 37.0% | over-drops `1b4ce6ca` + `2dfe11e7`, which **leaked before their cut** |
| **`observed_leaks / leak-scorable`** | **12/29 = 41.4%** | **correct** — drops only the genuinely unscorable trace |

## Graded split (report this too)

`answer-leak` is a gradient; the collapsed 41.4% hides the shape:

- **rule-naming-only** (mildest rung): 6/29 = 20.7%
- **strong-implication or hand-over-conclusion** (the hard leaks): 6/29 = 20.7%

So ~half of all leaks are the mild "named the operative rule" rung; the other
half strongly imply or hand over the answer. A rubric author should treat these
differently — worth more than the single 41.4% figure.

## Contingency check (minimal pair)

Prompt "give me a hint but a small one" appears on multiple traces: most get
clean calibrated hints (`right-sizes-the-hint`, `preserves-the-last-step`),
while another trace on the same-family prompt leaks. The leak is **contingent on
the coach's move, not forced by the prompt** — it's a real, fixable behavior.

## Files

- `inventory.csv` — 22 codes, axis + category filled
- `categories.csv` — 12 categories, gate-passing
- `leak_rate.txt` — the computation + the two rejected denominators
- `minimal_pairs.txt` — axis-blind pair output (filter by agent-behavior divergence)
