/**
 * Recalled-memories eval disclosure (chat-persistence Phase B, B2). Under an
 * assistant turn, a collapsible "memories recalled here" list of the items the
 * agent recalled for THIS turn (key + type + content), each with a Reject
 * button that soft-suppresses the memory globally (D5).
 *
 * Gated to a dev/eval surface by the parent (`evalMode`) so production chat
 * stays clean — this component itself is purely presentational (F-R1): it
 * takes the resolved items + an `onReject` callback as typed props, invents no
 * transport, and reads no state. The parent JOINS the run view's recalled KEYS
 * against the owner's loaded memory panel to produce `items` (content never
 * rides the recall wire event — the privacy invariant holds; the owner already
 * has their own content in the panel).
 *
 * Renders nothing when there are no recalled items (no recall / flag off) so it
 * never adds noise.
 *
 * Deterministic hooks (design §6 testid contract):
 *   data-testid="recalled-memories"        the disclosure
 *   data-testid="recalled-memory-{key}"    one recalled item row
 *   data-testid="reject-memory-{key}"      the Reject (soft-suppress) button
 */

import * as React from "react";
import type { MemoryItem } from "@/lib/wire/agent_protocol";

export function RecalledMemories(props: {
  items: ReadonlyArray<MemoryItem>;
  onReject: (key: string) => void;
  /** Pre-open the disclosure (eval surface defaults open so the recalled list
   *  — and its Reject affordances — are part of the capture). */
  defaultOpen?: boolean;
}): React.JSX.Element | null {
  if (props.items.length === 0) return null;
  const n = props.items.length;
  return (
    <details
      data-testid="recalled-memories"
      className="text-xs text-muted"
      open={props.defaultOpen ?? false}
    >
      <summary className="cursor-pointer select-none">
        {n === 1 ? "1 memory recalled here" : `${n} memories recalled here`}
      </summary>
      <ul className="m-0 mt-1 list-none p-0 grid gap-1">
        {props.items.map((item) => (
          <li
            key={item.key}
            data-testid={`recalled-memory-${item.key}`}
            className="flex items-start justify-between gap-2"
          >
            <span className="min-w-0">
              {item.type ? (
                <span className="uppercase tracking-wide opacity-70 mr-1">
                  {item.type}
                </span>
              ) : null}
              <span className="break-words">{item.content}</span>
            </span>
            <button
              type="button"
              data-testid={`reject-memory-${item.key}`}
              onClick={() => props.onReject(item.key)}
              className="shrink-0 underline hover:no-underline text-red-600 dark:text-red-400"
              aria-label={`Reject this memory`}
            >
              Reject
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
