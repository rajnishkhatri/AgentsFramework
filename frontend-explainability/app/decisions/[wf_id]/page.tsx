/**
 * /decisions/[wf_id] — Decision audit detail page (S1.2.2).
 */
import Link from "next/link";
import { buildAdapters } from "@/lib/composition";
import { DecisionList } from "@/components/decisions/DecisionList";

interface Props {
  params: Promise<{ wf_id: string }>;
}

// Skip static prerender — every render reads live decision logs over HTTP.
export const dynamic = "force-dynamic";

export default async function DecisionsDetailPage({ params }: Props) {
  const { wf_id } = await params;
  const { explainabilityClient } = buildAdapters();
  const decisions = await explainabilityClient.getWorkflowDecisions(wf_id);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2 border-b border-border pb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Decision Audit
            </p>
            <h1 className="font-mono text-xl font-semibold text-foreground">
              {wf_id}
            </h1>
          </div>
          <Link
            href="/decisions"
            className="text-xs text-muted-foreground hover:text-foreground hover:underline"
          >
            ← All decision audits
          </Link>
        </div>
        <p className="text-xs text-muted-foreground">
          {decisions.length} decision{decisions.length === 1 ? "" : "s"}{" "}
          recorded · grouped by workflow phase
        </p>
      </header>

      <DecisionList decisions={decisions} />
    </div>
  );
}
