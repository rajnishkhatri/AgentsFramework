---
name: playwright-agentic-e2e
description: >-
  End-to-end testing of streaming AI/agentic chat apps with Playwright — from
  zero-config scaffolding through authenticated, full-stack runs against
  cloud-hosted deployments. Use whenever the work touches Playwright and a
  chatbot / LLM / agent UI: setting up playwright.config and browser install,
  wiring authenticated sessions via storageState (WorkOS, Auth0, NextAuth,
  Clerk, custom cookies), mocking or asserting on SSE / streaming token
  responses, writing specs against a real or mocked agent, or pointing tests at
  a staging/production URL on Cloud Run, Vercel, or similar. Also for the
  surrounding lifecycle — choosing a test tier, handling non-deterministic LLM
  output, and verifying a run server-side via logs and traces. Trigger even when
  the user says "e2e tests", "browser tests", "test the chat UI", "log in during
  tests", "test streaming", or "test against staging" without naming Playwright.
  For project-specific commands and selectors, pair with a workspace skill.
license: Complete terms in LICENSE.txt
---

# Playwright E2E for Agentic Chat Apps

Testing a streaming agent UI end-to-end is harder than a normal web app for two
reasons: **the response is non-deterministic** (an LLM, not a fixture), and **it
arrives incrementally** (a token stream, not a single payload). Most flaky
agentic E2E suites fail because they ignore one of these — they assert exact
text that varies run-to-run, or they wait for a "request finished" signal that
never fires behind a long-lived stream.

This skill gives you a way of thinking that handles both, plus the mechanics for
auth and cloud-hosted targets. The organizing idea is the **mock cut-point**.

## The one decision that drives everything: where do you cut?

A chat app is a chain. A user message flows through the browser, usually an
auth/edge layer, a backend-for-frontend (BFF) or API route, and finally the
agent runtime (the LLM + tools). The reply streams back along the same chain.

```
Browser UI ── Edge/Auth ── BFF/API route ── Agent runtime (LLM + tools)
   │             │              │                    │
  T1 cut ────────┘              │                    │   page.route() — mock the stream in the browser
  T2 cut ───────────────────────┘                    │   mock backend HTTP — real BFF, fake agent
  T3 cut (no cut) ───────────────────────────────────┘   everything real, incl. the live model
```

Where you cut decides **what you can assert, how you handle auth, and how you
deal with non-determinism**. Pick the highest cut (most mocked) that still
exercises what you care about — it's faster, deterministic, and safe in CI.

| Tier | Cut point | What's real | What you assert | Auth | CI cadence |
| --- | --- | --- | --- | --- | --- |
| **T1 mocked** | Browser network layer (`page.route`) | UI + edge/auth middleware | Structure: an event rendered, a button appeared, a tool card showed | Unauth public surfaces, or a *fake* session cookie | Per-commit / PR |
| **T2 integration** | A mock backend HTTP server | UI + edge + real BFF/API routes | Proxy/transport behavior: headers survive, heartbeats, cancel, CRUD | Fake session, or real if the BFF demands it | Nightly |
| **T3 full-stack** | Nothing | The entire stack incl. the live model | Behavior: a real answer appeared, latency budgets, provenance | Real sign-in, once, reused | On-demand / release gate |

If the codebase already has a tier taxonomy (look for `e2e/`, a
`PLAYWRIGHT_TESTING_ARCHITECTURE` doc, or `test:e2e:t*` scripts), adopt its
names and cut-points instead of inventing your own. A paired workspace skill, if
present, will spell out the exact commands and selectors.

## Configure the skill to the workspace

This skill is deliberately stack-agnostic. Before writing code, fill in this
config from the repo (read `package.json`, the existing playwright config, the
auth library, and any architecture doc). Keep it in your working notes; the
templates and references refer back to these names.

```yaml
# --- App + runner ---
frontend_dir:        frontend         # where playwright.config lives
test_dir:            e2e              # specs root
package_manager:     pnpm             # npm | pnpm | yarn | bun
base_url_local:      http://localhost:3000
base_url_remote:     # e.g. https://my-app-xxxx-uc.a.run.app (Cloud Run) — set per run via BASE_URL

# --- Auth (see references/authentication.md) ---
auth_library:        # workos-authkit | auth0 | nextauth | clerk | custom
session_cookie_name: # e.g. wos-session, __session, next-auth.session-token
auth_gate_env:       E2E_AUTHENTICATED   # env flag that turns real sign-in on
storage_state_path:  e2e/.auth/state.json

# --- Streaming transport (see references/streaming-and-agents.md) ---
stream_endpoint:     # the path the UI POSTs to, e.g. /api/run/stream
stream_transport:    fetch            # fetch-stream | EventSource  (CHANGES mocking strategy!)
stream_protocol:     # sse | ndjson | websocket | ag-ui

# --- DOM handles (prefer data-testid; fall back to roles) ---
composer_selector:   # input the user types into
send_selector:       # the submit button
message_selector:    # where the assistant reply renders (mind aria-live, see below)
```

The single most consequential field is **`stream_transport`**. Playwright's
`page.route()` intercepts `fetch()` but **does not intercept native
`EventSource`** ([known issue](https://github.com/microsoft/playwright/issues/15353)).
If the app streams over `EventSource`, T1 browser-level mocking won't work and
you must mock one layer deeper (T2) or test live (T3). Confirm this early — it
silently breaks otherwise-correct T1 specs.

## Workflow

Follow these in order. Each step points to a reference for depth and a template
to copy. Don't read every reference up front — pull the one for the step you're on.

### 1. Scaffold (if Playwright isn't set up yet)

```bash
cd <frontend_dir>
<pm> create playwright            # or: <pm> add -D @playwright/test
<pm> exec playwright install --with-deps   # one-time browser download
```

Start from `assets/playwright.config.template.ts`. It already encodes the
patterns below — env-driven `baseURL`, conditional `webServer` (start a local
dev server only when the target is localhost), conditional auth, retain-trace
-on-failure, and one project per browser/device. Read
`references/configuration.md` for the why behind each block.

Two defaults that prevent the most common pain:
- `baseURL: process.env.BASE_URL ?? <base_url_local>` — the same specs then run
  against local *or* a deployed URL with zero code change.
- Only spin up a `webServer` when `BASE_URL` is local. Against a remote target
  there's nothing to start, and a stray `webServer` block will hang the run.

### 2. Set up authentication once, reuse everywhere

Almost every agent chat is behind a login. The wrong move is logging in inside
each test — slow and flaky. The right move: **sign in once, persist the session,
load it into every test's browser context.** That persisted blob is Playwright's
`storageState` (cookies + localStorage).

Read `references/authentication.md` — it covers the two patterns (a `setup`
project dependency, which is current Playwright best practice, vs. `globalSetup`,
which many existing repos use and is fine), all the provider-specific sign-in
flows (WorkOS AuthKit, Auth0, NextAuth, Clerk), and the **fake-session** trick:
minting a valid signed cookie locally so UI/visual tests run authenticated with
no network round-trip and no real user. Copy `assets/global-setup.template.ts`
and `assets/auth.fixture.template.ts`.

Three rules that save hours:
- **Gate real sign-in behind an env flag** (`<auth_gate_env>`). Unauthenticated
  CI must not attempt a login and crash; it should skip authed specs gracefully.
- **Pin the browser locale.** Headless Chromium picks a locale from
  `Accept-Language` and hosted login pages localize off it — a suite can suddenly
  render Afrikaans/another language and every text selector breaks. Set
  `locale: "en-US"` and an explicit `Accept-Language` header on the context.
- **Never commit `storageState`** — it's a live session. `.gitignore` the
  `.auth/` dir. Don't print secrets; read credentials from env, never hardcode.

### 3. Write specs at the right tier

Decide the cut (the table above), then write. Read
`references/streaming-and-agents.md` before writing anything that sends a message
and waits — it's the heart of testing these apps. Copy
`assets/spec.template.ts`.

The non-negotiables for streaming agent UIs:
- **Assert structure and provenance, not exact LLM prose.** "An assistant turn
  appeared and is non-empty", "a tool card rendered", "the trace id propagated",
  "latency p50 < budget" — these are stable. Exact wording is not; if you must
  check content, match a normalized substring or a regex, or use an LLM-judge
  step (see the reference).
- **Wait by polling for the rendered text to *settle*, not for a "finished"
  signal.** A streamed answer grows token by token; the reliable ready-signal is
  "the visible text stopped changing for N consecutive reads." Do **not** gate on
  the SSE response object's `finished()` (it can hang forever behind a long-lived
  stream or a route intercept) and do **not** assume "composer re-enabled" means
  done (some backends never re-enable it). The settle-poll is in
  `assets/helpers.template.ts` as `waitForResponse`.
- **Target the live region carefully.** Streaming UIs render into an
  `aria-live` region so screen readers announce tokens — but frameworks add their
  *own* live regions (e.g. Next.js's route announcer is
  `div[aria-live="assertive"][role="alert"]`). Scope your selector to the
  message container (e.g. `article div[aria-live="polite"]`), or you'll match the
  router's announcer and read empty text. Prefer a `data-testid` if you can add one.

### 4. Run — locally, then against the cloud-hosted target

```bash
# Local, fully mocked (T1) — no backend, no auth:
<pm> run test:e2e:t1                  # or: playwright test <mocked specs>

# Against a deployed environment (Cloud Run / Vercel / staging):
export BASE_URL=https://<your-deployment-url>
export <auth_gate_env>=1
export E2E_USER_EMAIL=...   E2E_USER_PASSWORD=...   # from env/secret store, never inline
<pm> exec playwright test <full-stack specs>
```

Read `references/running-and-ci.md` for the remote-target playbook (one BASE_URL
swaps the whole suite over), sharding, the CI cadence per tier, and headed/debug/
trace-viewer commands. The golden rule: **only T1 belongs in per-commit CI.**
Tiers that hit a real backend or a live model are on-demand / release-gate — they
cost money, they're slower, and a live model makes them inherently a bit flaky.

### 5. Verify the run server-side (full-stack only)

A green DOM assertion proves the *frontend* rendered something. For an agentic
system you often also need to prove the *backend* did the right thing — the
request reached the agent, the right tools ran, a trace was recorded. The UI
alone can't show this, and (importantly) a UI that renders nothing doesn't always
mean the backend failed — it may have completed while the final token never
reached the DOM. Cross-check both sides.

Read `references/cloud-and-verification.md` for the GCP/Cloud Run specifics
(structured-log queries — the gotcha that your bridge line is often in
`jsonPayload.message`, not `textPayload`), and how to reconcile DOM captures
with backend traces (Langfuse/OpenTelemetry/W&B). The bundled
`scripts/verify_run.py` is a starting point for "did N expected events land in
the logs/traces for this run?"

## Reference map

Read the one you need; each is self-contained.

| File | Read it when |
| --- | --- |
| `references/configuration.md` | Setting up / editing `playwright.config`, projects, webServer, env wiring |
| `references/authentication.md` | Any auth: storageState, setup-project vs globalSetup, provider flows, fake sessions |
| `references/streaming-and-agents.md` | Writing specs that send a message / assert on streamed or tool output; handling non-determinism |
| `references/running-and-ci.md` | Running locally or against a remote URL; sharding; CI tiering; debugging |
| `references/cloud-and-verification.md` | GCP/Cloud Run targets; verifying a run via logs + traces |

## Templates (copy, then adapt to the config)

| File | What it is |
| --- | --- |
| `assets/playwright.config.template.ts` | Env-driven config: conditional webServer, conditional auth, browser projects |
| `assets/global-setup.template.ts` | One-time sign-in + fake-session minting; writes storageState |
| `assets/auth.fixture.template.ts` | `authenticatedPage` fixture that loads storageState and skips gracefully |
| `assets/helpers.template.ts` | `sendMessage` (Enter + button fallback) and `waitForResponse` (settle-poll) |
| `assets/spec.template.ts` | A tiered spec skeleton with the right imports and skip guards |

## A note on safety

These tests drive real logins and can hit paid model endpoints. Keep credentials
in env vars or a secret manager, never in committed files or shell history.
Don't point destructive or write-heavy specs at production. When minting a fake
session, the signing secret must match the app's configured cookie password —
and a fake session is for *local* targets; against production it won't match the
server's secret and shouldn't be attempted.
