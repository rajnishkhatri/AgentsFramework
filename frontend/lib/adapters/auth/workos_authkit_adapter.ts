/**
 * WorkOSAuthKitAdapter (S3.3.2, V3 AuthProvider).
 *
 * SDK isolation: the WorkOS SDK type surface is hidden behind the local
 * `WorkOSSDK` interface; the V3 wiring in `composition.ts` constructs the
 * shim from `@workos-inc/authkit-nextjs` so the SDK package is referenced
 * EXACTLY once at the composition root. No SDK type escapes the adapter
 * (A4 / F-R8).
 *
 * Storage policy: the adapter NEVER writes JWTs to localStorage (FE-AP-18
 * AUTO-REJECT). Sessions live in the WorkOS HttpOnly cookie set by the
 * Next.js middleware; this adapter only reads via the SDK helpers.
 *
 * Refresh policy: getAccessToken() returns the cached token when >60s of
 * life remain; otherwise it refreshes (S1).
 *
 * Error translation table (Rule A5):
 *   sdk.getSession()        rejection -> swallowed; method returns `null`
 *                                        (defensive contract per port docs)
 *   sdk.getAccessToken()    rejection -> propagated as-is (cached path)
 *   sdk.refreshAccessToken() rejection -> AuthRefreshError (with `cause`)
 *   sdk.signOut()           rejection -> propagated as-is
 *
 * SDK pin (Rule A9): see `frontend/package.json`.
 *   @sdk @workos-inc/authkit-nextjs ^2 (server-side helpers only)
 */

import type { AuthProvider } from "../../ports/auth_provider";
import type { IdentityClaim } from "../../trust-view/identity";
import { createAdapterLogger, type Logger } from "../_logger";

const log: Logger = createAdapterLogger("auth");

/**
 * Narrow shim that the composition root populates from `@workos-inc/authkit-nextjs`.
 * Keeping the adapter's public coupling on this interface (rather than the
 * vendor type) means tests can pass a hand-rolled fake.
 */
export interface WorkOSSDK {
  getSession(): Promise<{
    sub: string;
    organizationId: string | null;
    roles: ReadonlyArray<string>;
    email: string | null;
  } | null>;
  getAccessToken(): Promise<string>;
  getAccessTokenExpiry(): Promise<number>; // epoch ms
  refreshAccessToken(): Promise<string>;
  signOut(): Promise<void>;
}

export class AuthRefreshError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "AuthRefreshError";
  }
}

const REFRESH_LEEWAY_MS = 60_000;

export interface WorkOSAuthKitAdapterOptions {
  readonly sdk: WorkOSSDK;
}

export class WorkOSAuthKitAdapter implements AuthProvider {
  private readonly sdk: WorkOSSDK;

  constructor(opts: WorkOSAuthKitAdapterOptions) {
    this.sdk = opts.sdk;
  }

  async getSession(): Promise<IdentityClaim | null> {
    try {
      const s = await this.sdk.getSession();
      if (!s) return null;
      return {
        sub: s.sub,
        org_id: s.organizationId,
        roles: [...s.roles],
        email: s.email,
      };
    } catch {
      log.warn("getSession swallowed SDK rejection", {
        adapter: "workos_authkit",
        error_type: "session_read_error",
      });
      // Defensive: never throw on session read; callers branch on null.
      return null;
    }
  }

  async getAccessToken(): Promise<string> {
    const expiresAt = await this.sdk.getAccessTokenExpiry();
    const remaining = expiresAt - Date.now();
    if (remaining > REFRESH_LEEWAY_MS) {
      return this.sdk.getAccessToken();
    }
    try {
      const token = await this.sdk.refreshAccessToken();
      log.info("access token refreshed", {
        adapter: "workos_authkit",
        latency_ms: Math.max(0, REFRESH_LEEWAY_MS - remaining),
      });
      return token;
    } catch (e) {
      log.error("access token refresh failed", {
        adapter: "workos_authkit",
        error_type: "refresh_error",
      });
      throw new AuthRefreshError(
        e instanceof Error ? e.message : "WorkOS refresh failed",
        { cause: e },
      );
    }
  }

  async signOut(): Promise<void> {
    log.info("signOut", { adapter: "workos_authkit" });
    await this.sdk.signOut();
  }
}
