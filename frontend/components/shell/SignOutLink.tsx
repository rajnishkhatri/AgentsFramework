/**
 * SignOutLink — full-document navigation to the WorkOS sign-out route.
 *
 * Must be a plain <a>, not next/link: App Router soft-nav to /api/auth/sign-out
 * skips the Set-Cookie clear + WorkOS logout redirect, so the session sticks
 * and "Sign out" appears to do nothing. Prefetch is irrelevant for <a>.
 *
 * `returnTo=/` lands on the unauthenticated CTA after WorkOS logout so the
 * next sign-in can exercise cross-session resume (FR-B1).
 */

import * as React from "react";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/utils";

/** Absolute path WorkOS will bounce back to after clearing the session. */
export const SIGN_OUT_HREF = "/api/auth/sign-out?returnTo=/";

export function SignOutLink(props: {
  className?: string;
  /** Collapsed rail: icon-only with accessible name. */
  iconOnly?: boolean;
}): React.JSX.Element {
  const { className, iconOnly = false } = props;
  return (
    <a
      href={SIGN_OUT_HREF}
      data-testid="sign-out"
      aria-label="Sign out"
      title="Sign out"
      className={cn(
        "inline-flex min-h-11 items-center text-sm text-muted hover:text-fg no-underline",
        iconOnly
          ? "size-11 justify-center rounded-md hover:bg-selected"
          : "px-2",
        className,
      )}
    >
      {iconOnly ? (
        <LogOut aria-hidden="true" className="size-4" strokeWidth={1.75} />
      ) : (
        "Sign out"
      )}
    </a>
  );
}
