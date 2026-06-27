# Planning-floor baseline — case-by-case walkthrough

**Generated:** 2026-06-17 by `scripts/report_planning_floor_walkthrough.py` (every *Actual* value is computed live against `components/`, not transcribed).

**Corpus:** `cache/goaljudge_eval/planning_floor_strata.jsonl` (59 rows) · **Harness:** `scripts/diagnose_planning_floor.py`

**Scope:** the case-by-case body is offline, deterministic, zero-cost — no LLM, no network, no deploy; each row is scored only on the surface(s) whose `want_*` field is set. The final **Tier 1 cross-check** section additionally reads a once-captured LLM checklist fixture (if present) for comparison.

## Scorecard

| Surface | Pass | Total | % |
|---------|------|-------|---|
| depth | 27 | 31 | 87.1% |
| branches | 11 | 11 | 100.0% |
| conditions | 4 | 4 | 100.0% |
| mece | 5 | 5 | 100.0% |
| replan | 8 | 8 | 100.0% |
| **OVERALL** | **55** | **59** | **93.2%** |

## 1. Depth selection (`select_planning_depth`)

| # | id | Prompt / input | Expected | Actual | ✓ | Signals & reasoning |
|---|----|----------------|----------|--------|---|---------------------|
| 1 | `depth-l0-1` | Print the current working directory. | `L0` | `L0` | ✅ | count=0; wc=5; reason=simple-initial-task<br/>**why:** bare single action |
| 2 | `depth-l0-2` | Delete the file temp.log. | `L0` | `L0` | ✅ | count=0; wc=4; reason=simple-initial-task<br/>**why:** single mutation, short |
| 3 | `depth-l0-trap-1` | Create the file /var/lib/app/data/cache/segments/region-eu-west-1/shard-0007/index.meta.js… | `L0` | `L0` | ✅ | count=0; wc=4; reason=simple-initial-task<br/>**why:** TRAP: long path, single create -> stays L0 (not long-task-floor) |
| 4 | `depth-l0-trap-2` | Write OK to /opt/services/payments/config/feature-flags/rollout/canary/state.txt | `L0` | `L0` | ✅ | count=0; wc=4; reason=simple-initial-task<br/>**why:** TRAP: long path single write -> L0 |
| 5 | `depth-l1-1` | Investigate the latency regression. | `L1` | `L1` | ✅ | count=0; wc=4, strong-verb=investigate; reason=strong-intent-verb<br/>**why:** strong-intent verb floor |
| 6 | `depth-l1-2` | Audit the dependency tree. | `L1` | `L1` | ✅ | count=0; wc=4, strong-verb=audit; reason=strong-intent-verb<br/>**why:** strong-intent verb floor |
| 7 | `depth-l1-3` | Build the index and then verify it loads. | `L1` | `L1` | ✅ | count=0; wc=8, conj, strong-verb=build; reason=strong-intent-verb<br/>**why:** and-then sequencing -> L1 |
| 8 | `depth-l1-4` | Explain what happens to in-flight requests when the load balancer drains a backend, how co… | `L1` | `L1` | ✅ | count=0; wc=29, conj; reason=moderate-complexity-initial-task<br/>**why:** >=25 words, no stacked markers -> L1 |
| 9 | `depth-l2-1` | Compare Kafka and RabbitMQ for our event bus, (1) measure throughput (2) test ordering gua… | `L2` | `L2` | ✅ | count=0; wc=27, markers=[compare,migration], conj, enum=3, strong-verb=compare; reason=high-complexity-initial-task<br/>**why:** 3 stacked signals -> high-complexity |
| 10 | `depth-l2-2` | Orders intermittently vanish from the dashboard after a successful checkout; trace how the… | `L2` | `L2` | ✅ | count=0; wc=30, conj, incident=[trace how,propagat,identify every,intermitt]; reason=incident-narrative<br/>**why:** incident markers + length -> L2 |
| 11 | `depth-l2-trap-1` | Audit the current deployment architecture, design a migration to the new region, refactor … | `L2` | `L1` | ❌ **MISS** | count=0; wc=31, markers=[architecture,migration,refactor,roadmap,design], conj, strong-verb=audit; reason=moderate-complexity-initial-task<br/>**why:** TRAP: multi-marker prose, intended L2 (known L2->L1 miss) |
| 12 | `depth-l2-trap-2` | Redesign the ingestion pipeline, migrate the existing jobs onto it, and refactor the downs… | `L2` | `L1` | ❌ **MISS** | count=0; wc=20, markers=[refactor,design], conj, strong-verb=redesign; reason=moderate-complexity-initial-task<br/>**why:** TRAP: redesign+migrate+refactor prose -> intended L2 |
| 13 | `depth-l2-trap-3` | Investigate the recurring OOM, design a memory-budget guard, and refactor the hot allocati… | `L2` | `L1` | ❌ **MISS** | count=0; wc=21, markers=[refactor,design], conj, strong-verb=investigate; reason=moderate-complexity-initial-task<br/>**why:** TRAP: investigate+design+refactor prose -> intended L2 |
| 14 | `depth-l2-trap-4` | Architect a multi-region failover story, design the data replication, and migrate the cont… | `L2` | `L1` | ❌ **MISS** | count=0; wc=16, markers=[design], conj; reason=moderate-complexity-initial-task<br/>**why:** TRAP: architecture+design+migrate prose -> intended L2 |
| 15 | `count-fresh-1` | Compare Kafka and RabbitMQ for our event bus, (1) measure throughput (2) test ordering (3)… | `L2` | `L2` | ✅ | count=0; wc=21, markers=[compare], conj, enum=3, strong-verb=compare; reason=high-complexity-initial-task<br/>**why:** count=0 -> real depth L2 (proves no leak from short-circuit) |
| 16 | `count-posttool-1` | Compare Kafka and RabbitMQ for our event bus, (1) measure throughput (2) test ordering (3)… | `L0` | `L0` | ✅ | count=2; wc=21, markers=[compare], conj, enum=3, strong-verb=compare; reason=post-tool-synthesis<br/>**why:** count>0 -> MUST be L0 post-tool-synthesis (GJ-012 short-circuit) |
| 17 | `count-fresh-2` | Investigate the latency regression. | `L1` | `L1` | ✅ | count=0; wc=4, strong-verb=investigate; reason=strong-intent-verb<br/>**why:** count=0 -> real depth L1 (proves no leak from short-circuit) |
| 18 | `count-posttool-2` | Investigate the latency regression. | `L0` | `L0` | ✅ | count=2; wc=4, strong-verb=investigate; reason=post-tool-synthesis<br/>**why:** count>0 -> MUST be L0 post-tool-synthesis (GJ-012 short-circuit) |
| 19 | `count-fresh-3` | Build the index and then verify it loads. | `L1` | `L1` | ✅ | count=0; wc=8, conj, strong-verb=build; reason=strong-intent-verb<br/>**why:** count=0 -> real depth L1 (proves no leak from short-circuit) |
| 20 | `count-posttool-3` | Build the index and then verify it loads. | `L0` | `L0` | ✅ | count=2; wc=8, conj, strong-verb=build; reason=post-tool-synthesis<br/>**why:** count>0 -> MUST be L0 post-tool-synthesis (GJ-012 short-circuit) |
| 21 | `oracle-1` | Echo the phrase quarterly review verbatim. | `L0` | `L0` | ✅ | count=0; wc=6; reason=simple-initial-task<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 22 | `oracle-2` | Overwrite /workspace/status.txt with the single character OK. | `L0` | `L0` | ✅ | count=0; wc=7; reason=simple-initial-task<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 23 | `oracle-3` | Read the first line of /workspace/notes.txt and print it. | `L0` | `L0` | ✅ | count=0; wc=9, conj; reason=simple-initial-task<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 24 | `oracle-4` | Add caching and then update the docs. | `L1` | `L1` | ✅ | count=0; wc=7, conj; reason=sequenced-multistep<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 25 | `oracle-5` | Design a rate limiter for the API. | `L1` | `L1` | ✅ | count=0; wc=7, markers=[design], strong-verb=design; reason=strong-intent-verb<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 26 | `oracle-6` | Plan the Postgres migration. | `L1` | `L1` | ✅ | count=0; wc=4, markers=[migration], strong-verb=plan; reason=strong-intent-verb<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 27 | `oracle-7` | Refactor the auth module. | `L1` | `L1` | ✅ | count=0; wc=4, markers=[refactor], strong-verb=refactor; reason=strong-intent-verb<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 28 | `oracle-8` | Walk me through what the login endpoint does when a session cookie is present but expired,… | `L1` | `L1` | ✅ | count=0; wc=31, conj; reason=long-task-floor<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 29 | `oracle-9` | Compare Redis and Memcached for our cache, (1) benchmark read latency (2) measure memory o… | `L2` | `L2` | ✅ | count=0; wc=22, markers=[compare], conj, enum=3, strong-verb=compare; reason=high-complexity-initial-task<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 30 | `oracle-10` | Our checkout sometimes double-charges customers when the payment provider times out but la… | `L2` | `L2` | ✅ | count=0; wc=39, conj, incident=[figure out,times out,sometimes]; reason=incident-narrative<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |
| 31 | `oracle-11` | Users report the feed shows stale posts after they publish; trace how a write propagates t… | `L2` | `L2` | ✅ | count=0; wc=32, conj, incident=[trace how,propagat,identify every]; reason=incident-narrative<br/>**why:** imported from depth_strata_rich.jsonl (depth regression guard) |

## 2. Branch extraction (`_extract_branches`)

| # | id | Prompt / input | Expected | Actual | ✓ | Signals & reasoning |
|---|----|----------------|----------|--------|---|---------------------|
| 1 | `branch-lines-1` | Set up the database Seed the fixtures Run the smoke test | `3` | `3` | ✅ | branches=[Set up the database \| Seed the fixtures \| Run the smoke test]<br/>**why:** 3 newline chunks |
| 2 | `branch-bullets-1` | - provision the bucket - set the lifecycle policy - enable versioning | `3` | `3` | ✅ | branches=[provision the bucket \| set the lifecycle policy \| enable versioning]<br/>**why:** 3 bullet markers stripped |
| 3 | `branch-enum-1` | Do the rollout in order: (1) drain traffic (2) deploy (3) re-enable traffic | `4` | `4` | ✅ | branches=[Do the rollout in order: \| drain traffic \| deploy \| re-enable traffic]<br/>**why:** lead-in clause + (1)(2)(3) -> 4 branches |
| 4 | `branch-enum-2` | (1) drain traffic (2) deploy the build (3) re-enable traffic | `3` | `3` | ✅ | branches=[drain traffic \| deploy the build \| re-enable traffic]<br/>**why:** pure (1)(2)(3) enumeration, no lead-in -> 3 |
| 5 | `branch-comma-and-1` | Back up the volume, snapshot the metadata, and detach the disk. | `3` | `3` | ✅ | branches=[Back up the volume \| snapshot the metadata \| detach the disk]<br/>**why:** X, Y, and Z imperative -> 3 (comma-then-and) |
| 6 | `branch-then-1` | Compile the assets, then upload them to the CDN. | `2` | `2` | ✅ | branches=[Compile the assets \| upload them to the CDN]<br/>**why:** , then -> 2 imperative clauses |
| 7 | `branch-single-1` | Restart the worker pool. | `1` | `1` | ✅ | branches=[Restart the worker pool]<br/>**why:** single action -> 1 branch |
| 8 | `branch-trap-path-1` | Open /workspace/f3.txt and read it. | `1` | `1` | ✅ | branches=[Open /workspace/f3.txt and read it]<br/>**why:** TRAP: /workspace/f3.txt must not sentence-split |
| 9 | `branch-trap-version-1` | Pin the dependency to v1.2.3 in the lockfile. | `1` | `1` | ✅ | branches=[Pin the dependency to v1.2.3 in the lockfile]<br/>**why:** TRAP: v1.2.3 must not sentence-split |
| 10 | `branch-trap-nounphrase-1` | Summarize the trade-offs and risks of the new design. | `1` | `1` | ✅ | branches=[Summarize the trade-offs and risks of the new design]<br/>**why:** TRAP: 'trade-offs and risks' is a noun phrase, 1 branch |
| 11 | `branch-trap-nounphrase-2` | Document the costs and benefits of the migration. | `1` | `1` | ✅ | branches=[Document the costs and benefits of the migration]<br/>**why:** TRAP: 'costs and benefits' noun phrase -> 1 branch |

## 3. Success conditions (`derive_success_conditions`)

| # | id | Prompt / input | Expected | Actual | ✓ | Signals & reasoning |
|---|----|----------------|----------|--------|---|---------------------|
| 1 | `cond-single-1` | Restart the worker pool. | `2 conds, tail=True` | `2 conds, tail=True` | ✅ | 1 branches -> 2 conditions (incl. generic tail)<br/>**why:** 1 branch -> 1 condition + generic tail = 2 |
| 2 | `cond-three-1` | Back up the volume, snapshot the metadata, and detach the disk. | `4 conds, tail=True` | `4 conds, tail=True` | ✅ | 3 branches -> 4 conditions (incl. generic tail)<br/>**why:** 3 branches -> 3 conditions + tail = 4 |
| 3 | `cond-cap-1` | Do these in order: (1) alpha (2) bravo (3) charlie (4) delta (5) echo (6) foxtrot (7) golf… | `7 conds, tail=True` | `7 conds, tail=True` | ✅ | 9 branches -> 7 conditions (incl. generic tail)<br/>**why:** 8 branches -> capped 6 conditions + tail = 7 (cap holds) |
| 4 | `cond-dedup-1` | Restart the worker pool Restart the worker pool Restart the worker pool | `2 conds, tail=True` | `2 conds, tail=True` | ✅ | 3 branches -> 2 conditions (incl. generic tail)<br/>**why:** duplicate branches dedup to 1 condition + tail = 2 |

## 4. MECE structure gate (`validate_plan_mece`)

| # | id | Prompt / input | Expected | Actual | ✓ | Signals & reasoning |
|---|----|----------------|----------|--------|---|---------------------|
| 1 | `mece-valid-1` | (plan fixture) | `valid=True` | `valid=True` | ✅ | no issues<br/>**why:** contiguous ids, distinct goals, non-empty conds -> valid |
| 2 | `mece-dupgoal-1` | (plan fixture) | `valid=False, issue~'overlapping goals'` | `valid=False` | ✅ | ordered_steps contain overlapping goals; plan is not MECE.<br/>**why:** duplicate goals -> not MECE |
| 3 | `mece-noncontig-1` | (plan fixture) | `valid=False, issue~'contiguous step_id'` | `valid=False` | ✅ | ordered_steps must use contiguous step_id values starting at 1.<br/>**why:** step ids 1,3 not contiguous -> invalid |
| 4 | `mece-emptygoal-1` | (plan fixture) | `valid=False, issue~'non-empty goal'` | `valid=False` | ✅ | each step must define a non-empty goal.<br/>**why:** blank goal -> invalid |
| 5 | `mece-noconds-1` | (plan fixture) | `valid=False, issue~'success_conditions'` | `valid=False` | ✅ | success_conditions must include at least one completion criterion.<br/>**why:** empty success_conditions -> invalid |

## 5. Replan gate (`plan_is_stale`)

| # | id | Prompt / input | Expected | Actual | ✓ | Signals & reasoning |
|---|----|----------------|----------|--------|---|---------------------|
| 1 | `replan-ok-fail` | Build the index and then verify it loads. | `True` | `True` | ✅ | last_tool_result={'ok': False, 'tool_name': 'shell', 'output': ''}<br/>**why:** ok=False -> stale |
| 2 | `replan-error` | Build the index and then verify it loads. | `True` | `True` | ✅ | last_tool_result={'ok': True, 'error': 'permission denied', 'tool_name': 'file_io'}<br/>**why:** non-empty error -> stale |
| 3 | `replan-outcome-failed` | Build the index and then verify it loads. | `True` | `True` | ✅ | last_tool_result={'outcome': 'failed', 'tool_name': 'http'}<br/>**why:** outcome=failed -> stale |
| 4 | `replan-surprising` | Build the index and then verify it loads. | `True` | `True` | ✅ | last_tool_result={'ok': True, 'surprising': True, 'tool_name': 'shell'}<br/>**why:** surprising flag -> stale |
| 5 | `replan-replan-flag` | Build the index and then verify it loads. | `True` | `True` | ✅ | last_tool_result={'ok': True, 'replan': True, 'tool_name': 'shell'}<br/>**why:** replan flag -> stale |
| 6 | `replan-clean` | Build the index and then verify it loads. | `False` | `False` | ✅ | last_tool_result={'ok': True, 'output': 'index built', 'tool_name': 'shell'}<br/>**why:** clean success -> NOT stale (continues to evaluate) |
| 7 | `replan-clean-2` | Build the index and then verify it loads. | `False` | `False` | ✅ | last_tool_result={'ok': True, 'outcome': 'success', 'output': 'ok', 'tool_name': 'file_io'}<br/>**why:** explicit success outcome -> NOT stale |
| 8 | `replan-none` | Build the index and then verify it loads. | `False` | `False` | ✅ | last_tool_result=None<br/>**why:** no tool result -> NOT stale (nothing to invalidate) |

## Divergence deep-dive

4 divergence(s). Each is a recorded baseline miss, surfaced not hidden.

**Root cause (all four are one failure mode).** The additive scorer needs `score >= 3` for L2. `has_multi_part_marker` contributes **+1 regardless of how many markers match** (it is a single boolean), and word count only adds points at >=35 / >=80. So a multi-marker *prose* task — many strong verbs but <35 words and no enumeration — tops out at score 2 (marker +1, conjunction +1) and fires `moderate-complexity-initial-task` (L1). Enumeration `(1)(2)(3)` is the orthogonal signal that pushes the comparable L2 rows over the line; prose lacks it. This is the single systematic residual and the only thing an Option A/B depth rule could move (e.g. a `distinct_marker_count >= 3 -> L2` rule).

### `depth-l2-trap-1` — depth (family: `l2-under-promote`)

- **Prompt:** Audit the current deployment architecture, design a migration to the new region, refactor the routing layer to support it, and produce a staged rollout roadmap with rollback criteria for each phase.
- **Expected:** `L2`  **Actual:** `L1`
- **Signals:** count=0; wc=31, markers=[architecture,migration,refactor,roadmap,design], conj, strong-verb=audit; reason=moderate-complexity-initial-task
- **Reading:** TRAP: multi-marker prose, intended L2 (known L2->L1 miss)

### `depth-l2-trap-2` — depth (family: `l2-under-promote`)

- **Prompt:** Redesign the ingestion pipeline, migrate the existing jobs onto it, and refactor the downstream consumers so nothing breaks during cutover.
- **Expected:** `L2`  **Actual:** `L1`
- **Signals:** count=0; wc=20, markers=[refactor,design], conj, strong-verb=redesign; reason=moderate-complexity-initial-task
- **Reading:** TRAP: redesign+migrate+refactor prose -> intended L2

### `depth-l2-trap-3` — depth (family: `l2-under-promote`)

- **Prompt:** Investigate the recurring OOM, design a memory-budget guard, and refactor the hot allocation path to stay under it across all tiers.
- **Expected:** `L2`  **Actual:** `L1`
- **Signals:** count=0; wc=21, markers=[refactor,design], conj, strong-verb=investigate; reason=moderate-complexity-initial-task
- **Reading:** TRAP: investigate+design+refactor prose -> intended L2

### `depth-l2-trap-4` — depth (family: `l2-under-promote`)

- **Prompt:** Architect a multi-region failover story, design the data replication, and migrate the control plane without downtime.
- **Expected:** `L2`  **Actual:** `L1`
- **Signals:** count=0; wc=16, markers=[design], conj; reason=moderate-complexity-initial-task
- **Reading:** TRAP: architecture+design+migrate prose -> intended L2

## Tier 1 cross-check — checklist length vs fired depth cap

Cross-references the deterministic depth verdict above with the **Tier 1** offline probe ([`planning_floor_outcome_validation.tier1_results.md`](planning_floor_outcome_validation.tier1_results.md)): a once-captured, 3-sample `TaskUnderstanding.success_conditions` checklist per prompt. The checklist is generated **at plan time, independent of the fired depth**, so `effective_len > cap` (generic tail removed) is an offline under-budgeting signal. **Caveat (results §2a):** checklist length over-reads the step cap by a near-constant offset — every L0 task is "over cap" too — so read the trap rows *relative to* their correctly-fired L1 peers, not in absolute terms.

| id | det. depth (want→fired) | det. ✓ | cap | checklist len ×3 | spread | over cap? |
|----|-------------------------|--------|-----|------------------|--------|-----------|
| `depth-l0-1` | L0→L0 | ✅ | 1 | 3,3,3 | 0 | **yes** |
| `depth-l0-2` | L0→L0 | ✅ | 1 | 3,3,3 | 0 | **yes** |
| `depth-l0-trap-1` | L0→L0 | ✅ | 1 | 3,3,3 | 0 | **yes** |
| `depth-l0-trap-2` | L0→L0 | ✅ | 1 | (gate-rej) | — | — |
| `depth-l1-1` | L1→L1 | ✅ | 3 | 4,3,3 | 1 | no ⚠FLIP |
| `depth-l1-2` | L1→L1 | ✅ | 3 | 4,4,4 | 0 | **yes** |
| `depth-l1-3` | L1→L1 | ✅ | 3 | 2,3,3 | 1 | no |
| `depth-l1-4` | L1→L1 | ✅ | 3 | 3,3,3 | 0 | no |
| `depth-l2-1` | L2→L2 | ✅ | 5 | 5,5,5 | 0 | no |
| `depth-l2-2` | L2→L2 | ✅ | 5 | 4,4,4 | 0 | no |
| `depth-l2-trap-1` | L2→L1 | ❌ | 3 | 4,4,4 | 0 | **yes** |
| `depth-l2-trap-2` | L2→L1 | ❌ | 3 | 4,4,4 | 0 | **yes** |
| `depth-l2-trap-3` | L2→L1 | ❌ | 3 | 4,4,4 | 0 | **yes** |
| `depth-l2-trap-4` | L2→L1 | ❌ | 3 | 3,3,3 | 0 | no |
| `count-fresh-1` | L2→L2 | ✅ | 5 | 4,4,4 | 0 | no |
| `count-fresh-2` | L1→L1 | ✅ | 3 | 4,3,3 | 1 | no ⚠FLIP |
| `count-fresh-3` | L1→L1 | ✅ | 3 | 2,3,2 | 1 | no |
| `oracle-1` | L0→L0 | ✅ | 1 | 2 | 0 | **yes** |
| `oracle-2` | L0→L0 | ✅ | 1 | 3,3,3 | 0 | **yes** |
| `oracle-3` | L0→L0 | ✅ | 1 | 2,2,3 | 1 | **yes** |
| `oracle-4` | L1→L1 | ✅ | 3 | 2,3,3 | 1 | no |
| `oracle-5` | L1→L1 | ✅ | 3 | 4,4,4 | 0 | **yes** |
| `oracle-6` | L1→L1 | ✅ | 3 | 4,5,5 | 1 | **yes** |
| `oracle-7` | L1→L1 | ✅ | 3 | 4,3,3 | 1 | no ⚠FLIP |
| `oracle-8` | L1→L1 | ✅ | 3 | 3,3,3 | 0 | no |
| `oracle-9` | L2→L2 | ✅ | 5 | 4,4,4 | 0 | no |
| `oracle-10` | L2→L2 | ✅ | 5 | 4,3,4 | 1 | no |
| `oracle-11` | L2→L2 | ✅ | 5 | 4,4,4 | 0 | no |

**Reading.** The 3 multi-marker prose traps (`depth-l2-trap-1/2/3`) fire L1 (cap 3) yet stably return a 4-item checklist (spread 0) → the floor budgets fewer steps than the task's own success criteria, corroborating the divergence deep-dive above. `depth-l2-trap-4` stably returns 3 (a corpus-label question, not a floor miss). Rows marked ⚠FLIP straddle the cap across samples (the 3-sample variance guard surfaced them) — honestly inconclusive, not signal. This raises the ROI of an Option A `distinct_marker_count >= 3 -> L2` rule but, per the §2a caveat, is *corroborating* not *causal* — a live A/B (Tier 2) remains the only test of "deeper → better answer."
