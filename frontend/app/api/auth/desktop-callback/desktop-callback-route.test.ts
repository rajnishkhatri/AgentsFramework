/**
 * Desktop-callback route test (P5 Step 2). Failure/guard paths first (FD6):
 * malformed params → 400, a failed exchange → 401, and only a clean exchange
 * sets the session + redirects to the app root.
 *
 * The desktop adapter is SDK-isolated + server-only; mock it so this test never
 * touches the WorkOS SDK.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

const completeDesktopAuth = vi.fn();
vi.mock("@/lib/adapters/auth/workos_desktop_auth", () => ({
  completeDesktopAuth: (...args: unknown[]) => completeDesktopAuth(...args),
}));

type GETType = typeof import("./route").GET;
const VALID_VERIFIER = "abcdefghijklmnopqrstuvwxyz0123456789-_ABCDEF";
const base = "https://example.com/api/auth/desktop-callback";

async function importGET(): Promise<GETType> {
  const mod = await import("./route");
  return mod.GET;
}

describe("desktop-callback — guard paths first", () => {
  let GET: GETType;
  beforeEach(async () => {
    vi.clearAllMocks();
    GET = await importGET();
  });

  it("400s when required params are missing", async () => {
    const res = await GET(new NextRequest(`${base}?code=xyz`));
    expect(res.status).toBe(400);
    expect(completeDesktopAuth).not.toHaveBeenCalled();
  });

  it("401s when the code exchange fails", async () => {
    completeDesktopAuth.mockRejectedValueOnce(new Error("exchange failed"));
    const res = await GET(
      new NextRequest(`${base}?code=xyz&code_verifier=${VALID_VERIFIER}&state=abcdefghij`),
    );
    expect(res.status).toBe(401);
  });
});

describe("desktop-callback — success", () => {
  let GET: GETType;
  beforeEach(async () => {
    vi.clearAllMocks();
    GET = await importGET();
  });

  it("exchanges the code+verifier and redirects to the app root", async () => {
    completeDesktopAuth.mockResolvedValueOnce(undefined);
    const req = new NextRequest(
      `${base}?code=xyz&code_verifier=${VALID_VERIFIER}&state=abcdefghij`,
    );
    const res = await GET(req);

    expect(completeDesktopAuth).toHaveBeenCalledOnce();
    const [params] = completeDesktopAuth.mock.calls[0]!;
    expect(params).toMatchObject({ code: "xyz", codeVerifier: VALID_VERIFIER, state: "abcdefghij" });
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("https://example.com/");
  });
});

describe("desktop-callback — invariants", () => {
  it("exports dynamic = 'force-dynamic' (B5 — no static cache)", async () => {
    const mod = await import("./route");
    expect(mod.dynamic).toBe("force-dynamic");
  });
});
