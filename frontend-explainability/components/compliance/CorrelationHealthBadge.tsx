/**
 * CorrelationHealthBadge — server component, presentational only (S3.2.2).
 *
 * Header pill summarising whether the four correlation keys (`trace_id`,
 * `user_id`, `task_id`, `agent_id`) are present.  Missing keys are NEVER
 * silently omitted (S3.2.2 AC) — the badge always names them explicitly.
 *
 * Rule U6: every class merge runs through `cn()`.
 */
import { cn } from "@/lib/utils";
import type { CorrelationHealth } from "@/lib/wire/responses";

export interface CorrelationHealthBadgeProps {
  health: CorrelationHealth;
}

const KEYS: Array<{
  label: string;
  has: keyof Pick<
    CorrelationHealth,
    "has_trace_id" | "has_user_id" | "has_task_id" | "has_agent_id"
  >;
  name: string;
}> = [
  { label: "trace_id", has: "has_trace_id", name: "trace_id" },
  { label: "user_id", has: "has_user_id", name: "user_id" },
  { label: "task_id", has: "has_task_id", name: "task_id" },
  { label: "agent_id", has: "has_agent_id", name: "agent_id" },
];

export function CorrelationHealthBadge({ health }: CorrelationHealthBadgeProps) {
  const complete = health.missing_keys.length === 0;
  return (
    <div
      data-correlation-complete={String(complete)}
      aria-label={
        complete
          ? "Correlation complete"
          : `Missing correlation keys: ${health.missing_keys.join(", ")}`
      }
      className={cn(
        "flex flex-col gap-2 rounded-lg border p-4",
        complete
          ? "border-green-600/20 bg-green-50"
          : "border-amber-600/30 bg-amber-50",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "text-sm font-semibold",
            complete ? "text-green-700" : "text-amber-700",
          )}
        >
          {complete
            ? "Correlation complete"
            : `Missing ${health.missing_keys.length} correlation key${health.missing_keys.length === 1 ? "" : "s"}`}
        </span>
        <span
          className={cn(
            "text-xs",
            complete ? "text-green-700" : "text-amber-700",
          )}
        >
          trace_id · user_id · task_id · agent_id
        </span>
      </div>
      <ul
        aria-label="Per-key correlation status"
        className="grid grid-cols-2 gap-1 text-xs sm:grid-cols-4"
      >
        {KEYS.map((k) => (
          <li
            key={k.name}
            data-key={k.name}
            data-present={String(health[k.has])}
            className={cn(
              "flex items-center gap-1 rounded-md bg-card/70 px-2 py-1 font-mono",
              health[k.has]
                ? "text-green-700"
                : "text-red-700",
            )}
          >
            <span aria-hidden="true">{health[k.has] ? "✓" : "✗"}</span>
            <span>{k.label}</span>
          </li>
        ))}
      </ul>
      {!complete && (
        <p className="text-xs text-amber-700">
          Missing:{" "}
          <span className="font-mono">
            {health.missing_keys.join(", ")}
          </span>
        </p>
      )}
    </div>
  );
}
