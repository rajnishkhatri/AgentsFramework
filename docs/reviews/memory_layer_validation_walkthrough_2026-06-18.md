# Memory Layer — End-to-End Validation Walkthrough (2026-06-18)

This is the session record for validating the live memory layer on the `mem` tag
of `agent-backend-combined`. Every validation point from
[`memory_layer_wiring.plan.md`](../plans/memory_layer_wiring.plan.md) is exercised
below as a **case**: prompt input → expected output → actual result → Langfuse
trace confirmation.

**Trace under audit:** workflow `ef236f957b6c4e64a723bee71d857d5b`
(`/tmp/memory_trace_ef236f95.json`, 20 observations) — the first authenticated
run to emit memory carriers after the `app_prod.py` wiring fix.
**Subject:** `user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX` (real WorkOS sub).
**Companion reports:** [governance_audit_ef236f95_2026-06-18.md](governance_audit_ef236f95_2026-06-18.md) · [governance_audit_memory_on_2026-06-18.md](governance_audit_memory_on_2026-06-18.md).

---

## Session overview — three turns, two phases

| # | Turn (prompt) | Trace | Phase | Carriers? |
|---|---|---|---|---|
| A | `hello. i am rajnish` | `66a49983…` (15:07 UTC) | PRE-fix | ❌ none (memory-blind graph) |
| B | `Remember that I prefer all measurements in metric units.` | `43cb3411…` (15:08 UTC) | PRE-fix | ❌ none |
| C | `my son name is garvit` | `ef236f95…` (16:28 UTC) | POST-fix | ✅ recalled(3) + stored + autocapture |

The pre-fix runs (A, B) are themselves a validation point: they prove the
diagnosis (no carriers despite `MEMORY_ENABLED=true`) and that the fix changed
the outcome. The recalled memories in run C ("i am rajnish", "metric units") are
literally the stored results of turns A and B — proving the full
**store → recall → inject** loop across turns.

---

## PART 1 — Live runtime validation (the authenticated run)

### Case C1 — Recall fires and is observable

| | |
|---|---|
| **Prompt input** | `my son name is garvit` (3rd turn, same authenticated user) |
| **Expected** | A `memory.recalled` carrier at the route seam with `{user_id, count, query_len}` — **no query text** |
| **Actual** | ✅ `memory.recalled` (step 3): `{"user_id": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX", "count": "3", "query_len": "21"}` |
| **Trace confirmation** | Observation `memory.recalled`, type SPAN, step 3. `count="3"` = three prior memories retrieved; `query_len="21"` = `len("my son name is garvit")`. No payload/query string on the wire. |

### Case C2 — Recalled memory is injected into the system prompt (the point of recall)

| | |
|---|---|
| **Prompt input** | (same run C) — recall query = `task_input` |
| **Expected** | The top-k recalled records folded into `additional_instructions` of the `call_llm` system prompt (Pattern H6), under a "Relevant context you remember about this user:" header |
| **Actual** | ✅ Found verbatim in `llm.call.input.input_text` (offset 2292): `Relevant context you remember about this user:` → `- Task: i am rajnish / Answer: Nice to meet you…` → `- Task: Remember that I prefer all measurements in metric units. / Answer: Got it! I'll make sure to use metric units…` |
| **Trace confirmation** | The injected block contains the **stored results of turns A and B** → store→recall→inject proven end-to-end across turns. The agent's reply even names "Garvit", showing it consumed the live turn alongside the recalled context. |

> The full injected fold (verbatim from `input_text`):
>
> ```
> Relevant context you remember about this user:
> - Task: i am rajnish
>   Answer: Nice to meet you...
> - Task: Remember that I prefer all measurements in metric units.
>   Answer: Got it! I'll make sure to use metric units...
> ```

### Case C3 — Store fires at run-end (key only, content absent)

| | |
|---|---|
| **Prompt input** | (run C completes successfully → terminal `done` → `reasoning_recap`) |
| **Expected** | One `memory.stored` carrier keyed by task_id, `{user_id, key}` — **no payload** |
| **Actual** | ✅ `memory.stored` (step 4): `{"user_id": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX", "key": "a37cf5e5659a4efba01b7ebd281f0a73"}` |
| **Trace confirmation** | `key` == the run_id; payload (the distilled `task_input`+`final_answer`) is NOT on the wire. Store seam is tier-agnostic (terminal `done` shared by T1/T2/T3). |

### Case C4 — Phase-2 autocapture is LIVE and correctly SHADOW

| | |
|---|---|
| **Prompt input** | (run C) — the typed extractor proposes a semantic fact |
| **Expected** | A `memory.stored` carrier with typed metadata AND `proposed_only: true` (shadow — proposed, not committed) |
| **Actual** | ✅ `memory.stored` (autocapture): `{"user_id": "...", "key": "profile", "type": "semantic", "salience": "0.8", "proposed_only": "True"}` |
| **Trace confirmation** | `proposed_only="True"` = shadow posture (MEMORY_AUTOCAPTURE_ENABLED absent → default off → propose-don't-commit). This carrier was DEAD pre-fix (same wiring bug); it now fires in shadow exactly as designed. It is also the first row of the Stage-0 shadow corpus the calibration runbook needs. |

### Case C5 — Privacy invariant: memory CONTENT never on the wire

| | |
|---|---|
| **Expected** | Across ALL memory carriers: only `user_id` / `count` / `query_len` / `key` / `type` / `salience` / `proposed_only` — never the recalled text, the stored fact, or the query string |
| **Actual** | ✅ Deep field-scan (name + metadata + input + output) of all 3 memory carriers shows zero free-text content. Metadata is the OTel envelope (`event_id`/`workflow_id`/`step`); domain output is the allow-listed scalars above. |
| **Trace confirmation** | Confirmed by the audit's privacy check; `integrity_hash` present on each carrier (tamper-evident). |

### Case C6 — Cross-user-leak guard: every memory op uses identity.owner

| | |
|---|---|
| **Expected** | Every memory carrier's `user_id` == the run `subject`; no op uses any other id; `""`/`anonymous` → no subject |
| **Actual** | ✅ `run.started.subject` = `run.finished.subject` = recalled.user_id = stored.user_id = autocapture.user_id = `user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX`. Backend log `auth_ok subject=user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX`. |
| **Trace confirmation** | Single subject across the whole trace. `eval.goal_judge` and `eval.task_understanding` also carry the same `user_id`/`subject`. |

### Case C7 — Carrier gate raised NO memory-attributable alert

| | |
|---|---|
| **Expected** | No `source: "carrier_gate"` / `would_enforce: true` alert caused by memory (it would mean a memory carrier was accidentally made a hard requirement) |
| **Actual** | ✅ 3 `carrier_gate` checks (routing / model_invocation / output_validation), all `{"outcome": "pass", "would_enforce": "False", "missing_pillars": "[]", "missing_carriers": "[]"}` |
| **Trace confirmation** | Memory introduced no governance gap; the four pillars stayed satisfied. |

### Case C8 — Graceful degradation (memory never fails a run)

| | |
|---|---|
| **Expected** | A backend error during recall/store logs a metadata-only warning and continues; run still completes |
| **Actual (this run)** | ✅ No backend error occurred — recall returned 3, store succeeded, run `outcome` terminal. The degrade path is covered by unit test `test_backend_failure_degrades_gracefully` (Part 2). |
| **Trace confirmation** | `run.finished.status="success"`, `error=null`; no `memory.recall degraded` line. (Degrade-path live evidence would need a fault-injected run, which we do not run on prod.) |

---

## PART 2 — Implementation-plan verification gates (test evidence)

These are the plan's numbered Verification steps, run fresh this session.
**Command prefix:** `LANGCHAIN_TRACING_V2=false LANGSMITH_API_KEY="" .venv/bin/python -m pytest …`

### V1 — Spike: which memory abstraction? (RESOLVED)

| | |
|---|---|
| **Expected** | Pick sync `LongTermMemoryService` + `Mem0MemoryBackend` over awaiting the async `MemoryClient` |
| **Actual** | ✅ RESOLVED 2026-06-17 — `mem0ai` SDK is synchronous; loop depends on one sync `MemoryBackend` port; SDK stays confined to `middleware/adapters/`. Blocking I/O offloaded via `await asyncio.to_thread(memory_service.search, …)`. |

### V2 — Unit/contract tests (flag OFF, flag ON, degrade, memoize)

| Case | Expected | Actual |
|---|---|---|
| Flag OFF → no `search`/`store`, prompt unchanged | regression guard | ✅ part of suite |
| Flag ON → recall injects into `additional_instructions`; run-end `store` once with right `user_id`/`key` | | ✅ |
| Backend raises → run completes, warning logged, **no content in logs** | privacy degrade | ✅ |
| Recall memoized — **one `search` per run, not per reflexion lap** (T2) | load-bearing T2 property | ✅ |
| **Result** | `tests/orchestration/test_memory_wiring.py` | **9 passed** |

### V3 — Architecture tests (inject at root only, no node imports backend)

| | |
|---|---|
| **Expected** | No new disallowed imports in components/orchestration; service injected at composition root; SDK confined to `middleware/adapters/` |
| **Actual** | ✅ `tests/architecture/` → **99 passed, 1 skipped** (`-k 'not swap_radius'`) |

### V4 — Governance trace check (THE mandatory post-impl gate)

| Acceptance bar | Expected | Actual |
|---|---|---|
| `MEMORY_RECALLED` (count, query_len) + `MEMORY_STORED` (key) present, content absent | carriers + privacy | ✅ Cases C1/C3/C5 |
| Four-pillar verdict COMPLIANT (or WITH-FINDINGS for pre-existing run-level only) | no memory-induced FAIL | ✅ **COMPLIANT WITH FINDINGS** (finding = caught corrupt success, run-level) |
| No `carrier_gate` / `would_enforce:true` memory alert | gate clean | ✅ Case C7 |
| Memory-OFF run byte-identical (shadow-first) | no carriers when off | ✅ V2 flag-OFF + pre-fix runs A/B carried none |
| **Result** | governance-trace-audit skill on `ef236f95` | **COMPLIANT WITH FINDINGS** |

### V5 — Prod-path wiring regression guard (NEW — closes the bug that shipped)

| | |
|---|---|
| **Expected** | A test pins that `build_combined_app` builds the graph from a bag with non-None `memory_service` + `memory_autocapture` |
| **Actual** | ✅ `tests/middleware/test_app_prod_memory_wiring.py` → **2 passed**; proven fail-on-bug / pass-on-fix (temporarily reintroduced the narrow-bag drop → both failed; restored → both passed) |

### V6 — Trace-fetch tooling

| | |
|---|---|
| **Expected** | Read-only Langfuse helper: name-query carriers, 429-retry-then-skip, exit 0/2 |
| **Actual** | ✅ `tests/scripts/test_fetch_memory_trace.py` → **7 passed**; used live to fetch `ef236f95` (exit 0, carriers found) |

### V7 — Tier compatibility (T1 ReAct / T2 Reflexion / T3 fan-out)

| Tier | Expected | Actual |
|---|---|---|
| T1 ReAct | recall once → injected at `call_llm`; run-end store | ✅ exercised live (run C is the T1/direct path: `route → call_llm → evaluate → done`) |
| T2 Reflexion | recall once per run (NOT per `reflect→route` lap); store at terminal done | ✅ memoization unit test (V2); run C `reflexion_attempt="0"` |
| T3 Supervisor fan-out | recall reaches supervisor (not `call_llm`-only); store reads join's answer | ✅ seam is in `route_node` (universal); tier-coverage unit tests (task #8) |
| **Design note** | recall seam lives in `route_node` (every tier passes through), NOT `call_llm` | ✅ confirmed in trace: `memory.recalled` at step 3 route seam, consumed by `call_llm` |

---

## PART 3 — Deploy / infra validation

| Case | Expected | Actual | Confirmation |
|---|---|---|---|
| `MEMORY_ENABLED` durable + on tag | `true` on `agent-backend-combined` mem tag | ✅ rev env `MEMORY_ENABLED='true'` | `gcloud run revisions describe` |
| Durable backend selected | `memory backend: mem0 (durable)` at boot | ✅ logged 15:07:39 + boot | Cloud Logging |
| Real image (no placeholder no-op) | image built from current HEAD, `runtime:langgraph` | ✅ rebuilt image carries the `app_prod.py` fix → carriers fire | Case C1–C4 |
| Prod untouched | `--tag mem --no-traffic`; prod serves its own rev | ✅ tag is no-traffic | traffic split |
| **The decisive deploy lesson** | `MEMORY_ENABLED=true` + healthy + durable-log are **necessary but NOT sufficient** | ✅ proven the hard way: pre-fix runs A/B had all three yet zero carriers | DEPLOY_PIECE_C §3d now enforces a carrier check |

---

## Run-level findings (NOT instrumentation defects)

1. **Corrupt success — caught by governance.** Run C: `outcome:"success"` but
   `goal_met:false`, `unmet_conditions:['my son name is garvit']`. The agent
   replied *"Thank you for sharing, Rajnish! …regarding Garvit…"* — it named
   Garvit but the judge's (deterministic) criterion "my son name is garvit"
   scored unmet because the answer didn't *confirm/restate* the fact. The judge
   caught it (`eval.goal_judge.goal_met=false`, evidence cites the gap) → the
   trace is honest. GIGO caveat: `conditions_source:"deterministic"` (condition
   is a prompt fragment, not understood intent). `downgrade_applied:false` =
   Stage-2 gate off (expected). **Not a memory or deploy defect.**

2. **TaskUnderstanding shadow fallback.** `eval.task_understanding`
   `consumed:false, mode:"shadow"`, grounding-gate rejected both attempts
   (`"grounding gate: condition 1 shares no content token with the task
   input"`). Shadow mode → did not block. Known pre-existing pattern, unrelated
   to memory.

---

## What remains UNVERIFIED (and the trace that would prove it)

- **Identity pillar, from-step-0 fields.** Run C is resumed at step 3 (3rd turn)
  → no `task.started` carrying `agent_name`/`agent_version`/`agent_facts_id`.
  Subject is present everywhere (the *who* is answerable), but the registered-
  agent identity block is not. **A single from-step-0 authenticated run on the
  `mem` tag** (a fresh thread, one "remember" turn) would close this cell.
- **Live degrade path (C8).** Proven by unit test, not by a live fault — we do
  not fault-inject on prod.
- **Durable chat sidebar.** Blocked on option B (`pg`/Cloud SQL thread repo);
  sidebar UI is built + mounted but renders empty (InMemory repo, no
  `DATABASE_URL`). See [bff_cloudsql_thread_repo.plan.md](../plans/bff_cloudsql_thread_repo.plan.md).

---

## Summary

| Validation area | Status |
|---|---|
| Live recall fires + observable (C1) | ✅ |
| Recall injected into prompt across turns (C2) | ✅ |
| Store at run-end (C3) | ✅ |
| Autocapture live + shadow (C4) | ✅ |
| Privacy: content never on wire (C5) | ✅ |
| Cross-user-leak guard (C6) | ✅ |
| No memory carrier-gate alert (C7) | ✅ |
| Graceful degradation (C8, via test) | ✅ |
| Unit/contract gate (V2) | ✅ 9 passed |
| Architecture gate (V3) | ✅ 99 passed |
| Governance audit (V4) | ✅ COMPLIANT WITH FINDINGS |
| Prod-path regression guard (V5) | ✅ 2 passed |
| Trace-fetch tooling (V6) | ✅ 7 passed |
| Tier compatibility T1/T2/T3 (V7) | ✅ |
| Deploy posture (Part 3) | ✅ |

**The memory layer is wired, deployed, exercised under real WorkOS auth, and
audited COMPLIANT.** The only open items are non-blocking: a one-time from-step-0
run for the full Identity pillar, and option B for durable sidebar persistence.
