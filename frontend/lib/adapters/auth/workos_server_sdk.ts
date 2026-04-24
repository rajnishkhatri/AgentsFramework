/**
 * Server-only WorkOS SDK shim factory.
 *
 * SDK isolation: this is the ONE file that imports `@workos-inc/authkit-nextjs`.
 * The composition root (lib/composition.ts) re-exports this factory so BFF
 * Route Handlers never name the SDK directly. Per F-R2 / A1 the SDK type
 * surface stays inside `lib/adapters/auth/`; consumers see only the
 * narrow `WorkOSSDK` interface.
 *
 * NOTE: this file MUST be imported only from server-side code (Next.js
 * Route Handlers, server actions, RSCs). The `server-only` import below
 * trips the build if a client component pulls it in.
 */

import "server-only";
import {
  withAuth,
  signOut,
  getTokenClaims,
} from "@workos-inc/authkit-nextjs";
import type { WorkOSSDK } from "./workos_authkit_adapter";

export function makeWorkOSServerSDK(): WorkOSSDK {
  return {
    async getSession() {
      try {
        const { user, accessToken } = await withAuth();
        if (!user) return null;
        const claims = accessToken ? await getTokenClaims() : null;
        return {
          sub: user.id,
          organizationId: (claims?.organizationId as string | undefined) ?? null,
          roles: ((claims?.roles as string[] | undefined) ?? []) as string[],
          email: user.email ?? null,
        };
      } catch {
        return null;
      }
    },
    async getAccessToken() {
      const { accessToken } = await withAuth();
      return accessToken ?? "";
    },
    async getAccessTokenExpiry() {
      const claims = (await getTokenClaims().catch(() => null)) as
        | { exp?: number }
        | null;
      return claims?.exp ? claims.exp * 1000 : Date.now() + 60_000;
    },
    async refreshAccessToken() {
      // AuthKit refreshes lazily on the next request; surface the current
      // token so the caller doesn't block on an explicit refresh.
      const { accessToken } = await withAuth();
      return accessToken ?? "";
    },
    async signOut() {
      await signOut();
    },
  };
}
