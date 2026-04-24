/**
 * Landing page (S3.7.1 / S3.8.1).
 *
 * RSC by default. Renders a sign-in CTA when no WorkOS session is present;
 * otherwise it renders the chat shell with Composer, streaming output,
 * thread sidebar, theme toggle, and run controls.
 */

import Link from "next/link";
import { withAuth } from "@workos-inc/authkit-nextjs";
import { Button } from "@/components/ui/button";
import { ChatShell } from "./chat-shell";

export default async function HomePage(): Promise<React.JSX.Element> {
  const { user } = await withAuth();

  if (user) {
    return (
      <ChatShell
        userEmail={user.email ?? user.firstName ?? "Agent"}
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
