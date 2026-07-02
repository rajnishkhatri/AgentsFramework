# Configuration

How to set up `playwright.config.ts` so the same specs run locally and against a
deployed environment, with auth and browser coverage handled cleanly. Copy
`assets/playwright.config.template.ts` and edit against your config block.

## Table of contents
- [Env-driven baseURL](#env-driven-baseurl)
- [Conditional webServer (the remote-target trap)](#conditional-webserver)
- [Conditional auth wiring](#conditional-auth-wiring)
- [Trace, screenshot, video on failure](#artifacts-on-failure)
- [Projects: browsers and devices](#projects)
- [Parallelism and a real-backend caveat](#parallelism)
- [Timeouts](#timeouts)

## Env-driven baseURL

Hardcoding a URL forces a code edit to retarget. Read it from the environment
with a local default:

```ts
const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
export default defineConfig({
  use: { baseURL: BASE_URL },
});
```

Now `page.goto("/")` resolves against whatever `BASE_URL` you export, and one
variable swaps the whole suite from local to staging to Cloud Run.

## Conditional webServer

Playwright's `webServer` block auto-starts your app before tests. That's right
for local runs — but against a *deployed* target there's nothing to start, and a
stray `webServer` will try to boot a local server and hang or conflict. Gate it
on whether the target is local:

```ts
function isLocalBaseUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "::1";
  } catch {
    return true;
  }
}

const webServers = [];
if (!process.env.CI && isLocalBaseUrl(BASE_URL)) {
  webServers.push({
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: true,   // but see the auth-bypass caveat below
    timeout: 60_000,
  });
}

export default defineConfig({
  ...(webServers.length ? { webServer: webServers } : {}),
});
```

**reuseExistingServer caveat.** If a test mode needs the dev server started with
special env (e.g. an auth-bypass flag), set `reuseExistingServer: false` for that
mode — a reused server started without the flag is still enforcing real auth and
will silently behave differently from what the test expects.

**Multiple servers.** If a tier needs an extra process (a mock backend on a
fixed port), push a second entry whose `url` points at that server's health
endpoint so Playwright waits for it to be ready before running specs.

## Conditional auth wiring

Authenticated runs are opt-in via an env gate so unauthenticated CI never tries
to sign in. Wire both `globalSetup` and the default `storageState` behind the
same flag:

```ts
const AUTHED = process.env.E2E_AUTHENTICATED === "1";
const STORAGE_STATE = process.env.E2E_STORAGE_STATE ?? "e2e/.auth/state.json";

export default defineConfig({
  ...(AUTHED ? { globalSetup: "./e2e/global-setup.ts" } : {}),
  use: {
    ...(AUTHED ? { storageState: STORAGE_STATE } : {}),
  },
});
```

Setting `storageState` at the top-level `use` means **every** test — including
plain `test` from `@playwright/test` and the visual suite — inherits the signed-in
session. Tests that build their own context (an `authenticatedPage` fixture) keep
working because they read the same file. See `authentication.md` for whether to
prefer this `globalSetup` form or the newer `setup`-project dependency.

## Artifacts on failure

Make failures debuggable without re-running:

```ts
use: {
  trace: "retain-on-failure",      // full timeline + DOM snapshots; open with `show-trace`
  screenshot: "only-on-failure",
  video: "retain-on-failure",      // optional; heavier
}
```

`retain-on-failure` keeps the artifact only for failing tests, so passing runs
stay cheap. Open a trace with `playwright show-trace <path>` — for streaming
bugs it's the fastest way to see exactly which events arrived and when.

## Projects

One project per browser/device. Names become CLI filters (`--project=<name>`):

```ts
projects: [
  { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } },
  { name: "webkit-desktop",   use: { ...devices["Desktop Safari"] } },
  { name: "firefox-desktop",  use: { ...devices["Desktop Firefox"] } },
  { name: "mobile-safari",    use: { ...devices["iPhone 14"] } },
  { name: "ipad",             use: { ...devices["iPad (gen 7)"] } },
],
```

Keep the per-commit tier on a single fast project (chromium) and reserve the
full matrix for the release gate — see `running-and-ci.md`.

## Parallelism

Playwright defaults to parallel workers. For a suite that hits **one shared
backend or a single test user**, parallel sign-ins and concurrent agent runs can
collide (rate limits, session contention, thread-id clashes). Many agentic suites
set `workers: 1` and `fullyParallel: false` for the real-backend tiers and let
the mocked tier run wide. Tune to your backend's tolerance; start serial for T3.

```ts
fullyParallel: false,
workers: process.env.CI ? 1 : undefined,
retries: process.env.CI ? 1 : 0,   // one retry absorbs live-model flakiness
```

## Timeouts

Local mocked tests are fast (default 30–60s per test is plenty). A live agent can
take far longer — a multi-tool run streaming a long answer may need 120–180s.
Set a generous per-test timeout for the full-stack tier (via
`test.setTimeout(180_000)` in the spec, or a higher config default), and a
shorter `expect` timeout for individual assertions so a genuinely stuck element
fails fast rather than eating the whole budget.
