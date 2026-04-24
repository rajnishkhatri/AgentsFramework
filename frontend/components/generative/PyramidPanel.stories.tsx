/**
 * Storybook stories for PyramidPanel (FD6.STORY, S3.8.4).
 *
 * Covers: flat root, nested tree, deep hierarchy.
 * Feature-flagged behind `pyramid_panel` in production; stories render
 * unconditionally for visual review.
 */

import * as React from "react";
import { PyramidPanel, type PyramidNode } from "./PyramidPanel";

export default {
  title: "generative/PyramidPanel",
  component: PyramidPanel,
};

const FLAT: PyramidNode = {
  title: "Root Observation",
  summary: "The system is healthy across all monitored endpoints.",
};

const NESTED: PyramidNode = {
  title: "Performance Analysis",
  summary: "Three bottlenecks identified.",
  children: [
    {
      title: "Database query latency",
      summary: "p95 at 340ms, above 200ms budget.",
    },
    {
      title: "SSE heartbeat gap",
      summary: "15s send / 30s detect thresholds OK.",
    },
    {
      title: "Cold start",
      summary: "Cloud Run min=0 introduces ~120ms overhead.",
    },
  ],
};

const DEEP: PyramidNode = {
  title: "Architecture Review",
  children: [
    {
      title: "Layering",
      children: [
        { title: "Wire purity", summary: "All 4 wire modules pass W1." },
        {
          title: "SDK isolation",
          summary: "CopilotKit confined to adapters/.",
          children: [
            { title: "ui_runtime adapter", summary: "F-R2 compliant." },
            { title: "tool_renderer adapter", summary: "F-R2 compliant." },
          ],
        },
      ],
    },
    {
      title: "Security",
      summary: "CSP strict, no unsafe-inline.",
    },
  ],
};

export function FlatRoot(): React.JSX.Element {
  return <PyramidPanel root={FLAT} />;
}

export function NestedTree(): React.JSX.Element {
  return <PyramidPanel root={NESTED} />;
}

export function DeepHierarchy(): React.JSX.Element {
  return <PyramidPanel root={DEEP} />;
}
