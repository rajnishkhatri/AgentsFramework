/**
 * /agents — Agent Registry catalog (S2.2.2).
 *
 * Server Component (no `'use client'`): fetches the list via the adapter and
 * delegates table + capability search to AgentCatalog (which is itself a
 * client component for the search box state).
 *
 * Rule B1 — top-level RSC; client boundary descends only into the catalog.
 */
import { buildAdapters } from "@/lib/composition";
import { AgentCatalog } from "@/components/agents/AgentCatalog";

export const metadata = {
  title: "Agent Registry — Explainability",
};

// Skip static prerender — every render reads live registry over HTTP.
export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const { explainabilityClient } = buildAdapters();
  const agents = await explainabilityClient.listAgents();

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">
          Agent Registry
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Read-only catalog of every registered agent identity. Click an agent
          to inspect its capabilities, policies, signature, and audit trail.
        </p>
      </header>
      <AgentCatalog agents={agents} />
    </div>
  );
}
