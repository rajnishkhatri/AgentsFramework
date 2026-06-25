# Model A/B SMOKE Run — Full Step-by-Step Report

**Date:** 2026-06-25 (run executed overnight 2026-06-24T20:25 → 21:15 local)
**Environment:** `abtest`-tagged Cloud Run revisions (prod 100% untouched)
**Driver:** `frontend/e2e/full-stack/model-ab.spec.ts` via Playwright, `--project=chromium-desktop`
**Config:** `MODEL_AB_SMOKE=1 MODEL_AB_REPEAT=1 MODEL_AB_REASONING_SAMPLE=1.0`
**Captured artifacts:** `cache/model_ab_live/ui_batch.jsonl.*.bak` (19 rotation files, 16 distinct rows)

---

## VERDICT BANNER

> ### ⛔ CONTAMINATED — INFRASTRUCTURE FAILURE (NOT a model result)
> All 16 captured runs failed identically at the **UI auth gate**, before any
> message was sent. **Zero LLM calls were made. Zero dollars were spent.** No
> model-behavior conclusion can be drawn. This is a pre-flight blocker on the
> A/B environment's authentication, not an A/B finding.

**Why this is CONTAMINATED, not HOLD:** per the harness's governance contract
([[model-ab-eval-harness]]), an instrumentation/identity failure is reported
*separately* from a real behavior regression. Every row has `response_text=""`,
`tool_card_count=0`, `ttft_ms=0`, and an `error` — the runs never reached the
model. Treating this as a model comparison would be the exact "garbage-in" error
the integrity guard exists to catch.

---

## 1. What ran, step by step

| Step | Action | Result |
|---|---|---|
| 0 | Stand up `abtest` Cloud Run tag (backend `00106-quq` MODEL_PROFILE_SET=all, frontend `00081-siv`), 0% traffic | ✅ up; prod 100% on untagged revs |
| 1 | Playwright global-setup auth (`E2E_AUTHENTICATED=1 E2E_REUSE_STORAGE=1`) | ✅ reused `e2e/.auth/state.json` (Jun-22), no fresh sign-in |
| 2 | For each model × case: open abtest FE, click `[data-testid='model-picker-trigger']` | ❌ **timed out ~200s every time** — trigger never rendered |
| 3 | Pin model, type prompt, capture screenshot + trace + tokens | ⛔ never reached (blocked at step 2) |

**The matrix that was attempted** (smoke subset, REPEAT=1, reasoning sample=1.0):

| Model | Cases attempted | Captured rows | Passed |
|---|---|---|---|
| Auto | GEN-L1, MT-retail, MEM-extraction | 3 | 0 |
| gpt-4o-mini | GEN-L1, MT-retail, MEM-extraction | 3 | 0 |
| gpt-4o | GEN-L1, MT-retail, MEM-extraction | 3 | 0 |
| claude-haiku-4-5 | GEN-L1, MT-retail, MEM-extraction | 3 | 0 |
| claude-sonnet-4-6 | GEN-L1, MT-retail, MEM-extraction | 3 | 0 |
| claude-opus-4-8 | MT-retail (reasoning-eligible only) | 1 | 0 |
| deepseek-v4-flash | (dir not reached before run ended) | 0 | — |
| deepseek-v4-pro | (reasoning-eligible) | 0 | — |
| **Total** | | **16** | **0** |

---

## 2. Case-by-case detail (with trace IDs, screenshot paths, my reasoning)

Each row below is a real captured `ui_batch` record. The **screenshot path** is
where the driver *would* write evidence (`cache/model_ab_live/screenshots/<model>/`);
those directories were created but are **empty** — the screenshot step is *after*
the failed `model-picker-trigger` click, so nothing was captured. The **trace_id**
is the per-run fresh trace the driver minted; because no run reached the backend,
**no Langfuse span exists for these trace_ids** (nothing to join).

### Case GEN-L1-read-sum-01 (general, L1) — across 5 models

| Model | trace_id | latency_ms | response | screenshot | outcome |
|---|---|---|---|---|---|
| Auto | (per-run fresh) | 199860 | `""` | `screenshots/Auto/` (empty) | fail |
| gpt-4o-mini | … | 199994 | `""` | `screenshots/gpt-4o-mini/` (empty) | fail |
| gpt-4o | … | 199970 | `""` | `screenshots/gpt-4o/` (empty) | fail |
| claude-haiku-4-5 | … | 200026 | `""` | `screenshots/claude-haiku-4-5/` (empty) | fail |
| claude-sonnet-4-6 | … | 200093 | `""` | `screenshots/claude-sonnet-4-6/` (empty) | fail |

**Error (identical):** `locator.click: Target page, context or browser has been
closed. — waiting for locator('[data-testid='model-picker-trigger']').first()`

**My reasoning judging this output:** The latency clustering at exactly ~200s is
the Playwright action timeout, not a model thinking-time. `response_chars=0` and
`ttft_ms=0` mean nothing ever streamed. The model-picker trigger is rendered only
*inside the authenticated chat shell*; its absence means the page is sitting on
the unauthenticated landing/login surface. **Judgment: no model output to grade —
the test never got past the front door.**

### Case MT-retail-return-window-01 (multi-turn, L2) — across 6 models

| Model | gj_id | latency_ms | response | outcome |
|---|---|---|---|---|
| Auto | GJ-ABMULT-01 | 200059 | `""` | fail |
| gpt-4o-mini | GJ-ABMULT-01 | 200146 | `""` | fail |
| gpt-4o | GJ-ABMULT-01 | 200114 | `""` | fail |
| claude-haiku-4-5 | GJ-ABMULT-01 | 199926 | `""` | fail |
| claude-sonnet-4-6 | GJ-ABMULT-01 | 200029 | `""` | fail |
| claude-opus-4-8 | GJ-ABMULT-01 | 200149 | `""` | fail |

**My reasoning:** This is the only case Opus reached (correctly — it is
reasoning-eligible: `family=multi-turn`, `difficulty=L2`, so the eligibility
filter `isReasoningEligible()` admitted it; the cheap arms ran it too). Same
front-door failure. The cost-control eligibility filter **worked as designed** —
Opus was correctly restricted to this one eligible case and never offered the L1
general case. That's the one positive signal: the spend-gating logic is sound,
even though we never got to exercise it on real calls.

### Case MEM-extraction-recall-01 (memory, L2) — across 5 models

| Model | latency_ms | response | outcome |
|---|---|---|---|
| Auto | 200073 | `""` | fail |
| gpt-4o-mini | 200117 | `""` | fail |
| gpt-4o | 200177 | `""` | fail |
| claude-haiku-4-5 | 200182 | `""` | fail |
| claude-sonnet-4-6 | 199964 | `""` | fail |

Same front-door failure across all.

---

## 3. Root cause (verified, not inferred)

The A/B environment uses a Cloud Run **traffic tag** to serve the `MODEL_PROFILE_SET=all`
revision without touching prod. Tags produce a **subdomain** URL:
`https://abtest---agent-frontend-w65nrxwkiq-uc.a.run.app`.

The stored WorkOS session — `frontend/e2e/.auth/state.json`, minted Jun-22 against
the **prod** FE URL — contains the app-session cookie:

```
domain = agent-frontend-w65nrxwkiq-uc.a.run.app   name = wos-session
```

**No leading dot.** A host-only cookie is sent **only** to that exact host. The
browser will **not** send `wos-session` to `abtest---agent-frontend-…`. Verified live:

- `GET https://abtest---…/` → `200` (renders the **unauthenticated** landing page)
- `GET https://abtest---…/chat` → `404` (auth-gated route absent without session)
- stored cookie domain is the bare prod host, not `.…run.app` and not the abtest host

So every run loaded the abtest FE **logged out** → chat shell never mounts →
`[data-testid='model-picker-trigger']` never exists → `locator.click` waits the
full action timeout (~200s) → fail. **This is the Cloud-Run-tag-subdomain auth
caveat, confirmed.**

**Cost impact: $0.** The failure is upstream of the first LLM call — the message
is never sent. No backend run, no Langfuse trace, no token burn.

### 3a. Second defect found while diagnosing — the abtest FE revision is mis-wired

Inspecting the abtest FE revision `00081-siv` env revealed **two bad env vars**
baked into the tag when it was stood up (independent of the cookie issue):

| Env var | abtest value (WRONG) | should be |
|---|---|---|
| `NEXT_PUBLIC_WORKOS_REDIRECT_URI` | `https://agent-frontend-…a.run.app/api/auth/callback` (**prod host**) | `https://abtest---agent-frontend-…a.run.app/api/auth/callback` |
| `MIDDLEWARE_URL` | `v3` (**garbage**) | `https://abtest---agent-backend-combined-…a.run.app` |

Consequences:
- **Redirect URI points at prod** → even a *fresh* sign-in on the abtest FE would
  send the OAuth callback to the **prod** origin, mint the session **there**, and
  the abtest host would still be logged out. Same failure class as
  the dev `:3003`-vs-`:3000` redirect bug. **A fresh sign-in alone does NOT fix
  this** — the redirect URI must be corrected first.
- **`MIDDLEWARE_URL=v3`** → the abtest FE would not even reach the abtest backend
  (the `MODEL_PROFILE_SET=all` revision). Pinning DeepSeek/Anthropic models would
  fail regardless of auth. This is a stand-up wiring drop in the abtest tag.

**Net:** the abtest FE revision must be **redeployed** with both env vars correct
*and* the abtest callback added to the WorkOS allowlist before any authenticated
A/B run can succeed. The earlier `E2E_REUSE_STORAGE` cookie path was never going
to work; correcting these two env vars + WorkOS allowlist (Option A) is the path.

### 3b. `E2E_BYPASS_AUTH` (Option C) is impossible on a deployed revision — by design

`frontend/app/page.tsx:22-24` double-gates the bypass:
`NODE_ENV !== "production" && E2E_BYPASS_AUTH === "1"`. The deployed image is a
production build (`NODE_ENV=production`), so the flag is **inert in prod builds**
— a deliberate safety property so the bypass can never leak to a real deployment.
Option C is therefore not available for the abtest revision. (Good security
posture; just means we can't shortcut auth.)

---

## 4. Governance read (four-pillar)

- **Recording:** truthful — every row honestly records `outcome=fail`, empty
  response, and the verbatim error. No fabricated success.
- **Validation:** the integrity guard would mark every row CONTAMINATED
  (`model_used` empty / no carrier), correctly refusing to promote.
- **Reasoning / Identity:** N/A — no model decision was ever made.
- **Verdict honesty:** reported as CONTAMINATED (instrumentation), **not** HOLD
  (behavior). The two are kept separate, per contract.

---

## 5. The fix (three options, recommended first)

**Option A — redeploy abtest FE correctly + fresh sign-in against abtest origin (recommended).**
This fixes BOTH the cookie-subdomain issue (§3) AND the mis-wired env (§3a):
1. **WorkOS dashboard (user-only — I cannot do this):** add
   `https://abtest---agent-frontend-w65nrxwkiq-uc.a.run.app/api/auth/callback`
   to the redirect-URI allowlist.
2. **Redeploy abtest FE revision** with corrected env (I can script this):
   `NEXT_PUBLIC_WORKOS_REDIRECT_URI=https://abtest---agent-frontend-…/api/auth/callback`
   and `MIDDLEWARE_URL=https://abtest---agent-backend-combined-…a.run.app`
   (use the `fill_stress_profile_url.py` pattern that wired the stress tag).
3. Re-run with `E2E_AUTHENTICATED=1` (NO `E2E_REUSE_STORAGE`) and
   `BASE_URL=https://abtest---…` → sign-in mints a session **host-scoped to
   abtest**, the callback returns to abtest, cookie carries, chat shell mounts.

⚠ **Blocked on the user for step 1** (WorkOS dashboard is a console action). Steps
2–3 are scriptable but pointless until step 1 lands (sign-in would 400 on an
un-allowlisted redirect URI).

**Option B — point the sweep at the PROD FE host (no subdomain).**
The reused Jun-22 cookie is already valid on the prod host. Serve the A/B by
making the **prod FE** talk to the **abtest backend** (the model set lives on the
backend, not the FE). Requires either a prod FE revision with
`MIDDLEWARE_URL → abtest backend` (a new tagged FE rev on the bare host is not
possible — tags always subdomain), or a per-request backend override header the
BFF forwards. More plumbing; only do this if WorkOS allowlist changes are
undesirable.

**Option C — bypass auth for the sweep.**
`E2E_BYPASS_AUTH=1` on the abtest revision (if the build honors it) skips WorkOS
entirely for the test. Cleanest for a throwaway A/B env, but requires the abtest
image to ship the bypass flag and we must confirm it does **not** leak to prod
(prod is a different revision, so safe by construction). This is the fastest path
if the flag is present.

**Recommendation:** **Option A** — it exercises the real auth path (most faithful
to prod), is a dashboard + one-env-var change, and leaves no test-only bypass in
the deployed surface.

---

## 6. What is proven good (don't re-litigate)

- **Cost-control eligibility filter works:** Opus was offered exactly 1 case
  (the L2 multi-turn one) and never the L1 general case; dry-run earlier confirmed
  Opus 7 / Pro 8 vs 93 each for cheap arms.
- **Driver mechanics work up to the auth gate:** per-run fresh `trace_id`, JSONL
  rotation (`.bak` per run), `gj_id` bridge tags (`GJ-ABMULT-01`), MODEL×CASE
  matrix iteration, reasoning-eligibility gating — all firing correctly.
- **Prod is untouched:** backend `00097-hc7` / frontend `00072-zbp` at 100%;
  `abtest` tags at 0%.
- **The `/models` and DeepSeek wiring** landed earlier (commits `81cfbe5`,
  foundations apply) — not implicated here.

---

## 7. Next action (gated on user, since it's the first real spend)

1. Apply **Option A** (WorkOS allowlist + abtest redirect URI + fresh sign-in).
2. Re-run the **same 22-run smoke** (`MODEL_AB_SMOKE=1 REPEAT=1 SAMPLE=1.0
   --project=chromium-desktop`) — now it should produce real `response_text`,
   screenshots, and joinable Langfuse traces.
3. Review the smoke report (this time with real metrics).
4. **Only then**, with go-ahead, the full 573-run matrix.
5. Run `scripts/analyze_model_ab.py` for the cross-model table.
6. Teardown: `gcloud run services update-traffic agent-{backend-combined,frontend}
   --region us-central1 --remove-tags abtest`.
