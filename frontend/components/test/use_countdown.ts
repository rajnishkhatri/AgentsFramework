/**
 * use_countdown — the live section countdown for Test Mode.
 *
 * A §14-sanctioned `useEffect` around the browser clock (the one external,
 * non-React signal Test Mode needs). It ticks once per second from a fixed
 * `durationMs`, exposes `remainingMs` + `expired`, and fires `onExpire` EXACTLY
 * ONCE when the clock reaches zero — the page turns that into a `submit_section`
 * dispatch (auto-submit). All derivable/formatting logic lives in the pure
 * `format_clock.ts`; this hook only owns the tick.
 *
 * Determinism for e2e: the duration is a prop, so a spec can inject a tiny value
 * (via the page's `?dur=` non-prod query) and watch auto-submit fire in ms, not
 * 35 minutes. The end time is anchored to `Date.now()` at mount (not a running
 * decrement), so a throttled tab still expires at the right wall-clock moment.
 *
 * Import rule: React only (no SDK). 'use client' is implied by the caller (a
 * client page); a hook file needs no directive itself.
 */

import * as React from "react";

export interface UseCountdownResult {
  readonly remainingMs: number;
  readonly expired: boolean;
}

export function useCountdown(
  durationMs: number,
  onExpire?: () => void,
): UseCountdownResult {
  // Anchor the deadline once, at mount, from the wall clock — so remaining time
  // is (deadline - now), robust to dropped/late ticks in a backgrounded tab.
  const deadlineRef = React.useRef<number>(Date.now() + durationMs);
  const firedRef = React.useRef<boolean>(false);
  const [remainingMs, setRemainingMs] = React.useState<number>(durationMs);

  // Keep the latest onExpire without re-arming the interval each render.
  const onExpireRef = React.useRef(onExpire);
  React.useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  React.useEffect(() => {
    // Re-anchor if the duration prop changes (e.g. a new section).
    deadlineRef.current = Date.now() + durationMs;
    firedRef.current = false;
    setRemainingMs(durationMs);

    const tick = (): void => {
      const left = Math.max(0, deadlineRef.current - Date.now());
      setRemainingMs(left);
      if (left <= 0 && !firedRef.current) {
        firedRef.current = true;
        onExpireRef.current?.();
      }
    };

    tick(); // immediate, so an already-elapsed duration expires without a 1s wait
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [durationMs]);

  return { remainingMs, expired: remainingMs <= 0 };
}
