"use client";
/**
 * ComplianceExportButtons — client component for the JSON / CSV download
 * affordances on the /compliance home (S3.2.1, hardened by Sprint 3 review F1).
 *
 * Rule B1 — `'use client'` is justified: the buttons trigger blob downloads
 * via `URL.createObjectURL` + `<a href download>`, which is browser-only API.
 *
 * Architecture:
 *   - The summary buttons receive the already-fetched integrity rows so
 *     no adapter call is needed at render time.
 *   - The "Export Full Bundle JSON" button fetches every workflow's true
 *     `ComplianceBundle` on click via the adapter (constructed from the
 *     server-supplied `apiUrl` so rule C5 stays intact).  This is the
 *     fix for Sprint 3 review F1 -- the previous "Export JSON Bundle"
 *     button only emitted summary rows and was misleading.
 *   - The CSV is hand-rolled (no `papaparse` SDK dependency) -- the schema
 *     is small and stable.
 *   - PDF export is intentionally OUT OF SCOPE for the MVP per the sprint
 *     board.
 *
 * Rule U6: every class merge runs through `cn()`.
 * Rule FD7.AP12: never `dangerouslySetInnerHTML` — text content only.
 */
import { useState } from "react";
import { cn } from "@/lib/utils";
import { HttpExplainabilityClient } from "@/lib/adapters/http_explainability_client";
import type {
  ComplianceBundle,
  IntegrityReport,
  WorkflowSummary,
} from "@/lib/wire/responses";

export interface ComplianceExportRow {
  workflow: WorkflowSummary;
  report: IntegrityReport | null;
}

export interface ComplianceExportButtonsProps {
  rows: readonly ComplianceExportRow[];
  /** ISO timestamp embedded into the download filename for traceability. */
  generatedAt: string;
  /**
   * Base API URL forwarded from the composition root so the client
   * component can construct an adapter on demand (only when the user
   * clicks the full-bundle export).  Rule C5: this remains the only
   * channel through which client code learns the API URL; it never
   * reads `NEXT_PUBLIC_EXPLAINABILITY_API_URL` directly.
   */
  apiUrl: string;
}

const CSV_HEADER = [
  "workflow_id",
  "started_at",
  "status",
  "event_count",
  "primary_agent_id",
  "chain_valid",
  "broken_at_event_id",
  "expected_hash",
  "actual_hash",
];

function csvEscape(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function rowsToCsv(rows: readonly ComplianceExportRow[]): string {
  const lines = [CSV_HEADER.join(",")];
  for (const { workflow: w, report: r } of rows) {
    lines.push(
      [
        csvEscape(w.workflow_id),
        csvEscape(w.started_at),
        csvEscape(w.status),
        csvEscape(w.event_count),
        csvEscape(w.primary_agent_id),
        csvEscape(r?.chain_valid ?? null),
        csvEscape(r?.broken_at_event_id ?? null),
        csvEscape(r?.expected_hash ?? null),
        csvEscape(r?.actual_hash ?? null),
      ].join(","),
    );
  }
  return lines.join("\n") + "\n";
}

function summaryToJson(
  rows: readonly ComplianceExportRow[],
  generatedAt: string,
): string {
  return JSON.stringify(
    {
      generated_at: generatedAt,
      bundle_type: "compliance_summary",
      workflow_count: rows.length,
      workflows: rows.map(({ workflow, report }) => ({
        workflow_summary: workflow,
        integrity: report,
      })),
    },
    null,
    2,
  );
}

interface FullBundleExportShape {
  generated_at: string;
  bundle_type: "compliance_audit_bundle";
  workflow_count: number;
  bundle_failures: { workflow_id: string; error: string }[];
  workflows: ComplianceBundle[];
}

function fullBundleToJson(
  bundles: ComplianceBundle[],
  failures: { workflow_id: string; error: string }[],
  generatedAt: string,
): string {
  const payload: FullBundleExportShape = {
    generated_at: generatedAt,
    bundle_type: "compliance_audit_bundle",
    workflow_count: bundles.length,
    bundle_failures: failures,
    workflows: bundles,
  };
  return JSON.stringify(payload, null, 2);
}

function triggerDownload(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function safeStamp(generatedAt: string): string {
  return generatedAt.replace(/[:.]/g, "-");
}

export function ComplianceExportButtons({
  rows,
  generatedAt,
  apiUrl,
}: ComplianceExportButtonsProps) {
  const stamp = safeStamp(generatedAt);
  const disabled = rows.length === 0;
  const [fullBundleStatus, setFullBundleStatus] = useState<
    "idle" | "loading" | "error"
  >("idle");

  async function handleFullBundleExport() {
    setFullBundleStatus("loading");
    try {
      const client = new HttpExplainabilityClient(apiUrl);
      const bundles: ComplianceBundle[] = [];
      const failures: { workflow_id: string; error: string }[] = [];
      // Sequential fetches — small N for the MVP and avoids hammering the
      // backend.  If row counts grow, switch to a bounded concurrency pool.
      for (const { workflow } of rows) {
        try {
          bundles.push(
            await client.getWorkflowCompliance(workflow.workflow_id),
          );
        } catch (err) {
          failures.push({
            workflow_id: workflow.workflow_id,
            error: err instanceof Error ? err.message : "unknown",
          });
        }
      }
      triggerDownload(
        fullBundleToJson(bundles, failures, generatedAt),
        `compliance-full-bundle-${stamp}.json`,
        "application/json",
      );
      setFullBundleStatus("idle");
    } catch {
      setFullBundleStatus("error");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={() =>
          triggerDownload(
            summaryToJson(rows, generatedAt),
            `compliance-summary-${stamp}.json`,
            "application/json",
          )
        }
        className={cn(
          "inline-flex items-center rounded-md border border-border bg-card px-3 py-1.5",
          "text-xs font-medium text-foreground transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        Export Summary JSON
      </button>
      <button
        type="button"
        disabled={disabled || fullBundleStatus === "loading"}
        onClick={handleFullBundleExport}
        data-testid="export-full-bundle"
        className={cn(
          "inline-flex items-center rounded-md border border-border bg-card px-3 py-1.5",
          "text-xs font-medium text-foreground transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        {fullBundleStatus === "loading"
          ? "Fetching bundles…"
          : "Export Full Bundle JSON"}
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() =>
          triggerDownload(
            rowsToCsv(rows),
            `compliance-summary-${stamp}.csv`,
            "text/csv",
          )
        }
        className={cn(
          "inline-flex items-center rounded-md border border-border bg-card px-3 py-1.5",
          "text-xs font-medium text-foreground transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        Export CSV
      </button>
      {fullBundleStatus === "error" && (
        <span role="alert" className="text-xs text-red-700">
          Bundle export failed — see browser console.
        </span>
      )}
      <span className="text-xs text-muted-foreground">
        PDF export is out of scope in the MVP.
      </span>
    </div>
  );
}
