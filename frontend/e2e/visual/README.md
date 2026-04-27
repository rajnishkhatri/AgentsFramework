# UI Visual Regression Suite

Chromium-only Playwright suite that captures screenshot baselines for the
core UI states and fails when the rendered UI drifts from those baselines.

It is **separate** from the T1/T2/T3 behavior suites and is excluded from
`pnpm test:e2e:t1` via the `@visual` tag in each test name. Run it
explicitly when you intend to verify or update visual baselines.

## Files

- `[ui-visual.spec.ts](ui-visual.spec.ts)` — the spec; one `@visual` test
per UI state.
- `ui-visual.spec.ts-snapshots/` — PNG baselines, generated on first run
and committed to git.

## States covered

Baselines that exist today (all generated with `E2E_BYPASS_AUTH=1`):


| Baseline                                             | Mode   |
| ---------------------------------------------------- | ------ |
| `landing-light-chromium-desktop-darwin.png`          | unauth |
| `landing-dark-chromium-desktop-darwin.png`           | unauth |
| `sign-in-cta-focused-chromium-desktop-darwin.png`    | unauth |
| `chat-empty-light-chromium-desktop-darwin.png`       | bypass |
| `chat-empty-dark-chromium-desktop-darwin.png`        | bypass |
| `composer-focused-typed-chromium-desktop-darwin.png` | bypass |
| `chat-plain-markdown-chromium-desktop-darwin.png`    | bypass |
| `tool-card-error-chromium-desktop-darwin.png`        | bypass |


Tests for **tool card success**, **run-controls toolbar**, **thread
sidebar**, and **generative pyramid panel** are still in the spec but
auto-skip today because `[../../app/chat-shell.tsx](../../app/chat-shell.tsx)`
is a placeholder shell that doesn't yet emit those components. Baselines
will fill in automatically the next time
`pnpm test:e2e:visual:auth:update` is run after those features ship.

All network calls are stubbed via `page.route()` (`/api/run/stream`,
`/api/run/cancel`, `/api/threads`) using the existing fixtures in
`[../fixtures/](../fixtures/)`, so the suite runs without a backend.

## Auth

`app/page.tsx` calls WorkOS `withAuth()` server-side. Without a session,
the page renders the sign-in CTA and the chat-shell-dependent tests
auto-skip. The landing-page baselines run regardless.

There are two ways to unlock the chat-shell baselines.

### Option A: dev-only auth bypass (default for visual tests)

`app/page.tsx` carries an env-gated escape hatch:

```ts
const E2E_BYPASS_AUTH =
  process.env.NODE_ENV !== "production" &&
  process.env.E2E_BYPASS_AUTH === "1";
```

When the flag is set on a non-production build, the page skips
`withAuth()` and renders the chat shell with a synthetic
`e2e@example.com` user. The double gate ensures the branch can never be
enabled in a production build.

The visual scripts wire this through automatically:

```bash
pnpm test:e2e:visual:auth:update   # generate / refresh baselines
pnpm test:e2e:visual:auth          # verify against committed baselines
```

Both scripts export `E2E_BYPASS_AUTH=1` and the
[Playwright webServer config](../../playwright.config.ts) propagates it
into the `next dev` process and forces a fresh server (no
`reuseExistingServer`) so the env actually takes effect. No WorkOS
credentials, JWKS access, or sealed cookies are required.

### Option B: real WorkOS sign-in

Drives the live AuthKit hosted UI. Use this when you specifically need a
real backend round-trip (e.g. SS2.10 trust-badge baselines that touch
the trust kernel).

```bash
export E2E_AUTHENTICATED=1
export E2E_USER_EMAIL=...
export E2E_USER_PASSWORD=...   # or E2E_USER_OTP=...
pnpm test:e2e:visual:update
```

`[../global-setup.ts](../global-setup.ts)` signs in once and persists
the WorkOS session to `e2e/.auth/state.json`; the
`storageState` default in
`[../../playwright.config.ts](../../playwright.config.ts)` loads it for
every test.

> An additional fake-session path (`E2E_FAKE_SESSION=1`) is implemented
> in `global-setup.ts` for unit-test scenarios that need a sealed
> `wos-session` cookie. It is **not** sufficient for the visual suite:
> AuthKit's middleware verifies the access-token signature against
> WorkOS JWKS at request time and drops the cookie when the local HS256
> token fails RS256 verification. Use Option A for the visual suite.

## Commands

From `frontend/`:

```bash
# Generate or refresh baselines after an intentional UI change.
pnpm test:e2e:visual:update

# Run the suite against the committed baselines (CI / local check).
pnpm test:e2e:visual

# Inspect failures.
pnpm exec playwright show-report
```

## Artifacts

- HTML report: `frontend/playwright-report/index.html`
- Failure screenshots, diffs, traces: `frontend/test-results/`
- Baselines: `frontend/e2e/visual/ui-visual.spec.ts-snapshots/`

## Conventions

- Every test name starts with `@visual` so the tag-based filter works
(`pnpm test:e2e:t1` uses `--grep-invert '@t2|@t3|@visual'`).
- `forceTheme(page, ...)` pins `data-theme` and `prefers-color-scheme` so
light/dark baselines are deterministic.
- `expect.toHaveScreenshot` defaults are tuned in
`[../../playwright.config.ts](../../playwright.config.ts)`:
`maxDiffPixelRatio: 0.02`, `threshold: 0.2`, `animations: "disabled"`,
`caret: "hide"`, `scale: "css"`. Override per-call when needed.
- Component-level shots target the closest stable locator (toolbar,
details card, panel) instead of full-page when full-page diffs would be
noisy.

## Adding a new visual

1. Add a `test("@visual <state>", ...)` block in
  `[ui-visual.spec.ts](ui-visual.spec.ts)` that drives the page into the
   desired state via `stubBackend()` + helpers from `../fixtures/`.
2. Run `pnpm test:e2e:visual:update` to generate the baseline.
3. Commit the new PNG under `ui-visual.spec.ts-snapshots/` along with the
  spec change.

