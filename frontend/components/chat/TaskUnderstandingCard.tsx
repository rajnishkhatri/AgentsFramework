/**
 * "Here's my understanding" soft-gate card (task_understanding plan §4.6,
 * Phase 3 display + Phase 4 edit mode).
 *
 * Renders the plan-time TaskUnderstanding artifact -- the restated intent
 * plus the success checklist the judge will score against -- while the run
 * keeps streaming (soft gate: it never blocks tokens). The provenance badge
 * tells the user whether the checklist was LLM-generated, the deterministic
 * floor, or their own edit.
 *
 * Edit mode (Phase 4): when `editable`, an Edit affordance pauses the run
 * (`onEditStart`), the intent + conditions become a small form, and Save
 * hands the draft to `onSave` (the hook POSTs it and resumes the thread).
 * Bounds mirror TaskUnderstandingEditRequest: intent 1..600, 2..7
 * conditions of 1..200 chars -- Save stays disabled outside them. All
 * lifecycle logic lives in the parent hook (F-R1): this component only
 * holds the draft.
 *
 * Deterministic hooks: `data-testid="task-understanding-card"`,
 * `data-source`, `data-condition-count`, `understanding-condition-{i}`,
 * `understanding-edit`, `understanding-intent-input`,
 * `understanding-condition-input-{i}`, `understanding-save`,
 * `understanding-cancel-edit`, `understanding-edit-error`.
 *
 * Per F-R1/F-R2/F-R8: typed props in, markup out -- no business logic, no
 * SDK imports, wire types only.
 */

import * as React from "react";
import { Square } from "lucide-react";
import type { AssistantRunView } from "@/lib/translators/run_view_reducer";

const SOURCE_LABEL: Record<string, string> = {
  deterministic: "derived from task",
  generated: "AI-restated",
  user_edited: "edited by you",
};

const MAX_INTENT_LEN = 600;
const MAX_CONDITION_LEN = 200;
const MIN_CONDITIONS = 2;
const MAX_CONDITIONS = 7;

export interface UnderstandingDraft {
  readonly restated_intent: string;
  readonly success_conditions: ReadonlyArray<string>;
}

function draftIsValid(intent: string, conditions: ReadonlyArray<string>): boolean {
  if (intent.trim().length === 0 || intent.length > MAX_INTENT_LEN) return false;
  if (conditions.length < MIN_CONDITIONS || conditions.length > MAX_CONDITIONS) {
    return false;
  }
  return conditions.every(
    (c) => c.trim().length > 0 && c.length <= MAX_CONDITION_LEN,
  );
}

export function TaskUnderstandingCard(props: {
  understanding: NonNullable<AssistantRunView["understanding"]>;
  /** Phase 4: render the Edit affordance (the run is pausable). */
  editable?: boolean;
  /** Rejected edit POST -- shown inside the form; the run stays paused. */
  editError?: string | null;
  /** Entering edit mode (the parent pauses the stream). */
  onEditStart?: () => void;
  /** Save the draft (the parent POSTs the edit and resumes). */
  onSave?: (draft: UnderstandingDraft) => void;
  /** Leave edit mode without saving (the parent resumes unchanged). */
  onCancel?: () => void;
}): React.JSX.Element {
  const { understanding } = props;
  // Edit mode is keyed to the artifact identity the draft was opened
  // against: a fresh artifact event (e.g. the post-resume user_edited
  // re-emit) supersedes the draft by derivation. Deliberately NOT an
  // effect -- a passive `setEditing(false)` reset races a fast Edit click
  // (the mount-commit effect can flush after the click and silently close
  // the form the user just opened).
  const [editingFor, setEditingFor] = React.useState<
    typeof understanding | null
  >(null);
  const [intent, setIntent] = React.useState("");
  const [conditions, setConditions] = React.useState<ReadonlyArray<string>>([]);
  const editing = editingFor === understanding;

  function startEdit(): void {
    setIntent(understanding.restated_intent);
    setConditions(understanding.success_conditions);
    setEditingFor(understanding);
    props.onEditStart?.();
  }

  function setCondition(i: number, value: string): void {
    setConditions((prev) => prev.map((c, idx) => (idx === i ? value : c)));
  }

  if (editing) {
    const valid = draftIsValid(intent, conditions);
    return (
      <aside
        data-testid="task-understanding-card"
        data-source={understanding.source}
        data-condition-count={conditions.length}
        data-editing="true"
        role="note"
        aria-label="Edit the agent's understanding of your task"
        className="@container/understanding surface-etched rounded-lg bg-surface p-3 text-sm grid gap-2"
      >
        <p className="m-0 font-medium">Correct my understanding</p>
        <textarea
          data-testid="understanding-intent-input"
          aria-label="Restated intent"
          value={intent}
          maxLength={MAX_INTENT_LEN}
          onChange={(e) => setIntent(e.target.value)}
          className="w-full rounded-sm border border-border bg-surface p-1 text-sm"
          rows={2}
        />
        <ul className="m-0 list-none p-0 grid gap-1">
          {conditions.map((condition, i) => (
            <li key={`draft-${i}`} className="flex gap-2 items-center text-xs">
              <Square className="size-3.5 shrink-0 text-muted" aria-hidden="true" />
              <input
                data-testid={`understanding-condition-input-${i}`}
                aria-label={`Success condition ${i + 1}`}
                value={condition}
                maxLength={MAX_CONDITION_LEN}
                onChange={(e) => setCondition(i, e.target.value)}
                className="w-full rounded-sm border border-border bg-surface p-1 text-xs"
              />
              <button
                type="button"
                data-testid={`understanding-remove-condition-${i}`}
                aria-label={`Remove condition ${i + 1}`}
                disabled={conditions.length <= MIN_CONDITIONS}
                onClick={() =>
                  setConditions((prev) => prev.filter((_, idx) => idx !== i))
                }
                className="text-muted hover:text-fg disabled:opacity-40 cursor-pointer bg-transparent border-0"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 items-center">
          <button
            type="button"
            data-testid="understanding-add-condition"
            disabled={conditions.length >= MAX_CONDITIONS}
            onClick={() => setConditions((prev) => [...prev, ""])}
            className="text-xs text-muted hover:text-fg disabled:opacity-40 cursor-pointer bg-transparent border border-border rounded-sm px-2 py-0.5"
          >
            + condition
          </button>
          <span className="flex-1" />
          <button
            type="button"
            data-testid="understanding-cancel-edit"
            onClick={() => {
              setEditingFor(null);
              props.onCancel?.();
            }}
            className="text-xs text-muted hover:text-fg cursor-pointer bg-transparent border border-border rounded-sm px-2 py-0.5"
          >
            Cancel
          </button>
          <button
            type="button"
            data-testid="understanding-save"
            disabled={!valid}
            onClick={() =>
              props.onSave?.({
                restated_intent: intent.trim(),
                success_conditions: conditions.map((c) => c.trim()),
              })
            }
            className="text-xs font-medium text-white bg-accent rounded-sm px-2 py-0.5 disabled:opacity-40 cursor-pointer border-0"
          >
            Save & resume
          </button>
        </div>
        {props.editError ? (
          <p
            data-testid="understanding-edit-error"
            role="alert"
            className="m-0 text-xs text-red-600 dark:text-red-400"
          >
            {props.editError}
          </p>
        ) : null}
      </aside>
    );
  }

  return (
    <aside
      data-testid="task-understanding-card"
      data-source={understanding.source}
      data-condition-count={understanding.success_conditions.length}
      role="note"
      aria-label="Agent's understanding of your task"
      className="@container/understanding surface-etched rounded-lg bg-surface p-3 text-sm grid gap-1"
    >
      <p className="m-0 font-medium flex flex-wrap items-baseline gap-x-2">
        <span>Here&apos;s my understanding</span>
        {/* The provenance label wraps under the heading in a narrow slot rather
           than overflowing the row (§5 container query via flex-wrap). */}
        <span className="text-xs font-normal text-muted">
          {SOURCE_LABEL[understanding.source] ?? understanding.source}
        </span>
        {props.editable ? (
          <button
            type="button"
            data-testid="understanding-edit"
            onClick={startEdit}
            aria-label="Edit the agent's understanding"
            className="ml-2 text-xs font-normal text-muted hover:text-fg cursor-pointer bg-transparent border border-border rounded-sm px-1.5 py-0"
          >
            Edit
          </button>
        ) : null}
      </p>
      <p className="m-0 italic">{understanding.restated_intent}</p>
      <ul className="m-0 mt-1 list-none p-0 grid gap-0.5">
        {understanding.success_conditions.map((condition, i) => (
          <li
            key={`cond-${i}`}
            data-testid={`understanding-condition-${i}`}
            className="flex gap-2 items-start text-xs"
          >
            <Square className="size-3.5 shrink-0 mt-0.5 text-muted" aria-hidden="true" />
            <span>{condition}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
