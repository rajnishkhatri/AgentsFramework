/**
 * D0 — (coach) route-group server layout: WorkOS page guard (FR-1/2/3) +
 * learn-identity RSC bridge (eng-coach-workos-learner-identity FR-4/5/6).
 *
 * RSC composition-adapter (Rule B2): awaits withAuth({ ensureSignedIn: true }),
 * resolves { learnerId, displayName, seedMode }, wraps children in
 * LearnIdentityProvider. One guard covers all /learn/* pages.
 *
 * E2E_BYPASS_AUTH mirrors app/page.tsx so learn-e2e (seeded, no WorkOS session)
 * keeps working; production builds never take this branch.
 */

import * as React from "react";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { LearnIdentityProvider } from "@/components/learn/LearnIdentityProvider";
import { resolveLearnIdentity } from "@/lib/learn/resolve_learn_identity";

export const dynamic = "force-dynamic";

const E2E_BYPASS_AUTH =
  process.env.NODE_ENV !== "production" &&
  process.env.E2E_BYPASS_AUTH === "1";

export default async function CoachGroupLayout(props: {
  children: React.ReactNode;
}): Promise<React.JSX.Element> {
  const identity = E2E_BYPASS_AUTH
    ? resolveLearnIdentity({ bypass: true, user: null })
    : resolveLearnIdentity({
        bypass: false,
        user: (await withAuth({ ensureSignedIn: true })).user,
      });

  return (
    <LearnIdentityProvider value={identity}>
      {props.children}
    </LearnIdentityProvider>
  );
}
