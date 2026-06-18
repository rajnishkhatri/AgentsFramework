/**
 * Memory panel (Phase 3, F1) -- the user-visible, editable view of their own
 * long-term memory. The visible/editable panel is the 2026 trust norm
 * (research §4): the user can see what the agent remembers, add a fact, delete
 * one, and toggle memory off entirely.
 *
 * Per F-R1/F-R2/F-R8: typed props in, markup out. NO business logic, NO SDK
 * imports, wire types only. All lifecycle (fetching the list, POST/DELETE,
 * persisting the toggle) lives in the parent hook/adapter -- this component
 * only renders the passed state and calls the passed callbacks.
 *
 * Deterministic hooks: data-testid="memory-panel", "memory-empty",
 * "memory-group-{type}", "memory-item-{key}", "memory-delete-{key}",
 * "memory-add-input", "memory-add-type", "memory-add-submit",
 * "memory-enabled-toggle".
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { MemoryItem, MemoryType } from "@/lib/wire/agent_protocol";

const TYPE_ORDER: ReadonlyArray<MemoryType> = [
  "semantic",
  "episodic",
  "procedural",
];

const TYPE_LABEL: Record<MemoryType, string> = {
  semantic: "Facts about you",
  episodic: "Past tasks",
  procedural: "Strategies that worked",
};

const MAX_CONTENT_LEN = 2000;

function groupByType(
  items: ReadonlyArray<MemoryItem>,
): Record<MemoryType, MemoryItem[]> {
  const groups: Record<MemoryType, MemoryItem[]> = {
    semantic: [],
    episodic: [],
    procedural: [],
  };
  for (const item of items) {
    // Items with no/unknown type fall under "facts about you" (semantic) so
    // they are never silently hidden.
    const t: MemoryType =
      item.type === "episodic" || item.type === "procedural"
        ? item.type
        : "semantic";
    groups[t].push(item);
  }
  return groups;
}

export function MemoryPanel(props: {
  items: ReadonlyArray<MemoryItem>;
  enabled: boolean;
  onAdd?: (content: string, type: MemoryType) => void;
  onDelete?: (key: string) => void;
  onToggleEnabled?: (enabled: boolean) => void;
}): React.JSX.Element {
  const [draft, setDraft] = React.useState("");
  const [draftType, setDraftType] = React.useState<MemoryType>("semantic");

  const groups = groupByType(props.items);
  const canAdd = draft.trim().length > 0 && draft.length <= MAX_CONTENT_LEN;

  const submit = () => {
    if (!canAdd || !props.onAdd) return;
    props.onAdd(draft.trim(), draftType);
    setDraft("");
  };

  return (
    <section
      data-testid="memory-panel"
      aria-label="Your memory"
      className="grid gap-4 p-4 border-l border-border-light bg-bg min-w-72"
    >
      <header className="flex items-center justify-between">
        <h2 className="text-fg text-sm font-semibold m-0">What I remember</h2>
        <label className="flex items-center gap-2 text-xs text-muted">
          <input
            type="checkbox"
            data-testid="memory-enabled-toggle"
            checked={props.enabled}
            onChange={(e) => props.onToggleEnabled?.(e.target.checked)}
          />
          Memory {props.enabled ? "on" : "off"}
        </label>
      </header>

      {props.items.length === 0 ? (
        <p data-testid="memory-empty" className="text-xs text-muted m-0">
          Nothing remembered yet.
        </p>
      ) : (
        TYPE_ORDER.map((type) =>
          groups[type].length === 0 ? null : (
            <div key={type} data-testid={`memory-group-${type}`}>
              <h3 className="text-xs uppercase tracking-wide text-muted m-0 mb-1">
                {TYPE_LABEL[type]}
              </h3>
              <ul className="grid gap-1 list-none p-0 m-0">
                {groups[type].map((item) => (
                  <li
                    key={item.key}
                    data-testid={`memory-item-${item.key}`}
                    className="flex items-start justify-between gap-2 text-sm text-fg"
                  >
                    <span className="flex-1">{item.content}</span>
                    <button
                      type="button"
                      data-testid={`memory-delete-${item.key}`}
                      aria-label={`Forget: ${item.content}`}
                      onClick={() => props.onDelete?.(item.key)}
                      className="text-muted hover:text-red-500 text-xs"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ),
        )
      )}

      <form
        className="grid gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <input
          data-testid="memory-add-input"
          value={draft}
          maxLength={MAX_CONTENT_LEN}
          placeholder="Add something to remember…"
          onChange={(e) => setDraft(e.target.value)}
          className="px-2 py-1 rounded-sm border border-border-light bg-bg text-fg text-sm"
        />
        <div className="flex items-center gap-2">
          <select
            data-testid="memory-add-type"
            value={draftType}
            onChange={(e) => setDraftType(e.target.value as MemoryType)}
            className="px-2 py-1 rounded-sm border border-border-light bg-bg text-fg text-xs"
          >
            {TYPE_ORDER.map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </select>
          <button
            type="submit"
            data-testid="memory-add-submit"
            disabled={!canAdd}
            className={cn(
              "px-3 py-1 rounded-sm text-xs",
              canAdd
                ? "bg-accent text-white"
                : "bg-transparent text-muted cursor-not-allowed",
            )}
          >
            Remember
          </button>
        </div>
      </form>
    </section>
  );
}
