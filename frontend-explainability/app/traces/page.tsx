/**
 * /traces — Workflow list page (Server Component, no 'use client').
 *
 * AC1: Server Component — fetches via buildAdapters() at request time.
 * AC2: delegates table rendering to WorkflowsTable.
 * AC3: empty state handled inside WorkflowsTable.
 * AC4: row click navigates to /traces/[wf_id] — handled in WorkflowsTable.
 */
import { buildAdapters } from "@/lib/composition";
import { WorkflowsTable } from "@/components/traces/WorkflowsTable";

export const metadata = {
  title: "Trace Explorer — Explainability Dashboard",
};

export default async function TracesPage() {
  const { explainabilityClient } = buildAdapters();
  const workflows = await explainabilityClient.listWorkflows();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">Trace Explorer</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          All recorded workflow runs — click a row to inspect the event timeline.
        </p>
      </div>
      <WorkflowsTable workflows={workflows} />
    </div>
  );
}
