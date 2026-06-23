/**
 * MessageActions — per-assistant-message actions (copy / regenerate), §6.
 *
 * Two input modalities, one set of actions:
 *  - **Desktop (pointer-fine):** an inline hover toolbar revealed on
 *    `group-hover` of the message, gated behind `@media (hover: hover)` so it
 *    never sticks visible on touch (§4c hover-gating).
 *  - **Touch (pointer-coarse):** a long-press anywhere on the message opens a
 *    DropdownMenu with the same actions. The long-press detection lives in the
 *    parent (it owns the message element); this component renders the menu and
 *    exposes the handlers to spread via `useLongPress`.
 *
 * Copy mirrors the CodeBlock idiom (`navigator.clipboard.writeText` + a
 * transient "Copied" flag); failures degrade silently (no toast dependency).
 * 44pt hit areas on every control (§4c). Reduced-motion safe (menu inherits
 * the primitive's `motion-reduce:animate-none`).
 */

"use client";

import * as React from "react";
import { Copy, Check, RotateCcw } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/** ms a pointer must be held (without moving) to count as a long-press. */
export const LONG_PRESS_MS = 500;
/** px of pointer movement that cancels an in-flight long-press. */
const MOVE_TOLERANCE_PX = 10;

/**
 * Long-press detector for touch. Returns pointer handlers to spread on the
 * pressable element; fires `onLongPress` after LONG_PRESS_MS of a stationary
 * hold. Pointer-fine devices are ignored (they use the hover toolbar).
 */
export function useLongPress(onLongPress: () => void): {
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: () => void;
  onPointerCancel: () => void;
} {
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const origin = React.useRef<{ x: number; y: number } | null>(null);

  const clear = React.useCallback((): void => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    origin.current = null;
  }, []);

  const onPointerDown = React.useCallback(
    (e: React.PointerEvent): void => {
      if (e.pointerType !== "touch" && e.pointerType !== "pen") return;
      origin.current = { x: e.clientX, y: e.clientY };
      timer.current = setTimeout(() => {
        onLongPress();
        clear();
      }, LONG_PRESS_MS);
    },
    [onLongPress, clear],
  );

  const onPointerMove = React.useCallback(
    (e: React.PointerEvent): void => {
      const o = origin.current;
      if (!o) return;
      if (
        Math.abs(e.clientX - o.x) > MOVE_TOLERANCE_PX ||
        Math.abs(e.clientY - o.y) > MOVE_TOLERANCE_PX
      ) {
        clear();
      }
    },
    [clear],
  );

  return { onPointerDown, onPointerMove, onPointerUp: clear, onPointerCancel: clear };
}

export function MessageActions(props: {
  /** The settled answer text to copy. */
  text: string;
  /** Re-run this turn from the user prompt. Omit/disable while a run is live. */
  onRegenerate?: () => void;
  /** Controlled long-press menu (touch). Parent owns open state. */
  menuOpen: boolean;
  onMenuOpenChange: (open: boolean) => void;
}): React.JSX.Element {
  const [copied, setCopied] = React.useState(false);

  const copy = React.useCallback(async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(props.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked (insecure context / permission) — fail silent.
    }
  }, [props.text]);

  return (
    <>
      {/* Desktop hover toolbar — hidden until the message is hovered, and only
         on pointer-fine devices. Opacity (not display) so it can fade. */}
      <div
        data-testid="message-actions-toolbar"
        className={cn(
          "flex items-center gap-1 opacity-0 transition-opacity",
          "[@media(hover:hover)]:group-hover:opacity-100",
          "[@media(hover:none)]:hidden",
          "motion-reduce:transition-none",
        )}
      >
        <button
          type="button"
          onClick={() => void copy()}
          aria-label={copied ? "Copied" : "Copy message"}
          data-testid="copy-message"
          className={cn(
            "flex size-11 items-center justify-center rounded-full",
            "text-muted transition-colors cursor-pointer hover:bg-selected hover:text-fg",
          )}
        >
          {copied ? (
            <Check className="size-4" aria-hidden="true" />
          ) : (
            <Copy className="size-4" aria-hidden="true" />
          )}
        </button>
        {props.onRegenerate ? (
          <button
            type="button"
            onClick={props.onRegenerate}
            aria-label="Regenerate response"
            data-testid="regenerate-message"
            className={cn(
              "flex size-11 items-center justify-center rounded-full",
              "text-muted transition-colors cursor-pointer hover:bg-selected hover:text-fg",
            )}
          >
            <RotateCcw className="size-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {/* Touch long-press menu — opened by the parent's long-press handlers.
         A zero-size trigger anchors the menu to the message bottom. */}
      <DropdownMenu open={props.menuOpen} onOpenChange={props.onMenuOpenChange}>
        <DropdownMenuTrigger asChild>
          <span aria-hidden="true" className="sr-only" />
        </DropdownMenuTrigger>
        <DropdownMenuContent data-testid="message-actions-menu" align="start">
          <DropdownMenuItem
            onSelect={() => void copy()}
            data-testid="copy-message-touch"
          >
            <Copy className="size-4" aria-hidden="true" />
            Copy
          </DropdownMenuItem>
          {props.onRegenerate ? (
            <DropdownMenuItem
              onSelect={props.onRegenerate}
              data-testid="regenerate-message-touch"
            >
              <RotateCcw className="size-4" aria-hidden="true" />
              Regenerate
            </DropdownMenuItem>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}
