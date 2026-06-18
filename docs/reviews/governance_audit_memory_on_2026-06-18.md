# Governance Trace Audit — memory-ON live run (Piece C deploy)

**Date:** 2026-06-18 (revised — see "Correction" below)
**Target (correct):** `agent-backend-combined` Cloud Run service, tag `mem`, revision
`agent-backend-combined-00083-wal`, project `agent-prod-gcp-dev`, region `us-central1`.
**Intended subject:** a `MEMORY_ENABLED=true` run carrying `memory.recalled` /
`memory.stored` carriers (plan §Verification step 4).

---

## VERDICT: **AUDIT PENDING — deploy is correct & healthy; no successful run has produced a trace yet**

> **One-liner (Slack-ready):** The memory-ON deploy is the **`mem` tag on
> `agent-backend-combined`** (rev `00083-wal`, real agent image, `MEMORY_ENABLED=true`,
> no-traffic — prod untouched on `00075-8js`). It's healthy and reachable, but the
> only request to it so far returned **401** (bearer auth), so **no run has produced
> a trace and there are zero memory carriers yet**. Instrumentation is *not* faulted —
> it simply hasn't run. **Next action:** make one authenticated from-step-0 run against
> the `mem` tag URL with a real `user_id` (a "remember X" turn + a "recall X" turn),
> then re-run this audit on that trace.

This is **not** a governance/instrumentation finding. The deploy is right; the audit
just needs a trace to audit.

---

## ⚠ Correction (supersedes the first version of this report)

The first version of this report concluded **"AUDIT BLOCKED — placeholder image"**
after auditing the **`agent-middleware`** service. **That was the wrong service.** There
are three Cloud Run services in this project:

| Service | Role | Image | Traffic |
|---|---|---|---|
| `agent-backend-combined` | **the real prod agent** (all e2e/stress/GoalJudge target it) | real `agent-backend@sha256:f8ddf3…` (prod), `e9cf7e…` (`mem` tag) | 100% on `00075-8js`; `mem` tag no-traffic |
| `agent-frontend` | **the prod BFF** (Cloud Run, *not* Cloudflare Pages) | real frontend image | 100% |
| `agent-middleware` | **orphaned V3-dev-tier service** — no traffic points at it | Cloud Run `hello` placeholder | 100% but unused |

`agent-middleware` *is* on the placeholder image — but it carries **no traffic** and
nothing routes to it (the BFF's `MIDDLEWARE_URL` → `agent-backend-combined`, not
`agent-middleware`). So the placeholder finding was **true but irrelevant**: it is a
dormant dev-tier service, not the memory deploy. The real Piece-C memory deploy landed
correctly on the `mem` tag of `agent-backend-combined`.

---

## Evidence (correct service)

### 1. The `mem` tag exists on the real backend, with a real agent image + memory ON

```
$ gcloud run services describe agent-backend-combined --region=us-central1 \
    --format="…traffic…"
  <no-tag>  agent-backend-combined-00075-8js  pct=100        (prod — untouched)
  mem       agent-backend-combined-00083-wal  no-traffic     https://mem---agent-backend-combined-…run.app

$ gcloud run revisions describe agent-backend-combined-00083-wal …
  image: …/agent-backend/agent-backend@sha256:e9cf7edac9a0…   (real agent, newer than prod)
  env:   MEMORY_ENABLED='true', MEM0_API_KEY=<secret>, DATABASE_URL=<secret database-url>,
         ARCHITECTURE_PROFILE=v3, BLACKBOX_RELAY_MODE=in_process, GOAL_JUDGE_ENABLED='true'
         (MEMORY_AUTOCAPTURE_ENABLED absent → defaults false → shadow, as intended)
  created: 2026-06-18T09:58:56Z
```

This is exactly the posture `DEPLOY_PIECE_C.md` intended: recall+store ON, autocapture
shadow, `--tag mem --no-traffic`, prod untouched.

### 2. The tag is reachable but unexercised — one request, a 401

```
# /run/stream on the mem tag revision, last 1d:
2026-06-18T10:04:32Z  https://mem---agent-backend-combined-…/run/stream   401
# memory log lines on 00083-wal:  (none)
```

`/run/stream` requires a WorkOS bearer JWT (`app_prod.py` `run_stream`). The single
request was unauthenticated → 401 → no run → no carriers. That matches the deploy doc's
own note: *"call the mem tag directly with bearer auth for /agent/memory roundtrips."*

### 3. Zero memory carriers in Langfuse since the deploy

```
$ scripts/fetch_memory_trace.py --since 2026-06-18T09:55:00Z
  observations name=memory.recalled: 0 found
  observations name=memory.stored:   0 found
```

Carrier names verified as the dotted form `memory.recalled` / `memory.stored`
(`services/governance/black_box_publisher.py:95-96`), so the query is correct — the
count is genuinely zero, because no authenticated run has happened on the `mem` tag.

---

## What's needed to complete the audit (one authenticated run)

1. **Drive one from-step-0 run** against the `mem` tag URL with a real bearer token and
   a `user_id`:
   - turn 1: a "remember" prompt (e.g. *"Remember I prefer metric units."*) → expect a
     `memory.stored` carrier at run-end;
   - turn 2 (same `user_id`): a "recall" prompt (e.g. *"What units do I prefer?"*) →
     expect a `memory.recalled` carrier at step 0 and the fact folded into the system
     prompt.
   Either hit `https://mem---agent-backend-combined-…/run/stream` with a WorkOS JWT, or
   point a test frontend revision at the `mem` backend URL and drive it through the UI.
2. **Re-run this audit** on the resulting trace:
   `scripts/fetch_memory_trace.py --since <run-time>` → feed the observation array to the
   `governance-trace-audit` skill. Acceptance bar (plan §Verification 4): `memory.recalled`
   (count, query_len) + `memory.stored` (key) present, **content absent**, four-pillar
   verdict COMPLIANT, no `source: "carrier_gate"` memory alert.

---

## Scorecard

| Pillar | Status | Why |
|---|---|---|
| Recording | **PENDING** | No trace yet — the `mem` tag hasn't had a successful run. |
| Identity | **PENDING** | "" |
| Validation | **PENDING** | "" |
| Reasoning | **PENDING** | "" |
| Memory carriers (`memory.recalled`/`memory.stored`) | **NOT YET EMITTED** | 0 in Langfuse; the one tag request was a 401 (no run). |
| Deploy posture | **✓ CORRECT** | real image, `MEMORY_ENABLED=true`, autocapture shadow, `--tag mem --no-traffic`, prod on `00075-8js`. |

PENDING (not BLOCKED, not FAIL): the deployment is correct and capable; it just awaits
one authenticated run to produce auditable telemetry.

---

## Side finding (low severity, dev-tier hygiene)

`agent-middleware` is an **orphaned** Cloud Run service running the `hello` placeholder
with `MEMORY_ENABLED=true` set on it (no effect — no agent, no traffic, nothing routes
to it). It's a leftover from the V3-dev-tier IaC. Not part of the memory deploy and
harmless, but worth deleting to avoid future confusion (it's what made the first version
of this report chase the wrong service). The Cloudflare-Pages dev-tier stack was removed
in the same cleanup (the BFF is `agent-frontend` on Cloud Run, not Pages).

## What is NOT in question

The memory wiring **code** is sound and tested (Phase-1 committed `935433e`, full suite
green, architecture clean), and the **deploy is correct**. This audit is simply waiting
for one authenticated run on the `mem` tag to produce the trace it scores.
