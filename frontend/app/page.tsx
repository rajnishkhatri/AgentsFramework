/**
 * Landing page (S3.7.1 / S3.8.1).
 *
 * RSC by default. Renders a sign-in CTA when no WorkOS session is present;
 * otherwise it renders the chat shell with Composer, streaming output,
 * thread sidebar, theme toggle, and run controls.
 *
 * Test escape hatch (`E2E_BYPASS_AUTH=1`): renders the chat shell with a
 * synthetic user when the env flag is set AND `NODE_ENV !== "production"`.
 * The double gate ensures this branch can never be enabled in a
 * production build. Used by `e2e/visual/` to capture chat-shell baselines
 * without going through WorkOS. See `e2e/visual/README.md`.
 */

import Link from "next/link";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { Button } from "@/components/ui/button";
import { ChatShell } from "./chat-shell";

export const dynamic = "force-dynamic";

const E2E_BYPASS_AUTH =
  process.env.NODE_ENV !== "production" &&
  process.env.E2E_BYPASS_AUTH === "1";

export default async function HomePage(props: {
  searchParams: Promise<{ eval?: string; model?: string }>;
}): Promise<React.JSX.Element> {
  // F7 eval-mode capture surface: `?eval=GJ-…` pins the case id and
  // freezes the UI for deterministic, admissible captures.
  // A/B seam: `?model=<name>` seeds the model-picker selection so a driver
  // can pin a model without the flaky dropdown click.
  const { eval: evalCase, model: initialModel } = await props.searchParams;
  if (E2E_BYPASS_AUTH) {
    return (
      <ChatShell
        userEmail="e2e@example.com"
        evalCase={evalCase ?? null}
        initialModel={initialModel ?? null}
      />
    );
  }

  const { user } = await withAuth();

  if (user) {
    return (
      <ChatShell
        userEmail={user.email ?? user.firstName ?? "Agent"}
        evalCase={evalCase ?? null}
        initialModel={initialModel ?? null}
      />
    );
  }

  return (
    <main className="min-h-dvh flex items-center justify-center p-8">
      <section className="max-w-lg text-center grid gap-4">
        <h1 className="text-3xl leading-tight m-0">ReAct Agent</h1>
        <p className="text-muted m-0">
          Claude-class chat with a self-hosted LangGraph runtime.
        </p>
        <Button asChild className="justify-self-center">
          <Link href="/api/auth/sign-in">Sign in with WorkOS</Link>
        </Button>
      </section>
    </main>
  );
}
