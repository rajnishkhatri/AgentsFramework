# Running & CI

How to run the suite locally and against a deployed target, what belongs in CI at
which cadence, and the debug tools that save you.

## Table of contents
- [Local runs](#local-runs)
- [Running against a deployed target](#running-against-a-deployed-target)
- [CI tiering: what runs when](#ci-tiering)
- [Sharding](#sharding)
- [Debugging](#debugging)
- [Reports & artifacts](#reports--artifacts)

## Local runs

```bash
cd <frontend_dir>
<pm> exec playwright install --with-deps   # one-time

# Fully mocked tier — no backend, no auth, deterministic:
<pm> run test:e2e:t1            # or: playwright test <mocked specs> --ignore-snapshots

# A single spec / a single test:
<pm> exec playwright test e2e/composer.spec.ts
<pm> exec playwright test -g "renders the composer"

# One browser project:
<pm> exec playwright test --project=chromium-desktop
```

## Running against a deployed target

The whole point of an env-driven `baseURL`: one variable retargets the suite. To
run the full-stack tier against a Cloud Run / Vercel / staging deployment:

```bash
export BASE_URL=https://<your-deployment-url>
export E2E_AUTHENTICATED=1
export E2E_USER_EMAIL=...            # from a secret manager / env, never inline
export E2E_USER_PASSWORD=...         # likewise
# (optional) point the app's own backend var at the deployed backend:
export MIDDLEWARE_URL=https://<your-backend-url>

<pm> exec playwright test <full-stack specs>
```

What happens: the conditional `webServer` sees a non-local `BASE_URL` and starts
nothing; `globalSetup` (gated by `E2E_AUTHENTICATED=1`) signs in once against the
deployed login and writes storageState; every authed spec reuses it and drives the
live UI. No code changes between local and remote — only env.

Tips:
- **Smoke first.** Run one representative spec (or one case via a filter env)
  against the deployment before the full batch, to catch auth/URL/selector drift
  cheaply.
- **Reuse the session within a session.** `E2E_REUSE_STORAGE=1` skips re-sign-in
  when a fresh state file exists — faster iteration while debugging one spec.
- **Stale state is the #1 remote failure.** If authed specs suddenly all skip or
  redirect to login, delete the state file and re-run; the session expired.

## CI tiering

Map tiers to triggers by cost and determinism. **Only the fully-mocked tier
belongs in per-commit CI** — it's deterministic and free. Anything that hits a
real backend or a live model is on-demand / release-gate: it costs money, it's
slower, and a live model makes it inherently a little flaky.

| Tier | Trigger | Typical time | Required env |
| --- | --- | --- | --- |
| Mocked (T1) | Every commit / PR | ~2 min | none |
| BFF integration (T2) | Nightly | ~5 min | mock-backend flag |
| Full-stack (T3) | Release gate / manual | ~15 min | auth gate + creds + BASE_URL + backend URL |
| Cross-browser matrix | Release gate | ~20 min | same as T3 (or mocked, if matrix is structural) |

In GitHub Actions, use `reporter: "github"` in CI (annotations on the PR) and
`html` locally. `forbidOnly: !!process.env.CI` fails the build if a stray
`test.only` was committed. Cache the Playwright browser binaries between runs.

## Sharding

For large suites, split across machines with `--shard`:

```bash
playwright test --shard=1/4    # machine 1 of 4
```

Note the interaction with auth: the **setup-project** pattern re-runs sign-in per
shard (each machine needs its own state file) — fine, but N logins. If that's
costly (rate limits on the test user), prefer producing the state file once in a
prep step and distributing it, or use an on-demand auth pattern that signs in only
where needed. Don't shard a real-backend tier so wide that concurrent agent runs
trip rate limits or collide on a shared test user.

## Debugging

```bash
<pm> exec playwright test --headed           # watch it run
<pm> exec playwright test --debug e2e/x.spec.ts   # Playwright Inspector, step through
<pm> exec playwright test --ui                # time-travel UI mode (best for streaming)
PWDEBUG=console <pm> exec playwright test     # pause + console access
```

For a streaming bug, **UI mode** and the **trace viewer** are far more useful than
`console.log` — they show each network event and DOM snapshot on a timeline, so
you can see exactly when (and whether) the final token reached the DOM.

```bash
<pm> exec playwright show-trace test-results/<...>/trace.zip
```

## Reports & artifacts

Every run produces:
- `playwright-report/index.html` — interactive report (`playwright show-report`)
- `test-results/` — traces, screenshots, videos for failures

For agentic full-stack runs it's common to also write a per-run **capture
artifact** (e.g. JSONL: one row per case with the prompt, the settled response
text, tool-card count, ids, timestamp, and target URL). That artifact is what you
reconcile against backend logs/traces in the verification step — see
`cloud-and-verification.md`. Clean up large debug screenshots and `test-results/`
between sessions so they don't accumulate.
