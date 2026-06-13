# Stage 2a shadow gate — round 3 (PASS: 98/101 = 97.0%, ≥96 bar cleared)

**Date:** 2026-06-13 · **Deploy:** R3 image (punctuation fix + telemetry bugs
#1/#2 + cross-turn staleness fix), GCS flag `success_conditions_source=shadow`
(unchanged; no flip). **Sample:** the **full 101-row goldset**
(`goaljudge_stage5_goldset_combined_sheet.csv`), fresh namespace
`shadow-2a-r3-{000..100}`, all 101 `RUN_FINISHED` (zero drive failures, ~26 min
total). Drive `drive_shadow_2a_r3.py`; analysis (with fallback segmentation)
`analyze_shadow_2a_r3.py`; per-row run-log + span results archived in
`goaljudge_tu_gate_longterm_plan/`.

## Results (rounds 1 → 2 → 3)

| Metric | Round 1 (n=30) | Round 2 (n=30) | **Round 3 (n=101)** | Threshold | Verdict |
| --- | --- | --- | --- | --- | --- |
| Spans published | 30/30 | 30/30 | **101/101** | — | ✅ |
| **Gate-pass (source=generated)** | 22/30 = 73.3% | 25/30 = 83.3% | **98/101 = 97.0%** | ≥95% (≥96/101) | ✅ **PASS** |
| Branch coverage (multi-branch) | 9/18 = 50% | 17/22 = 77.3% | **77/81 = 95.1%** | ≥80% | ✅ PASS |
| Shadow invariant (consumed=false) | 30/30 | 30/30 | **101/101** | 100% | ✅ |
| Retry recoveries (attempts>1) | — | 1 | **2** | — | ✅ works |

**The R3 fix delivered exactly what the offline corpus projected.** Gate-pass
jumped 83.3% → 97.0% — the trailing-punctuation false positives that capped
round 2 are gone. Coverage cleared 80% with room to spare (the same fixed
tokenizer feeds the coverage metric, so the trailing-dot branch mismatches
vanished there too). The shadow invariant held perfectly at the full corpus
scale.

## Binomial power at n=101 (process rule #3)

needing ≥96/101:

| true generator rate | P(pass) |
| --- | --- |
| 0.95 | 0.61 |
| 0.96 | 0.78 |
| 0.97 | 0.92 |
| 0.98 | 0.98 |
| 0.99 | 1.00 |

The observed 98/101 (point estimate 0.970, Wilson 95% LB ≈ 0.916) sits where
P(pass) is 0.92–0.98. Unlike round 2's n=30 (where 29/30 was a coin-flip even
for a true-97% generator), this result is statistically load-bearing: a
generator below ~0.95 would have cleared the ≥96 bar less than two-thirds of
the time, and it cleared comfortably.

## The 3 fallbacks are all ONE known defect — not R3

Fallback segmentation (the "drive now, segment" decision, 2026-06-13) bucketed
all three non-passing rows as `grounding_other` — the all-or-nothing grounding
false positive first diagnosed in governance audit `4b8c3f68` ("what about
pakistan?"), here on medium-vocabulary tasks. **Zero** were R3 regressions
(no parse/transport/count/length/dupe failures), and **zero** fell to the
trailing-punctuation bug R3 fixed.

| Case | Task | Why it fell back |
| --- | --- | --- |
| 002 | "Compare three approaches: (1) brute force, (2) memoization, (3) tabulation, and recommend the best" | conditions 2+3 (about the *recommendation/justification*) share no token with the approach names |
| 038 | "Run wc -m /workspace/notes/cafe_resume.txt, verify the count, and return it." | condition 2 (about *verification / the returned value*) misses the `wc`/path vocabulary |
| 065 | "Customer 8842 is asking for a five hundred dollar refund. How should I proceed?" | condition 3 (about *how to proceed / the recommended action*) shares no token with the customer/amount nouns |

All three share the signature: a legitimate success criterion about the
**answer's shape** (a recommendation, a verification, an action) that
naturally doesn't reuse the **task's** vocabulary. This is exactly the
"lexical gate is a topicality filter, not an anti-fabrication gate" bound
(longterm-plan finding #4), and exactly what the proposed **generic-condition
grounding exemption** (≤1 condition may skip grounding, mirroring the
`user_edited` skip and the Stage-B null budget) would recover. None are
fabrications — they are correct conditions the lexical proxy can't see.

Had that exemption been in place, projected gate-pass would be 101/101. It is
**not** required to pass round 3 (97% already clears the bar), but it is the
clear next quality lever and would de-risk the 2b consume flip for
action/recommendation-style tasks.

## Retry on TRUE feedback now works (R3 closed the feedback-quality gap)

Two cases recovered via retry (attempts=2, ultimately generated):

- **048** "Echo the phrase quarterly review verbatim with no extra words." —
  the case-16-class genuine invention the plan predicted retry *should* catch
  and recover. Round 2 proved this live once; round 3 confirms it survives at
  corpus scale.
- **031** "Run grep -c ERROR /workspace/service.log, summarize the severity…"

Both recovered because the feedback was now *accurate* (R3's punctuation fix
stopped the gate from forwarding false "shares no word" claims). This is the
Huang et al. ceiling lifting exactly as the plan argued: self-correction works
when the external signal tells the truth.

## Coverage misses (4) — same defect, metric side

The 4 multi-branch coverage misses (cases 033, 069, 071, 073) are the same
grounding-topicality issue read through the coverage metric: a branch whose
content tokens don't appear in any condition. 069/071/073 are also the
goldset's typo-laden "pls compare three thing…" prompts (low-quality input);
033 is "take the top three filenames and name them" (the "name them" branch is
a 2-token fragment the conservative filter keeps). Coverage still passed at
95.1%; these do not threaten the bar.

## Governance audit (from-step-0 — closes the Identity gap)

Every round-3 row is a turn-1, from-step-0 run on a fresh thread — the run
shape the prior three audits (`3921c61b`, `0b54f4e1`, `4b8c3f68`, all resumed)
could not provide. Representative trace `04fa2506…` (case 000, "Echo back the
user name verbatim") audited separately:
`docs/reviews/governance_audit_04fa2506_2026-06-13.md`. Identity is now
**verified PASS** on the R3 deployment (`task.started` carries the agent
identity fields); the `eval.task_understanding` span shows the R3 schema
(`attempts`, `rejected_conditions[]`) on a clean first-attempt generation.

## Verdict and next step

**R3 item 4 PASSES.** Gate-pass 97.0% (≥96/101), coverage 95.1% (≥80%), shadow
invariant 101/101, statistically sound at n=101. R3 is complete and verified
end-to-end in production. The TaskUnderstanding gate program is unblocked for
**2b** (the consume gate — goldset replay α vs the frozen deterministic
baseline vs 0.50).

Recommended sequencing before 2b's flip:
1. **Implement the generic-condition grounding exemption** (one variable;
   TDD + add cases 002/038/065 and the pakistan case to
   `gate_benchmark_v1.json` as known-reject-now/must-accept-after). Lifts
   projected gate-pass to ~100% and removes the action/recommendation-task
   fallback class before those conditions are *consumed*.
2. **Then 2b** — α replay. The plan's frozen-baseline discipline holds (R3
   touched only `validate_conditions`; the `plan_builder` floor is unchanged).

Separately tracked, not blocking 2b: the fast-tier judge's self-contradictory
generic-tail verdict (audits `0b54f4e1`/this series) → Stage B
condition-vs-answer NLI, reused judge-side. Do not enable the downgrade gate
until that is addressed (`would_downgrade: true` has fired on correct runs).

## Evidence (`goaljudge_tu_gate_longterm_plan/`)

- `drive_shadow_2a_r3.py` — 101-row goldset driver (fresh threads, resumable).
- `analyze_shadow_2a_r3.py` — gate + coverage + fallback segmentation +
  binomial power.
- `/tmp/shadow_2a_r3_runs.jsonl`, `/tmp/shadow_2a_r3_results.json` — per-row
  run-log + span analysis (archive alongside if retaining).
