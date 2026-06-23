/**
 * Card — shadcn primitive (P1). §2.6: surface fill, hairline border,
 * radius-lg soft chrome (the message-card / panel look).
 */
import * as React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Tactile surface treatment (design showcase / frozen v13). `flat` is the
   * plain hairline surface; `etched` recesses the card (inset shadow + bottom
   * highlight); `embossed` raises it (top highlight + soft drop). The shadow
   * recipes live in globals.css (`.surface-etched` / `.surface-embossed`).
   */
  variant?: "flat" | "etched" | "embossed";
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "flat", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-border bg-surface text-fg",
        variant === "etched" && "surface-etched",
        variant === "embossed" && "surface-embossed",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col gap-1 p-4", className)} {...props} />
));
CardHeader.displayName = "CardHeader";

export const CardTitle = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("text-base font-semibold", className)} {...props} />
));
CardTitle.displayName = "CardTitle";

export const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-4 pt-0", className)} {...props} />
));
CardContent.displayName = "CardContent";
