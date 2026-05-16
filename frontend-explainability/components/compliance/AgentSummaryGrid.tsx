/**
 * AgentSummaryGrid — server component, presentational only (S3.2.1).
 *
 * Compact identity grid for the Compliance home: one tile per agent with
 * the same status + signature-verification semantics as the full IdentityCard.
 * Read-only by design (F-R6).
 *
 * Rule U6: every class merge runs through `cn()`.
 */
import Link from "next/link";
import { cn } from "@/lib/utils";
import type {
  AgentCard,
  SignatureVerificationStatus,
} from "@/lib/wire/responses";

export interface AgentSummaryGridProps {
  agents: readonly AgentCard[];
}

const STATUS_CLASS: Record<string, string> = {
  active: "bg-green-50 text-green-700 ring-green-600/20",
  suspended: "bg-amber-50 text-amber-700 ring-amber-600/20",
  revoked: "bg-red-50 text-red-700 ring-red-600/20",
};

function statusClass(status: string): string {
  return STATUS_CLASS[status] ?? "bg-muted text-muted-foreground ring-border";
}

const VERIFICATION_LABEL: Record<SignatureVerificationStatus, string> = {
  verified: "verified",
  failed: "verification failed",
  unavailable: "verification unavailable",
};

const VERIFICATION_CLASS: Record<SignatureVerificationStatus, string> = {
  verified: "text-green-700",
  failed: "text-red-700",
  unavailable: "text-amber-700",
};

export function AgentSummaryGrid({ agents }: AgentSummaryGridProps) {
  if (agents.length === 0) {
    return (
      <div
        role="status"
        aria-label="No agents"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-10 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No agents registered.</p>
      </div>
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <li
          key={agent.agent_id}
          className={cn(
            "flex flex-col gap-2 rounded-lg border border-border bg-card p-4",
          )}
          data-status={agent.status}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <Link
                href={`/agents/${agent.agent_id}`}
                className={cn(
                  "block truncate font-mono text-sm font-medium",
                  "text-primary underline-offset-4 hover:underline",
                )}
              >
                {agent.agent_id}
              </Link>
              <p className="truncate text-xs text-muted-foreground">
                {agent.agent_name}
              </p>
            </div>
            <span
              className={cn(
                "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                statusClass(agent.status),
              )}
            >
              {agent.status}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-muted-foreground">Signature</dt>
              <dd
                data-verification-status={agent.signature_verification_status}
                className={cn(
                  "mt-0.5 font-medium",
                  VERIFICATION_CLASS[agent.signature_verification_status],
                )}
              >
                {VERIFICATION_LABEL[agent.signature_verification_status]}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Capabilities</dt>
              <dd className="mt-0.5 tabular-nums text-foreground">
                {agent.capabilities.length}
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}
