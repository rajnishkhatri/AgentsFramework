// Justification (B1, U2): every thread row attaches an `onClick` handler
// that calls the parent's `onSelect` callback (event handlers are not
// serialisable from RSC -> client). The component itself remains tiny and
// renders no other client state, so the leaf-client boundary stays narrow
// (parent pages can still be RSC and pass server-fetched threads in).
"use client";

/**
 * Thread sidebar (S3.8.6, F1).
 *
 * Leaf "use client" boundary -- the parent page (RSC) fetches threads
 * through the ThreadStore port and passes them in as a serialisable prop.
 * Filtering / search is in-memory over the loaded page; cursor-based
 * pagination is owned by the page's data fetcher.
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { ThreadState } from "@/lib/wire/agent_protocol";

export function ThreadSidebar(props: {
  threads: ReadonlyArray<ThreadState>;
  activeThreadId?: string;
  onSelect?: (id: string) => void;
}): React.JSX.Element {
  return (
    <nav
      aria-label="Threads"
      className="grid gap-1 p-3 border-r border-border-light bg-bg min-w-64"
    >
      {props.threads.map((t) => (
        <a
          key={t.thread_id}
          href={`/threads/${t.thread_id}`}
          aria-current={
            props.activeThreadId === t.thread_id ? "page" : undefined
          }
          onClick={(e) => {
            if (props.onSelect) {
              e.preventDefault();
              props.onSelect(t.thread_id);
            }
          }}
          className={cn(
            "block px-3 py-2 rounded-sm text-fg no-underline",
            props.activeThreadId === t.thread_id
              ? "bg-accent-light"
              : "bg-transparent",
          )}
        >
          {t.thread_id}
        </a>
      ))}
    </nav>
  );
}
