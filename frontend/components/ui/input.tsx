/**
 * Input — shadcn primitive (P1). §2.6: hairline border, surface focus,
 * radius-md. Used by the sidebar search; the Composer keeps its own
 * autosize textarea but adopts the same token vocabulary.
 */
import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type, ...props }, ref) => {
  return (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-border bg-transparent px-3 py-1",
        "text-base text-fg placeholder:text-muted",
        "transition-colors focus:outline-none focus:border-accent",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
});
Input.displayName = "Input";
