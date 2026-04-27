import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost";
  size?: "sm" | "md";
  asChild?: boolean;
}

function buttonClasses(
  variant: "default" | "outline" | "ghost" = "default",
  size: "sm" | "md" = "md",
  className?: string,
): string {
  return cn(
    "inline-flex items-center justify-center font-semibold transition-opacity",
    "rounded-md disabled:cursor-not-allowed disabled:opacity-60 no-underline",
    variant === "default" && "bg-accent text-white border-0",
    variant === "outline" && "bg-transparent text-fg border border-border",
    variant === "ghost" && "bg-transparent text-fg border-0",
    size === "sm" && "px-2.5 py-1 text-sm rounded-sm",
    size === "md" && "px-4 py-2 text-base",
    className,
  );
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", asChild, ...props }, ref) => {
    if (asChild && React.isValidElement(props.children)) {
      return React.cloneElement(props.children as React.ReactElement<Record<string, unknown>>, {
        className: buttonClasses(variant, size, className),
        ref,
      });
    }
    return (
      <button
        ref={ref}
        className={buttonClasses(variant, size, className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
