# Coach failure taxonomy — coded_slice.jsonl (N=30, 21 codes)

Five categories. Four agent-behavior + one environment-confound. Gate: `axial_checker.py` = green.

## Category map (category → axis → member codes → polarity)

### 1. answer-handling  ·  agent-behavior  ·  ±  ·  dimension = leak-severity
The core bucket: how much of the conclusion the reply gives away. Ordered gradient.

| Rung | Codes | Traces |
|---|---|---|
| 0 · no leak (good pole) | `teaches-rule-no-leak`, `preserves-the-last-step`, `declines-to-confirm-answer` | 4 / 4 / 1 |
| 1 · rule-named-only | `rule-naming-as-leak` | 6 |
| 2 · strong implication | `leak-strong-implication`, `overshoots-the-ask` | 6 / 2 |
| 3 · hand-over (bad pole) | `hands-over-conclusion` | 4 |

- Prevalence: **21/30** traces touch answer-handling.
- **Any leak (rungs 1–3): 12/30 (40%).  Strong leak (rungs 2–3): 6/30 (20%).**
  Report both — the 40% is dominated by the mild rung-1 naming; the 20% is the
  learner-cost number.

### 2. scaffolding-quality  ·  agent-behavior  ·  +
Does the reply give a concrete, right-sized next move?
- Codes: `gives-concrete-move` (16), `elicits-evidence` (10), `right-sizes-the-hint` (7), `names-specific-locus` (4).
- Prevalence: **21/30** traces. This is the coach's dominant *strength* on this slice.

### 3. learner-responsiveness  ·  agent-behavior  ·  ±
Does the reply engage *this* learner's stated hypothesis / confusion?
- Good: `addresses-real-confusion` (7), `builds-on-learner-hypothesis` (1), `switches-strategy-when-stuck` (1).
- Bad: `ignores-learner-hypothesis` (2), `no-teach-back` (5).
- Prevalence: **14/30** traces; misses (ignore OR no-teach-back) = **7/30**.

### 4. boundary-holding  ·  agent-behavior  ·  ±
Under pressure, hold the coaching frame without caving or padding.
- Good: `resists-answer-begging` (3), `redirects-off-topic` (2), `validates-frustration` (1).
- Bad: `empty-praise` (1).
- Prevalence: **6/30** traces (only fires when a prompt applies pressure).

### 5. sandbox-artifact  ·  environment-confound  ·  −
- Code: `truncated-reply` (3). Harness cut the reply; behavior unscorable *past the cut*.
- **Not** a coach failure. `confound_only_excluded = 0` (all 3 also show pre-cut
  agent behavior), so the agent denominator stays 30.

## Testable checks (from categories.csv)
- **answer-handling** (per rung): Rung0 teaches/points without narrowing options? ·
  Rung1 names rule but leaves item application to learner? · Rung2 applies rule to
  THIS item leaving ~1 option live? · Rung3 states / all-but-states the correct choice?
- **scaffolding-quality:** concrete right-sized next move (specific locus + doable action) vs. vague nudge?
- **learner-responsiveness:** engages what THIS learner said (build on / address / redirect) vs. ignores / skips teach-back?
- **boundary-holding:** holds the coaching frame under pressure without empty praise?
- **sandbox-artifact:** cut off by the harness → unscorable (exclude from agent denominators)?

## Minimal pairs (agent-behavior divergence)
- `"i think it's between b and c"` — `builds-on-learner-hypothesis` vs.
  `ignores-learner-hypothesis` (learner-responsiveness contingency).
- `"if i had to explain this sentence to a friend, i honestly couldn't"` —
  `hands-over-conclusion` (rung 3) vs. `rule-naming-as-leak` (rung 1) — two rungs
  apart on leak-severity, same prompt.
