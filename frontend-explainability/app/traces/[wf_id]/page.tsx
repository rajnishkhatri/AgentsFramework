/**
 * /traces/[wf_id] — Workflow detail page (S1.1.2).
 *
 * Server Component (rule B1): fetches events through the adapter, runs them
 * through the pure translator, and hands the resulting frames to the client
 * wrapper that owns the selection state.
 */
import { notFound } from "next/navigation";
import Link from "next/link";
import { buildAdapters } from "@/lib/composition";
import { ExplainabilityClientError } from "@/lib/ports/explainability_client";
import { eventsToTimeline } from "@/lib/translators/event_to_timeline";
import { TimelineWithDetail } from "@/components/traces/TimelineWithDetail";
import { cn } from "@/lib/utils";

interface Props {
  params: Promise<{ wf_id: string }>;
}

// Skip static prerender — every render reads live workflow events over HTTP.
export const dynamic = "force-dynamic";

export default async function WorkflowDetailPage({ params }: Props) {
  const { wf_id } = await params;
  const { explainabilityClient } = buildAdapters();

  let workflow;
  try {
    workflow = await explainabilityClient.getWorkflowEvents(wf_id);
  } catch (error) {
    if (error instanceof ExplainabilityClientError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  const frames = eventsToTimeline(workflow.events);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2 border-b border-border pb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Workflow
            </p>
            <h1 className="font-mono text-xl font-semibold text-foreground">
              {workflow.workflow_id}
            </h1>
          </div>
          <Link
            href="/traces"
            className="text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            ← Back to all traces
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>
            <strong className="text-foreground">{workflow.event_count}</strong>{" "}
            events
          </span>
          <span aria-hidden="true">·</span>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 font-medium ring-1 ring-inset",
              workflow.hash_chain_valid
                ? "bg-green-50 text-green-700 ring-green-600/20"
                : "bg-red-50 text-red-700 ring-red-600/20",
            )}
          >
            {workflow.hash_chain_valid
              ? "Hash chain valid"
              : "Hash chain BROKEN"}
          </span>
        </div>
      </header>

      <TimelineWithDetail frames={frames} />
    </div>
  );
}
