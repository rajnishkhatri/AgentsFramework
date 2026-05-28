/**
 * WorkflowDeepDive — server component, presentational only (S3.2.2).
 *
 * Brainstorm §5b layout: four quadrants for Recording, Identity, Validation,
 * and Reasoning, joined to a single workflow. The component never re-fetches
 * — every datum comes from the already-fetched `ComplianceBundle`.
 *
 * Each quadrant ends with a "drill into" link back to the dedicated module
 * route so the operator can jump to the full surface (trace timeline,
 * agent identity card, guardrail monitor, decision audit).
 *
 * Rule U6: every class merge runs through `cn()`.
 * Rule B1: RSC by default — no `'use client'` here.
 * Rule FD4.SEM: every drill-in is a `<Link>` (anchor), never `<div onClick>`.
 */
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  countGuardrails,
  type GuardrailCounts,
} from "@/lib/translators/compliance_bundle";
import type { ComplianceBundle } from "@/lib/wire/responses";

export interface WorkflowDeepDiveProps {
  bundle: ComplianceBundle;
}

function truncateHash(hash: string | null | undefined): string {
  if (!hash) return "—";
  if (hash.length <= 16) return hash;
  return `${hash.slice(0, 8)}…${hash.slice(-8)}`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function Quadrant({
  title,
  caption,
  children,
  drillLabel,
  drillHref,
  testid,
}: {
  title: string;
  caption: string;
  children: React.ReactNode;
  drillLabel: string;
  drillHref: string;
  testid: string;
}) {
  return (
    <article
      data-quadrant={testid}
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-card p-4",
      )}
    >
      <header className="flex items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">{caption}</p>
        </div>
        <Link
          href={drillHref}
          className="text-xs text-primary underline-offset-4 hover:underline"
        >
          {drillLabel} →
        </Link>
      </header>
      <div className="text-sm">{children}</div>
    </article>
  );
}

function PassFailBar({ counts }: { counts: GuardrailCounts }) {
  if (counts.total === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No guardrail checks recorded for this workflow.
      </p>
    );
  }
  const passPct = (counts.pass / counts.total) * 100;
  return (
    <dl className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between text-xs">
        <dt className="text-muted-foreground">Pass / Fail</dt>
        <dd className="tabular-nums text-foreground">
          {counts.pass} / {counts.fail}
        </dd>
      </div>
      <div className="h-2 overflow-hidden rounded bg-red-100">
        <div
          className="h-full bg-green-500"
          style={{ width: `${passPct}%` }}
          role="progressbar"
          aria-valuenow={Math.round(passPct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Pass rate ${passPct.toFixed(1)}%`}
        />
      </div>
    </dl>
  );
}

export function WorkflowDeepDive({ bundle }: WorkflowDeepDiveProps) {
  const guardrailCounts = countGuardrails(bundle);
  const firstEvent = bundle.events[0];
  const lastEvent = bundle.events[bundle.events.length - 1];
  const agents = Object.entries(bundle.identity_cards);
  const decisions = bundle.phase_decisions;

  return (
    <section
      aria-label="Four-pillar workflow deep dive"
      className="grid grid-cols-1 gap-3 lg:grid-cols-2"
    >
      <Quadrant
        title="Recording"
        caption="Hash-chain status, event counts, time-bounds."
        drillLabel="Open trace timeline"
        drillHref={`/traces/${bundle.workflow_id}`}
        testid="recording"
      >
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <dt className="text-muted-foreground">Chain</dt>
            <dd
              data-chain-valid={bundle.hash_chain_valid}
              className={cn(
                "mt-0.5 font-medium",
                bundle.hash_chain_valid ? "text-green-700" : "text-red-700",
              )}
            >
              {bundle.hash_chain_valid ? "valid" : "tampered"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Events</dt>
            <dd className="mt-0.5 tabular-nums text-foreground">
              {bundle.event_count}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">First event</dt>
            <dd className="mt-0.5 text-foreground">
              {formatDate(firstEvent?.timestamp)}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Last event</dt>
            <dd className="mt-0.5 text-foreground">
              {formatDate(lastEvent?.timestamp)}
            </dd>
          </div>
        </dl>
        {/*
          Sprint 3 review F4: when the chain is broken, name the broken
          event and show the truncated expected/actual hashes so an
          operator drilling in here gets stronger evidence than the home
          table can offer.
        */}
        {!bundle.hash_chain_valid && bundle.integrity.broken_at_event_id && (
          <dl
            data-testid="recording-break-evidence"
            className="mt-2 flex flex-col gap-1 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs"
          >
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-red-800">Broken at event</dt>
              <dd className="font-mono text-red-900">
                {bundle.integrity.broken_at_event_id}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-red-800">Expected hash</dt>
              <dd className="font-mono text-red-900">
                {truncateHash(bundle.integrity.expected_hash)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-red-800">Actual hash</dt>
              <dd className="font-mono text-red-900">
                {truncateHash(bundle.integrity.actual_hash)}
              </dd>
            </div>
          </dl>
        )}
      </Quadrant>

      <Quadrant
        title="Identity"
        caption="Agents involved in this workflow."
        drillLabel="All agents"
        drillHref="/agents"
        testid="identity"
      >
        {agents.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No identity cards available — no registry was wired in.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {agents.map(([agentId, card]) => (
              <li
                key={agentId}
                data-agent={agentId}
                className={cn(
                  "flex items-center justify-between gap-2 rounded-md border border-border",
                  "bg-background px-3 py-2",
                )}
              >
                <Link
                  href={`/agents/${agentId}`}
                  className="font-mono text-xs text-primary underline-offset-4 hover:underline"
                >
                  {agentId}
                </Link>
                {card === null ? (
                  <span className="text-xs text-muted-foreground">
                    not registered
                  </span>
                ) : (
                  <span
                    data-verification-status={
                      card.signature_verification_status
                    }
                    className={cn(
                      "text-xs font-medium",
                      card.signature_verification_status === "verified" &&
                        "text-green-700",
                      card.signature_verification_status === "failed" &&
                        "text-red-700",
                      card.signature_verification_status === "unavailable" &&
                        "text-amber-700",
                    )}
                  >
                    {card.signature_verification_status === "verified"
                      ? "verified"
                      : card.signature_verification_status === "failed"
                        ? "verification failed"
                        : "verification unavailable"}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Quadrant>

      <Quadrant
        title="Validation"
        caption="Guardrail pass/fail counts for this workflow's events."
        drillLabel="Open guardrail monitor"
        drillHref="/guardrails"
        testid="validation"
      >
        <PassFailBar counts={guardrailCounts} />
      </Quadrant>

      <Quadrant
        title="Reasoning"
        caption="Phase decisions recorded for this workflow."
        drillLabel="Open decision audit"
        drillHref={`/decisions/${bundle.workflow_id}`}
        testid="reasoning"
      >
        {decisions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No phase decisions recorded.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {decisions.slice(0, 4).map((d, idx) => (
              <li
                key={`${d.timestamp ?? "no-ts"}-${idx}`}
                className="rounded-md border border-border bg-background px-3 py-2"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-mono text-xs text-muted-foreground">
                    {d.phase}
                  </span>
                  <span className="tabular-nums text-xs text-muted-foreground">
                    {(d.confidence * 100).toFixed(0)}% conf
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-foreground">
                  {d.description}
                </p>
              </li>
            ))}
            {decisions.length > 4 && (
              <li className="text-xs text-muted-foreground">
                +{decisions.length - 4} more — see decision audit
              </li>
            )}
          </ul>
        )}
      </Quadrant>
    </section>
  );
}
