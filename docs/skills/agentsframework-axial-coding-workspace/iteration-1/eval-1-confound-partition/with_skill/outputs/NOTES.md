# Leak-rate on `coded_slice.jsonl` — confound-partitioned

**Question:** what fraction of traces show the coach leaking the answer, given that
some replies are `truncated-reply` (a sandbox cutoff, not coach behavior)?

**Answer to trust: 0.414 (12/29, ~41%).**

## Runbook followed (agentsframework-axial-coding)

- **Step 0 — Inventory:** `build_coach_open_code_inventory.py` → `inventory.csv`
  (22 rows initially; 21 distinct codes after the header). 30 traces total.
- **Step 1 — Partition:** filled the `axis` column. One code is
  `environment-confound` (`truncated-reply`); everything else is `agent-behavior`.
  No `judge-reliability` codes in this slice.
- **Step 2 — Cluster:** grouped the agent-behavior codes into 5 named, testable
  categories (`categories.csv`). The leak family — `leak-strong-implication`,
  `hands-over-conclusion`, `rule-naming-as-leak`, `overshoots-the-ask` — clusters
  into **answer-leak** (negative polarity).
- **Step 3 — Gate:** `axial_checker.py` → **exit 0, emit allowed**.
- **Step 4 — Count:** `axial_matrix.py` (see below).

## The one hard rule applied to the leak count

The leak family = `{leak-strong-implication, hands-over-conclusion,
rule-naming-as-leak}` (the three codes that mean "the item is resolved to <=1 live
option for the learner"). A trace "leaks" if it carries >=1 of these.

- **12 of 30** traces carry a leak code.
- **3** traces carry `truncated-reply`: `05fa7a88`, `1b4ce6ca`, `2dfe11e7`.

`truncated-reply` is **environment-confound by cause** (a harness/streaming cutoff,
not a coach decision) — so it can't be counted as agent behavior. But the skill's
**straddle rule** says: assign by cause, decide the *consequence* per case. For the
*leak* question specifically, a truncated reply is only unscorable if the cut lands
**before** any leak is observable. Reading the memos:

| trace | truncated? | leak visible in observed text? | verdict |
|-------|-----------|-------------------------------|---------|
| `05fa7a88` | yes | **no** — memo: "actionability not codeable, next move may be in lost tail"; reply is a neutral parse that cuts at "extra informat…" before reaching any leak | **unscorable for leak** — drop from denominator |
| `1b4ce6ca` | yes | **yes** — `rule-naming-as-leak`; memo: "names the operative rule for a redundancy item, leak by rule-naming… closing guidance lost" (the leak preceded the cut) | leak verdict safe — keep |
| `2dfe11e7` | yes | **yes** — `leak-strong-implication`+`hands-over-conclusion`; memo: "leak stands on observed text alone… subject=Each declared singular… zero judgment left" | leak verdict safe — keep |

So only **1** truncated trace (`05fa7a88`) is genuinely unscorable for leak. The
other two already leaked before they were cut — excluding them would *hide real
leaks*.

## Three candidate rates

| # | treatment | count | rate |
|---|-----------|-------|------|
| A | naive — count all 30 (poisoned aggregate) | 12/30 | 0.400 |
| B | exclude ALL 3 truncated (over-correction) | 10/27 | 0.370 |
| **C** | **exclude only the 1 unscorable truncated (trust)** | **12/29** | **0.414** |

- **A is wrong** because it counts `05fa7a88` in the denominator as a clean
  "no-leak" trace when its leak status is actually unknown (the tail was cut) —
  that dilutes the rate downward with a non-observation.
- **B is wrong** in the other direction: it throws out `1b4ce6ca` and `2dfe11e7`,
  two traces where the leak was already on screen. Excluding them both shrinks the
  numerator (drops 2 real leaks) *and* the denominator, understating the leak rate.
  This is the classic "confound over-correction" — treating the cause as if it
  erased the observation.
- **C is right:** drop only the trace whose leak verdict the truncation actually
  destroyed. Numerator unchanged (12 real, observed leaks), denominator 29
  (30 minus the 1 unscorable). **12/29 = 0.414.**

## Note on `axial_matrix.py`

The bundled matrix reports `confound_only_excluded: 0` and
`agent_denominator: 30` — correct for *its* rule (FR-3 excludes only **pure**
confound traces, i.e. those with *no* agent-behavior code; all 3 truncated traces
also carry agent-behavior codes, so none is pure-confound at the trace level). That
denominator is for the category-frequency matrix, not the leak-verdict question.
The leak rate needs the finer, per-verdict scorability call above, which is
exactly the "decide the consequence per case" half of the straddle rule. Both are
consistent: the matrix drops pure confounds; the leak rate additionally drops the
one trace whose *leak verdict* is unscorable.

## Final

**Leak-rate = 0.414 (12/29, ~41%).** Round to **~41%**. If a single-decimal
headline is needed, **12 of 29 scorable traces leaked the answer.**
