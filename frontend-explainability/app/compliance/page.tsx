/**
 * /compliance — Compliance Center home (S3.2.1, hardened by Sprint 3 review).
 *
 * Server Component (no `'use client'`): one batched call returns every
 * workflow + integrity row (`getComplianceSummary`), and the audit-window
 * bounds come from the URL search params so a shared link reproduces the
 * exact view another operator saw.
 *
 *   - `?since=<iso>&until=<iso>`   bounds applied to listings + summaries.
 *   - The page renders both bounds verbatim, derived from the server's
 *     ``generated_at`` payload so an empty form still tells the operator
 *     "all-time" instead of leaving them guessing.
 *
 * Sprint 3 review fixes integrated:
 *   - F2: `since`/`until` parsed from `searchParams` and forwarded to the
 *         workflow listing AND guardrail summary.
 *   - F3: per-row N+1 `getWorkflowIntegrity` fan-out replaced with one
 *         `getComplianceSummary(...)` call.
 *   - F1/F6: export buttons now offer a real `Export Full Bundle JSON`
 *           that fetches each ComplianceBundle on click.
 *
 * Rule B1 (RSC by default) — only the export buttons escape to a client
 *   boundary; the audit-window form is a plain `<form method="GET">`.
 * Rule U6 — every class merge is via `cn()` (delegated to child components).
 */
import { buildAdapters } from "@/lib/composition";
import { failActionDistributionToSlices } from "@/lib/translators/action_distribution";
import { KpiCard } from "@/components/dashboard/KpiCard";
import {
  chainValidTone,
  guardrailRejectTone,
} from "@/components/dashboard/kpi_thresholds";
import { ValidatorTable } from "@/components/guardrails/ValidatorTable";
import { ActionDistributionPie } from "@/components/guardrails/ActionDistributionPie";
import { RecentFailuresTable } from "@/components/guardrails/RecentFailuresTable";
import {
  IntegrityStatusTable,
  type IntegrityRow,
} from "@/components/compliance/IntegrityStatusTable";
import { AgentSummaryGrid } from "@/components/compliance/AgentSummaryGrid";
import Link from "next/link";
import { ComplianceExportButtons } from "@/components/compliance/ComplianceExportButtons";

export const metadata = {
  title: "Compliance Center — Explainability",
};

// Skip static prerender — every render reads live governance artifacts.
export const dynamic = "force-dynamic";

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function parseDateParam(value: string | string[] | undefined): Date | undefined {
  if (typeof value !== "string" || value.trim() === "") return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date;
}

function toFormValue(date: Date | undefined): string {
  if (date === undefined) return "";
  // `<input type="datetime-local">` expects `YYYY-MM-DDTHH:mm`.
  return date.toISOString().slice(0, 16);
}

export default async function ComplianceHomePage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { explainabilityClient, apiUrl } = buildAdapters();
  const resolved = (await searchParams) ?? {};
  const since = parseDateParam(resolved["since"]);
  const until = parseDateParam(resolved["until"]);

  const [summary, agents, guardrails] = await Promise.all([
    explainabilityClient.getComplianceSummary(since, until),
    explainabilityClient.listAgents(),
    explainabilityClient.getGuardrailSummary(since, until),
  ]);

  const rows: IntegrityRow[] = summary.rows.map((row) => ({
    workflow: row.workflow,
    report: row.integrity,
  }));

  const validCount = rows.filter((r) => r.report?.chain_valid === true).length;
  const invalidCount = rows.filter(
    (r) => r.report?.chain_valid === false,
  ).length;
  const unknownCount = rows.length - validCount - invalidCount;
  const verifiedAgents = agents.filter(
    (a) => a.signature_verification_status === "verified",
  ).length;
  const generatedAt = summary.generated_at;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">
              Compliance Center
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Cross-pillar view of recording integrity, agent identity, and
              guardrail validation across every recorded workflow.
            </p>
          </div>
          <ComplianceExportButtons
            rows={rows}
            generatedAt={generatedAt}
            apiUrl={apiUrl}
          />
        </div>
      </header>

      <form
        method="GET"
        aria-label="Audit window filter"
        className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3"
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-muted-foreground">Since</span>
          <input
            type="datetime-local"
            name="since"
            defaultValue={toFormValue(since)}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-muted-foreground">Until</span>
          <input
            type="datetime-local"
            name="until"
            defaultValue={toFormValue(until)}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          />
        </label>
        <button
          type="submit"
          className="inline-flex items-center rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-accent"
        >
          Apply window
        </button>
        <Link
          href="/compliance"
          className="text-xs text-primary underline-offset-4 hover:underline"
        >
          Reset
        </Link>
        <span
          data-testid="active-window"
          className="ml-auto text-xs text-muted-foreground"
        >
          {since === undefined && until === undefined
            ? "All-time view"
            : `Window: ${since?.toISOString() ?? "−∞"} → ${until?.toISOString() ?? "+∞"}`}
        </span>
      </form>

      <section
        aria-label="Compliance KPIs"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        <KpiCard
          label="Workflows"
          value={rows.length.toString()}
          tone="neutral"
          caption={
            rows.length === 0
              ? "No data yet"
              : `${validCount} valid · ${invalidCount} tampered · ${unknownCount} unknown`
          }
        />
        <KpiCard
          label="Chain Valid %"
          value={
            rows.length === 0
              ? "—"
              : formatPct(validCount / Math.max(rows.length, 1))
          }
          tone={chainValidTone(validCount, invalidCount)}
          caption={
            rows.length === 0
              ? undefined
              : `${invalidCount} chain breaks recorded`
          }
        />
        <KpiCard
          label="Agents Verified"
          value={
            agents.length === 0
              ? "—"
              : `${verifiedAgents} / ${agents.length}`
          }
          tone={
            agents.length === 0
              ? "neutral"
              : verifiedAgents === agents.length
                ? "green"
                : "red"
          }
          caption={
            agents.length === 0
              ? undefined
              : "Signature-verified active agents"
          }
        />
        <KpiCard
          label="Guardrail Pass %"
          value={
            guardrails.total_checks === 0
              ? "—"
              : formatPct(guardrails.pass_rate)
          }
          tone={guardrailRejectTone(guardrails.pass_rate)}
          caption={
            guardrails.total_checks === 0
              ? undefined
              : `${guardrails.fail_count} of ${guardrails.total_checks} rejected`
          }
        />
      </section>

      <section className="flex flex-col gap-2">
        <header>
          <h2 className="text-sm font-semibold text-foreground">
            Recording integrity
          </h2>
          <p className="text-xs text-muted-foreground">
            Hash-chain verification across every recorded workflow. Click a
            workflow to open its compliance deep-dive.
          </p>
        </header>
        <IntegrityStatusTable rows={rows} />
      </section>

      <section className="flex flex-col gap-2">
        <header>
          <h2 className="text-sm font-semibold text-foreground">
            Agent identity
          </h2>
          <p className="text-xs text-muted-foreground">
            Read-only agent registry summary. Suspend / restore is an
            administrative action and is intentionally not exposed here.
          </p>
        </header>
        <AgentSummaryGrid agents={agents} />
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <article className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <header>
            <h2 className="text-sm font-semibold text-foreground">
              Guardrail per-validator breakdown
            </h2>
            <p className="text-xs text-muted-foreground">
              Reused from the Guardrail Monitor (S2.1.2).
            </p>
          </header>
          <ValidatorTable validators={guardrails.per_validator} />
        </article>
        <article className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
          <header>
            <h2 className="text-sm font-semibold text-foreground">
              Fail-action distribution
            </h2>
            <p className="text-xs text-muted-foreground">
              How rejections were handled across the recorded window.
            </p>
          </header>
          <ActionDistributionPie
            slices={failActionDistributionToSlices(
              guardrails.fail_action_distribution,
            )}
          />
        </article>
      </section>

      <section className="flex flex-col gap-2">
        <header>
          <h2 className="text-sm font-semibold text-foreground">
            Recent guardrail failures
          </h2>
          <p className="text-xs text-muted-foreground">
            Latest rejections — click a workflow to inspect its full timeline.
          </p>
        </header>
        <RecentFailuresTable failures={guardrails.recent_failures} />
      </section>
    </div>
  );
}
