/**
 * Sheet — Radix Dialog with edge-anchored content (P1). The mobile
 * drawer (thread list, §5) and bottom sheet (reasoning/tools panel).
 * §2.6 surface + hairline; safe-area padding is applied at the call
 * site (§4a). Honors prefers-reduced-motion.
 */
"use client";
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { DialogOverlay, DialogPortal } from "./dialog";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

const sheetVariants = cva(
  cn(
    "fixed z-50 bg-bg border-border shadow-lg transition ease-in-out",
    "data-[state=open]:animate-in data-[state=closed]:animate-out motion-reduce:animate-none",
  ),
  {
    variants: {
      side: {
        left: "inset-y-0 left-0 h-full w-3/4 max-w-sm border-r data-[state=open]:slide-in-from-left data-[state=closed]:slide-out-to-left",
        right: "inset-y-0 right-0 h-full w-3/4 max-w-sm border-l data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right",
        bottom: "inset-x-0 bottom-0 max-h-[85%] rounded-t-lg border-t data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
        top: "inset-x-0 top-0 rounded-b-lg border-b data-[state=open]:slide-in-from-top data-[state=closed]:slide-out-to-top",
      },
    },
    defaultVariants: { side: "left" },
  },
);

export interface SheetContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>,
    VariantProps<typeof sheetVariants> {}

export const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  SheetContentProps
>(({ side = "left", className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(sheetVariants({ side }), className)}
      {...props}
    >
      {children}
      <DialogPrimitive.Close
        className={cn(
          "absolute right-4 top-4 rounded-sm text-muted transition-colors hover:text-fg",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        )}
      >
        <X className="size-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
SheetContent.displayName = "SheetContent";

export const SheetTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold text-fg", className)}
    {...props}
  />
));
SheetTitle.displayName = DialogPrimitive.Title.displayName;
