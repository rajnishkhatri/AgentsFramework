/**
 * Badge — shadcn/cva primitive (P1). §2.6: rationed accent; the eval
 * badge / status chips. radius-sm, surface or accent-tint fills.
 */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-surface text-muted border border-border",
        accent: "bg-accent-light text-accent border-0",
        outline: "bg-transparent text-fg border border-border",
        // Status tints (frozen): success green / danger red, as a soft
        // token-mix fill so the chip reads colored but not loud.
        success:
          "border-0 text-success [background:color-mix(in_oklab,var(--color-success)_18%,transparent)]",
        danger:
          "border-0 text-danger [background:color-mix(in_oklab,var(--color-danger)_18%,transparent)]",
        warning:
          "border-0 text-warning [background:color-mix(in_oklab,var(--color-warning)_18%,transparent)]",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  asChild?: boolean;
}

export function Badge({ className, variant, asChild = false, ...props }: BadgeProps): React.JSX.Element {
  const Comp = asChild ? Slot : "span";
  return <Comp className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
