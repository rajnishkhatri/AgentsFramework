"use client";
/**
 * Client wrapper that owns the "selected frame" state.
 *
 * Rule B1 — `'use client'` is justified: the only stateful UI on this route is
 * the timeline-bar selection, which the detail panel reads to render its body.
 * Everything else on the route is a Server Component.
 */
import { useState } from "react";
import { Timeline } from "./Timeline";
import { EventDetailPanel } from "./EventDetailPanel";
import type { TimelineFrame } from "@/lib/translators/event_to_timeline";

export interface TimelineWithDetailProps {
  frames: readonly TimelineFrame[];
}

export function TimelineWithDetail({ frames }: TimelineWithDetailProps) {
  const [selectedId, setSelectedId] = useState<string | null>(
    frames[0]?.id ?? null,
  );
  const selected = frames.find((f) => f.id === selectedId) ?? null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_22rem]">
      <Timeline
        frames={frames}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      <EventDetailPanel frame={selected} />
    </div>
  );
}
