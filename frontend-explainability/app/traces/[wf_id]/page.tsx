/**
 * /traces/[wf_id] — Workflow detail placeholder (AC4 of S0.3.3).
 *
 * Full timeline view is implemented in Sprint 1 (S1.1.2).
 */
interface Props {
  params: Promise<{ wf_id: string }>;
}

export default async function WorkflowDetailPage({ params }: Props) {
  const { wf_id } = await params;
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-lg font-medium text-foreground">
        Workflow:{" "}
        <span className="font-mono text-primary">{wf_id}</span>
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        Timeline view available in Sprint 1.
      </p>
    </div>
  );
}
