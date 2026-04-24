/**
 * Security-headers middleware contract test (S3.7.2).
 *
 * Per FRONTEND_STYLE_GUIDE §19 / FD3.CSP3 / FE-AP-19 AUTO-REJECT.
 *
 * The middleware now composes AuthKit session management with CSP + hardening
 * headers. `authkitMiddleware` is mocked so we test only OUR header logic,
 * not the SDK internals.
 *
 * Dev-mode CSP relaxation (NODE_ENV !== "production") is tested separately
 * from production-mode strict CSP. Failure paths first (FD6).
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest, NextResponse } from "next/server";

// Mock authkitMiddleware — return a pass-through NextResponse
vi.mock("@workos-inc/authkit-nextjs", () => ({
  authkitMiddleware: () => {
    return async (_req: NextRequest) => NextResponse.next();
  },
}));

// ── Production-mode tests (NODE_ENV=production / test) ────────────────

describe("middleware security headers — production CSP (failure-path guards)", () => {
  let middlewareFn: typeof import("./middleware").middleware;

  beforeEach(async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.resetModules();
    const mod = await import("./middleware");
    middlewareFn = mod.middleware;
  });

  async function call(url = "https://example.com/"): Promise<Response> {
    const req = new NextRequest(url);
    return middlewareFn(req);
  }

  it("CSP forbids 'unsafe-inline' in production [FE-AP-19 AUTO-REJECT]", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).not.toContain("unsafe-inline");
  });

  it("CSP forbids 'unsafe-eval' in production", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).not.toContain("unsafe-eval");
  });

  it("CSP includes frame-ancestors 'none' (clickjacking guard)", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/frame-ancestors\s+'none'/);
  });

  it("CSP script-src includes 'strict-dynamic' in production [FD3.CSP2]", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/script-src[^;]*'strict-dynamic'/);
  });

  it("CSP embeds a per-request nonce on script-src", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/script-src[^;]*'nonce-[A-Za-z0-9+/=_-]{8,}'/);
  });

  it("CSP embeds a per-request nonce on style-src in production", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/style-src[^;]*'nonce-[A-Za-z0-9+/=_-]{8,}'/);
  });

  it("CSP connect-src includes WorkOS origin [FD3.CSP2]", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/connect-src[^;]*https:\/\/\*\.workos\.com/);
  });

  it("CSP connect-src does NOT include ws://localhost in production", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).not.toContain("ws://localhost");
  });

  it("CSP includes object-src 'none' and base-uri 'self'", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/object-src\s+'none'/);
    expect(csp).toMatch(/base-uri\s+'self'/);
  });

  it("nonce is fresh on each request", async () => {
    const a = (await call()).headers.get("content-security-policy")!;
    const b = (await call()).headers.get("content-security-policy")!;
    const matchA = /'nonce-([A-Za-z0-9+/=_-]+)'/.exec(a);
    const matchB = /'nonce-([A-Za-z0-9+/=_-]+)'/.exec(b);
    expect(matchA?.[1]).toBeTruthy();
    expect(matchB?.[1]).toBeTruthy();
    expect(matchA![1]).not.toBe(matchB![1]);
  });

  it("HSTS uses max-age=63072000 with includeSubDomains and preload [FD3.HDR1]", async () => {
    const hsts = (await call()).headers.get("strict-transport-security") ?? "";
    expect(hsts).toContain("max-age=63072000");
    expect(hsts).toContain("includeSubDomains");
    expect(hsts).toContain("preload");
  });

  it("sets X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy", async () => {
    const h = (await call()).headers;
    expect(h.get("x-content-type-options")).toBe("nosniff");
    expect(h.get("x-frame-options")).toBe("DENY");
    expect(h.get("referrer-policy")).toBe("strict-origin-when-cross-origin");
    expect(h.get("permissions-policy")).toContain("camera=()");
    expect(h.get("permissions-policy")).toContain("microphone=()");
    expect(h.get("permissions-policy")).toContain("geolocation=()");
  });
});

// ── Dev-mode CSP relaxation tests ─────────────────────────────────────

describe("middleware security headers — dev-mode CSP relaxation", () => {
  let middlewareFn: typeof import("./middleware").middleware;

  beforeEach(async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.resetModules();
    const mod = await import("./middleware");
    middlewareFn = mod.middleware;
  });

  async function call(url = "https://example.com/"): Promise<Response> {
    const req = new NextRequest(url);
    return middlewareFn(req);
  }

  it("CSP script-src includes 'unsafe-eval' in dev (webpack HMR)", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/script-src[^;]*'unsafe-eval'/);
  });

  it("CSP script-src does NOT include 'strict-dynamic' in dev", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).not.toMatch(/script-src[^;]*'strict-dynamic'/);
  });

  it("CSP style-src includes 'unsafe-inline' in dev (style injection)", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/style-src[^;]*'unsafe-inline'/);
  });

  it("CSP connect-src includes ws://localhost:* in dev (HMR websocket)", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/connect-src[^;]*ws:\/\/localhost:\*/);
  });

  it("hardening headers are still set in dev mode", async () => {
    const h = (await call()).headers;
    expect(h.get("x-content-type-options")).toBe("nosniff");
    expect(h.get("x-frame-options")).toBe("DENY");
    expect(h.get("strict-transport-security")).toContain("max-age=63072000");
  });

  it("frame-ancestors 'none' is present even in dev", async () => {
    const csp = (await call()).headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/frame-ancestors\s+'none'/);
  });
});
