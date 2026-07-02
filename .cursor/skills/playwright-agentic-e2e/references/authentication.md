# Authentication & Authorization

Agent chat apps are almost always behind a login. This is how to sign in once and
reuse that session across every test, across providers, plus the fake-session
shortcut for tests that don't need a real user.

## Table of contents
- [The core pattern: storageState](#the-core-pattern-storagestate)
- [Two ways to run setup: setup-project vs globalSetup](#two-ways-to-run-setup)
- [The authenticatedPage fixture](#the-authenticatedpage-fixture)
- [Gating real sign-in behind an env flag](#gating-real-sign-in)
- [Provider sign-in flows](#provider-sign-in-flows) (WorkOS, Auth0, NextAuth, Clerk, Google SSO)
- [Fake sessions: skip the network entirely](#fake-sessions)
- [The locale trap](#the-locale-trap)
- [Security rules](#security-rules)

## The core pattern: storageState

A login produces session state — cookies (often HttpOnly) and sometimes
localStorage. Playwright can **save** that state to a JSON file after one sign-in
and **load** it into any number of browser contexts, so each test starts already
authenticated without repeating the login. That file is `storageState`.

```ts
// After signing in on a page:
await context.storageState({ path: "e2e/.auth/state.json" });

// Later, in any test:
const ctx = await browser.newContext({ storageState: "e2e/.auth/state.json" });
```

This is faster and far less flaky than driving the login UI per test, and it's
the officially recommended approach. ([Playwright auth docs](https://playwright.dev/docs/auth).)

## Two ways to run setup

You need to produce the storageState file *once* before the authed tests run.
Two patterns — both valid; match what the repo already does.

**(a) `setup` project as a dependency — current best practice.** Define a project
whose only job is to sign in, then make the real projects depend on it. Playwright
runs it first, and on retries it can re-run just setup.

```ts
projects: [
  { name: "setup", testMatch: /global\.setup\.ts/ },
  {
    name: "chromium-desktop",
    use: { ...devices["Desktop Chrome"], storageState: "e2e/.auth/state.json" },
    dependencies: ["setup"],
  },
],
```

**(b) `globalSetup` — older, still fine, common in existing repos.** A single
module that runs before everything. Less granular (doesn't show as a test, no
per-project retry) but simpler, and it composes cleanly with an env gate.

```ts
export default defineConfig({
  globalSetup: "./e2e/global-setup.ts",
  use: { storageState: "e2e/.auth/state.json" },
});
```

Don't migrate a working `globalSetup` repo to the setup-project pattern just for
fashion — there's a [good write-up](https://dev.to/vitalets/authentication-in-playwright-you-might-not-need-project-dependencies-2e02)
on why on-demand auth is sometimes simpler. Use `globalSetup` when auth is a
hard gate for the whole run; use the setup project when you have mixed
public/authed/multi-role suites that benefit from per-project state files.

## The authenticatedPage fixture

Give authed specs a ready-to-use page and make them **skip gracefully** when the
state file is missing (so unauthenticated CI doesn't crash):

```ts
export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ browser }, use, testInfo) => {
    const p = path.resolve(STORAGE_STATE_PATH);
    if (!fs.existsSync(p)) {
      testInfo.skip(true, `No storage state at ${p}. Run global setup.`);
    }
    const ctx = await browser.newContext({ storageState: p, ...CONTEXT_DEFAULTS });
    const page = await ctx.newPage();
    try { await use(page); } finally { await ctx.close(); }
  },
});
export { expect } from "@playwright/test";
```

Authed specs then `import { test, expect } from "./fixtures/auth.fixture"` and
take `{ authenticatedPage }`. See `assets/auth.fixture.template.ts`.

## Gating real sign-in

A real login needs credentials and network. CI that runs the mocked tier has
neither and must not attempt it. Gate on an env flag (e.g. `E2E_AUTHENTICATED=1`):
when unset, `globalSetup` returns early and the fixture skips. When set, it signs
in. This single switch keeps one config serving both unauthenticated per-commit
runs and authenticated release gates.

```ts
export default async function globalSetup() {
  if (process.env.E2E_AUTHENTICATED !== "1") {
    console.log("[setup] E2E_AUTHENTICATED!=1 — skipping auth.");
    return;
  }
  // ...sign in, write storageState...
}
```

Optionally support `E2E_REUSE_STORAGE=1` to skip sign-in when a valid state file
already exists — handy for fast local iteration. Remember storageState expires;
regenerate it when sessions go stale.

## Provider sign-in flows

The hosted login UI differs per provider; the saved storageState is the same idea.
Drive the form with resilient selectors (offer multiple, `.first()`), then wait
for the redirect *back* to your app before saving state.

**WorkOS AuthKit (email + password):**
```ts
await page.locator("input[type='email'], input[name='email']").first().fill(email);
await page.locator("button[type='submit'], button:has-text('Continue')").first().click();
await page.locator("input[type='password']").first().fill(password);
await page.locator("button[type='submit'], button:has-text('Sign in')").first().click();
await page.waitForURL((u) => u.toString().startsWith(BASE_URL), { timeout: 90_000 });
```
WorkOS also supports OTP (`input[autocomplete='one-time-code']`) and SSO. The
session lands in an HttpOnly cookie (commonly `wos-session`) — tests never see
the JWT, which is the point.

**Auth0 / Okta (Universal Login):** same shape — fill `#username`/`input[name=username]`,
click continue, fill `#password`, submit, wait for the callback URL. Watch for a
consent screen on first login (click "Accept").

**NextAuth:** if using the credentials provider you can often POST to
`/api/auth/callback/credentials` with a CSRF token from `/api/auth/csrf` and skip
the UI entirely — fastest of all. Otherwise drive the provider's hosted page as above.

**Clerk:** has an official testing token flow (`@clerk/testing`) that bypasses bot
detection; prefer it over scripting the Clerk UI, which actively resists automation.

**Google SSO (when the app delegates to Google):** click "Continue with Google",
`waitForURL(/accounts\.google\.com/)`, fill email → Next → password → Next. Use a
dedicated test Google account; real accounts may trigger 2FA/security challenges
that block automation. Set `E2E_AUTH_PROVIDER=google` to branch into this path.

Detect a *failed* login explicitly so the error is legible rather than a generic
redirect timeout:
```ts
catch (e) {
  const body = await page.locator("body").innerText();
  if (/invalid (email|password)/i.test(body)) {
    throw new Error("[setup] Provider rejected the test credentials.");
  }
  throw e;
}
```

## Fake sessions

For UI/visual/component tests you often need the app to *think* it's logged in,
but you don't need a real user or the live identity provider. If the app seals its
session into a signed cookie, you can mint one locally — no network, no test user,
instant.

The recipe (for an `iron-session`/`jose`-style sealed cookie, as used by WorkOS
AuthKit's `test-helpers`):

```ts
import { sealData } from "iron-session";
import { SignJWT } from "jose";

const accessToken = await new SignJWT({ sid: "session_e2e", role: "member" })
  .setProtectedHeader({ alg: "HS256" })
  .setIssuedAt().setExpirationTime("2h")
  .sign(new TextEncoder().encode(COOKIE_PASSWORD));

const mockUser = { id: "user_e2e", email: "e2e@example.com", /* ...shape the app expects... */ };
const sealed = await sealData(
  { accessToken, refreshToken: "refresh_e2e", user: mockUser },
  { password: COOKIE_PASSWORD },
);
await ctx.addCookies([{
  name: COOKIE_NAME, value: sealed, domain: new URL(BASE_URL).hostname, path: "/",
  httpOnly: true, secure: BASE_URL.startsWith("https:"), sameSite: "Lax",
  expires: Math.floor(Date.now()/1000) + 7200,
}]);
await ctx.storageState({ path: stateFile });
```

Critical constraints:
- **The signing secret must match the app's configured cookie password** (often a
  `*_COOKIE_PASSWORD`, min 32 chars for iron-session). The server unseals with the
  same secret; a mismatch yields an "unauthenticated" app.
- **Fake sessions are for local/dev targets only.** Against production the secret
  won't match the server's, and you shouldn't be minting prod sessions anyway.
- **Match the cookie *shape* the app expects** (claim names, user object fields).
  Copy it from the auth library's own test helpers if available — that's the
  authoritative shape.

This is the single biggest speed win for non-functional tests: an authed render
with zero auth latency. See `global-setup.template.ts` for a complete
implementation guarded by a flag (e.g. `E2E_FAKE_SESSION=1`).

## The locale trap

Headless Chromium derives its locale from `Accept-Language`, and hosted login
pages localize off it. Without pinning, a CI machine can hand you a login page in
Afrikaans (or any locale) while your dev machine stays English — and every
`has-text('Sign in')` selector breaks. Pin it on the context:

```ts
export const CONTEXT_DEFAULTS = {
  locale: "en-US",
  extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" },
};
```

Apply the same defaults in `globalSetup`'s context, the fixture's context, and
(optionally) per-project `use`, so sign-in and tests agree on language.

## Security rules

- **Credentials come from env or a secret manager**, never committed files, never
  inlined in shell history. Read `process.env.E2E_USER_PASSWORD`; don't paste the
  literal into a command.
- **`.gitignore` the storageState dir** (`.auth/`) — it's a live session that
  grants access if leaked.
- **Tests never read or assert on raw JWTs/tokens** in browser storage — that's
  both a security anti-pattern and brittle. Assert on observable auth *effects*
  (the chat shell rendered, a protected route loaded), not on token contents.
- **Don't run write/destructive authed specs against production.** Point them at a
  staging deployment or a disposable environment.
