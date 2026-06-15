# T3 fan-out benchmark corpus — plan

> **Scope.** A synthetic benchmark corpus that validates the T3 supervisor / parallel-fan-out tier on the
> GCP-hosted pipeline. This is the *workload* half of T3 validation; the *mechanism* (the `supervisor_plan.py`
> component, the `Send` fan-out/fan-in nodes) is specced in
> [`t3_supervisor_plan.component.md`](t3_supervisor_plan.component.md) and §3.5a/§8.2 of
> [`planning_pipeline_tiered_loops.plan.md`](planning_pipeline_tiered_loops.plan.md). This doc owns *which tasks*,
> *why each one*, and *how it scores* — it does **not** re-spec the component contract or the orchestration topology.
>
> **Status.** 🔮 PLANNED. T3 itself is design-complete-but-unbuilt (Phase 4). This corpus is authored **with** T3
> (impl §7.6) — it is the eval that gates the Phase 4 build. Nothing here runs until `supervisor_plan.py` + the
> fan-out nodes exist.
>
> **Honesty banner (carried from §3.5a).** The published evidence is that **single-agent beats multi-agent on
> GAIA** — fanning out a *dependent* task is actively harmful (MAST, arxiv 2503.13657). So this corpus's headline
> is **not** "fan-out wins." It is: *the supervisor decides correctly when to fan out and when to decline, the seam
> is layer-clean and observable, and it survives partial branch failure.* The load-bearing rows are the **decline**
> rows, not the happy-path rows.

---

## 1. Why this corpus exists (and why it's synthetic)

§2.3 of the tiered-loops plan established — from the real task corpus — that **genuine parallel work is ~0%**: the
workload is overwhelmingly sequential. T3 is being built anyway, as a deliberate *de-risk-the-seam* exercise (user
decision 2026-06-15, [[t3-supervisor-fanout-research]]). That decision has a direct consequence for validation:
**there is no organic dataset to evaluate T3 against.** We must author one.

A synthetic corpus is the honest tool here precisely because the acceptance bar (§3.5a) is **seam + layer-clean +
observable + MAST-bounded, not throughput**. We are not claiming T3 makes the product faster on real work. We are
proving the *decision surface* behaves: that the supervisor fans out when branches are independent, declines when
they are not, and the fan-in survives a dead branch. A corpus engineered to span that decision surface tests
exactly that — and the engineered **decline** and **fault** rows are things an organic corpus would rarely contain.

This mirrors the T1/T2 stress corpus exactly ([`build_planning_stress_corpus.py`](../../scripts/build_planning_stress_corpus.py)):
synthetic prompts, per-phase `want_*` expectations, aggregate-rate scoring (never per-case exact-prose, because T3
is non-deterministic), calibration-first then gate.

## 2. The T3 planning decision space (what the corpus must span)

The corpus is dimensioned by **what the supervisor actually decides**, not by arbitrary task variety. The decision
surface comes straight from the component spec (`t3_supervisor_plan.component.md` §2, conditions 1–5) and the
runtime seam. Five axes; every row is a point in this space, and the corpus must put rows at the boundaries and the
adversarial corners — not just the easy interior.

| Axis | Poles | The decision it stresses | Component condition |
|---|---|---|---|
| **A. Independence** | independent ⟷ sequentially-dependent | the GAIA guard — fan out vs decline | conditions 2, 4, 5; `depends_on` / `validate_independence` |
| **B. Cardinality** | 0–1 branch ⟷ 2 ⟷ many (cap) | the "<3 don't bother" floor; the `max_concurrency` ceiling | condition 1 (floor); run-config cap |
| **C. Disguise** | obviously-parallel ⟷ near-miss (looks parallel, is dependent) | discrimination quality — the *hard* decline | condition 2's deterministic dependency signal |
| **D. Fault** | all-healthy ⟷ one-branch-fails / times-out | the sentinel + per-branch-timeout path; super-step survival | (runtime, not component) — MAST bound |
| **E. Depth/trigger** | L0 ⟷ L1 ⟷ L2 | does fan-out only engage at the right planning depth? | condition 1 (`planning_depth == "L0"` → decline) |

The four §8.2 families are the *coarse* grouping; these axes are the *fine* coverage check. A family with rows all
clustered at one pole (e.g. all decline rows obviously-sequential, none near-miss) would pass while leaving the real
risk untested. **Every row below is tagged with the axis-poles it occupies**, and §6 has a coverage matrix that
must show no empty cell on the axes that matter (A, C, D especially).

## 3. Family allocation (scaled to cover the space; cap 40)

The 8/6/3/3 split was the answer for a 20-row corpus. The follow-on direction — *"cover all the dimensions in T3
planning space … if required we cap at 40"* — means scaling the families up to fill §2's coverage matrix, not
holding at 20. The plan: **start at 20 (the answered split), then add boundary/edge/stress rows family-by-family
until every coverage cell in §6 is non-empty, capping at 40.** Target landing zone:

| Family | `phase` | Decision tested | 20-row (answered split) | Scaled target | Why scale here |
|---|---|---|---|---|---|
| **`FANOUT-independent-NN`** | `fanout` | the fan_out happy path | 8 | **10–12** | needs cardinality spread (2 / 3 / many) × domain blend × an L2 row |
| **`FANOUT-decline-NN`** | `fanout` | the GAIA guard (load-bearing) | 6 | **10–12** | the hardest family — must cover obvious-sequential AND near-miss disguise (axis C); weighted heaviest |
| **`FANOUT-fault-NN`** | `fanout` | partial-survival (MAST bound) | 3 | **5–6** | needs fail-fast / timeout / all-but-one-fail / join-degraded variants (axis D spread) |
| **`FANOUT-control-NN`** | `fanout` | precision guard (no fan-out on trivial work) | 3 | **4–5** | L0 floor + single-step boundary + a deliberately-ambiguous trivial |
| **total** | | | **20** | **≈30, hard cap 40** | |

Recommendation: **author to ~30**, treat 40 as the hard ceiling. Past ~30, a non-deterministic batch's per-family
rates stop tightening and the Langfuse trace quota (§8) starts to bite. If the §6 coverage matrix fills before 30,
stop there — coverage, not row count, is the bar.

## 4. Row catalog (domain blend; consumer + benchmark; near-miss traps seeded)

> **✅ BUILT 2026-06-15.** The 29 rows below are now authored in
> [`build_planning_stress_corpus.py`](../../scripts/build_planning_stress_corpus.py) (`_fanout_rows()` +
> per-family producers), `phase="fanout"`. Verified: `python build_planning_stress_corpus.py` →
> `fanout 29` (independent 10 / decline 10 / fault 5 / control 4); the case-id + trace_id uniqueness guards pass;
> `pytest tests/scripts/` 64/64 green; the §6 coverage matrix's two critical cells are full (near-miss=7, fault=5);
> `want_fanout` balance 15 True / 14 False (real negatives for precision). The corpus is **data only** — it does
> nothing until the Phase 4 supervisor/worker/join nodes exist to emit the carriers it scores.

The blend (user pick): roughly **half consumer tuples** (relatable, your trip/restaurant examples) + **half
benchmark-derived** (GAIA multi-doc, Tau² policy, WebArena multi-tab). Each row lists its **axis poles** (§2) and
the `want_*` it scores against. Benchmark rows **adapt task shapes, never the private answer sets** (§8.2).

### 4.1 `FANOUT-independent` — genuinely parallel (happy path)
`want_fanout=True`, `want_branch_count≥2`, `want_join_synthesizes=True`.

| Row | Domain | Prompt shape | Branches (independent) | Axis poles |
|---|---|---|---|---|
| `independent-trip-research-01` | consumer | "Research, in parallel, the **typical** Aug cost of (a) a rental car in Lisbon, (b) a 4-star hotel in Lisbon, (c) a round-trip flight LIS↔your city. Report all three." | 3, no shared date constraint → independent *research* | A:independent, B:3, C:obvious |
| `independent-restaurant-survey-02` | consumer | "Find 3 highly-rated restaurants — one Italian, one Thai, one sushi — and report each one's rating + price band. They're unrelated." | 3 independent cuisine lookups | A:independent, B:3, C:obvious |
| `independent-gift-shortlist-03` | consumer | "Shortlist a gift under \$50 for each of 3 people with given interests; the choices are unrelated." | 3 independent shortlists | A:independent, B:3, C:obvious |
| `independent-multidoc-summary-04` | GAIA-style | "Summarize the key finding of each of these 3 unrelated documents independently." | 3 independent doc summaries (the canonical GAIA fan-out) | A:independent, B:3, C:obvious |
| `independent-multidoc-extract-05` | GAIA-style | "Extract the publication year from each of 4 separate sources." | 4 independent extractions | A:independent, B:4, C:obvious |
| `independent-policy-checks-06` | Tau²-style | "Independently verify each of 3 separate policy conditions against the account; none depends on another." | 3 independent policy checks | A:independent, B:3, C:obvious |
| `independent-multitab-lookup-07` | WebArena-style | "Look up the current price of 3 unrelated SKUs, one per tab." | 3 independent lookups | A:independent, B:3, C:obvious |
| `independent-two-branch-08` | consumer | "Compare just two unrelated things: the weather forecast for City A and City B this weekend." | **2** — the cardinality floor (exactly at "≥2") | A:independent, **B:2 (boundary)** |
| `independent-many-branch-09` | GAIA-style | "Summarize each of these **6** unrelated abstracts." | **6** — stresses `max_concurrency` cap | A:independent, **B:many (ceiling)** |
| `independent-L2-decompose-10` | benchmark | "Independently produce a one-paragraph briefing on each of these three unrelated regions — Nordics, Iberia, and Baltics — covering, for each region separately, (1) its largest city (2) its primary language (3) its currency. The three briefings do not depend on each other." | engineered to fire L2 *and* stay independent — see §4.1a | A:independent, **E:L2**, B:3 |

### 4.1a The L2-trigger problem (and how this one row threads it)

> **§10.3 open question, resolved — but it surfaced a real finding worth stating plainly.**

I read the actual depth scorer ([`select_planning_depth`, router.py:97-229](../../components/router.py)) and the L2
rows of the strata fixture the `depth` phase reuses. The honest finding:

**Every prompt shape that reliably fires L2 in this scorer is sequentially *dependent*.** L2 needs
`complexity_score ≥ 3`, and the score's levers are: word-count (≥35/≥80), the multi-part markers
(`compare`/`migration`/`refactor`/`architecture`/`design`/`roadmap`/`trade-off`), conjunctions
(`and`/`then`/`also`), newline structure, and `(1)…(2)` enumeration — *plus* the `incident-narrative` promotion
(`trace how`/`root cause`/`propagat`/`sometimes`). Look at what the fixture's L2 rows actually are: *"Compare Redis
and Memcached, (1) benchmark… (2) measure…"* (that's the `decline-benchmark-then-tune` shape — **dependent**);
*"Audit architecture, design a migration, refactor…"* (a pipeline — **dependent**); the two incident narratives
(single-thread debugging — **dependent**). **The scorer's L2 vocabulary is almost exactly the dependency detector's
(§3a) decline vocabulary** — and that's not an accident: deep planning correlates with sequential structure. A
naive "genuinely L2 *and* independent" row is close to a contradiction in this scorer.

**How this row threads the needle — borrow L2's *structural* levers without its *dependency* levers.** The
engineered prompt hits `complexity_score ≥ 3` using only the signals that carry **no** inter-step dependency:

| L2 signal used | Present via | Dependency implied? |
|---|---|---|
| `(1)…(2)…(3)` enumeration | "(1) its largest city (2) its primary language (3) its currency" | **no** — these are *attributes of each item*, not ordered steps |
| word-count ≥ 35 | the full prompt is ~45 words | no |
| (a conjunction) | "and Baltics" / the list | no — list conjunction, not "then" |

Crucially it **avoids** every dependency marker the §3a detector trips on: no `then` / `use the result` / `based on`
/ `for that`; no shared write target; the explicit "do not depend on each other" closes the anaphora door. So the
*depth scorer* sees enough structure to score L2 (enumeration + length), while the *dependency detector* sees a
clean independent fan-out (three parallel per-region briefings). The `(1)(2)(3)` here are **per-branch sub-fields**,
not branch-ordering — that's the whole trick.

**Acceptance for this row is two-gate, and the first gate can fail gracefully.** The row carries `want_depth="L2"`
*and* `want_fanout=True`. If a calibration run shows it fired **L1** (the scorer under-plans —
[[planning-depth-underplans]]: 9/12 complex tasks fired L0 live), that is **not** a corpus failure — it's the row
doing its second job, which is to *measure* the depth↔fan-out interaction. The fan-out decision (`want_fanout`) does
**not** require L2: `plan_delegations` declines only at `planning_depth == "L0"` (component condition 1), so an L1
result still fans out. The row's primary expectation is `want_fanout=True`; the `want_depth="L2"` is a *secondary,
non-gating* observation reported in the coverage matrix's E-axis cell. **The fallback is built in:** if L2 proves
unreachable for an independent task in this scorer, the row drops to documenting "fan-out works at L1; L2 is
empirically dependency-coupled in this scorer" — itself a finding, recorded, not a gap.

### 4.2 `FANOUT-decline` — must NOT fan out (the load-bearing family)
`want_fanout=False`. Split into **obvious-sequential** (easy) and **near-miss disguise** (the hard discrimination,
axis C — the traps you asked me to seed).

| Row | Domain | Prompt shape | Why decline | Axis poles |
|---|---|---|---|---|
| `decline-trip-dated-01` ⚠️ | consumer | "**Book a trip**: flight, then a hotel **around the flight dates**, then a car **for the hotel stay**." | the classic trap — hotel depends on flight, car depends on hotel; looks like 3 parallel bookings, is a chain | A:dependent, **C:near-miss**, B:3 |
| `decline-restaurant-then-route-02` ⚠️ | consumer | "Pick a highly-rated restaurant with an open slot, **then** get directions to **it** and a reservation under that name." | directions + reservation both depend on which restaurant got picked | A:dependent, **C:near-miss** |
| `decline-benchmark-then-tune-03` ⚠️ | technical | "Benchmark Redis and Memcached, **then use those numbers** to recommend one and tune its config." | the §2.3 gather-then-compare shape; tune depends on benchmark | A:dependent, **C:near-miss** |
| `decline-fetch-then-transform-04` ⚠️ | GAIA-style | "Fetch the dataset, **then** clean it, **then** compute the summary stat from the cleaned data." | strict ETL chain disguised as 3 'tasks' | A:dependent, **C:near-miss** |
| `decline-shared-write-05` ⚠️ | technical | "Have three workers each append a section to **the same report file** /workspace/report.md." | independent-*looking* but shared write target → conflict (the `validate_independence` shared-write signal) | A:dependent, **C:near-miss (shared write)** |
| `decline-pick-then-act-06` ⚠️ | consumer | "Choose the cheapest of 3 flights, **then** book it and add the seat and the bag for **that** flight." | downstream all depend on the choice | A:dependent, **C:near-miss** |
| `decline-obvious-chain-07` | consumer | "Read seed.txt to get a filename, then read THAT file, then summarize it." | obviously sequential (no disguise) — the easy decline | A:dependent, **C:obvious** |
| `decline-obvious-pipeline-08` | technical | "Compile the code, then run the tests, then deploy if green." | obvious sequential pipeline | A:dependent, **C:obvious** |
| `decline-single-multistep-09` | consumer | "Plan and then write a 3-paragraph essay on X." | single coherent task, not decomposable into parallel branches | A:dependent, **C:obvious** |
| `decline-policy-dependent-10` | Tau²-style | "Check eligibility, **and if eligible**, apply the discount, **then** confirm the new total." | conditional chain — branch 2 gated on branch 1's result | A:dependent, **C:near-miss (conditional)** |

⚠️ = a **near-miss trap** (looks parallel, is dependent). These are the rows that make the corpus a real test of
the supervisor's discrimination rather than a softball. If T3 fans any ⚠️ row out, that's a GAIA-failure and the
gate must catch it.

### 4.3 `FANOUT-fault` — partial-survival (the MAST bound, on a live trace)
`want_fanout=True`, `want_survives_partial=True`. A branch is engineered to fail/time out; the join must still
answer from the survivors, and the super-step must not hang.

| Row | Fault mode | Prompt shape | What it proves | Axis poles |
|---|---|---|---|---|
| `fault-one-branch-errors-01` | hard error | 3 independent lookups; one objective targets a missing resource → tool error | sentinel path; join answers from 2/3 | D:one-fails, A:independent |
| `fault-one-branch-times-out-02` | timeout | 3 independent lookups; one branch's objective is unbounded | per-branch timeout fires; no super-step hang | D:timeout |
| `fault-all-but-one-fail-03` | majority fail | 3 branches, 2 fail | join degrades to a single-survivor answer, still non-empty | D:majority-fail |
| `fault-join-degraded-04` | partial synthesis | 3 branches, 1 returns empty/garbage | join synthesizes a *coherent* answer noting the gap (not a crash) | D:degraded-input |
| `fault-slow-branch-05` | straggler | 3 branches, one much slower (within timeout) | super-step barrier waits correctly; no premature join | D:straggler (barrier) |

### 4.3a Fault-injection mechanism (how a branch reliably faults — and why it matters)

> **The §10.2 open question, answered.** A fault row is worthless if the fault is flaky: `want_survives_partial`
> can only be scored if the branch fails *deterministically* on a live GCP trace, while still exercising the *real*
> sentinel path — not a stubbed shortcut. This section pins how.

**What we are actually testing — the orchestration sentinel, not the dispatcher.** Ground truth from the runtime:
`LocalLLMDelegationDispatcher.dispatch` returns `{"status","output","error","child_correlation_id"}`, and its
`_run_async` **re-raises** any worker exception ([`delegation_dispatcher.py:87-88`](../../services/tools/delegation_dispatcher.py)).
So a worker that throws propagates straight up. At the graph level, the research finding is decisive: **a Send
branch that raises CANCELS the entire super-step** ([[t3-supervisor-fanout-research]]) — every sibling branch is
torn down and the join never runs. Therefore the *only* thing standing between a single bad branch and a dead
fan-out is the **worker node's try/except → sentinel** (the §3.5a MAST bound). **That sentinel is the unit under
test.** The fault corpus exists to prove, on a live trace, that the worker node catches the fault, emits a
sentinel result, and the join answers from the survivors. If the worker node had no try/except, every `fault-*` row
would hang or crash the whole batch — which is exactly the failure these rows are designed to catch.

**The injection contract — two layers, picked per fault mode.** A fault is injected at the *objective* level
(prompt-driven, realistic) wherever possible, falling back to a *dispatch-shim* level only for the modes a prompt
can't make deterministic:

| Fault mode | Injection layer | Mechanism (deterministic) | Real path exercised |
|---|---|---|---|
| **hard error** (`-01`, `-03`) | objective | branch objective targets a guaranteed-missing resource (`read /workspace/__nonexistent_fault_42__.txt`) → the worker's tool call errors → worker raises | tool-error → worker try/except → sentinel; **the real error path**, no shim |
| **timeout** (`-02`) | dispatch-shim (env-gated) | a `FANOUT_FAULT_INJECT` env flag + a magic objective token (`__FAULT_TIMEOUT__`) makes the worker node `await asyncio.sleep(timeout+ε)` *before* the LLM call → the per-branch `asyncio.wait_for` fires | the real per-branch-timeout → `TimeoutError` → sentinel path |
| **degraded output** (`-04`) | objective | objective asks for output the worker will return empty/garbage for (`return exactly an empty string`) → no exception, but join gets a useless branch result | join's *degraded-input* path (synthesize-around-a-gap), distinct from the error path |
| **straggler** (`-05`) | dispatch-shim (env-gated) | magic token `__FAULT_SLOW__` → `await asyncio.sleep(timeout-ε)` (under the ceiling) → branch completes late but succeeds | the super-step **barrier** waits for the slowest branch; no premature join |

**Why an env-gated shim, not a code branch in the worker.** The two timing modes (`timeout`, `straggler`) can't be
made deterministic by prompt alone — an LLM's latency is variable. The shim is a single guarded block at the top of
the worker node:

```python
# orchestration worker node — fault hook, OFF unless explicitly enabled
if os.getenv("FANOUT_FAULT_INJECT") == "1":
    await _maybe_inject_fault(delegation.objective, per_branch_timeout)
# ...then the normal dispatch
```

It is **off in prod** (gated on `FANOUT_FAULT_INJECT=1`, set only on the `--tag stress` revision, §8) and reads a
**magic token in the objective** (`__FAULT_TIMEOUT__` / `__FAULT_SLOW__`) so only the row that asked for the fault
gets it — no blast radius onto the healthy branches in the same fan-out. The hard-error and degraded modes need
*no* shim: they're injected purely through the prompt, so they exercise the genuine error/degraded paths with
nothing stubbed. This keeps the *interesting* faults (the ones that test the error sentinel) shim-free, and confines
the shim to the two modes that are fundamentally about *timing*, which is environmental, not semantic.

**Scoring `want_survives_partial` (the three conjuncts).** A fault row passes iff **all** hold on the captured
trace — this is the precise operationalization of "survives partial":
1. **sentinel observed** — a per-branch carrier shows a caught fault (the worker emitted a `delegation_failed` /
   sentinel result rather than propagating). Proves the try/except fired.
2. **final answer non-empty** — the `join_node` produced a coherent answer from the surviving branches (for `-03`,
   from the single survivor; for `-04`, an answer that *notes* the gap rather than crashing).
3. **no super-step hang** — the trace reached a terminal `task_completed` (the run didn't deadlock waiting on the
   torn-down branch). For `-05`, additionally: the join carrier's timestamp is *after* the slow branch's completion
   (the barrier waited, didn't fire early).

All three are read from the same Step-0 carriers the other phases use — no new telemetry primitive, just new carrier
*values* (`delegation_failed`, sentinel markers). The fault rows therefore validate the MAST bound **as observable
trace evidence**, which is exactly the §3.5a acceptance bar (observable + MAST-bounded), not a unit-test claim.

### 4.4 `FANOUT-control` — precision guard (no fan-out on trivial work)
`want_fanout=False`. The false-positive guard, mirroring the `control-trivial` reflexion rows.

| Row | Prompt shape | Why no fan-out | Axis poles |
|---|---|---|---|
| `control-L0-trivial-01` | "Echo 'pipeline ok' verbatim." | L0 single-action → condition-1 floor decline | E:L0, B:0–1 |
| `control-single-write-02` | "Write 42 to /workspace/answer.txt." | single step, nothing to parallelize | B:0–1 |
| `control-single-read-03` | "Read the first line of /workspace/notes.txt." | single step | B:0–1 |
| `control-ambiguous-trivial-04` | "Write 'a' to a.txt and 'b' to b.txt." | two *trivial* writes — technically independent but below the "<3 don't bother" floor; correct decision is **decline** (overhead > benefit) | **B:2 but below-floor (boundary)** |

`control-ambiguous-trivial-04` is deliberately the **boundary** case: it *is* independent (axis A) but its
cardinality (2) and triviality put it below the "<3 don't bother" rule. It tests that the floor (condition 1 / the
cardinality rule) wins over raw independence. This is the single most subtle precision row.

## 5. New row shape & expectation keys (extends `_row`)

The builder ([`build_planning_stress_corpus.py`](../../scripts/build_planning_stress_corpus.py)) gets a
`_fanout_rows()` producer and `_row()` gains the fan-out expectation keys. `phase="fanout"`. Keys (from §8.2, plus
the axis tag for the coverage matrix):

| Key | Type | Meaning | Scored by (§7) |
|---|---|---|---|
| `want_fanout` | bool | should the supervisor emit ≥2 parallel branches? (decline/control rows = `False`) | did `supervisor` emit ≥2 `Send` / `delegation_requested` carriers? |
| `want_branch_count` | int? | expected branch count (independent rows only) | count of per-branch `delegation_requested` carriers |
| `want_join_synthesizes` | bool? | did the join produce one coherent answer? | `join_node` carrier present + GoalJudge ran on the merged answer |
| `want_survives_partial` | bool? | (fault rows) one branch fails → join still answers | sentinel carrier observed; final answer non-empty; no super-step hang |
| `axis` | list[str] | the §2 axis-poles this row occupies (for the §6 coverage matrix; not a scored expectation) | coverage report only |

Absent keys are not scored (same contract as the T1/T2 rows). The `axis` tag rides along as extra metadata — per
the open-coding skill's "any extra keys survive the round-trip" rule, it lands in the dataset item metadata for
later filtering, and the coverage report reads it.

## 6. Coverage matrix (the real bar — must show no empty critical cell)

Authoring stops when this matrix has no empty cell on the **critical axes (A, C, D)** — not when a row count is
hit. The builder prints this matrix; a cell count of 0 on a critical axis is an authoring failure.

| | independent (A) | dependent (A) | near-miss disguise (C) | one-branch-fault (D) | L0/L1/L2 (E) |
|---|---|---|---|---|---|
| **`independent`** | ✅ ≥10 | — | — | — | L0✗ L1✓ **L2 attempted (row 10; falls back to L1 — §4.1a)** |
| **`decline`** | — | ✅ ≥10 | ✅ ≥6 ⚠️ | — | — |
| **`fault`** | ✅ (healthy branches) | — | — | ✅ ≥5 | — |
| **`control`** | ✅ (row 04, below-floor) | — | — | — | **L0✓(row 01)** |

The two cells that an organic corpus would never fill, and that this corpus exists to fill: **decline × near-miss
disguise** (the GAIA guard's hard case) and **fault × one-branch-fault** (the MAST bound on a live trace). If
either is thin, add rows there before adding anywhere else.

## 7. Analyzer delta (scoring)

[`analyze_planning_traces.py`](../../scripts/analyze_planning_traces.py) `score_run` (line 237) dispatches by
`phase`; a `fanout` branch slots in exactly like the existing four. **⚠️ Until that branch is added (Phase 4 work,
impl §7.6), a `fanout` row falls through the `if/elif` chain — it is counted in `n` but never scored a hit, so it
reports `rate=0.0` with no mismatches** (a silent zero, not a crash). Don't read a calibration run as "fan-out
failed" before the `fanout` branch exists; the rows are inert data until then. The fan-out phase is scored as
**precision/recall over the fan-out *decision*** (the same confusion-matrix shape as `escalation`, line 295) plus a
**partial-survival rate** for the fault rows:

```text
elif phase == "fanout":
    want_fanout = bool(row.get("want_fanout"))
    got_fanout  = _branch_count(events) >= 2          # ≥2 delegation_requested carriers
    # confusion matrix on the DECISION (decline cases are the negatives):
    #   tp: wanted fan-out, fanned out            (independent rows)
    #   fp: did NOT want fan-out, fanned out       ← the GAIA failure (near-miss trap fanned out)
    #   tn: did NOT want fan-out, declined         (decline + control rows, correct)
    #   fn: wanted fan-out, declined               (missed parallelism — the cheap error)
    # for fault rows additionally: survived = sentinel seen AND final answer non-empty
    #                              AND no super-step hang (trace terminated)
```

Two headline metrics, matching the §3.5a acceptance bar:
- **fan-out precision** = `tp / (tp + fp)` — *of the rows we fanned out, how many should have been.* The **`fp`
  cell is the GAIA-failure detector**: a near-miss ⚠️ row that got fanned out lands here. High precision is the
  load-bearing result.
- **partial-survival rate** = (fault rows where the join answered from survivors) / (fault rows). The MAST-bound
  evidence on a live trace.

Recall (`tp / (tp + fn)`) is reported but **not** the headline — per §3.5a, a missed fan-out is the *cheap* error
(it just runs sequentially, which already works), so we deliberately tolerate low recall and prize precision. The
analyzer also emits the §6 coverage matrix from the `axis` tags so a run report shows both *did it decide right*
and *did we test the whole space*.

**Calibration first** (`--calibration` default, records never gates), exactly as the T1/T2 phases. Bars are set
from the first non-deterministic batch, then `--gate` enforces them. Proposed initial bars to calibrate toward
(not asserted until calibrated): **fan-out precision ≥ 0.9** (near-miss traps almost never fanned out),
**partial-survival = 1.0** (every fault row's join answers — this is a *mechanism* guarantee, not a rate), recall
unconstrained.

## 8. Running it on the GCP-hosted pipeline

Same harness as the T1/T2 stress run — the corpus rides the existing `planning-stress` e2e spec + the
`gj:`-thread/`trace_id` bridge. Sequence:

1. **Backend must be loops-on *and* T3-on.** The Step-0 env flags (`REFLEXION_ENABLED` / `PLANNING_PLAN_SOURCE` /
   `MAX_REFLEXION_ATTEMPTS`) plus a new T3 enable flag are **not** in `cloud-run-backend.tf`
   ([[deploy-gcp-stress-revision]]). Stand up a loops+T3 backend via the out-of-band `--tag stress --no-traffic`
   gcloud revision (prod untouched), per the deploy-gcp skill.
2. **Smoke first** (one row per family, chromium-only) — confirms the fan-out carriers (`delegation_requested`,
   `join_node`) actually emit on a live trace before the full batch. The Langfuse monthly trace quota has 429'd
   before ([[goaljudge-gcp-playwright-gotchas]]); a 4-row smoke protects it.
3. **Full batch** via `TEST_PROFILE=stress` ([[live-testing-profiles-config]]), `STRESS_PHASE=fanout`.
4. **Analyze** `--source langfuse` (Cloud Run tmpfs recordings are ephemeral) with `--calibration` first; read the
   precision + partial-survival + coverage matrix; then re-run `--gate` once bars are set.

## 9. Optional: hand-code the fan-out traces (open-coding skill)

The [`agentsframework-open-coding`](../skills/agentsframework-open-coding/SKILL.md) skill is the right tool for the
**qualitative** half — *why* did the supervisor (mis)decide on the hard rows, especially the near-miss ⚠️ declines.
After a batch:

1. Build `cases.json` from the captured fan-out traces (one row per trace: `prompt`, `final_answer`,
   `want_fanout`, the `axis` tag, the per-branch carrier counts, GoalJudge rationale). Extra keys survive to dataset
   metadata.
2. Serve the coder, **human-code** each near-miss row: tags like `near-miss-fanned-out` (a GAIA failure),
   `decline-correct`, `branch-objective-vague`, `join-dropped-survivor`. Trace is ground truth, narration is a
   suspect claim (the skill's cardinal rule) — code what the `Send` carriers and join actually did, not what the
   supervisor's reason text *claimed*.
3. Export to a Langfuse dataset (`fanout-open-coding`) for paginated review; the codes roll up (via
   `llm-eval-grounded-theory`) into whether condition 2's dependency signal needs sharpening.

This is **not** for first-pass code generation (the skill forbids LLM-authored first-pass codes) — it's the
human-in-the-loop error analysis of the decline discrimination, which is exactly the part most likely to be wrong.

## 10. Open questions before build

1. ~~Condition 2's deterministic dependency signal~~ **SPECCED** —
   [`t3_supervisor_plan.component.md` §3a](t3_supervisor_plan.component.md). The detector reuses T1's existing
   sequencing markers ([`router.py:224-227`](../../components/router.py) /
   [`plan_builder.py:46-55`](../../components/plan_builder.py)) **inverted** (markers that promote depth = markers
   that mean "dependent → decline"), plus a structural **shared-write-target** signal that pure lexical scanning
   misses. It runs over the T1 plan steps (not the raw prompt). Each near-miss ⚠️ decline row in §4.2 is built to
   trip a *named* signal (the crosswalk is in §3a) — detector and corpus are co-designed and validated against each
   other via the `fp` cell of the fan-out confusion matrix (§7). **Residual:** unmarked *semantic* chains are a
   documented false-negative (acceptable by the cost asymmetry; an LLM third-gate is deferred to T3.1).
2. ~~Fault injection mechanism~~ **SPECCED** — §4.3a above. Two layers: **objective-level** (a guaranteed-missing
   resource / empty-output instruction) for the hard-error + degraded modes — these exercise the *real* error and
   degraded-input paths with nothing stubbed; and an **env-gated dispatch-shim** (`FANOUT_FAULT_INJECT=1` + a magic
   objective token) for the two *timing* modes (timeout, straggler) that a prompt can't make deterministic. Surfaced
   a **hard build dependency**: the worker node MUST wrap dispatch in try/except → sentinel, because a raising Send
   branch cancels the whole super-step ([[t3-supervisor-fanout-research]]) — that sentinel is the unit these rows
   test. Scoring `want_survives_partial` = sentinel-observed AND non-empty-answer AND no-super-step-hang (§4.3a).
3. ~~L2 trigger for `independent-L2-decompose-10`~~ **RESOLVED** — §4.1a above. Reading the scorer
   ([router.py:97-229](../../components/router.py)) surfaced a real finding: **every shape that reliably fires L2 is
   sequentially dependent** — the scorer's L2 vocabulary ≈ the §3a decline vocabulary. The row threads it by
   borrowing L2's *structural* levers (`(1)(2)(3)` as per-branch **sub-fields**, ≥35 words) while avoiding every
   dependency marker, so the depth scorer scores L2 but the dependency detector sees clean independence.
   **Two-gate, fail-graceful:** `want_fanout=True` is primary and does *not* need L2 (fan-out declines only at L0);
   `want_depth="L2"` is a secondary, non-gating observation. If calibration shows L1, the row drops to documenting
   "fan-out works at L1; L2 is empirically dependency-coupled in this scorer" — a finding, not a gap.

---

### Cross-references
- Mechanism / contract: [`t3_supervisor_plan.component.md`](t3_supervisor_plan.component.md)
- Why / acceptance / §8.2 spec: [`planning_pipeline_tiered_loops.plan.md`](planning_pipeline_tiered_loops.plan.md) §3.5a, §8.2
- Build sequence (Phase 4): [`planning_pipeline_tiered_loops.impl.md`](planning_pipeline_tiered_loops.impl.md) §7
- Builder to extend: [`build_planning_stress_corpus.py`](../../scripts/build_planning_stress_corpus.py)
- Analyzer to extend: [`analyze_planning_traces.py`](../../scripts/analyze_planning_traces.py) `score_run`
- Hand-coding skill: [`agentsframework-open-coding`](../skills/agentsframework-open-coding/SKILL.md)
