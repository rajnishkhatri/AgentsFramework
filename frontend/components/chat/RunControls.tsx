/**
 * Stop / regenerate / edit-and-resend controls (S3.8.7, F3).
 *
 * Pure presentation. The handler callbacks come from the chat page, which
 * routes them into `UIRuntime.{stop,regenerate,editAndResend}` via the
 * adapter context (composition).
 */

// B1: 'use client' required — onClick event handlers are non-serializable
// props that cannot cross the RSC boundary.
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function RunControls(props: {
  isRunning: boolean;
  onStop: () => void;
  onRegenerate: () => void;
  onEditResend: () => void;
}): React.JSX.Element {
  return (
    <div role="toolbar" aria-label="Run controls" className="flex gap-2">
      <Button variant="outline" size="sm" onClick={props.onStop} disabled={!props.isRunning}>
        Stop
      </Button>
      <Button variant="outline" size="sm" onClick={props.onRegenerate}>
        Regenerate
      </Button>
      <Button variant="outline" size="sm" onClick={props.onEditResend}>
        Edit &amp; resend
      </Button>
    </div>
  );
}
