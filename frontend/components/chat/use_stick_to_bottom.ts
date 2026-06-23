/**
 * useStickToBottom — tracks whether a scroll container is pinned to (near) its
 * bottom edge, so the chat surface can (a) auto-scroll new turns into view ONLY
 * while the user is already at the bottom, and (b) reveal a "scroll to latest"
 * affordance when they've scrolled up to read history (P4 §6).
 *
 * The unconditional `scrollIntoView` it replaces yanked the viewport down on
 * every token while a user was reading earlier messages — the stickiness gate
 * fixes that: stream freely, but don't move someone who scrolled away.
 *
 * Pure DOM, no deps. `THRESHOLD_PX` of slack absorbs sub-pixel rounding and the
 * last line's leading so "basically at the bottom" still counts as stuck.
 * SSR-safe: `isAtBottom` defaults true (a fresh, empty conversation is at the
 * bottom) and the listener is wired in an effect after mount.
 */

"use client";

import * as React from "react";

/** Distance from the bottom (px) still treated as "stuck to bottom". */
export const THRESHOLD_PX = 80;

/** True when the element is scrolled to within THRESHOLD_PX of its bottom. */
export function isNearBottom(
  el: Pick<HTMLElement, "scrollHeight" | "scrollTop" | "clientHeight">,
  threshold: number = THRESHOLD_PX,
): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;
}

export interface StickToBottom {
  /** Attach to the scroll container (`overflow-y-auto`). */
  readonly ref: React.RefObject<HTMLDivElement | null>;
  /** Whether the container is currently pinned near its bottom. */
  readonly isAtBottom: boolean;
  /** Scroll the container to the bottom. */
  readonly scrollToBottom: (behavior?: ScrollBehavior) => void;
}

export function useStickToBottom(): StickToBottom {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const [isAtBottom, setIsAtBottom] = React.useState(true);

  const scrollToBottom = React.useCallback(
    (behavior: ScrollBehavior = "smooth"): void => {
      const el = ref.current;
      if (!el) return;
      // `scrollTo` is unimplemented in jsdom — guard so tests (and any exotic
      // host) don't throw; fall back to assigning scrollTop.
      if (typeof el.scrollTo === "function") {
        el.scrollTo({ top: el.scrollHeight, behavior });
      } else {
        el.scrollTop = el.scrollHeight;
      }
    },
    [],
  );

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = (): void => setIsAtBottom(isNearBottom(el));
    // Seed from the current position, then track passively.
    onScroll();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return { ref, isAtBottom, scrollToBottom };
}
