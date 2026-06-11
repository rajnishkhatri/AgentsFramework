# GoalJudge Stage 5 — Post-α Coverage Check

> **Run date:** 2026-06-11
> **Input:** [`goaljudge_stage5_goldset_full_sheet.csv`](goaljudge_stage5_goldset_full_sheet.csv) (79 rows, frozen labels)
> **Gate:** Phase 5-G — does the **labeling pass** collapse failure-mode coverage on any D1 or D5 cell?
> **Status:** **PASS — no labeling collapse detected**

---

## What this gate actually checks

The Tier 3 plumbing locks `D1_FLOORS` (planning_depth) and `D5_FLOORS` (tool_cluster)
at sizes calibrated for the **combined ~250-row Stage 5 goldset** (sum of D1 floors:
220; sum of D5 floors: 180). The fresh 79-row corpus is **one sourcing stream** —
the other streams (pilot 22-row, future production-traffic sampling) fill the
floor counts at Phase 6 assembly.

Phase 5-G therefore asks a different question than "are the floors met":

> **Within the rows we DO have, did human labeling collapse any cell to zero
> `goal_met=false` rows?**

A cell with zero failures after labeling is a silent eval-coverage hole — Stage 6
can't measure GoalJudge precision/recall on a cluster with no labeled failures.
That's the failure mode this gate exists to catch.

---

## Failure-share rate per cell (the labeling-collapse signal)

### D1 — planning_depth

| depth | total | false | failure rate | status |
|---|---|---|---|---|
| L0 | 16 | 12 | 75.0 % | OK |
| L1 | 38 | 29 | 76.3 % | OK |
| L2 | 25 | 24 | 96.0 % | OK |

Every planning depth lands at ≥ 75 % `false` — no collapse. L2's 96 % is the highest:
the L2 cells in this corpus are deliberately heavy on multi-step compose / wrong-tool /
impossible — the L2 routing is what the agent's planner-truncation regression risks
silently fail at, so over-representing failures on L2 is by design.

### D5 — tool_cluster

| cluster | total | false | failure rate | status |
|---|---|---|---|---|
| blocked-tool | 4 | 4 | **100 %** | OK |
| compose | 25 | 24 | 96.0 % | OK |
| file-only | 14 | 12 | 85.7 % | OK |
| no-tool | 7 | 5 | 71.4 % | OK |
| request_approval | 4 | 3 | 75.0 % | OK |
| shell-bound | 11 | 8 | 72.7 % | OK |
| web-bound | 8 | 5 | 62.5 % | OK |
| wrong-tool | 6 | 4 | 66.7 % | OK |

Every cluster lands at ≥ 62.5 % `false`. The lowest rate (`web-bound` at 62.5 %)
reflects the cluster's authoring: a real fraction of web-search prompts are
straightforwardly answerable. The 5 / 3 / 4 false counts on `no-tool` /
`request_approval` / `blocked-tool` are sufficient to support ≥ 1 `failure_mode`
sample per code in each cluster — Stage 6's binomial-CI per-code estimates need
this, and it's intact.

### Stratum (sanity check)

| stratum | total | false | failure rate |
|---|---|---|---|
| representative | 32 | 23 | 71.9 % |
| boundary | 23 | 19 | 82.6 % |
| edge | 16 | 15 | 93.8 % |
| impossible | 8 | 8 | **100 %** |

The stratum gradient is exactly what the Phase 4 authoring brief targeted:
representative is the most ambiguous (71.9 % false reflects rubric-edge calls,
not labeling noise); impossible is unanimous-false by construction.

---

## Tier 3 floor counts — gap by design

If you run `evaluate_goldset_post_alpha_coverage` with the strict
`adjudicated_goal_met=="false"` filter (the function as-shipped) on this 79-row
sheet, you will see large gaps:

```
total items considered: 17     (adjudicated-false only; agreement rows dropped)
L0 gap: 58 / 60 (only 2 met)
L1 gap: 92 / 100 (only 8 met)
L2 gap: 53 / 60 (only 7 met)
```

This is **expected**. Two things are happening:

1. The function only counts rows where `adjudicated_goal_met` is canonically
   `"false"` — which only fires on **disagreement rows the adjudicator routed
   to false** (17 of the 22 disagreements). It does NOT count the 48
   agreement rows where `r1==r2=="false"`, because those rows leave
   `adjudicated_goal_met` blank by design (per Rule 5: don't write adjudicated
   columns on agreement rows).
2. Even if we count all 65 frozen-false rows (incl. agreement-row implicit
   false), the floors expect 220 D1 / 180 D5 — a ~250-row goldset. The fresh
   corpus alone is 79.

Both gaps close at **Phase 6 assembly** when the fresh-corpus rows merge with
the pilot stream and future production sampling. The strict filter is the
right Phase 6 check, not the Phase 5 check.

---

## Verdict

**PASS** — no labeling collapse. All 8 D5 clusters and all 3 D1 depths have ≥ 3
`false` rows. Stage 6 will be able to compute per-cluster failure-mode estimates
on every cell in this corpus.

**Phase 6 handoff is unblocked from a labeling-quality standpoint.** The remaining
floor gaps are a sourcing-quantity question, not a labeling-quality question.

---

## Next steps

1. **Protocol update** — append a `request_approval` clause to Rule 7 of the
   [full-set labeling protocol](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md),
   documenting the GJ-F-088 / GJ-F-090 reconciliation. This is the only durable
   rubric change the round-1 process surfaced.
2. **Phase 6 — assemble** the goldset manifest from the frozen full sheet via
   `assemble_goaljudge_goldset.py`. The script's `assert_assembly_invariants`
   will enforce the D1/D5 floors at the **combined** level (fresh + pilot + …),
   not on this sheet alone.
3. **Future sourcing waves** — when production traffic sampling lands, the
   incremental rows merge into the same sheet schema and re-run through Phase 5
   (label + α + adjudicate + post-α coverage check), then Phase 6 re-freezes.
