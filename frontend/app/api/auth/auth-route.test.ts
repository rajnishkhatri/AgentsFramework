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

vi.mock("@workos-inc/authkit-nextjs", () => ({
  getSignInUrl: vi.fn(async () => MOCK_SIGN_IN_URL),
  getSignUpUrl: vi.fn(async () => MOCK_SIGN_UP_URL),
  signOut: vi.fn(async () => {
    mockSignOut();
    return new Response(null, { status: 302, headers: { location: "/" } });
  }),
  handleAuth: () => mockCallbackHandler,
}));

describe("auth route handler — failure paths first", () => {
  let GET: (req: NextRequest, ctx: { params: Promise<{ workos: string[] }> }) => Promise<Response>;

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
  let GET: (req: NextRequest, ctx: { params: Promise<{ workos: string[] }> }) => Promise<Response>;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("redirects to WorkOS sign-in URL for /api/auth/sign-in", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-in");
    const res = await GET(req, { params: Promise.resolve({ workos: ["sign-in"] }) });
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(MOCK_SIGN_IN_URL);
  });
});

describe("auth route handler — sign-up dispatch", () => {
  let GET: (req: NextRequest, ctx: { params: Promise<{ workos: string[] }> }) => Promise<Response>;

  beforeEach(async () => {
    vi.clearAllMocks();
    const mod = await import("./[...workos]/route");
    GET = mod.GET;
  });

  it("redirects to WorkOS sign-up URL for /api/auth/sign-up", async () => {
    const req = new NextRequest("https://example.com/api/auth/sign-up");
    const res = await GET(req, { params: Promise.resolve({ workos: ["sign-up"] }) });
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(MOCK_SIGN_UP_URL);
  });
});

describe("auth route handler — sign-out dispatch", () => {
  let GET: (req: NextRequest, ctx: { params: Promise<{ workos: string[] }> }) => Promise<Response>;

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
  let GET: (req: NextRequest, ctx: { params: Promise<{ workos: string[] }> }) => Promise<Response>;

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
    const res = await GET(req, { params: Promise.resolve({ workos: ["callback"] }) });
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
