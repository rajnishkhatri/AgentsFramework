# Where to spend the days — T3 finish vs. governance-trace enforcement gate

**Status:** scoping note — **2026-06-17**. No code changes; decision input only.
**Context:** after the planning-floor research arc landed on "do-nothing on the floor; spend the engineering days on the unbuilt T3 nodes or the open governance-trace gate," this note scopes both **against the actual code** (not memory) so the choice is made on facts.
**Headline correction:** the T3 "empty-answer" defect that memory flagged as open is **already fixed** (commit `2b9e58a`, `langgraph_runtime.py:680-708` — the comment literally names "(Stage B live defect)"). That changes T3 from "chase a live defect" to "harden a feature that already works behind a flag."

---

## 1. Ground truth (verified in code today)

### T3 supervisor fan-out
- **Nodes exist and are wired:** `supervisor_node` / `worker_node` / `join_node` in `orchestration/react_loop.py:2336-2561`, gated by `agent_config.t3_fanout_enabled` (**default OFF** → graph byte-identical to the pre-T3 spine).
- **The join produces a real answer:** `join_node` returns `{"messages": [AIMessage(content=joined)], "last_final_answer": joined}` with a deterministic floor that *guarantees non-empty* even on total branch failure (`react_loop.py:2512-2525`).
- **The UI-stream defect is fixed:** `langgraph_runtime.py:680-708` emits the `Started/Token/Ended` trio from `last_final_answer`, resolving the empty-stream Stage B defect.
- **Governance carriers are present:** per-branch `delegation_requested/completed`, `STEP_EXECUTED` token carriers, `ERROR_OCCURRED` sentinels, `decision_id` join keys — all already emitted (the last commit `eaf1fcf` hardened exactly these).
- **Test coverage exists but is thin:** 5 test files touch fan-out (`test_supervisor_plan.py`, `test_tier_topology_sim.py`, `test_agent_runtime_composition.py`, + 2 script tests); the stream-fix itself has an L1 guard (`TestChainEndJoinAnswer`, 5 tests). **No live/e2e test of the flag-ON join→stream path** — Stage B was validated by a manual GCP run, not a committed test.
- **One open layer-cleanliness debt (AP-5):** the `supervisor`/`worker`/`join` nodes (78/111/59 lines) carry extractable logic — a thin-node violation flagged in the earlier review. Pulling the join synthesis into a pure component (and unit-testing the message-delta shape) is the natural place to also lock in the stream fix.

### Governance-trace enforcement gate
- **Trace is recorded everywhere:** `PhaseLogger.phase()` / `log_decision()` wrap every phase (init/validation/routing/completion) and the T3 fan-out decision — emitting join-keyed carriers for the four pillars (Reasoning / Recording / Validation / Identity).
- **But it is record-only, audited post-hoc:** the *only* `raise` in `phase_logger.py` (line 203) is a storage-write failure re-raise — **there is no check that a pillar carrier is actually present at a phase boundary.** Pillar completeness is assessed *after the fact* by the `governance-trace-audit` skill (96% vs 41% baseline), never enforced inline.
- **The gap = no inline gate:** nothing fails — loudly or softly — when a phase completes missing its pillar carrier. A "silent skip" is structurally possible; today it is only *caught later by a human running the skill*, never by the pipeline itself.

---

## 2. The research argument (why the gate looks more valuable now)

[arXiv 2603.01548](https://arxiv.org/abs/2603.01548) (the deterministic-routing finding from the fresh scan): *"binary observability — every failure is either a logged reroute or an explicit escalation, **never a silent skip**."* That is precisely the property the governance trace **lacks today** — it logs, but it cannot *guarantee* a missing carrier surfaces. [MAST](https://github.com) puts **Verification & Termination at 21.3%** of agent failures — a distinct, large bucket that an inline completeness gate directly attacks. By contrast, no 2026 finding argues T3 fan-out is the high-value gap (the prior T3 research itself concluded *throughput is not the win; seam-cleanliness + observability + MAST-bounding is* — and that's already built).

**Net:** the research tilts toward the **governance gate** — it converts an *audited-after* property into an *enforced-during* one, which is the exact "no silent skip" guarantee the literature now treats as best practice. T3 is a feature to *finish*; the gate is a capability to *add*.

---

## 3. Scoping ledger

| Dimension | **T3 finish/harden** | **Governance enforcement gate** |
|-----------|----------------------|----------------------------------|
| **What "done" means** | Flag-ON path has a committed e2e regression test (join→stream, partial-survival, fault-inject); decision to flip default or keep OFF is made on evidence | At each phase boundary, a deterministic check asserts the required pillar carrier(s) exist; missing → shadow-warn first, then a real gate (raise/degrade); audit skill's post-hoc role shrinks to spot-checks |
| **Net-new capability?** | No — hardening + test debt on a working feature | **Yes** — "binary observability / no silent skip" the pipeline cannot currently guarantee |
| **Touches hot path?** | No (flag OFF; tests exercise it in isolation) | **Yes** — runs on every workflow phase; must be O(1) and fail-safe (a gate bug must not brick prod) |
| **Effort** | **S–M** — wiring is done; mostly a deterministic e2e test + a flag-flip decision memo | **M–L** — design the pillar-completeness contract per phase, shadow-instrument, then gate; needs a rollout (shadow→warn→enforce) like GoalJudge |
| **Risk** | **Low** — isolated behind a default-OFF flag | **Medium** — it's on the hot path; mitigated by shadow-first + the deterministic-O(1) discipline the floor research already established |
| **Reversibility** | Trivial (flag) | Shadow phase is free; the enforce phase needs the same `deterministic→shadow→consume` discipline + a kill switch |
| **Dependencies** | None new | A per-phase "required carriers" spec (small); reuse `PhaseLogger` + the audit skill's existing pillar rubric as the oracle |
| **Strategic fit** | Closes a started workstream; de-risks a seam you may never turn on | Directly realizes the 2603.01548 best practice + attacks MAST's 21.3% verification bucket; compounds the value of all the trace carriers already emitted |

---

## 4. Honest recommendation

**Do a thin slice of *both*, in this order — T3 test-debt first (cheap, closes a loop), then the governance gate as the real project.**

1. **First, ~half a day: pay T3's test debt.** Write the one committed e2e test that proves flag-ON join→stream works (the thing Stage B validated only manually). This is cheap, it *locks in* the `2b9e58a` fix against regression, and it lets you stop carrying T3 as "unfinished" mentally. **Do not flip the default flag** — the T3 research already concluded fan-out's value isn't throughput and the corpus has ~0 parallel tasks; keep it OFF, just make it *trustworthy when on*.

2. **Then, the governance enforcement gate is the real spend.** It is the only one of the two that is *net-new capability backed by current research*. Build it the way the floor research taught: **deterministic, O(1), shadow-first.** Phase 1 = a `validate_phase_carriers(phase, recorded)` pure check that *warns* on a missing pillar carrier (record-only, like the floor's `would_downgrade`); Phase 2 = promote to a gate (raise in dev / degrade-with-loud-trace in prod) once the shadow phase shows the warn rate is real-signal not false-positive. Reuse the audit skill's pillar rubric as the *oracle* for the check, exactly like `depth_strata_rich.jsonl` is the oracle for depth.

**Why this order and not "just the gate":** the T3 test is so cheap and the mental-overhead of an unfinished seam so real that paying it first is worth the half-day; but it is *not* where the strategic value is, so it stays a chore, not the project. The governance gate is where the research says the value moved — turning the trace from *auditable* into *self-enforcing* is the "no silent skip" property, and it makes every carrier you already emit load-bearing instead of advisory.

**What I would NOT do:** flip the T3 default ON (no demand, ~0 parallel corpus, MAST warns multi-agent underperforms single-agent), or build the gate enforce-phase before a shadow phase proves the warn signal (same trap the floor research flagged — gating before calibration is theater).

---

## 5. Open decisions

| ID | Question | Recommendation |
|----|----------|----------------|
| NW-1 | Both, T3-only, or gate-only? | **Both, gate as the project** — T3 test is a half-day chore, gate is the strategic build |
| NW-2 | Governance gate: where does the per-phase "required carriers" spec live? | A pure dict/Pydantic in `services/governance/` (data), checked by a pure `validate_phase_carriers` — no I/O, L1-testable, mirrors the floor's component discipline |
| NW-3 | Shadow→enforce trigger for the gate | Promote only after a shadow run shows the missing-carrier warn rate is real (not false-positive on legitimate phase-skips) — calibrate before gating |
| NW-4 | T3 default flag | **Keep OFF** — make it trustworthy-when-on; do not enable |

*Scoping only. No implementation implied until a plan references §4.*
