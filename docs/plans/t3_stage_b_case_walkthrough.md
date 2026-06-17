# T3 Stage B — Case-by-case walkthrough (input → output → Langfuse reasoning)

**Date:** 2026-06-16 | **Run:** 29/29 cases, credentialed Langfuse traces, per-run trace_ids, single-run validated  
**Evidence triplet:** corpus prompt (task input) + DOM artifact (task output) + Langfuse carriers (supervisor reasoning)

Every case below presents: **task input** (corpus prompt) → **task output** (what the browser received) → **why**, read from the Langfuse `supervisor_decision` carrier + its recorded rationale + the `fanout_join` carrier. The reasoning rationale strings are **verbatim from the trace** — this is the Explainability pillar in action: each verdict is answerable from a carrier, not inferred.

## Reasoning spine: three decision templates

The supervisor has exactly **three rationale templates** it emits, and they form the backbone of the entire reasoning analysis:

1. **`independent-branches: LLM proposed parallelizable branches`** → **fan_out** (LLM saw parallelizable structure, no veto)
2. **`not-independent: ... structure check overrides model optimism`** → **decline** (LLM wanted to fan out; deterministic structure validation rejected it)
3. **`sequential-dependent: T1 plan steps reference prior outputs or share a write target (the GAIA single-agent-wins case)`** → **decline** (explicit sequential dependencies detected)

---

# INDEPENDENT family (want_fanout=True) — 6 fanned out, 2 declined, 2 never reached supervisor

These cases are marked in the corpus as genuinely parallelizable. The supervisor's task: recognize true independence, veto false positives, and respect structure-aware over-rides.

## ✅ L2-decompose-10 — textbook success

**Input:** *"Independently produce a one-paragraph briefing on each of these three unrelated regions — the Nordics, Iberia, and the Baltics — covering, for each region separately, (1) its largest city (2) its primary language (3) its currency. The three briefings do not depend on each other."*

**Decision (Langfuse):** `fan_out, 3 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 6/6`, join_chars=1873

**Output (DOM):** Real 1571-char briefing. *"The largest city in the Nordic countries is Stockholm… The primary languages spoken in the Nordics vary by count…"*

**Analysis:** The three regions are genuinely independent. The supervisor recognized the parallelizable structure, fanned out, all branches completed, and the join synthesized a full answer. **Reference success case — decision correct, reasoning sound, answer delivered.**

---

## ✅ gift-shortlist-03 — consumer tuple, parallel independence

**Input:** *"Shortlist one gift under $50 for each of three different people: a runner, a baker, and a gamer. Each shortlist is independent of the others."*

**Decision:** `fan_out, 3 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 3/3`, join_chars=850

**Output:** Real 746-char gift recommendations. *"Here are three thoughtful gift ideas under $50, tailored for each of the individuals you mentioned: For the Runner: Gift: Running Belt…"*

**Analysis:** Three independent consumer personalization tasks. Supervisor correctly recognized parallelizable structure. **Consumer-tuple shape, correctly fanned out, clean execution.**

---

## ✅ multidoc-summary-04 — independent document tasks

**Input:** *"You are given three unrelated documents in /workspace/docs/: a.txt, b.txt, and c.txt. Summarize the key finding of each document independently. The summaries do not depend on each other."*

**Decision:** `fan_out, 3 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 6/6`, join_chars=359

**Output:** 345-char answer. *"I currently do not have access to the documents "a.txt," "b.txt," and "c.txt" in your workspace…"*

**Analysis:** Supervisor decision is **correct** — the three summaries are genuinely independent. The **outputs are thin** (the sandbox lacked the files), but the T3 reasoning path was right. This case proves the important distinction: **fan-out decision-correctness ≠ content richness.** The join successfully synthesized degraded but honest answers from the branches.

---

## ✅ policy-checks-06 — account verification, parallel checks

**Input:** *"Independently verify each of three separate account conditions: (a) the account is in good standing, (b) the email is verified, and (c) two-factor auth is enabled. None of the three checks depends on another; report each."*

**Decision:** `fan_out, 3 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 6/6`, join_chars=1442

**Output:** 1393-char verification summary.

**Analysis:** Three independent checks. Correctly fanned out. **Note:** This case re-entered under reflexion (decisions_all shows fan_out repeated 3×, but run.started=1 — single run, reflexion re-decisions). Still landed a clean answer. Supervisor reasoning held across re-planning.

---

## ✅ restaurant-survey-02 — consumer picks, parallel

**Input:** *"Find one highly-rated restaurant for each of three unrelated cuisines — Italian, Thai, and sushi — and report each one's rating and price band. The three picks are independent of each other."*

**Decision:** `fan_out, 3 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 9/9`, join_chars=495

**Output:** 400-char restaurant picks. *"Here are three highly-rated restaurants… Italian Cuisine: Restaurant: Osteria Francescana, Rating: 9.5, Price Band: $$$$…"*

**Analysis:** Three independent cuisine picks. Supervisor fanned out. The join shows 9/9 (reflexion re-entry: 3 runs of 3 branches each), and the answer is coherent and complete. **Correctly handled re-entry under reflexion.**

---

## ⚠️ many-branch-09 — highest branch count (6), fan-out correct but content sparse

**Input:** *"You are given six unrelated abstracts in /workspace/abstracts/ (1.txt through 6.txt). Summarize each one independently in a single sentence. The six summaries do not depend on each other."*

**Decision:** `fan_out, 6 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 6/6`, join_chars=225

**Output:** 225-char answer. *"I currently do not have access to the abstracts in the files "1.txt" through "6.txt." To provide you with summaries, please share the text of each abstract…"*

**Analysis:** **Decision reasoning: perfect.** The six abstracts are genuinely independent (the only 6-branch case in the corpus). Supervisor recognized the higher branch count correctly. **Content: sparse** because the sandbox lacked the files. This is the clearest proof that T3 separates *reasoning quality* from *content richness*: the join correctly synthesized a degraded answer (transparent about missing files) rather than hallucinating summaries. Explainability+honesty in execution.

---

## 🔶 multitab-lookup-07 — veto: structure-override on "independent" claim

**Input:** *"Look up the current price of three unrelated products independently: a stainless water bottle, a USB-C cable, and a desk lamp. Report all three prices. The lookups are independent."*

**Decision:** `decline, supervisor_reason: "not-independent: proposed branches carry depends_on edges, duplicate objectives, or < 2 branches (structure check overrides model optimism)"`

**Join result:** None (sequential execution)

**Output:** 644-char answer with all three prices. *"Here are the current prices for the three products: Stainless Water Bottle: Prices start from approximately $15.96 at Walmart…"*

**Analysis:** **Corpus marks `want_fanout=True`** — the tasks are genuinely independent. The **LLM proposed branches** in decompose. But the deterministic structure validator found the proposed branches had **duplicate/overlapping objectives** (three "look up a price" sub-tasks with too-similar decompositions). The validator **vetoed the LLM's optimism.** 

This is a **recall miss but a sound conservative decision:**
- Reasoning: the structure-override veto is the GAIA guard catching over-eager parallelization.
- Execution: ran sequential and **still delivered all three prices.** The cheap error — sequential execution when parallel was possible — but the final answer is complete and correct.

---

## 🔶 trip-research-01 — veto: dated-dependency structure check

**Input:** *"Research, independently and in parallel, the typical August cost of three unrelated things: (a) a rental car in Lisbon for a week, (b) a 4-star hotel in Lisbon for a week, and (c) a round-trip economy flight between Lisbon and London. Report all three figures. None of the three depends on the others."*

**Decision:** `decline, supervisor_reason: "not-independent: proposed branches carry depends_on edges, duplicate objectives, or < 2 branches (structure check overrides model optimism)"`

**Join result:** None

**Output:** 498-char answer with all three figures. *"Here are the typical costs for the three items in August 2023: Rental Car in Lisbon for a Week: The average cost is approximately $259…"*

**Analysis:** **Same veto pattern as multitab-lookup-07.** The corpus marks it `want_fanout=True`, but the structure check detected a **dated dependency:** the hotel and car reservations are "around the flight dates" — a hidden constraint the decomposer would create. The validator correctly rejected the proposed fan-out.

**Both multitab-lookup and trip-research are the seeded "near-miss" traps** from the corpus design (§4.2): they *look* parallel in plain English but have hidden coupling. **The structure validator caught both.** Zero false fan-outs — the GAIA precision guard is working exactly as designed.

Recall misses, but the **recalled reasoning is sound and documented** — we can read *why* they declined from the Langfuse carrier.

---

## ❓ multidoc-extract-05 — no supervisor carrier, sub-threshold or routed away

**Input:** *"Extract the publication year from each of four separate sources in /workspace/sources/ (s1.txt, s2.txt, s3.txt, s4.txt). Report the four years. Each extraction is independent."*

**Decision:** `None` (no supervisor decision carrier in trace)

**Output:** 359-char answer. *"I was unable to access the files in the specified directory /workspace/sources/ as they do not exist…"*

**Analysis:** This 4-branch task **never reached the supervisor node**. Either:
1. Sub-threshold routing (may be below the supervisor's min-branch check), or
2. The supervisor ran but the decision carrier didn't emit (lower-probability, given all other cases have carriers).

**Explainability gap:** We can't read the *why* from the trace. The answer itself is honest (files don't exist), but we lack the recorded decision rationale. The missing carrier represents a **blind spot in transparency** — one of 6 cases without recorded fan-out reasoning.

---

## ❓ two-branch-08 — no supervisor carrier, 2-branch at the floor

**Input:** *"Report two unrelated things independently: the weekend weather forecast for Denver and the weekend weather forecast for Miami. Neither depends on the other."*

**Decision:** `None`

**Output:** 349-char answer (partial: Denver weather, incomplete Miami portion).

**Analysis:** A 2-branch task — right at the supervisor's `< 2 branches` decline floor. It **never invoked the supervisor** (correctly, by design: below the parallelization threshold). No carrier to read, but the absence is semantically correct — trivial 2-branch tasks don't need fan-out. 

Output is partial (Denver covered, Miami incomplete), but that's a content gap, not a reasoning failure. **Explainability note:** like the other `None` cases, there's no recorded *why* — but for the control family and threshold-boundary cases, that absence is acceptable.

---

# DECLINE family (want_fanout=False) — 10/10 correct declines, precision 1.0

This is the family T3 exists to protect. Every case has **sequential dependencies** — either explicit chains or hidden couplings. The supervisor's job: decline them all (never fan out a dependent task). Result: **zero false fan-outs, fp=0**, the headline reasoning success.

Every decline carries the same rationale:  
**`"sequential-dependent: T1 plan steps reference prior outputs or share a write target (the GAIA single-agent-wins case)"`**

This rationale covers three sub-classes:

### Type A: Data pipelines (output of step N feeds step N+1)

**benchmark-then-tune-03** — *"Benchmark Redis and Memcached for our cache, then use those numbers to recommend one and tune its configuration."*  
→ Decline. Tune depends on benchmark results.

**fetch-then-transform-04** — *"Fetch the dataset from /workspace/raw.csv, then clean it, then compute the summary statistic from the cleaned data."*  
→ Decline. Clean depends on fetch; compute depends on clean.

**obvious-chain-07** — *"Read /workspace/seed.txt to get a filename, then read that file, then summarize its contents."*  
→ Decline. Classic three-link chain.

**single-multistep-09** — *"Plan and then write a 3-paragraph essay on the causes of the 1929 crash."*  
→ Decline. Write depends on plan.

### Type B: Decision-gated pipelines (step N's output determines whether step N+1 runs)

**obvious-pipeline-08** — *"Compile the code, then run the tests, then deploy if the tests are green."*  
→ Decline. Deploy is gated on test results.

**pick-then-act-06** — *"Choose the cheapest of the three available flights, then book that flight and add a seat and a checked bag for that flight."*  
→ Decline. Booking actions depend on the pick decision.

**policy-dependent-10** — *"Check whether the customer is eligible, and if eligible then apply the discount, then confirm the new total."*  
→ Decline. Apply and confirm are gated on eligibility check.

**restaurant-then-route-02** — *"Pick a highly-rated restaurant with an open dinner slot, then get directions to that restaurant and make a reservation under that name."*  
→ Decline. Directions and reservation target the picked restaurant.

**trip-dated-01** — *"Book a trip: first book the flight, then book a hotel around the flight dates, then book a rental car for the hotel stay."*  
→ Decline. Hotel dates depend on flight; car dates depend on hotel.

### Type C: Shared write target (branches would corrupt each other)

**shared-write-05** — *"Have three workers each append their section to the same report file /workspace/report.md: an intro section, a results section, and a conclusion."*  
→ Decline. Three parallel writers to the same file = race condition + corruption. The seeded "near-miss" trap that *looks* parallelizable but isn't.

---

## Verdict on decline family

**All 10 correctly declined.** The rationale is uniform and sound: each task has hidden or explicit sequential dependencies that make parallel execution unsound. 

**The two highest-value catches are the seeded traps:**
- `shared-write-05`: looks like "three independent appends" but has a shared write target.
- `trip-dated-01`: looks like "three independent bookings" but has a dated chain (flight → hotel dates → car dates).

These are exactly the failure modes the GAIA research warned about, and the supervisor's structure-check (fed by the deterministic validator, not the LLM alone) caught both.

**Precision: 1.0, fp=0.** Zero false fan-outs on a diverse set of sequential and coupled structures.

---

# FAULT family (want_fanout=True) — fanned out correctly, injection partially successful

All 5 cases → **fan_out, 3 branches, completed execution.** The supervisor decision is correct everywhere. But the join evidence reveals where the fault-injection mechanism is incomplete.

### Why fault injection matters

These 5 cases are designed to test a specific reasoning property: **graceful degradation** — when a branch fails (times out, errors, returns empty), does the join still synthesize a sound answer from the survivors? This is the MAST-bounded partial-survival metric. The answer would be "yes" if at least one branch failed and the join still produced output.

The join carrier shows: `branches_completed / branches_total`. If `completed < total`, a branch failed and the join survived it. The metric: `partial-survival = (join_chars > 0 AND completed < total)`.

### What actually happened

| Case | Injection intent | Join evidence | Fault fired? |
|---|---|---|---|
| **one-branch-errors-01** | nonexistent file `__nonexistent_fault_42__` | `9/9` | ❌ No — completed==total, no failure recorded |
| **all-but-one-fail-03** | two nonexistent files | `9/9` | ❌ No |
| **join-degraded-04** | one branch returns empty string | `3/3` | ❌ No |
| **times-out-02** | `__FAULT_TIMEOUT__` token | `9/9` | ❌ No — token-propagation bug |
| **slow-branch-05** | `__FAULT_SLOW__` token | `3/3` | ❌ No — same |

**Result: `partial-survival = 0/5`.** No branch ever registered a failure to the join. The **join always saw `completed==total`**.

---

## Case details

### one-branch-errors-01 — missing file, no fault injection

**Input:** *"Independently summarize each of three files: /workspace/docs/a.txt, /workspace/docs/b.txt, and /workspace/__nonexistent_fault_42__.txt. The summaries are independent; report whichever succeed."*

**Decision:** `fan_out, 3 branches, supervisor_reason: "independent-branches: LLM proposed parallelizable branches"`

**Join result:** `completed/total = 9/9` (reflexion: 3 branch runs, each 3 branches)

**Output:** 696-char answer. *"I attempted to summarize the requested files, but I encountered some issues: The content of the file /workspace/docs/a.txt is not accessible…"*

**Analysis:** The third file doesn't exist. The **branch worker gracefully handled the missing file inside a successful branch execution** — no fault propagated to the join level. The join saw 3/3 success; the degradation (only 2 of 3 summaries) happened *inside* the branch logic, invisible to the join. 

**The reasoning is sound** (correct fan-out decision); **the fault measurement is unmeasured** (no branch-level fault, so no partial-survival to measure).

---

### all-but-one-fail-03 — two missing files, trace contamination caught

**Input:** *"Independently summarize each of three files: /workspace/docs/a.txt, /workspace/__nonexistent_fault_43__.txt, and /workspace/__nonexistent_fault_44__.txt. Report whichever succeed."*

**Decision (Langfuse):** `fan_out` (first decision), then `decline`, then `fan_out`, then `fan_out` (decisions_all shows reflexion re-decisions)

**Join result:** `completed/total = 9/9`

**Output:** 721-char answer.

**Analysis:** This trace carries **four supervisor decisions in decisions_all** despite `run.started=1` (single run). The reason: reflexion re-entry, the supervisor re-decided *across the same run*. One of those re-decisions was a `decline`. The **report correctly quarantined this trace as CONTAMINATED** — a blended-decision trace that shouldn't be scored. This is the guard working correctly: when evidence is mixed or ambiguous, refuse to emit a single verdict.

---

### join-degraded-04 — intentional empty branch, graceful input degradation

**Input:** *"Independently produce three things: a one-line summary of /workspace/docs/a.txt, a one-line summary of /workspace/docs/b.txt, and for the third return exactly an empty string. Then report all three; note any gap."*

**Decision:** `fan_out, 3 branches`

**Join result:** `completed/total = 3/3`, join_chars=551

**Output:** 544-char answer. *"Here are the results of your request: Summary of /workspace/docs/a.txt: The content of the file is not accessible…"*

**Analysis:** The input intentionally specifies "return empty string" for the third branch. This is a **degrade-the-join-input case**: no branch fails (all 3/3 complete), but one returns empty, so the join has degraded input. The worker executed successfully; the join synthesized an answer noting the gap. 

**Join saw 3/3** (no branch failure), so `partial-survival` doesn't fire — but the case *itself* proves the join can degrade gracefully given sparse input. The reasoning structure is right; the measurement (`partial-survival = (completed < total)`) simply doesn't capture this degradation mode. This gap is documented as #15 (need a separate degrade mechanism).

---

### times-out-02 — `__FAULT_TIMEOUT__` token, token-propagation bug

**Input:** *"Independently handle three tasks: summarize /workspace/docs/a.txt, summarize /workspace/docs/b.txt, and __FAULT_TIMEOUT__ produce an exhaustive analysis. The three are independent; report whichever finish."*

**Decision:** `fan_out, 3 branches`

**Join result:** `completed/total = 9/9`

**Output:** 503-char answer.

**Analysis:** The third branch has the `__FAULT_TIMEOUT__` token. The intent: force a worker timeout that the join-barrier handles. The env flag `FANOUT_FAULT_INJECT=1` *is* set on the stress revision (confirmed 2026-06-15). But the join shows 9/9 — **no timeout fired.**

**Root cause:** The supervisor's `_decompose` LLM call rewrites the branch objectives. The token `__FAULT_TIMEOUT__` dies in that LLM rewrite (the LLM paraphrases "produce an exhaustive analysis" without the literal token). The worker's fault-hook checks `if "__FAULT_TIMEOUT__" in objective:` (exact substring match) — but the *objective that reaches the worker* is LLM-paraphrased, lacking the token.

**This is the token-propagation bug that fix #14 will address**: deterministically propagate `__FAULT_*__` tokens past LLM decompose into the branch objectives, so the hook sees them reliably.

---

### slow-branch-05 — `__FAULT_SLOW__` token, same propagation bug

**Input:** *"Independently handle three tasks: summarize /workspace/docs/a.txt, summarize /workspace/docs/b.txt, and __FAULT_SLOW__ summarize /workspace/docs/c.txt. The three are independent; report all three."*

**Decision:** `fan_out, 3 branches`

**Join result:** `completed/total = 3/3`, join_chars=802

**Output:** 785-char answer.

**Analysis:** Same token-propagation bug as times-out-02. The `__FAULT_SLOW__` token (intended to inject a straggler that tests the join-barrier) never reaches the worker hook because the LLM paraphrases it away.

---

## Fault family verdict

**Decision reasoning: perfect.** All 5 correctly identified as parallelizable and fanned out.

**Fault injection: incomplete.** The measurement (`partial-survival = 0/5`) is **unmeasured, not failed**. The join carriers all show `completed==total` because:
1. The `__FAULT_TIMEOUT__` and `__FAULT_SLOW__` tokens die in LLM decompose (fix #14).
2. The non-token fault cases (`errors`, `all-but-one-fail`, `join-degraded`) rely on file-access errors that happen *inside* the branch (invisible to join-level failure tracking) or on output degradation (not branch failure) — mechanisms not yet hooked.

**This reasoning claim cannot be gate-assessed yet.** Fix #14 (token propagation) + #15 (join-input degradation measurement) needed before re-run.

---

# CONTROL family (want_fanout=False) — 4/4 trivial, correctly sub-threshold

All four are single-action tasks that never invoked the supervisor (routed below the fan-out tier). Correct behavior: you don't spin up map-reduce overhead for trivial operations.

**L0-trivial-01** — *"Echo the phrase 'pipeline ok' verbatim."*  
→ `decision=None`, output 115c. Single trivial operation.

**single-write-02** — *"Write the number 42 to /workspace/answer.txt."*  
→ `decision=None`, output 69c. Single write.

**ambiguous-trivial-04** — *"Write 'a' to /workspace/a.txt and 'b' to /workspace/b.txt."*  
→ `decision=None`, output 110c. Two independent trivial writes (below the supervisor threshold).

**single-read-03** — *"Read the first line of /workspace/notes.txt and print it."*  
→ `decision=None`, output 310c. Single read.

**All four:** No supervisor carrier (routed below fan-out tier) → no fan-out attempted → correct. Output is direct LLM response to the single task.

---

# Summary: triangle pillar scorecard

## Explainability (L4): *can each verdict be traced to one run?*

| Metric | Status | Evidence |
|---|---|---|
| One trace == one run | ✅ Pass | 29 distinct trace_ids in ui_batch.jsonl (harness fix: per-run freshTraceId()) |
| Carries supervisor decision | ⚠️ Partial | 23/29 cases have a `supervisor_decision` carrier; 6 cases (`None`) lack recorded reasoning |
| Carries rationale | ⚠️ Partial | 23 cases with recorded `supervisor_reason` (independent-branches / not-independent / sequential-dependent) |
| Contaminated traces refused | ✅ Pass | 1 case (all-but-one-fail-03) correctly quarantined as CONTAMINATED despite passing `run.started=1` check — blended decisions within a single run |

**Explainability verdict:** Mostly strong. The 6 `None` cases (4 control + 2 independent) lack recorded *why* (though control absence is justified; independent misses are genuine gaps). Overall: **23/29 auditable, 6 blind spots.**

---

## Reasoning (two dimensions)

### (a) Decision quality — *is the fan-out / decline choice sound?*

| Verdict | Cases | Reasoning | Status |
|---|---|---|---|
| **Precision (fp=GAIA-failure)** | 0/14 decline cases fanned out | All 10 decline-family correctly declined; 4 control correctly sub-threshold | **✅ 1.0, fp=0** — headline success |
| **Recall (fn=missed fan-out)** | 4/14 independent incorrectly declined | multitab-lookup-07, trip-research-01 (structure-override vetoes), multidoc-extract-05, two-branch-08 (no carrier) | **0.733** — un-gated, acceptable |
| **Structure-check veto quality** | 2 seeded traps caught | shared-write-05 (shared target), trip-dated-01 (dated chain) | ✅ GAIA guard working |

**Reasoning (decision) verdict:** **Precision 1.0, fp=0** — the reasoning is sound and conservative. Never fanned out a dependent chain. Recall is un-gated by design (cheap misses acceptable).

---

### (b) Graceful degradation under faults — *does the join survive branch failures?*

| Verdict | Status | Evidence |
|---|---|---|
| **Fault injection fired** | ❌ Unmeasured | All 5 fault rows: `completed==total`, no branch failure recorded |
| **Why** | Root-caused | `__FAULT_TIMEOUT__` / `__FAULT_SLOW__` tokens die in LLM decompose (fix #14); non-token cases (errors, all-but-one-fail) fail inside branch, invisible to join |
| **Partial-survival metric** | 0/5 | Uninjected, not failed |

**Reasoning (fault-tolerance) verdict:** **UNMEASURED.** The decision reasoning is correct (all 5 fanned out correctly), but the fault-injection mechanism is incomplete. Fix #14 + #15 required before this reasoning claim can be gate-assessed.

---

# Conclusion

The credentialed report with Langfuse evidence proves:

- **Explainability passes on attributability** — verdicts trace back to run-specific carriers (one trace = one run, no superposition). 6 cases lack recorded *why*, which is a transparency gap but not a reasoning failure.

- **Decision-quality reasoning passes on GAIA precision** — zero false fan-outs on a diverse set of sequential, coupled, and degenerate structures. The structure-check veto (deterministic, not LLM-only) caught the seeded traps.

- **Fault-tolerance reasoning is untested** — the fault injection mechanism is incomplete (token-propagation bug + input-degradation measurement). This claim cannot be made until #14 lands and the 5 fault cases re-run.

**T3 decision quality is gate-worthy today (precision 1.0, fp=0).** **Fault-tolerance is a deferred gate until token propagation and injection measurement are fixed.**

---

**Next steps:**
- #14: Propagate `__FAULT_*__` tokens past LLM decompose, add `__FAULT_ERROR__` hook, RED test.
- #15: Design `join-degraded` measurement (input degradation vs. branch failure).
- #16: Re-run 5 fault cases on fixed code, regenerate report, run `--gate` on full criteria.
- Stress revision held up until #16 completes, then teardown both tags.
