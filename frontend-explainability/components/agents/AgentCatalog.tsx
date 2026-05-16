"use client";
/**
 * AgentCatalog — searchable agent table for the /agents route (S2.2.2).
 *
 * Rule B1 — `'use client'` is justified: the capability search box maintains
 * local input state. Server Components cannot host `useState`.
 *
 * Behavioural contract (S2.2.2 AC):
 *   - Empty-string query returns the full agent list (failure-first test
 *     covers this so a regression to `query.length > 0 ? filter : []` cannot
 *     ship).
 *   - Match is substring-based against capability names; case-insensitive.
 *   - Status badge surface mirrors the workflows-table StatusBadge style.
 *
 * Rule U6: every class merge runs through `cn()`.
 * Rule FD4.SEM: clickable affordances use `<Link>` (which renders `<a>`),
 *   never `<div onClick>`.
 */
import { useMemo, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { AgentCard } from "@/lib/wire/responses";

export interface AgentCatalogProps {
  agents: readonly AgentCard[];
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        status === "active" && "bg-green-50 text-green-700 ring-green-600/20",
        status === "suspended" &&
          "bg-amber-50 text-amber-700 ring-amber-600/20",
        status === "revoked" && "bg-red-50 text-red-700 ring-red-600/20",
        status !== "active" &&
          status !== "suspended" &&
          status !== "revoked" &&
          "bg-muted text-muted-foreground ring-border",
      )}
    >
      {status}
    </span>
  );
}

export function AgentCatalog({ agents }: AgentCatalogProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    // S2.2.2 AC: empty-string query returns the full list.
    if (trimmed === "") return agents;
    return agents.filter((agent) =>
      agent.capabilities.some((cap) =>
        cap.name.toLowerCase().includes(trimmed),
      ),
    );
  }, [agents, query]);

  if (agents.length === 0) {
    return (
      <div
        role="status"
        aria-label="No agents"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-16 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No agents registered.</p>
        <p className="mt-1 text-xs">
          Run{" "}
          <code className="font-mono">
            python -m explainability_app.dev_seed
          </code>{" "}
          to seed sample data.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <label className="flex max-w-md items-center gap-2 text-sm">
        <span className="font-medium text-foreground">Capability search</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. shell.run"
          aria-label="Filter agents by capability name"
          className={cn(
            "flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm",
            "outline-none focus:ring-2 focus:ring-primary",
          )}
        />
      </label>

      {filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No agents match the capability filter.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/50">
              <tr>
                {["Agent", "Owner", "Version", "Status", "Capabilities"].map(
                  (col) => (
                    <th
                      key={col}
                      scope="col"
                      className={cn(
                        "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide",
                        "text-muted-foreground",
                      )}
                    >
                      {col}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-card">
              {filtered.map((agent) => (
                <tr
                  key={agent.agent_id}
                  className={cn("transition-colors hover:bg-accent/50")}
                >
                  <td className="px-4 py-3 font-mono text-xs">
                    <Link
                      href={`/agents/${agent.agent_id}`}
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      {agent.agent_id}
                    </Link>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {agent.agent_name}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {agent.owner}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-muted-foreground">
                    {agent.version}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={agent.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {agent.capabilities.length === 0
                      ? "—"
                      : agent.capabilities
                          .map((c) => c.name)
                          .join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
