// Justification (B1, U2): thread rows attach onClick/onSelect handlers (event
// handlers are not serialisable from RSC -> client), so this stays a leaf
// "use client" boundary. The parent page (RSC) fetches the thread list through
// the ThreadStore port and passes it in; all time-bucketing is the pure
// `groupThreadsByTime` helper, so the component holds no domain logic (F-R1).
"use client";

/**
 * Thread sidebar (Phase 3 — chat history).
 *
 * Renders the caller's threads grouped Today / Yesterday / Previous 7 days /
 * Older (via `groupThreadsByTime`), each row showing its TITLE (not the raw
 * thread_id). Click resumes (onSelect); per-row rename (onRename) and delete
 * (onDelete) affordances call back to the parent hook, which owns the
 * BFF/runtime lifecycle.
 *
 * Deterministic hooks: data-testid="thread-sidebar", "thread-empty",
 * "thread-group-{label}", "thread-row-{id}", "thread-rename-{id}",
 * "thread-delete-{id}".
 */

import * as React from "react";
import { Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ThreadState } from "@/lib/wire/agent_protocol";
import { groupThreadsByTime } from "@/lib/thread_grouping";

function groupTestId(label: string): string {
  return `thread-group-${label.toLowerCase().replace(/\s+/g, "-")}`;
}

/**
 * Phase A thread preview subtitle: the first user message's text, trimmed to a
 * single muted line under the title (the screenshot's `.thread .p`). Purely
 * presentational — no wire change. Returns "" when the list payload carries no
 * usable first-message snippet (the BFF list response defaults `messages` to
 * `[]`), in which case the row renders title-only (plan §2d Phase A fallback).
 * A subtitle that merely echoes the title (the common single-message case where
 * the title IS the first-message slice) is suppressed so the row isn't doubled.
 */
function threadSubtitle(t: ThreadState): string {
  const first = t.messages?.[0];
  if (!first) return "";
  const raw = first["content"] ?? first["text"];
  if (typeof raw !== "string") return "";
  const snippet = raw.trim().replace(/\s+/g, " ");
  if (!snippet) return "";
  // Suppress a subtitle that is just the title again (no new information).
  if (snippet === t.title || snippet.startsWith(t.title)) return "";
  return snippet;
}

export function ThreadSidebar(props: {
  threads: ReadonlyArray<ThreadState>;
  activeThreadId?: string;
  now?: number; // injectable for deterministic grouping in tests
  /**
   * True when `threads` is the result of an active search filter. An empty
   * filtered list then shows the "no match" message instead of the cold
   * "no conversations yet" empty state (UI refresh Phase 4).
   */
  isFiltered?: boolean;
  onSelect?: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onDelete?: (id: string) => void;
}): React.JSX.Element {
  const groups = groupThreadsByTime(props.threads, props.now);

  return (
    <nav
      data-testid="thread-sidebar"
      aria-label="Chat history"
      className="grid gap-3 p-3 bg-bg min-w-64"
    >
      {props.threads.length === 0 ? (
        props.isFiltered ? (
          <p
            data-testid="thread-search-empty"
            className="text-xs text-muted m-0"
          >
            No conversations match.
          </p>
        ) : (
          <p data-testid="thread-empty" className="text-xs text-muted m-0">
            No conversations yet.
          </p>
        )
      ) : (
        groups.map((group) => (
          <div key={group.label} data-testid={groupTestId(group.label)}>
            {/* Labeled etched divider (design .separator-label): the group
               name centered between two hairline rules. */}
            <h3 className="separator-label m-0 mb-1">{group.label}</h3>
            <ul className="grid gap-0.5 list-none p-0 m-0">
              {group.threads.map((t) => {
                const active = props.activeThreadId === t.thread_id;
                const subtitle = threadSubtitle(t);
                return (
                  <li
                    key={t.thread_id}
                    className="group flex items-center justify-between gap-1"
                  >
                    <a
                      data-testid={`thread-row-${t.thread_id}`}
                      href={`/threads/${t.thread_id}`}
                      aria-current={active ? "page" : undefined}
                      onClick={(e) => {
                        if (props.onSelect) {
                          e.preventDefault();
                          props.onSelect(t.thread_id);
                        }
                      }}
                      className={cn(
                        // nav-item (frozen): plain by default, subtle fg/5%
                        // overlay on hover, stronger --color-selected when
                        // active — hover stays lighter than active so the two
                        // states read apart. Hover suppressed on touch.
                        "flex-1 block px-3 py-2 rounded-md no-underline text-sm transition-colors min-w-0",
                        active
                          ? "bg-selected text-fg font-semibold"
                          : "bg-transparent text-muted font-medium [@media(hover:hover)]:hover:bg-[color-mix(in_oklab,var(--color-fg)_5%,transparent)] [@media(hover:hover)]:hover:text-fg",
                      )}
                      title={t.title}
                    >
                      <span className="block truncate">{t.title}</span>
                      {subtitle ? (
                        // Phase A preview subtitle (design .thread .p): a second
                        // muted, truncated line. Omitted entirely when absent so
                        // there is no empty line.
                        <span
                          data-testid={`thread-subtitle-${t.thread_id}`}
                          className="block truncate text-xs text-muted font-normal mt-0.5"
                        >
                          {subtitle}
                        </span>
                      ) : null}
                    </a>
                    {props.onRename ? (
                      <button
                        type="button"
                        data-testid={`thread-rename-${t.thread_id}`}
                        aria-label={`Rename: ${t.title}`}
                        onClick={() => {
                          const next = window.prompt(
                            "Rename conversation",
                            t.title,
                          );
                          if (next && next.trim()) {
                            props.onRename?.(t.thread_id, next.trim());
                          }
                        }}
                        className="text-muted hover:text-fg opacity-0 group-hover:opacity-100 flex items-center"
                      >
                        <Pencil className="size-3.5" aria-hidden="true" />
                      </button>
                    ) : null}
                    {props.onDelete ? (
                      <button
                        type="button"
                        data-testid={`thread-delete-${t.thread_id}`}
                        aria-label={`Delete: ${t.title}`}
                        onClick={() => props.onDelete?.(t.thread_id)}
                        className="text-muted hover:text-danger opacity-0 group-hover:opacity-100 flex items-center"
                      >
                        <X className="size-3.5" aria-hidden="true" />
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ))
      )}
    </nav>
  );
}
