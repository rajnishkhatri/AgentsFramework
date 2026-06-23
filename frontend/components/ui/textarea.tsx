/**
 * Textarea — shadcn primitive (P1). Shares the Composer's autosize idiom
 * (`field-sizing: content`) so the pill composer (§2.6) and any plain
 * textarea read the same. Token-driven border/focus.
 */
import * as React from "react";
import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      ref={ref}
      className={cn(
        "flex w-full rounded-md border border-border bg-transparent px-3 py-2",
        "text-base text-fg placeholder:text-muted",
        "[field-sizing:content] min-h-[2.5rem] max-h-[12rem]",
        "transition-colors focus:outline-none focus:border-accent",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
});
Textarea.displayName = "Textarea";
