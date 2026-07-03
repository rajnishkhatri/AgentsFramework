/**
 * Toast — sonner wrapper (P1, shadcn-standard). Errors / cancel
 * notifications (§6). Themed to §2.6 tokens; theme follows [data-theme].
 * Mount <Toaster /> once at the shell; call `toast(...)` from anywhere.
 */
"use client";
import * as React from "react";
import { Toaster as Sonner, toast } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

export function Toaster(props: ToasterProps): React.JSX.Element {
  return (
    <Sonner
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast border border-border bg-bg text-fg rounded-lg shadow-lg",
          description: "text-muted",
          actionButton: "bg-accent text-on-accent rounded-md",
          cancelButton: "bg-surface text-muted rounded-md",
          error: "border-border",
        },
      }}
      {...props}
    />
  );
}

export { toast };
