/**
 * LearnIdentityProvider — shared seam for /learn/* learnerId + displayName
 * (eng-coach-workos-learner-identity FR-6).
 *
 * RSC (coach)/layout resolves identity; this client context fans it to pages
 * and EngineProvider seedMode. useLearnIdentity() throws outside the provider
 * (never silently defaults to Garvit).
 */

"use client";

import * as React from "react";
import type { LearnIdentity } from "@/lib/learn/resolve_learn_identity";

const LearnIdentityContext = React.createContext<LearnIdentity | null>(null);

export function LearnIdentityProvider(props: {
  value: LearnIdentity;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <LearnIdentityContext.Provider value={props.value}>
      {props.children}
    </LearnIdentityContext.Provider>
  );
}

/**
 * Read the learn identity from context. Throws outside the provider so a
 * missing RSC bridge fails loudly instead of inventing `"Garvit"`.
 */
export function useLearnIdentity(): LearnIdentity {
  const ctx = React.useContext(LearnIdentityContext);
  if (ctx == null) {
    throw new Error(
      "useLearnIdentity() must be called inside <LearnIdentityProvider> — " +
        "ensure (coach)/layout wraps the learn shell with resolved identity.",
    );
  }
  return ctx;
}
