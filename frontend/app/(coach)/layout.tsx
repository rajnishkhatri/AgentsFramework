/**
 * D0 — (coach) route-group server layout: WorkOS page guard (FR-1/2/3).
 *
 * RSC composition-adapter (Rule B2): awaits withAuth({ ensureSignedIn: true })
 * then renders the existing 'use client' learn/layout.tsx shell as children.
 * One guard covers all /learn/* pages and future siblings under (coach).
 *
 * E2E_BYPASS_AUTH mirrors app/page.tsx so learn-e2e (seeded, no WorkOS session)
 * keeps working; production builds never take this branch.
 */

import * as React from "react";
import { withAuth } from "@workos-inc/authkit-nextjs";

export const dynamic = "force-dynamic";

const E2E_BYPASS_AUTH =
  process.env.NODE_ENV !== "production" &&
  process.env.E2E_BYPASS_AUTH === "1";

export default async function CoachGroupLayout(props: {
  children: React.ReactNode;
}): Promise<React.JSX.Element> {
  if (!E2E_BYPASS_AUTH) {
    await withAuth({ ensureSignedIn: true });
  }
  return <>{props.children}</>;
}
