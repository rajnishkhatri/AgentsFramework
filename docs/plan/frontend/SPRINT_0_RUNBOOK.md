# Sprint 0 — Decisions Locked + Spike Validation (Runbook)

> **Status**: active.
> **Owner**: rajnishkhatri.
> **Tracks**: [SPRINT_BOARD.md](SPRINT_BOARD.md) Sprint 0.
> **Base plan**: [FRONTEND_PLAN_V3_DEV_TIER.md](FRONTEND_PLAN_V3_DEV_TIER.md).
> **Architecture source of truth**: [docs/Architectures/FRONTEND_ARCHITECTURE.md](../../Architectures/FRONTEND_ARCHITECTURE.md).

This is the executable companion to Sprint 0 of the sprint board. Every checkbox here is a single user-confirmable step. We execute them one at a time; nothing in `agent_ui_adapter/`, `pyproject.toml`, or `.env.example` changes until each step is explicitly green-lit.

---

## 0. Decisions Locked (this conversation)

The following decisions are now binding for Sprint 0 → Sprint 1. Any change requires re-opening this section.

| # | Decision | Rationale | Source |
|---|----------|-----------|--------|
| **D-S0-1** | The new "middleware" layer extends the existing `agent_ui_adapter/` package — **no parallel `middleware/` package is forked**. New work goes under `agent_ui_adapter/adapters/{auth,memory,observability}/`, `agent_ui_adapter/composition.py`, and `agent_ui_adapter/policy/tool_acl.py`. Renaming to `middleware/` later is a `git mv`. | `agent_ui_adapter/` already provides 80%+ of the spec'd surface (FastAPI app, JwtVerifier protocol, AgentRuntime port, LangGraph runtime, wire kernels, translators, transport, architecture tests). Forking would duplicate ~1500 LoC for zero architectural gain. | This conversation; cross-checked against `agent_ui_adapter/server.py:build_app`, `tests/architecture/test_agent_ui_adapter_layer.py`. |
| **D-S0-2** | All Sprint-1 WorkOS tests use **mocked JWKs and hand-rolled signed JWTs**. No live WorkOS calls in CI. A real WorkOS account is set up later for end-to-end smoke runs only. | AGENTS.md §Testing Rules forbids live LLM/cloud calls in CI; same principle applies to identity providers. | This conversation; AGENTS.md §Testing Rules. |
| **D-S0-3** | The Sprint-1 dependency additions are **`pyjwt[crypto]>=2.8`**, **`cryptography>=42`**, **`workos>=4`**, and **`langgraph-cli[inmem]`**. Added to `pyproject.toml` `[project.dependencies]` (not optional) when the owning story lands, **not** during Sprint 0. | AGENTS.md §"Ask first" requires sign-off for new deps; user signed off on this set. | This conversation. |
| **D-S0-4** | Tool ACL (S1.3.1) is **runtime-configurable** via `MIDDLEWARE_TOOL_ACL_JSON` env var. Default mapping (when unset): `admin → all tools`, `beta → all except shell`, unknown group → 403. | Avoids hard-coded policy; lets operators tune without redeploy. | This conversation; sprint-board S1.3.1 acceptance criteria. |
| **D-S0-5** | **Spike B (self-hosted LangGraph in FastAPI) is SKIPPED**. Rationale: `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` already wraps `orchestration.react_loop:build_graph` and is exercised by `tests/agent_ui_adapter/test_smoke_langgraph.py`. The "embedded in FastAPI" claim is therefore proven by the existing `agent_ui_adapter/server.py` + that smoke test. The remaining `langgraph.json` config-loading variant is deferred to Sprint 1 (S1.1.1) where it owns the implementation. | The risk Spike B was meant to retire (H10/H11) is already retired by the existing test suite — re-running it as a "spike" is busywork. | This conversation; existing test surface in `tests/agent_ui_adapter/`. |
| **D-S0-6** | **Spike D (Langfuse Cloud Hobby) is SKIPPED**, activating the V1 fallback path: **Cloud Trace + Cloud Logging only**. Implication: F16 (observability) loses prompt-version capture and tool-span hierarchy in v1; an OTel exporter slot under `agent_ui_adapter/adapters/observability/` is reserved but populated by a `CloudTraceExporter` (Stage A) and only later swapped to `LangfuseCloudHobbyAdapter` if/when an account is provisioned. | User chose the documented V1 fallback. Avoids a hard external-account dependency for v1 launch. | This conversation; SPRINT_BOARD.md "V1 Fallback Paths" table. |
| **D-S0-7** | **Spike A (CopilotKit) and Spike C (Mem0 Cloud) PROCEED** as soon as the user has signed up and provided API keys. Both are required for v1 (CopilotKit owns F5/F13/F14; Mem0 owns F15). | User explicitly chose "have account" path for both. | This conversation. |
| **D-S0-8** | **Spike C measurement FAILED (search p95 = 447.6 ms vs the 200 ms budget) but the spike is ACCEPTED for v1.** Mem0 Cloud Hobby is retained as the F15 substrate; the latency gap is captured as **documented technical debt** with an explicit re-evaluation ladder. The alternatives shortlist (pgvector on Neon, Cloudflare Vectorize, Upstash, Zep, Mem0 OSS in pod, LangMem) is preserved on disk at [spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md](spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md) so a future swap does not redo the legwork. | (1) Mem0's auto-fact-extraction value-add is unique among free options; switching to pgvector/Vectorize means writing the extraction pass too — expands v1 scope. (2) Mem0 read can be parallelised with prompt construction, making user-perceptible latency closer to one round-trip (~320 ms p50) rather than the full 750 ms add+search wall-clock. (3) The substrate swap is a composition-root-only change per F3 — known, pre-priced exit. (4) Mem0 Hobby remains free at our dev volumes. | This conversation; backed by [spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md](spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md). |

### Implications fanning out from these decisions

| Affected story / component | Old wording (sprint board) | New wording after D-S0-* |
|---|---|---|
| S1.1.1 | "`middleware/server.py`" | "`agent_ui_adapter/server.py` extension + `agent_ui_adapter/adapters/runtime/langgraph_dev_loader.py` (langgraph.json variant)" |
| S1.1.2 | "`middleware/composition.py`" | "`agent_ui_adapter/composition.py` (extracted from inline composition in `server.py:build_app`)" |
| S1.2.1 | "`middleware/adapters/auth/workos_jwt_verifier.py`" | "`agent_ui_adapter/adapters/auth/workos_jwt_verifier.py`" |
| S1.3.1 | "`middleware/` enforces tool allowlists" | "`agent_ui_adapter/policy/tool_acl.py` + dependency in `agent_ui_adapter/server.py`; mapping driven by `MIDDLEWARE_TOOL_ACL_JSON`" |
| S1.4.1 | "`tests/architecture/test_middleware_layer.py`" | Tightening of existing `tests/architecture/test_agent_ui_adapter_layer.py`: forbid `agent_ui_adapter/ → services.governance/` and `agent_ui_adapter/ → orchestration/` (already implied by R1/R2 but make it explicit; T3 already forbids the inverse). |
| S0.5.1 (Spike D) | "Langfuse Cloud Hobby" | **Skipped**. Replaced by `CloudTraceExporter` adapter slot in Sprint-2 work. |
| S2.1.4 (Secrets) | "`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`" | **Removed** for v1. Re-added at Stage B if Langfuse adopted later. |
| Cross-cutting `.env.example` | — | Will gain `WORKOS_*`, `MEM0_API_KEY`, `MIDDLEWARE_TOOL_ACL_JSON`, `NEXT_PUBLIC_CPK_PUBLIC_API_KEY`, `ARCHITECTURE_PROFILE` when each owning story lands. |

---

## 1. Sprint 0 Master Checklist

Run top-to-bottom. Each row is one self-contained step the user confirms before we move on.

| # | Step | Owner | Gate | Status |
|---|------|-------|------|--------|
| 1 | **Epic 0.1 / S0.1.1** — V3-Dev-Tier plan committed to `main` (cross-check that `docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md` is on `main`, references AGENTS.md invariants, lists D1-D8 carry-overs and §6.5/6.6 graduation triggers). | rajnish | review-only; no code change | ⏳ pending verification |
| 2 | **Epic 0.1 / S0.1.2** — Register GCP project `agent-prod-gcp-dev` in `us-central1`. Enable Secret Manager API + Cloud Run API. Assign IAM roles (Secret Manager Accessor, Cloud Run Developer, Logs Writer). | rajnish | manual GCP console | ⏳ pending |
| 3 | **Epic 0.2 / Spike A** — CopilotKit Cloud account + API key. See [§2 below](#2-spike-a-walkthrough--copilotkit-cloud-account--api-key). | rajnish + agent | key + all 3 sub-stories PASS | ✅ **PASS** — 2026-04-23. All 3 sub-stories (useCopilotAction tool cards, sandboxed-iframe generative UI, live state indicators) verified end-to-end against CopilotKit Cloud on Next.js 16 + React 19. See [SPIKE_A.md](spike_reports/SPIKE_A.md). 1 minor finding (§4.1 result-type) tracked into Sprint 3 work. |
| 4 | **Epic 0.3 / Spike B** | — | **SKIPPED per D-S0-5.** Document this in [SPIKE_B.md](spike_reports/SPIKE_B.md) when reports folder is created in step 7. | ➖ skipped |
| 5 | **Epic 0.4 / Spike C** — Mem0 Cloud account + API key. See [§3 below](#3-spike-c-walkthrough--mem0-cloud-account--api-key). | rajnish + agent | key + measurement OR product accept-with-debt | ⚠️ **PASS (accepted with documented latency debt)** — 2026-04-23. Measurement failed (search p95 = 447.6 ms vs 200 ms budget) but Decision **D-S0-8** keeps Mem0 in v1; alternatives shortlist preserved at [SPIKE_C_ALTERNATIVES_RESEARCH.md](spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md) for future swap. See [SPIKE_C.md §6](spike_reports/SPIKE_C.md#6-decision-update--accepted-with-latency-debt-2026-04-23). Active fanout in [§7.1 below](#71-spike-c-accepted-with-debt-2026-04-23--mem0-stays-in-v1). |
| 6 | **Epic 0.5 / Spike D** | — | **SKIPPED per D-S0-6.** Activates Cloud Trace + Cloud Logging fallback. | ➖ skipped |
| 7 | Create `docs/plan/frontend/spike_reports/` folder with one report per spike (`SPIKE_A.md`, `SPIKE_B.md`, `SPIKE_C.md`, `SPIKE_D.md`). Skipped spikes still get a one-paragraph rationale. | agent | done when 4 files exist on `main` | ✅ done — 2026-04-23 |
| 8 | **Sprint 0 sign-off**: rajnish reviews every report, confirms PASS/SKIP for each, and explicitly approves Sprint 1 kick-off. | rajnish | written approval in chat | ⏳ pending |

---

## 2. Spike A walkthrough — CopilotKit Cloud account + API key

**Goal**: provision the public API key needed to validate `useFrontendTool`, `useComponent`, and `useCoAgentStateRender` against the existing `react_loop` graph (S0.2.1, S0.2.2, S0.2.3).

### 2.1 Account setup (you do this in the browser)

1. Open <https://cloud.copilotkit.ai/sign-up>.
2. Sign up with **GitHub** or **Google** (no email/password flow as of 2026-Q2).
3. After sign-in you land on the Copilot Cloud dashboard.
4. The onboarding wizard will prompt you for an **OpenAI API key**. Paste your existing `OPENAI_API_KEY` (the same one used in `.env`). Copilot Cloud uses it to broker LLM calls when you opt into their managed model layer; you can revoke and rotate it any time.
5. After OpenAI key validation, the dashboard generates a **public API key** that looks like `cpk_pub_...`. Copy it immediately.
6. Confirm the key is associated with a "Project" — note the project name; you'll see it in the Cloud dashboard's left rail.

> Reference: <https://docs.copilotkit.ai/quickstart> and <https://docs.copilotkit.ai/langgraph/tutorials/agent-native-app/step-3-setup-copilotkit>.

### 2.2 Hand off the key (you tell me when ready)

Reply with the line below filled in, and I'll write it into `.env` (gitignored) and add a placeholder to `.env.example`:

```env
NEXT_PUBLIC_CPK_PUBLIC_API_KEY=cpk_pub_xxxxxxxxxxxxxxxxxxxx
```

> Note on env-var name: CopilotKit docs as of 2026 standardise on **`NEXT_PUBLIC_CPK_PUBLIC_API_KEY`** (not the older `NEXT_PUBLIC_COPILOT_API_KEY` seen in some 2024 tutorials). We use the new name.

### 2.3 Spike execution (I do this once you supply the key)

| Sub-step | What I'll do | Pass criterion |
|----------|--------------|----------------|
| 2.3.1 | Scaffold `spikes/spike-a-copilotkit/` (Next.js 15 + CopilotKit v2 throwaway app, gitignored). | `pnpm dev` boots; Copilot panel renders. |
| 2.3.2 | Wire it to a local `agent_ui_adapter/server.py` instance pointed at `react_loop`. | Browser receives at least one streamed event. |
| 2.3.3 | Register `useFrontendTool` for `shell`, `file_io`, `web_search`. | All three render their input/output JSON in tool cards. |
| 2.3.4 | Register `useComponent` to render an HTML snippet inside `<iframe sandbox="allow-scripts">` (no `allow-same-origin`). | Iframe renders; `window.parent.document` from inside the iframe throws cross-origin error. |
| 2.3.5 | Register `useCoAgentStateRender` to render a fake `step_meter` + `model_badge` from synthetic SSE events. | Both update in real time as events arrive. |
| 2.3.6 | Write `docs/plan/frontend/spike_reports/SPIKE_A.md` with PASS/FAIL per sub-step, screenshots, and any impedance mismatches found. | Report committed; spike marked PASS or fallback to assistant-ui per V1 invoked. |

**Estimated wall-clock**: 1 working day after key is in hand.

---

## 3. Spike C walkthrough — Mem0 Cloud account + API key

**Goal**: prove Mem0 Cloud Hobby `add()` + `search()` round-trip stays under 200ms p95 from a Cloud Run-equivalent network position (S0.4.1).

### 3.1 Account setup (you do this in the browser)

1. Open <https://app.mem0.ai>.
2. Click **Sign up**. As of 2026-Q2 you can use email + password, GitHub, or Google.
3. Verify your email (Mem0 sends a magic-link).
4. After first login you land on the Mem0 dashboard.
5. Navigate to **API Keys** in the left sidebar (direct link: <https://app.mem0.ai/dashboard/api-keys>).
6. Click **Create API Key**.
7. Name the key `agent-spike-c-2026q2` (or anything memorable; we will rotate it after Sprint 0 finishes regardless).
8. **Copy the key immediately** — Mem0 only displays it once. The format is `m0-xxxxxxxxxxxxxxxx`.
9. Note the Hobby tier limits visible in the dashboard: **10,000 memories + 1,000 retrievals / month**. We will trip the 80% alarm in Sprint 4 (S4.2.1).

> References: <https://docs.mem0.ai/platform/quickstart>, <https://docs.mem0.ai/api-reference>.

### 3.2 Hand off the key (you tell me when ready)

Reply with:

```env
MEM0_API_KEY=m0-xxxxxxxxxxxxxxxx
MEM0_BASE_URL=https://api.mem0.ai
```

I'll write these into `.env` (gitignored) and add placeholders + 2-line docstring to `.env.example`.

### 3.3 Spike execution (I do this once you supply the key)

| Sub-step | What I'll do | Pass criterion |
|----------|--------------|----------------|
| 3.3.1 | Add `mem0ai` (or `httpx`-only) client under a throwaway `spikes/spike-c-mem0/client.py` (NOT under `agent_ui_adapter/adapters/memory/` yet — that comes in a Sprint-3 story). | Module imports cleanly; no SDK type leakage past its own boundary. |
| 3.3.2 | Seed the user namespace with 100 representative memories (synthetic). | All 100 `add()` calls return 200; total wall-clock recorded. |
| 3.3.3 | Run 50 sequential `search()` calls measuring per-call latency from a US-central origin (your machine; we note the network position is friendlier than Cloud Run's, but it's a strict lower bound). | p50, p95, p99 latencies recorded; **PASS if p95 ≤ 200 ms**. |
| 3.3.4 | Confirm SDK type `m0_*` never leaks past the client boundary (return values are dicts shaped by `wire/`-style schemas). | grep + manual review. |
| 3.3.5 | Write `docs/plan/frontend/spike_reports/SPIKE_C.md` with the latency histogram, quota burn (added memories vs Hobby cap), and PASS/FAIL verdict. | Report committed. **FAIL → defer F15 to v1.5 per V1 fallback.** |
| 3.3.6 | Tear down: `delete_all` against the spike namespace so we don't burn Hobby quota waiting for Sprint-3. | Quota dashboard shows zero memories. |

**Estimated wall-clock**: 0.5 working day after key is in hand.

---

## 4. Skipped-spike documentation

Even skipped spikes need a one-paragraph rationale committed to the repo so future contributors can audit the decision. These will be created in step 7 of [§1](#1-sprint-0-master-checklist).

### 4.1 SPIKE_B.md content (to be written)

> **Status**: SKIPPED per Sprint 0 decision D-S0-5.
> **Reason**: The H10/H11 hypotheses Spike B was meant to retire — that the existing `react_loop` graph can be embedded in a FastAPI app and serve Agent Protocol routes — are already proven by `agent_ui_adapter/server.py:build_app()` and the `tests/agent_ui_adapter/test_smoke_langgraph.py` smoke test. Re-running them as a Sprint-0 spike would not generate new evidence.
> **What is deferred**: the specific `langgraph.json`-config-based loading mechanism (vs the current direct Python import of `build_graph`) is owned by Sprint 1 story S1.1.1 and validated as part of that story's acceptance tests, not as a separate spike.
> **Re-open trigger**: if S1.1.1's `langgraph.json` loader cannot be made to work with `langgraph-cli[inmem]`, we open Spike B as a salvage exercise and may invoke the V2-Frontier fallback (LangGraph Platform Cloud SaaS Plus, +$89-104/mo).

### 4.2 SPIKE_D.md content (to be written)

> **Status**: SKIPPED per Sprint 0 decision D-S0-6, activating the V1 fallback path.
> **Reason**: User opted not to provision a Langfuse Cloud account for v1. Cloud Trace + Cloud Logging cover the minimum-viable observability surface (per-run trace tree, structured logs, error rates).
> **Cost & feature impact**: F16 (observability) ships in v1 without prompt-version capture and without Langfuse-style tool-span hierarchy. We retain `trace_id` propagation through every layer (cross-cutting DoD requirement), and Cloud Trace's spans give us the call-tree shape for free.
> **Adapter slot retained**: `agent_ui_adapter/adapters/observability/` will hold a `CloudTraceExporter` for v1 and is structured so a `LangfuseCloudHobbyAdapter` is a drop-in composition-root swap if/when an account is provisioned.
> **Re-open trigger**: first prompt-version A/B test request from product, or any postmortem that requires retroactive prompt-version forensics.

---

## 5. What changes in the repo *during* Sprint 0

Sprint 0 is intentionally low-write: the only files that change on `main` are documentation and reports.

| Path | Change | When |
|------|--------|------|
| `docs/plan/frontend/SPRINT_0_RUNBOOK.md` | This file. | now (this commit) |
| `docs/plan/frontend/spike_reports/SPIKE_A.md` | New — Spike A report. | step 7 of §1 |
| `docs/plan/frontend/spike_reports/SPIKE_B.md` | New — skip rationale (§4.1). | step 7 of §1 |
| `docs/plan/frontend/spike_reports/SPIKE_C.md` | New — Spike C report. | step 7 of §1 |
| `docs/plan/frontend/spike_reports/SPIKE_D.md` | New — skip rationale (§4.2). | step 7 of §1 |
| `.env.example` | Add `NEXT_PUBLIC_CPK_PUBLIC_API_KEY`, `MEM0_API_KEY`, `MEM0_BASE_URL` (placeholder values only). | when Spike A and C keys are in hand (steps 3 and 5) |
| `.env` (gitignored) | Real keys written locally only. | same |
| `.gitignore` | Add `spikes/` (entire throwaway-spike folder excluded from git). | on first spike code commit |
| `pyproject.toml` | **No changes during Sprint 0** — deps for Spike C live in the throwaway spike's own venv if needed. | n/a |
| `agent_ui_adapter/**` | **No changes during Sprint 0**. | Sprint 1 |

---

## 6. Sprint 0 Definition of Done

- [ ] All 8 rows in [§1 master checklist](#1-sprint-0-master-checklist) are either ✅ done or ➖ skipped (with rationale committed).
- [ ] Four spike reports exist under `docs/plan/frontend/spike_reports/` (two PASS/FAIL, two SKIPPED with rationale).
- [ ] `.env.example` documents every new env var introduced by passed spikes (no real secrets ever committed).
- [ ] `spikes/` folder is in `.gitignore` and contains no committed throwaway code.
- [ ] User explicitly approves Sprint 1 kick-off in chat (recorded as `D-S1-0` decision in the Sprint 1 runbook, which is created at the start of Sprint 1).

---

## 7. Spike-decision fanout

Each Sprint-0 spike that did **not** trivially PASS produces a fanout into
Sprint 1+ work. This section captures the **active** fallouts so we don't
forget them when later sprint work begins. (Historical / superseded
fanouts live inside the spike reports themselves, not here.)

### 7.1 Spike C ACCEPTED-WITH-DEBT (2026-04-23) — Mem0 stays in v1

Per Decision **D-S0-8** (see §0). The original "defer F15 to v1.5" fanout
that was first written for the FAIL verdict is preserved as historical
context inside [SPIKE_C.md §5.1](spike_reports/SPIKE_C.md#51-fanout-into-the-rest-of-the-plan-historical--superseded-by-61);
the **active** fanout is below and matches [SPIKE_C.md §6.1](spike_reports/SPIKE_C.md#61-fanout-into-the-rest-of-the-plan-active--replaces-51).

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
| User's Mem0 Cloud account | **Keep** the account and the active key. **Do not** rotate the Hobby key after Sprint 0; it carries forward into v1 until either quota or latency triggers a swap. Quota burn from the spike was ~1 % of the 10 K Hobby cap. | rajnish |
| `.env.example` | `MEM0_API_KEY` and `MEM0_BASE_URL` placeholders **stay**, with a comment that they are required for v1 (not v1.5 deferred). | sprint-1 owner |
| Re-evaluation triggers | See [SPIKE_C.md §7](spike_reports/SPIKE_C.md#7-re-open--swap-triggers) — "Mem0 search p95 > 800 ms over 24 h" alarm, Hobby quota at 80 %, traced TTFT regression, Mem0 latency improvements, or v1.5 product spec change. | sprint-3 owner |

### 7.2 Spike D SKIP (D-S0-6) — Cloud Trace + Cloud Logging only

| Surface | Change | Owner |
|--------|--------|-------|
| F16 (observability) | Ships in v1 without prompt-version capture and without Langfuse-style tool-span hierarchy; Cloud Trace covers the call-tree shape. | — |
| Sprint 2 — `S2.1.4` | **Drop** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` from the v1 secret set. | infra |
| Sprint 3 — `agent_ui_adapter/adapters/observability/` | Ship a `CloudTraceExporter` for v1; `LangfuseCloudHobbyAdapter` is a future composition-root-only swap. | sprint-3 owner |
| Sprint 4 — `S4.2.1` alarms | **Drop** the "Langfuse Cloud Hobby quota at 80%" alarm for v1. | sprint-4 owner |

---

## 8. Sprint 1 hand-off

Once §6 DoD is signed off, Sprint 1 begins **per the user's chosen scope option** (`skeleton_first` from this conversation):

1. **Pass 1** — scaffolding + tightened architecture test (S1.4.1).
2. **Pass 2** — `agent_ui_adapter/composition.py` + `langgraph.json` loader (S1.1.1, S1.1.2).
3. **Pass 3** — WorkOS JWT verifier adapter (S1.2.1) + tool ACL (S1.3.1).

Each pass ends with `pytest tests/ -q` green before the next begins. The Sprint 1 runbook (`SPRINT_1_RUNBOOK.md`) is written when Sprint 0 closes, mirroring this file's structure.
