/**
 * /agents/[agent_id] — Agent identity detail page (S2.2.2).
 *
 * Server Component: fetches the card and audit trail in parallel via the
 * adapter, then composes IdentityCard + AuditTimeline. F-R6 (read-only):
 * the page never renders Suspend / Restore / Revoke buttons.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { buildAdapters } from "@/lib/composition";
import { ExplainabilityClientError } from "@/lib/ports/explainability_client";
import { IdentityCard } from "@/components/agents/IdentityCard";
import { AuditTimeline } from "@/components/agents/AuditTimeline";

interface Props {
  params: Promise<{ agent_id: string }>;
}

// Skip static prerender — every render reads live registry over HTTP.
export const dynamic = "force-dynamic";

export default async function AgentDetailPage({ params }: Props) {
  const { agent_id } = await params;
  const { explainabilityClient } = buildAdapters();

  let card;
  let audit;
  try {
    [card, audit] = await Promise.all([
      explainabilityClient.getAgentCard(agent_id),
      explainabilityClient.getAgentAudit(agent_id),
    ]);
  } catch (err) {
    if (err instanceof ExplainabilityClientError && err.status === 404) {
      notFound();
    }
    throw err;
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Agent
          </p>
          <h1 className="font-mono text-xl font-semibold text-foreground">
            {agent_id}
          </h1>
        </div>
        <Link
          href="/agents"
          className="text-xs text-muted-foreground hover:text-foreground hover:underline"
        >
          ← All agents
        </Link>
      </header>

      <IdentityCard agent={card} />

      <section className="flex flex-col gap-3">
        <header>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Audit trail
          </h2>
          <p className="text-xs text-muted-foreground">
            Every register, suspend, restore, and revoke action recorded for
            this agent.
          </p>
        </header>
        <AuditTimeline entries={audit} />
      </section>
    </div>
  );
}
