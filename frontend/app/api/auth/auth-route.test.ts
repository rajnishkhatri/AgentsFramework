/**
 * Auth route handler dispatch test (S3.7.1).
 *
 * Verifies the catch-all `[...workos]/route.ts` dispatches:
 *   - /api/auth/sign-in  → getSignInUrl() → 307 redirect
 *   - /api/auth/sign-up  → getSignUpUrl() → 307 redirect
 *   - /api/auth/sign-out → signOut()
 *   - /api/auth/callback → handleAuth() callback handler
 *
 * All SDK functions are mocked — no network, no WorkOS credentials needed.
 * Failure paths first (FD6).
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

const MOCK_SIGN_IN_URL = "https://authkit.workos.com/sign-in?client_id=test";
const MOCK_SIGN_UP_URL = "https://authkit.workos.com/sign-up?client_id=test";
const mockSignOut = vi.fn();
const mockCallbackHandler = vi.fn();
// Shared spy so the returnTo-threading tests (FR-6/7) can assert the exact
// options getSignInUrl was called with. Typed with the real optional-options
// arg so `.mock.calls[0]?.[0]` narrows (getSignInUrl({ returnTo? })).
const mockGetSignInUrl = vi.fn(
  async (_options?: { returnTo?: string }) => MOCK_SIGN_IN_URL,
);

vi.mock("@workos-inc/authkit-nextjs", () => ({
  getSignInUrl: mockGetSignInUrl,
  getSignUpUrl: vi.fn(async () => MOCK_SIGN_UP_URL),
  signOut: vi.fn(async () => {
    mockSignOut();
    return new Response(null, { status: 302, headers: { location: "/" } });
  }),
  handleAuth: () => mockCallbackHandler,
}));

// Desktop adapter is SDK-isolated + server-only; mock it so the route test
// stays free of the WorkOS SDK and `server-only` import.
const MOCK_DESKTOP_AUTH_URL = "https://api.workos.com/authorize?desktop=1";
vi.mock("@/lib/adapters/auth/workos_desktop_auth", () => ({
  buildDesktopAuthorizationUrl: vi.fn(() => MOCK_DESKTOP_AUTH_URL),
}));

// Derived from the route module so the test can never drift from the
// handler's real signature (`signOut()` returns Promise<void>, so the
// handler is `Promise<void | Response>`).
type AuthRouteGET = typeof import("./[...workos]/route").GET;

/** Narrow `void | Response` with a real assertion that a Response came back. */
function asResponse(res: Awaited<ReturnType<AuthRouteGET>>): Response {
  if (!(res instanceof Response)) {
    throw new Error("expected the handler to return a Response");
  }
  return res;
}

describe("auth route handler — failure paths first", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("returns a redirect for unknown actions (falls through to callback handler)", async () => {
    mockCallbackHandler.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { message: "Something went wrong" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const req = new NextRequest("https://example.com/api/auth/unknown-action");
    const res = await GET(req, { params: Promise.resolve({ workos: ["unknown-action"] }) });
    expect(mockCallbackHandler).toHaveBeenCalledWith(req);
    expect(res).toBeTruthy();
  });
});

describe("auth route handler — sign-in dispatch", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("redirects to WorkOS sign-in URL for /api/auth/sign-in", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-in");
    const res = asResponse(
      await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) }),
    );
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(MOCK_SIGN_IN_URL);
  });
});

describe("auth route handler — returnTo threading (Q1 / FR-6, FR-7)", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("threads ?returnTo=/learn into getSignInUrl (FR-6)", async () => {
    const req = new NextRequest(
      "https://example.com/api/auth/sign-in?returnTo=/learn",
    );
    await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) });
    expect(mockGetSignInUrl).toHaveBeenCalledWith({ returnTo: "/learn" });
  });

  it("a bare sign-in calls getSignInUrl with NO returnTo — default stays / (FR-7)", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-in");
    await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) });
    // No options object (or no returnTo) → AuthKit default returnPathname, i.e. /.
    const callArg = mockGetSignInUrl.mock.calls[0]?.[0] as
      | { returnTo?: string }
      | undefined;
    expect(callArg?.returnTo).toBeUndefined();
  });
});

describe("auth route handler — desktop sign-in (P5 Step 2)", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  const VALID_CHALLENGE = "abcdefghijklmnopqrstuvwxyz0123456789-_ABCDEF";

  it("400s a desktop sign-in missing the PKCE challenge (never falls through)", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-in?client=desktop&state=abcdefghij");
    const res = asResponse(
      await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) }),
    );
    expect(res.status).toBe(400);
  });

  it("redirects a well-formed desktop sign-in to the desktop authorize URL", async () => {
    const req = new NextRequest(
      `https://example.com/api/auth/sign-in?client=desktop&code_challenge=${VALID_CHALLENGE}&state=abcdefghij`,
    );
    const res = asResponse(
      await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) }),
    );
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(MOCK_DESKTOP_AUTH_URL);
  });

  it("leaves the web sign-in unchanged when client!=desktop", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-in");
    const res = asResponse(
      await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) }),
    );
    expect(res.headers.get("location")).toBe(MOCK_SIGN_IN_URL);
  });
});

describe("auth route handler — sign-up dispatch", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("redirects to WorkOS sign-up URL for /api/auth/sign-up", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-up");
    const res = asResponse(
      await GET(req, { params: Promise.resolve({ workos: ["sign-up"] }) }),
    );
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(MOCK_SIGN_UP_URL);
  });
});

describe("auth route handler — sign-out dispatch", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("calls signOut() for /api/auth/sign-out", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-out");
    await GET(req, { params: Promise.resolve({ workos: ["sign-out"] }) });
    expect(mockSignOut).toHaveBeenCalledOnce();
  });
});

describe("auth route handler — callback dispatch", () => {
  let GET: AuthRouteGET;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("delegates to handleAuth() for /api/auth/callback with code", async () => {
    mockCallbackHandler.mockResolvedValueOnce(
      new Response(null, { status: 302, headers: { location: "/" } }),
    );
    const req = new NextRequest("https://example.com/api/auth/callback?code=abc123");
    const res = asResponse(
      await GET(req, { params: Promise.resolve({ workos: ["callback"] }) }),
    );
    expect(mockCallbackHandler).toHaveBeenCalledWith(req);
    expect(res.status).toBe(302);
  });
});

describe("auth route handler — invariants", () => {
  it("exports dynamic = 'force-dynamic' (B5 — no static cache)", async () => {
    const mod = await import("./[...workos]/route");
    expect(mod.dynamic).toBe("force-dynamic");
  });
});
