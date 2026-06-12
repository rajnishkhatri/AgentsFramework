/**
 * "Here's my understanding" soft-gate card (task_understanding plan §4.6,
 * Phase 3: display-only).
 *
 * Renders the plan-time TaskUnderstanding artifact -- the restated intent
 * plus the success checklist the judge will score against -- while the run
 * keeps streaming (soft gate: it never blocks tokens). The provenance badge
 * tells the user whether the checklist was LLM-generated, the deterministic
 * floor, or their own edit. Edit/pause affordances arrive in Phase 4.
 *
 * Deterministic hooks: `data-testid="task-understanding-card"`,
 * `data-source`, `data-condition-count`, `data-testid="understanding-condition-{i}"`.
 *
 * Per F-R1/F-R2/F-R8: typed props in, markup out -- no business logic, no
 * SDK imports, wire types only.
 */

import * as React from "react";
import type { AssistantRunView } from "@/lib/translators/run_view_reducer";

const SOURCE_LABEL: Record<string, string> = {
  deterministic: "derived from task",
  generated: "AI-restated",
  user_edited: "edited by you",
};

export function TaskUnderstandingCard(props: {
  understanding: NonNullable<AssistantRunView["understanding"]>;
}): React.JSX.Element {
  const { understanding } = props;
  return (
    <aside
      data-testid="task-understanding-card"
      data-source={understanding.source}
      data-condition-count={understanding.success_conditions.length}
      role="note"
      aria-label="Agent's understanding of your task"
      className="rounded-md border border-border bg-muted/30 p-3 text-sm grid gap-1"
    >
      <p className="m-0 font-medium">
        Here&apos;s my understanding
        <span className="ml-2 text-xs font-normal text-muted">
          {SOURCE_LABEL[understanding.source] ?? understanding.source}
        </span>
      </p>
      <p className="m-0 italic">{understanding.restated_intent}</p>
      <ul className="m-0 mt-1 list-none p-0 grid gap-0.5">
        {understanding.success_conditions.map((condition, i) => (
          <li
            key={`cond-${i}`}
            data-testid={`understanding-condition-${i}`}
            className="flex gap-2 items-baseline text-xs"
          >
            <span aria-hidden="true">☐</span>
            <span>{condition}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
