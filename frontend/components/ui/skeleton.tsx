/**
 * Skeleton — shadcn primitive (P1). Streaming/loading placeholders (§6).
 * Pulse honors prefers-reduced-motion.
 */
import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>): React.JSX.Element {
  return (
    <div
      className={cn(
        "animate-pulse motion-reduce:animate-none rounded-md bg-selected",
        className,
      )}
      {...props}
    />
  );
}
