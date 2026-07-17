/**
 * CoachDrawer — overlay chrome for coachMode === "drawer" (Q-C4 / FR-2/8/17).
 *
 * Hosts the same CoachPanel Zone stack. Not Sheet chrome (no edge-tab).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getFocusable(root: HTMLElement): HTMLElement[] {
  const nodes = root.querySelectorAll<HTMLElement>(
    'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])',
  );
  return [...nodes].filter(
    (el) => !el.hasAttribute("disabled") && el.tabIndex !== -1,
  );
}

export function CoachDrawer(props: {
  open: boolean;
  onClose: () => void;
  /** Element that receives focus restore on close (pill). */
  restoreFocusRef?: React.RefObject<HTMLElement | null>;
  children: React.ReactNode;
}): React.JSX.Element | null {
  const { open, onClose, restoreFocusRef, children } = props;
  const panelRef = React.useRef<HTMLDivElement>(null);
  const closeBtnRef = React.useRef<HTMLButtonElement>(null);
  const [visible, setVisible] = React.useState(open);

  React.useEffect(() => {
    if (open) {
      setVisible(true);
      return;
    }
    const delay = prefersReducedMotion() ? 0 : 220;
    const t = window.setTimeout(() => {
      setVisible(false);
      restoreFocusRef?.current?.focus();
    }, delay);
    return () => window.clearTimeout(t);
  }, [open, restoreFocusRef]);

  React.useEffect(() => {
    if (!open) return;
    const id = window.requestAnimationFrame(() => {
      closeBtnRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(id);
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent): void {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || panelRef.current == null) return;
      const focusable = getFocusable(panelRef.current);
      if (focusable.length === 0) return;
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first || !panelRef.current.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last || !panelRef.current.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!visible && !open) return null;

  const instant = prefersReducedMotion();

  // absolute (not fixed): host is <main>'s quiz column. fixed inset-0 covered
  // the left AppNav rail so Home / Progress taps hit the scrim (FR-B1).
  return (
    <div data-testid="coach-drawer-root" className="absolute inset-0 z-50">
      <button
        type="button"
        data-testid="coach-drawer-scrim"
        aria-label="Close coach"
        onClick={onClose}
        className={cn(
          "absolute inset-0 bg-black/32",
          !instant && "transition-opacity duration-[180ms]",
        )}
        style={{ opacity: open ? 1 : 0 }}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Coach"
        data-testid="coach-drawer"
        className={cn(
          "absolute inset-y-0 right-0 flex flex-col bg-surface shadow-lg",
          !instant &&
            "transition-transform duration-[220ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
          "motion-reduce:!transition-none",
        )}
        style={{
          width: "min(430px, 100%)",
          transform: open ? "translateX(0)" : "translateX(100%)",
        }}
      >
        <div className="flex shrink-0 justify-end border-b border-border p-2">
          <button
            ref={closeBtnRef}
            type="button"
            data-testid="coach-drawer-close"
            aria-label="Close coach"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-md text-muted hover:bg-selected hover:text-fg"
          >
            ✕
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}
