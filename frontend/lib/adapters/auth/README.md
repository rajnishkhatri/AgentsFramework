# `adapters/auth/` — AuthProvider family

Per Rule **A10**, every adapter family carries a one-page README declaring
the port it satisfies, current implementations, and the substrate-swap
trigger. Reviewers paste this section into PR comments when discussing
auth changes.

## Port

[`AuthProvider`](../../ports/auth_provider.ts) — vendor-neutral session
holder. Returns an [`IdentityClaim`](../../trust-view/identity.ts) view
of the WorkOS session; never exposes vendor types past the boundary
(Rule **A4 / F-R8**).

## Current implementations

| Profile | Adapter | SDK pin |
|---------|---------|---------|
| **V3-Dev-Tier** (default) | [`WorkOSAuthKitAdapter`](./workos_authkit_adapter.ts) | `@workos-inc/authkit-nextjs ^2` (server-side helpers only) |

The WorkOS SDK is loaded by [`workos_server_sdk.ts`](./workos_server_sdk.ts)
which carries `import "server-only"` so the package never lands in browser
bundles. The composition root injects the resulting `WorkOSSDK` shim into
the adapter so unit tests can pass a hand-rolled fake (no network).

## Environment (`@workos-inc/authkit-nextjs`)

Set these in `frontend/.env.local` (see repo root `.env.example`). The SDK reads **`NEXT_PUBLIC_WORKOS_REDIRECT_URI`** for the OAuth redirect (for example `http://localhost:3000/api/auth/callback`); it does **not** use `WORKOS_REDIRECT_URI`. The value must match the WorkOS dashboard redirect allowlist and the dev server port you actually use.

| Variable | Notes |
|----------|--------|
| `WORKOS_API_KEY` | Secret; server only |
| `WORKOS_CLIENT_ID` | Public |
| `WORKOS_COOKIE_PASSWORD` | Secret; ≥ 32 characters |
| `NEXT_PUBLIC_WORKOS_REDIRECT_URI` | Full callback URL (public); must match `app/api/auth/[...workos]/route.ts` + dashboard |

## Logger

`frontend:adapter:auth` (Rule **A7 / O3**). Emitted lines:

| Event | Meta | When |
|-------|------|------|
| `getSession swallowed SDK rejection` | `error_type=session_read_error` | SDK throws on session read; adapter returns `null` per port contract |
| `access token refreshed` | `latency_ms` | Token within 60s of expiry; refresh succeeded |
| `access token refresh failed` | `error_type=refresh_error` | `AuthRefreshError` is about to be thrown |
| `signOut` | — | `signOut()` called |

No PII (Rule **O2**). Tokens, raw email, and raw cookie values never
appear in the meta bag.

## Error translation table (Rule A5)

| SDK condition | Adapter behavior |
|---------------|------------------|
| `sdk.getSession()` rejects | swallowed; method returns `null` (defensive contract) |
| `sdk.getAccessToken()` rejects | propagated as-is (cached path) |
| `sdk.refreshAccessToken()` rejects | wrapped in `AuthRefreshError` (with `cause`) |
| `sdk.signOut()` rejects | propagated as-is |

## Storage policy

JWTs **never** land in `localStorage` / `sessionStorage` (FE-AP-18
**AUTO-REJECT**). Sessions live in the WorkOS HttpOnly + Secure +
SameSite=Strict cookie set by the Next.js middleware; the adapter only
reads via the SDK helpers.

## Substrate swap trigger

| When | Swap to | How |
|------|---------|-----|
| WorkOS pricing changes / vendor risk | hand-rolled OIDC adapter or Auth0 / Clerk | new `AuthProvider` impl + composition selector update; no `ports/`, `wire/`, `trust-view/` files change (**F3**) |

## Tests

- [`workos_authkit_adapter.test.ts`](./workos_authkit_adapter.test.ts) —
  failure-paths-first per Rule **FD6.ADAPTER**: null session, SDK throw,
  cached token, stale-then-refresh, refresh failure, then happy path.
