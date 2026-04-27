# SPIKE_C — Mem0 Cloud Hobby latency validation


| Field                     | Value                                                                                                            |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Sprint**                | 0                                                                                                                |
| **Story**                 | S0.4.1                                                                                                           |
| **Hypothesis under test** | H5 — Mem0 Cloud Hobby `add()` + `search()` round-trips < 200 ms p95 from a Cloud-Run-equivalent network position |
| **Run date**              | 2026-04-23                                                                                                       |
| **Origin**                | Developer workstation, US (single-network sample; **lower bound** on the production Cloud-Run latency we'll see) |
| **Throwaway code**        | `spikes/spike-c-mem0/` (gitignored)                                                                              |
| **Verdict (measurement)** | ❌ **FAIL** — search p95 = 447.6 ms vs the 200 ms criterion                                                       |
| **Verdict (decision)**    | ⚠️ **ACCEPTED with documented latency debt** per **D-S0-8** (2026-04-23). Mem0 Cloud Hobby retained for v1; alternatives shortlist preserved at [SPIKE_C_ALTERNATIVES_RESEARCH.md](SPIKE_C_ALTERNATIVES_RESEARCH.md) for re-evaluation. See [§6 below](#6-decision-update--accepted-with-latency-debt-2026-04-23). |


## 1. Result

```
search p95 = 447.6 ms  (threshold ≤ 200 ms)
search p99 = 566.2 ms
search p50 = 320.0 ms
search mean = 328.4 ms
add    p95 = 631.5 ms
add    p50 = 426.5 ms
```

**Both** `search()` and `add()` were 2–3× over the H5 budget across all
percentiles. There were zero transport errors (50/50 search calls returned
non-empty results), so the API itself is healthy — the failure mode is **steady-state latency**, not reliability.

Full numeric output: `spikes/spike-c-mem0/results.json` (gitignored).

## 2. Method


| Sub-step | Description                                                                                                                                                                                                                                                     | Outcome                                                                         |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| 3.3.1    | Throwaway httpx-based client at `spikes/spike-c-mem0/client.py`. No SDK / httpx type appears in any return value.                                                                                                                                               | ✅                                                                               |
| 3.3.2    | Seed 100 synthetic memories under user_id `spike-c-814ff664` via 100 sequential `POST /v1/memories/`. Each returned a `PENDING` queue receipt; ingestion is async on Mem0's side.                                                                               | ✅ 100/100 succeeded; mean per-call wall-clock 451.6 ms                          |
| 3.3.3    | Sleep 30 s for ingestion to settle, then 50 sequential `POST /v2/memories/search/` calls with varied queries. Measure each round-trip via `time.perf_counter`.                                                                                                  | ✅ 50/50 succeeded; **100% returned non-zero hits** (proves ingestion completed) |
| 3.3.4    | Static review of `client.py` confirms no `httpx.`*, `mem0.*`, or vendor-typed object leaks past the client's public methods — return types are `MemoryEvent`, `Memory` dataclasses + Python primitives.                                                         | ✅                                                                               |
| 3.3.5    | This report.                                                                                                                                                                                                                                                    | ✅                                                                               |
| 3.3.6    | Best-effort teardown via `delete_user()` (list + per-id delete). Mem0's list endpoint paginates at 10 per page; we did not iterate pages, so ~90 of 100 seeded memories remained in the user namespace. **Hobby quota burn: ~100 of 10,000 (1%)** — negligible. | ⚠️ partial; non-blocking                                                        |


## 3. Why this matters

The Mem0 round-trip latency is on the **client's critical path** for every
turn that uses long-term memory:

```
user message
  → middleware (Mem0.search to pull facts)   ← measured here, 320 ms p50
  → LLM (with retrieved context)
  → middleware (Mem0.add to persist new fact) ← measured here, 426 ms p50
  → SSE stream back to browser
```

That is **746 ms of pure Mem0 wall-clock at p50** added to every memory-using
turn. Combined with the ~100 ms Cloud-Run cold start, ~500 ms Neon cold start
(if scale-to-zero kicked in), and however many seconds the LLM takes, our
"first token" budget is already blown before the first LLM byte arrives.

The H5 hypothesis demanded < 200 ms p95 specifically because anything above
that pushes us past the F2 streaming-UX bar.

## 4. Hypotheses for the latency

Recorded for future investigation; **not** acted on for v1.

1. Mem0 Cloud Hobby may have lower compute priority than paid tiers (Starter
  $19, Pro $249). Worth re-running on a Starter trial before declaring
   Mem0-Cloud-as-a-substrate dead.
2. Geographic round-trip from `api.mem0.ai`'s region to the developer
  workstation is unknown. From Cloud Run in `us-central1` the numbers may
   differ by ±50 ms. Even a best case of 250 ms p95 from Cloud Run still
   fails the budget.
3. Re-rank / inference enrichment may add latency that's invisible on the
  docs page. We did not pass `infer=false`.

## 5. Original recommendation (HISTORICAL — superseded by §6)

> The text in this section reflects the **first-pass conservative reading** of
> the Spike C numeric failure on 2026-04-23. It was superseded the same day by
> Decision **D-S0-8** (see §6), which keeps Mem0 Cloud Hobby in v1 and accepts
> the latency debt rather than activating the V1 fallback. The §5 text is kept
> for audit so the chain of reasoning is preserved on disk.

Per `SPRINT_BOARD.md` "V1 Fallback Paths" table:

> Spike C (Mem0 Cloud) — Latency >500ms p95 → **Defer F15 (memory) to v1.5** —
> No long-term memory in v1.

Our search p99 was 566 ms (just over the documented 500 ms decision point);
search p95 was 447 ms. The plan's threshold is "p95 ≥ 500 ms triggers fallback",
which we narrowly miss — but the spike's PASS criterion is the tighter
"p95 ≤ 200 ms". We fail the spike's criterion outright; we trip the V1
fallback's letter only if we also reject Mem0's *paid* tier. The original
report chose the conservative reading: defer F15 to v1.5 until we have
either (a) Mem0 Starter latency data or (b) a working alternate (Zep Flex,
self-hosted Mem0 in the same Cloud Run pod).

The §5.1 fanout below describes that *original* (now-superseded) plan.

### 5.1 Fanout into the rest of the plan (HISTORICAL — superseded by §6.1)


| Surface                              | Change (HISTORICAL — not applied)                                                                                                                                                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sprint 1                             | No change. F15 was not on the Sprint-1 critical path.                                                                                                                                                                              |
| Sprint 2 (`infra/dev-tier/`)         | Drop `MEM0_API_KEY` from `S2.1.4` Secret Manager seeding for v1. (Keep the `.env.example` placeholder so the v1.5 work picks up where we left off.)                                                                                |
| Sprint 3 (frontend)                  | Remove the Mem0 adapter slot from the `agent_ui_adapter/adapters/memory/` planned work for v1; **the port + the empty-implementation no-op `NullMemoryClient` still ship** so the composition root has a typed seam to swap into.  |
| Sprint 4 hardening (`S4.2.1` alarms) | Drop the `Mem0 Cloud Hobby quota at 80%` alarm for v1.                                                                                                                                                                             |
| F15 acceptance criteria              | Move from v1 to v1.5. Re-open Spike C against (a) Mem0 Starter, (b) Zep Flex $25/mo, or (c) self-hosted Mem0 in the same pod, **before** committing to a substrate.                                                                |
| `.env.example`                       | Keep `MEM0_API_KEY` and `MEM0_BASE_URL` placeholders. Add a comment noting v1.5 status.                                                                                                                                            |
| User's Mem0 Cloud account            | **Keep** but do not generate further keys until v1.5 work begins. Quota burn from this spike was ~1%.                                                                                                                              |


## 6. Decision update — ACCEPTED with latency debt (2026-04-23)

After §5 was written, an alternatives review (see
[SPIKE_C_ALTERNATIVES_RESEARCH.md](SPIKE_C_ALTERNATIVES_RESEARCH.md)) showed
that several substrates (pgvector on Neon Free, Cloudflare Vectorize, Upstash
Vector, self-hosted Mem0 in pod) would all clear the 200 ms p95 budget with
multiple-x headroom. Despite that, Decision **D-S0-8** (in
[SPRINT_0_RUNBOOK.md](../SPRINT_0_RUNBOOK.md) §0) chose to **keep Mem0 Cloud
Hobby in v1** and **accept the measured ~447 ms p95 search latency as
documented technical debt** rather than swap substrates during Sprint 0.

The reasoning behind D-S0-8:

1. **Mem0's value-add is the auto-fact-extraction pass.** None of the
   sub-200 ms alternatives (except Zep, which has its own cost cliff) provide
   that out of the box. Switching to pgvector means writing the extraction
   pass too, which expands v1 scope.
2. **The latency debt is bounded and quantified** (~750 ms of Mem0 wall-clock
   per memory-using turn — see §3). v1's UX bar is "first token streamed";
   Mem0 reads/writes can be parallelised with the LLM call (read before, write
   after) so the user-perceptible cost is closer to ~320 ms (one search round
   trip) added to first-token-time, not 750 ms.
3. **The substrate swap is a composition-root-only change** per F3, so the
   debt has a known and pre-priced exit (the alternatives shortlist in §5 of
   the alternatives research doc). We're choosing **when** to take that work,
   not **whether** we can.
4. **Mem0 Hobby is still free.** If we hit the 10 K adds / 1 K retrievals/mo
   ceiling we either pay $19/mo for Starter or trigger the swap then — both
   are bounded responses.

### 6.1 Fanout into the rest of the plan (ACTIVE — replaces §5.1)


| Surface | Change (ACTIVE) | Owner |
|---|---|---|
| F15 (long-term memory) | **Stays in v1.** Mem0 Cloud Hobby retained as the substrate. | product / planning |
| Sprint 1 | No change — F15 is not on the Sprint-1 critical path. | — |
| Sprint 2 — `S2.1.4` (Secret Manager seeding) | **Keep** `MEM0_API_KEY` in the v1 secret set. | infra |
| Sprint 3 — `agent_ui_adapter/adapters/memory/` | Ship `Mem0CloudHobbyAdapter` implementing `MemoryClient`. SDK confined per F-R8/A4 (the spike's `client.py` is the structural blueprint). | sprint-3 owner |
| Sprint 3 — composition root | Wire `Mem0CloudHobbyAdapter` for the `v3` profile; reserve a `PgVectorMemoryClient` slot (not yet implemented) for the future swap, per the alternatives shortlist. | sprint-3 owner |
| Sprint 3 — adapter design choice | The adapter must **parallelise** Mem0 calls with the LLM call where possible (read-memory in parallel with prompt-construction; write-memory fire-and-forget after streaming). This bounds the user-perceptible latency hit. | sprint-3 owner |
| Sprint 4 — `S4.2.1` alarms | **Keep** "Mem0 Cloud Hobby quota at 80 %" alarm. **Add** "Mem0 search p95 > 800 ms over 24 h window" alarm so we get notified if Mem0's latency degrades from the spike baseline. | sprint-4 owner |
| Sprint 4 — UX guard | Ensure the streaming UX (`useCoAgentStateRender` step indicator) hides the Mem0 round-trip behind a "thinking" state rather than blocking first token. | sprint-4 owner |
| User's Mem0 Cloud account | **Keep** the account and the active key. **Do not** rotate the Hobby key after Sprint 0; it carries forward into v1 until either quota or latency triggers a swap. Quota burn from this spike was ~1 % of the 10 K Hobby cap. | rajnish |
| Re-evaluation triggers | See §7. | sprint-3 owner |
| `.env.example` | `MEM0_API_KEY` and `MEM0_BASE_URL` placeholders **stay**, with a comment that they are required for v1 (not v1.5 deferred). | sprint-1 owner |

## 7. Re-open / swap triggers

Re-run this spike (or jump straight to Spike C-prime against pgvector, per
the alternatives doc §6) when **any** of these is true:

- Mem0 search p95 from production exceeds **800 ms** over a 24 h window
  (the §6.1 alarm). This is 2× the spike baseline and is our "the latency
  debt has compounded" signal.
- Mem0 Cloud Hobby quota hits 80 % (10 K adds or 1 K retrievals/mo). At that
  point we either pay Starter ($19/mo) or swap; the alternatives doc says
  swap is cheaper.
- A user-facing TTFT (time-to-first-token) regression is traced to Mem0 by
  the new "Mem0 search p95" alarm or by Cloud Trace spans.
- Mem0 announces edge-pop / regional latency improvements published as
  changelog evidence (would tighten the gap without a swap).
- v1.5 product spec for long-term memory lands and chooses a non-Mem0
  substrate (Zep Flex, self-hosted Mem0, pgvector, Cloudflare Vectorize).

## 8. Throwaway-code lifecycle

`spikes/spike-c-mem0/` stays on the developer workstation only — it is
gitignored per `SPRINT_0_RUNBOOK.md` §5. It **is** the structural blueprint
for the Sprint-3 production adapter (per D-S0-8); the production adapter
will live at `agent_ui_adapter/adapters/memory/mem0_cloud_hobby_adapter.py`
and follow the patterns in
`docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md`. Specifically:

- Public methods return only local dataclasses (`MemoryEvent`, `Memory`) —
  no httpx / mem0 SDK types past the boundary (verified in §3.4 of this
  report).
- Async client (`httpx.AsyncClient`) — the Sprint-3 version replaces the
  spike's sync `httpx.Client` so memory I/O can run in parallel with the
  LLM call (§6.1 design constraint).
- Same auth header (`Authorization: Token <key>`) and base URL (`MEM0_BASE_URL`).
- The pagination-aware `delete_user()` cleanup the spike skipped is
  required for the production adapter's user-deletion endpoint.