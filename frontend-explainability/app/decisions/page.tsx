/**
 * /decisions — Decision audit landing.
 *
 * Server Component: lists every workflow with a link to its decision audit
 * detail page.  Reuses the same workflow list as /traces.
 */
import Link from "next/link";
import { buildAdapters } from "@/lib/composition";
import { cn } from "@/lib/utils";

export const metadata = {
  title: "Decision Audit — Explainability Dashboard",
};

// Skip static prerender — every render reads live workflow list over HTTP.
export const dynamic = "force-dynamic";

export default async function DecisionsLandingPage() {
  const { explainabilityClient } = buildAdapters();
  const workflows = await explainabilityClient.listWorkflows();

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">
          Decision Audit
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a workflow to inspect every routing and evaluation decision the
          agent recorded for it.
        </p>
      </header>

      {workflows.length === 0 ? (
        <div
          role="status"
          aria-label="No workflows"
          className={cn(
            "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
            "py-16 text-center text-sm text-muted-foreground",
          )}
        >
          <p className="font-medium">No workflows recorded yet.</p>
          <p className="mt-1 text-xs">
            Run <code className="font-mono">python -m explainability_app.dev_seed</code>{" "}
            to generate sample data.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {workflows.map((wf) => (
            <li key={wf.workflow_id}>
              <Link
                href={`/decisions/${wf.workflow_id}`}
                className={cn(
                  "flex items-center justify-between px-4 py-3 text-sm",
                  "transition-colors hover:bg-accent/50",
                )}
              >
                <span className="font-mono text-xs">{wf.workflow_id}</span>
                <span className="text-xs text-muted-foreground">
                  {wf.event_count} events · {wf.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
