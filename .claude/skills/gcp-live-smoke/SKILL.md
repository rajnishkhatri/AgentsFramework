---
name: gcp-live-smoke
type: skill
description: >-
  Run the Phase 2 live GCP smoke test for the eval-UI stack — one real
  browser run against the deployed Cloud Run frontend that proves the
  agent pipeline end-to-end (terminal complete state, tool cards, and the
  F10-Tier2 reasoning recap). Use this whenever the user asks to verify a
  GCP/Cloud Run deploy, run the live smoke, check the deployed frontend,
  validate the reasoning recap in production, run "phase 2" of the smoke
  plan, or confirm a redeploy worked — even if they don't say "smoke test"
  explicitly.
---

# GCP Live Smoke (Phase 2 of the critical-path smoke plan)

Two bounded Playwright tests against the deployed frontend, always run
together. Both sign in to WorkOS for real.

**Test 1 — quick recap smoke.** One prompt forcing ≥2 tool calls (write a
file, read it back); asserts the three things the eval pipeline depends on:

1. The assistant message reaches `data-state="complete"` (the same
   terminal anchor the GoalJudge batch harness waits on).
2. At least one tool card rendered from the real tool chain.
3. The `[data-testid='reasoning-summary']` expander exists, is collapsed
   by default, and reveals non-empty recap text — proving the in-stream
   `CUSTOM reasoning_summary` event flows through the deployed build.

**Test 2 — L2 planning stress (τ-bench-style).** A three-turn conversation
in one thread: a multi-file pipeline plan, then a non-collaborative
mid-task revision ("bananas should be 9, not 7 — and add dates.txt"),
then a continuation that only works if checkpointer state survived the
earlier turns. Asserts every turn settles to `complete`, ≥6 tool cards
total with **zero** `data-status="errored"`, ≥1 reasoning recap, and
**cross-turn continuity**: the last read of bananas.txt must return the
revised value ("9"). The continuity check exists because tool calls can
report success while an overwrite silently fails to stick (seen live
2026-06-12 — stale file_io reads); a continuity failure with zero errored
cards means exactly that bug shape, not a test problem. This is the turn
shape where ReAct agents and stale state historically break.

Plan context: `docs/plans/critical_path_smoke_testing.plan.md` §Phase 2.
This is the only test that touches the real stack; never expand it into a
full-suite run (the full T1 tier takes 8+ hours locally and is banned as a
local gate).

## Prerequisites

- The build under test is already deployed to Cloud Run (this skill
  verifies a deploy; it does not deploy).
- WorkOS credentials `E2E_USER_EMAIL` + `E2E_USER_PASSWORD` in the
  repo-root `.env` (global-setup loads it automatically). Never print
  these values — if you must verify one, use a fingerprint (length +
  character classes) only.
- No local server needed: BASE_URL is remote, so Playwright skips the
  webServer entirely.

## Run it

From the repo root, in the background (results must survive session
interruptions), with a hard 10-minute bound:

```bash
cd frontend && \
BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app \
E2E_AUTHENTICATED=1 \
npx playwright test full-stack/reasoning-recap-live.spec.ts \
  --project=chromium-desktop --global-timeout=600000 \
  --reporter=json > recap-live-results.json 2> recap-live-stderr.log
```

Notes:
- Expected wall time is ~2–4 min (login + quick smoke ~20 s + 3-turn
  stress run). Anything past 10 minutes is a hang; the global timeout
  kills it — treat that as a failure.
- `E2E_AUTHENTICATED=1` triggers `e2e/global-setup.ts`, which performs a
  fresh WorkOS password login and writes `e2e/.auth/state.json`. Do not
  set `E2E_REUSE_STORAGE=1` unless a login just succeeded in this session
  — stale storage state silently 401s.
- macOS has no GNU `timeout`; the bound comes from `--global-timeout`.

## Read the verdict

Parse `frontend/recap-live-results.json`. **Gotcha:** global-setup prints
a log line to stdout before the JSON reporter output, so slice from the
first `{` before parsing:

```bash
python3 -c "
import json
raw = open('frontend/recap-live-results.json').read()
d = json.loads(raw[raw.index('{'):])
print(d['stats'])
"
```

Pass = `stats.expected == 2` and `stats.unexpected == 0`. Report the
verdict from this file, never from terminal scrollback.

Screenshot evidence lands in `frontend/smoke-screenshots/`:
`recap-live.png` / `stress-live.png` on pass, `*_FAILED.png` on fail
(one evidence shot per test; gitignored run
artifacts; each run overwrites the previous file of the same outcome).
All tool cards and the reasoning expander are force-opened before
capture, so the screenshot shows every tool's input/output — on a
failure, look there for the errored tool's payload (`data-status`
distinguishes completed vs errored cards). Mention the path in your
report so the user can eyeball the final UI state.

## If it fails: first-pass diagnosis

Report the failing assertion and error from the JSON report plus the
screenshot path, then check these known causes in order — they have all
happened before:

1. **Login failed / tests skipped with "storage state not found"** — the
   usual culprit is a stale `E2E_USER_PASSWORD` in the repo-root `.env`
   (drifted from the working value; WorkOS shows "Ongeldige e-pos of
   wagwoord"). Ask the user to re-save the real value to `.env`; verify
   value-free via fingerprint only.
2. **Run settles to `data-state="error"` with a red `OperationalError`
   line** ("server closed the connection unexpectedly" / "the connection
   is closed") — the checkpointer's Postgres connection to Cloud SQL went
   stale. Confirm via the Cloud SQL Auth Proxy log
   (`gcloud logging read 'resource.labels.service_name="agent-backend-combined" AND "connection"' --freshness=30m`
   — look for "connection aborted … connection reset by peer" on
   `agent-db:3307`). The backend does not currently self-heal a dead
   pooled connection, so retries fail until the Cloud Run instance
   recycles. This is a backend bug to report, not a deploy problem.
3. **Timeout waiting for `data-state="complete"`** — the run never
   settled. Check Cloud Run logs for the backend error:
   `gcloud logging read 'resource.labels.service_name="agent-backend-combined"' --freshness=1h`
   (gcloud is authed as rajnish.khatri@gmail.com, project
   `agent-prod-gcp-dev`, us-central1). Cold starts can also push the
   first token late — a single retry is acceptable here.
4. **Recap expander missing (`reasoning-summary` count 0)** — either the
   deployed backend predates the reasoning-recap feature (commit
   `345a619`; redeploy needed) or the run made fewer than 2 tool calls so
   the cost guard skipped the recap. The screenshot shows how many tool
   cards rendered — if <2, the model answered without tools; rerun once
   before concluding the deploy is bad.
5. **Selector never matches despite a visible answer** — the streamed
   text lives in `article div[aria-live='polite']` (the DIV, not the
   article). If helpers changed, re-check `e2e/fixtures/helpers.ts`.

Do not loop retries: one diagnostic rerun maximum, then report findings
and stop.
