/**
 * /compliance/[wf_id] — Workflow Deep Dive (S3.2.2).
 *
 * Server Component (no `'use client'`): fetches the four-pillar bundle via
 * the adapter and renders the Recording / Identity / Validation / Reasoning
 * quadrants.  The correlation health badge sits at the top so any missing
 * key (`trace_id`, `user_id`, `task_id`, `agent_id`) is named explicitly.
 *
 * Rule B1 (RSC by default) — every child component is also RSC.
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { buildAdapters } from "@/lib/composition";
import { ExplainabilityClientError } from "@/lib/ports/explainability_client";
import { CorrelationHealthBadge } from "@/components/compliance/CorrelationHealthBadge";
import { WorkflowDeepDive } from "@/components/compliance/WorkflowDeepDive";

interface Props {
  params: Promise<{ wf_id: string }>;
}

// Skip static prerender — every render reads live governance artifacts.
export const dynamic = "force-dynamic";

export default async function ComplianceDeepDivePage({ params }: Props) {
  const { wf_id } = await params;
  const { explainabilityClient } = buildAdapters();

  let bundle;
  try {
    bundle = await explainabilityClient.getWorkflowCompliance(wf_id);
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
            Workflow Compliance
          </p>
          <h1 className="font-mono text-xl font-semibold text-foreground">
            {wf_id}
          </h1>
        </div>
        <Link
          href="/compliance"
          className="text-xs text-muted-foreground hover:text-foreground hover:underline"
        >
          ← Compliance home
        </Link>
      </header>

      <CorrelationHealthBadge health={bundle.correlation_health} />

      <WorkflowDeepDive bundle={bundle} />
    </div>
  );
}
