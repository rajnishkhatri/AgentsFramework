# Critical-Path Smoke Testing Plan

**Status:** COMPLETE 2026-06-12 — Phase 1 PASSED; Phase 2 PASSED (live GCP)
**Owner:** frontend E2E verification for the eval-UI / GoalJudge stack
**Supersedes:** full T1 Playwright tier as a local verification gate

## Why this plan exists

The full T1 tier (`npm run test:e2e:t1`) is **610 tests across 5 browser
projects** (chromium-desktop, mobile-safari, webkit-desktop, firefox-desktop,
ipad) run **strictly serially** (`workers: 1`, `fullyParallel: false` in
`frontend/playwright.config.ts`). Locally it takes many hours — four background
attempts on 2026-06-11/12 ran 8h+ without completing and produced no
recoverable report.

Decision (2026-06-12): full-suite Playwright regression is **out of scope for
local verification**. We smoke-test only the critical path. The 5-browser
matrix remains a CI / overnight concern, not a commit gate.

## The 6 critical-path spec files

All live in `frontend/e2e/`. Together: **27 tests** on chromium-desktop.

| # | Spec file | Critical path covered | Why it gates commits |
|---|-----------|----------------------|----------------------|
| 1 | `smoke.spec.ts` | App boots, composer renders, a message can be sent | If this fails, nothing else matters |
| 2 | `streaming.spec.ts` | SSE token deltas reach the answer body progressively | Core chat output path (connectFetchSSE → reducer → StreamingMarkdown) |
| 3 | `chat-shell.spec.ts` | Terminal `data-state="complete"` on the assistant message | The deterministic anchor the GoalJudge T3 batch harness waits on |
| 4 | `tool-cards.spec.ts` | Tool calls render as collapsible cards, incl. errored state (`Error:` prefix) | Eval evidence: `tool_card_count > 0` is a T3 acceptance criterion |
| 5 | `guaranteed-answer.spec.ts` | F11 fallback answer synthesized when the model returns no prose | Guarantees `response_text` is never empty in batch captures |
| 6 | `reasoning-summary.spec.ts` | F10-Tier2 "Show reasoning" expander: absent on cost-guarded runs, collapsed by default, expands to recap text | Newest feature (commit `345a619`); exercises the `Custom{reasoning_summary}` wire path |

All 6 use **mocked SSE** (`page.route("**/api/run/stream")` + fixtures in
`frontend/e2e/fixtures/scenarios.ts`) — no backend, no LLM cost, deterministic.

## Phase 1 — local smoke run (gate for frontend-touching commits)

```bash
cd frontend && E2E_BYPASS_AUTH=1 E2E_SCREENSHOTS=1 npx playwright test \
  smoke.spec.ts streaming.spec.ts chat-shell.spec.ts \
  tool-cards.spec.ts guaranteed-answer.spec.ts reasoning-summary.spec.ts \
  --project=chromium-desktop --output=smoke-screenshots \
  --reporter=json > smoke-results.json
```

Operational rules:
- **`E2E_BYPASS_AUTH=1` is mandatory** — without it the composer never renders
  and every test self-skips (silent false-green).
- Run in **background with `--reporter=json` to a file** so results survive
  session kills/compaction; never pipe through `tail` (swallows all progress).
- **Hard time bound: 10 minutes.** Expected runtime is ~2–4 min; anything
  past 10 is a hang — kill it and treat as a failure to diagnose.
- Port 3000 must be free first (`lsof -nP -iTCP:3000 -sTCP:LISTEN`); orphaned
  `next-server` processes from killed runs are the usual culprit.
- Read the verdict from `smoke-results.json` → `.stats` (expected/unexpected/
  skipped), not from terminal scrollback.

### Screenshot evidence (both phases)

Every smoke run leaves visual evidence, pass or fail:
- **Phase 1:** `E2E_SCREENSHOTS=1` flips the Playwright `screenshot` option
  from `only-on-failure` to `on`, so each test saves a final-state
  screenshot; `--output=smoke-screenshots` collects them under
  `frontend/smoke-screenshots/<test-dir>/test-finished-1.png`.
- **Phase 2:** the live spec writes `recap-live.png` (pass) or
  `recap-live_FAILED.png` (fail) directly to `frontend/smoke-screenshots/`
  (override via `SMOKE_SCREENSHOT_DIR`) and attaches it to the report.
  Tool cards + reasoning expander are force-opened before capture so the
  evidence shows each tool's input/output (incl. errored payloads).
- `frontend/smoke-screenshots/` is a run artifact — gitignored, never
  committed.

Pass criteria: **0 unexpected** (expected shape: 15 passed / 12 skipped).
The 12 skips are by design, not failures: most of `smoke.spec.ts` plus
`streaming.spec.ts`'s incremental-render test require real WorkOS
credentials (`E2E_USER_EMAIL` / `E2E_AUTHENTICATED`) and self-skip in
mocked mode; the strict-CSP test skips on localhost because `next dev`
serves the dev CSP (`buildDevCSP` in `frontend/middleware.ts`) — it only
asserts against deployed targets.

## Phase 2 — one live GCP smoke (after redeploy)

Pre-requisite: redeploy `agent-backend-combined` + frontend so commit
`345a619` (reasoning recap) is live.

One bounded test (~3 min) against
`BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app`:
- Send a single prompt that forces ≥2 tool calls (write file then read it
  back — same shape as the GJ-001 registry case).
- Assert: run reaches `data-state="complete"`, ≥1 tool card rendered,
  `[data-testid="reasoning-summary"]` present with non-empty recap text.
- Auth via the saved WorkOS storage state (see
  `frontend/e2e/` auth setup; stale `.env` creds are a known gotcha).

Also includes an **L2 planning stress test** (τ-bench-style): a 3-turn
conversation in one thread — multi-file pipeline plan, mid-task revision,
state-dependent continuation — asserting all turns complete, ≥6 tool
cards with zero errored, ≥1 recap. Both tests always run together.

These are the only tests that touch the real stack; everything else stays
mocked. Implemented as `frontend/e2e/full-stack/reasoning-recap-live.spec.ts`;
runnable via the `gcp-live-smoke` skill (`docs/skills/gcp-live-smoke/`).

## Out of scope (explicitly)

- The other 11 T1 spec files (accessibility, theme, thread-sidebar,
  eval-mode, composer, error-resilience, generative-ui, mobile-responsive,
  observability, run-controls, task-list) — valuable, but not commit gates.
- mobile-safari / webkit / firefox / ipad projects locally.
- The 22-case GoalJudge T3 batch — already passed 22/22 on 2026-06-11
  (`cache/goaljudge_eval/ui_batch_t3_2026-06-11_v2.jsonl`); rerun only after
  deploys that touch the run pipeline.

## Execution record

- 2026-06-12: plan drafted, reviewed, and approved by Rajnish.
- 2026-06-12: Phase 1 first run — 35s, 15 passed / 11 skipped / **1 failed**:
  the strict-CSP test asserts the production policy and can never pass
  against the local dev server. Fixed by adding an `isLocalTarget()` skip
  guard to `frontend/e2e/smoke.spec.ts` (matches the file's existing
  skip-guard convention; the assertion is unchanged for deployed targets).
- 2026-06-12: Phase 1 rerun — **PASSED**: 15 passed / 12 by-design skipped /
  0 unexpected in 34s (`frontend/smoke-results.json`). Phase 1 gate green.
- 2026-06-12: Phase 2 — **PASSED** after Rajnish redeployed with `345a619`.
  New spec `frontend/e2e/full-stack/reasoning-recap-live.spec.ts` (auth
  fixture + fresh WorkOS login via global-setup) drove one real 2-tool run
  (write `recap_smoke.txt`, read it back) against
  `https://agent-frontend-w65nrxwkiq-uc.a.run.app`. All three criteria held:
  `data-state="complete"`, ≥1 tool card, non-empty recap in the
  `reasoning-summary` expander (collapsed by default). 1 passed / 0
  unexpected, test 7.5s, 15.3s wall incl. login
  (`frontend/recap-live-results.json`). Note: `--reporter=json` stdout gets
  a global-setup log line prepended — parse from the first `{`.
- Lessons captured: macOS has no GNU `timeout` — use Playwright's
  `--global-timeout=600000` for the 10-minute bound instead.
- 2026-06-12: Phase 2 wrapped as the `gcp-live-smoke` skill
  (`docs/skills/gcp-live-smoke/SKILL.md`); screenshots now captured on
  pass AND fail (see §Screenshot evidence). Skill validation caught a
  real backend bug: a Cloud SQL connection reset (09:24 UTC) left the
  checkpointer's pooled Postgres connection dead — runs failed with
  `OperationalError` until a fix was deployed. Post-fix rerun via the
  skill: **PASSED** 1/1 in 36.6s (run start 09:56 UTC), evidence
  `frontend/smoke-screenshots/recap-live.png`.
