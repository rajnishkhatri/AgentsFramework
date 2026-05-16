/**
 * IdentityCard — presentational, no `'use client'`.
 *
 * Renders the agent's identity panel: header, status badge, three-state
 * signature verification badge, and the grouped capabilities/policies
 * lists.  Verification is computed server-side -- the browser never
 * re-verifies the HMAC.  The badge consumes
 * ``signature_verification_status`` so it can distinguish ``verified``
 * (HMAC matched), ``failed`` (mismatch / suspended), and ``unavailable``
 * (verify could not run, e.g. missing secret) instead of collapsing all
 * three into a binary.
 *
 * F-R6: this component shows NO Suspend / Restore / Revoke controls.
 *   The agents UI is read-only by design; mutations live behind a separate
 *   admin interface that is not part of the explainability MVP.
 *
 * Rule U6: every class merge runs through `cn()`.
 */
import { cn } from "@/lib/utils";
import type {
  AgentCard,
  SignatureVerificationStatus,
} from "@/lib/wire/responses";

export interface IdentityCardProps {
  agent: AgentCard;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset",
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

const VERIFICATION_LABELS: Record<SignatureVerificationStatus, string> = {
  verified: "verified",
  failed: "verification failed",
  unavailable: "verification unavailable",
};

function VerificationBadge({
  status,
}: {
  status: SignatureVerificationStatus;
}) {
  const label = VERIFICATION_LABELS[status];
  return (
    <span
      data-verification-status={status}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset",
        status === "verified" &&
          "bg-green-50 text-green-700 ring-green-600/20",
        status === "failed" && "bg-red-50 text-red-700 ring-red-600/20",
        status === "unavailable" &&
          "bg-amber-50 text-amber-800 ring-amber-600/20",
      )}
      aria-label={`Signature ${label}`}
    >
      {label}
    </span>
  );
}

export function IdentityCard({ agent }: IdentityCardProps) {
  return (
    <article
      aria-label={`Identity card for ${agent.agent_id}`}
      data-status={agent.status}
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-border bg-card p-6",
      )}
    >
      <header className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              {agent.agent_name}
            </h2>
            <p className="font-mono text-xs text-muted-foreground">
              {agent.agent_id}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={agent.status} />
            <VerificationBadge
              status={agent.signature_verification_status}
            />
          </div>
        </div>
        {agent.description && (
          <p className="text-sm text-muted-foreground">{agent.description}</p>
        )}
      </header>

      <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Owner
          </dt>
          <dd className="mt-0.5 text-foreground">{agent.owner}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Version
          </dt>
          <dd className="mt-0.5 tabular-nums text-foreground">
            {agent.version}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Signature
          </dt>
          <dd className="mt-0.5 break-all font-mono text-xs text-foreground">
            {agent.signature_truncated || "—"}
          </dd>
        </div>
      </dl>

      <section aria-label="Capabilities" className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Capabilities ({agent.capabilities.length})
        </h3>
        {agent.capabilities.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No capabilities declared.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {agent.capabilities.map((c) => (
              <li
                key={c.name}
                className={cn(
                  "rounded-md border border-border bg-background px-2 py-1 text-xs",
                  "font-mono text-foreground",
                )}
                title={c.description || undefined}
              >
                {c.name}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Policies" className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Policies ({agent.policies.length})
        </h3>
        {agent.policies.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No policies attached.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {agent.policies.map((p) => (
              <li
                key={p.name}
                className={cn(
                  "rounded-md border border-border bg-background px-2 py-1 text-xs",
                  "font-mono text-foreground",
                )}
                title={p.description || undefined}
              >
                {p.name}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
