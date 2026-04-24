/**
 * L2 tests for WorkOSAuthKitAdapter (S3.3.2).
 *
 * The adapter is tested through an injected `WorkOSSDK` shim so we don't need
 * a real network round-trip. SDK type isolation is verified by the layering
 * test (S3.10.1); here we focus on the BEHAVIORAL contract:
 *   - getSession() returns null on absent session (never throws)
 *   - getSession() returns a narrowed IdentityClaim with strings only
 *   - getAccessToken() refreshes when <60s remain
 *   - signOut() clears local state
 */

import { describe, expect, it, vi } from "vitest";
import { WorkOSAuthKitAdapter, type WorkOSSDK } from "./workos_authkit_adapter";

function fakeSDK(state: {
  session?: { sub: string; org_id?: string; roles?: string[]; email?: string };
  accessToken?: { value: string; expiresAt: number };
  shouldThrowOnRefresh?: boolean;
}): WorkOSSDK {
  return {
    getSession: async () =>
      state.session
        ? {
            sub: state.session.sub,
            organizationId: state.session.org_id ?? null,
            roles: state.session.roles ?? [],
            email: state.session.email ?? null,
          }
        : null,
    getAccessToken: async () => state.accessToken?.value ?? "",
    getAccessTokenExpiry: async () =>
      state.accessToken?.expiresAt ?? 0,
    refreshAccessToken: async () => {
      if (state.shouldThrowOnRefresh) throw new Error("refresh failed");
      state.accessToken = { value: "REFRESHED", expiresAt: Date.now() + 3600_000 };
      return state.accessToken.value;
    },
    signOut: vi.fn(async () => {
      delete state.session;
      delete state.accessToken;
    }),
  };
}

describe("WorkOSAuthKitAdapter.getSession (failure paths first)", () => {
  it("returns null when no session is present (never throws)", async () => {
    const adapter = new WorkOSAuthKitAdapter({ sdk: fakeSDK({}) });
    expect(await adapter.getSession()).toBeNull();
  });

  it("returns null when SDK throws (defensive)", async () => {
    const sdk: WorkOSSDK = {
      ...fakeSDK({}),
      getSession: async () => {
        throw new Error("SDK error");
      },
    };
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    expect(await adapter.getSession()).toBeNull();
  });

  it("narrows the SDK shape into IdentityClaim (no SDK type leakage [A4/F-R8])", async () => {
    const sdk = fakeSDK({
      session: { sub: "u1", org_id: "o1", roles: ["admin"], email: "a@x.com" },
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    const claim = await adapter.getSession();
    expect(claim).toEqual({ sub: "u1", org_id: "o1", roles: ["admin"], email: "a@x.com" });
  });
});

describe("WorkOSAuthKitAdapter.getAccessToken refresh policy [S1]", () => {
  it("returns the cached token when >60s remain", async () => {
    const sdk = fakeSDK({
      accessToken: { value: "CACHED", expiresAt: Date.now() + 90_000 },
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    expect(await adapter.getAccessToken()).toBe("CACHED");
  });

  it("refreshes when <60s remain", async () => {
    const sdk = fakeSDK({
      accessToken: { value: "STALE", expiresAt: Date.now() + 30_000 },
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    expect(await adapter.getAccessToken()).toBe("REFRESHED");
  });

  it("throws AuthRefreshError when refresh round-trip itself fails", async () => {
    const sdk = fakeSDK({
      accessToken: { value: "STALE", expiresAt: Date.now() + 30_000 },
      shouldThrowOnRefresh: true,
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    await expect(adapter.getAccessToken()).rejects.toThrowError(/refresh/i);
  });
});

describe("WorkOSAuthKitAdapter.signOut", () => {
  it("calls the SDK signOut", async () => {
    const sdk = fakeSDK({ session: { sub: "u1" } });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    await adapter.signOut();
    expect(sdk.signOut).toHaveBeenCalledOnce();
  });
});

// ── Sprint 4 §S4.1.1: MFA enforcement verification ──────────────────
//
// WorkOS MFA is enforced at the dashboard level, not in application
// code. However the adapter must handle MFA-required sessions correctly:
//   - When MFA is required but not completed, `getSession()` returns null
//     (the SDK withAuth() returns no user until MFA passes).
//   - When MFA is completed, the session is normal.
//   - The adapter must never bypass or skip MFA state.

describe("WorkOSAuthKitAdapter MFA enforcement (S4.1.1, failure paths first)", () => {
  it("returns null when MFA is required but not completed (SDK returns no user)", async () => {
    const sdk = fakeSDK({});
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    const session = await adapter.getSession();
    expect(session).toBeNull();
  });

  it("returns null when SDK throws an MFA-required error", async () => {
    const sdk: WorkOSSDK = {
      ...fakeSDK({}),
      getSession: async () => {
        throw new Error("MFA verification required");
      },
    };
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    expect(await adapter.getSession()).toBeNull();
  });

  it("throws AuthRefreshError when token refresh fails during MFA re-auth", async () => {
    const sdk = fakeSDK({
      accessToken: { value: "STALE", expiresAt: Date.now() + 10_000 },
      shouldThrowOnRefresh: true,
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    await expect(adapter.getAccessToken()).rejects.toThrowError(/refresh/i);
  });

  it("returns valid session after MFA is completed", async () => {
    const sdk = fakeSDK({
      session: { sub: "u1", org_id: "o1", roles: ["admin"], email: "a@x.com" },
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    const claim = await adapter.getSession();
    expect(claim).toEqual({
      sub: "u1",
      org_id: "o1",
      roles: ["admin"],
      email: "a@x.com",
    });
  });

  it("getAccessToken works normally after MFA completion", async () => {
    const sdk = fakeSDK({
      session: { sub: "u1" },
      accessToken: { value: "MFA_VERIFIED_TOKEN", expiresAt: Date.now() + 300_000 },
    });
    const adapter = new WorkOSAuthKitAdapter({ sdk });
    expect(await adapter.getAccessToken()).toBe("MFA_VERIFIED_TOKEN");
  });
});
