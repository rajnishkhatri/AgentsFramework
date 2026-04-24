/**
 * AuthProvider -- vendor-neutral session port.
 *
 * V3 implementation: WorkOSAuthKitAdapter.
 *
 * Port rules: P1, P2, P3, P4, P6.
 */

import type { IdentityClaim } from "../trust-view/identity";

/**
 * Vendor-neutral session port. Wraps the WorkOS AuthKit (V3) and any future
 * identity provider. SDK types are confined to the adapter; the port surface
 * speaks only in `IdentityClaim` from `trust-view/`.
 *
 * Behavioral contract:
 *   - `getSession()` returns the verified session or `null`. NEVER throws
 *     on an absent / expired session -- callers branch on null.
 *   - `getAccessToken()` returns a Bearer token suitable for the BFF. If
 *     fewer than 60 seconds of life remain the adapter refreshes silently
 *     (S1).
 *   - `signOut()` clears local session state and revokes refresh tokens.
 *   - JWTs are stored in HttpOnly + Secure + SameSite=Strict cookies, NEVER
 *     in localStorage (FE-AP-18 AUTO-REJECT).
 */
export interface AuthProvider {
  /**
   * Returns the verified session or `null` (no session, expired, etc.).
   * Never throws; callers branch on `null`.
   */
  getSession(): Promise<IdentityClaim | null>;

  /**
   * Returns the current access token. Refreshes silently when <60s remain.
   *
   * @throws AuthRefreshError when the refresh round-trip itself fails.
   */
  getAccessToken(): Promise<string>;

  /**
   * Sign out and clear all local session state.
   */
  signOut(): Promise<void>;
}
