/**
 * useSurface — the device-surface seam for the shell (FR-J1/J2/J3).
 *
 * The width→surface mapping is pure domain logic (F-R1) and lives in
 * `surfaceForWidth`, exercised in node with no React. `useSurface` is the thin
 * client hook that reads the live viewport width and re-derives the surface on
 * resize — the only React-aware part, kept tiny so the boundaries stay testable.
 *
 * Breakpoints (FR-J): iPhone ≤480 (covers the ≤393pt phone), iPad 481..1024
 * (11" landscape), desktop >1024.
 */

"use client";

import * as React from "react";
import type { Surface } from "./nav_model";

/** Inclusive phone ceiling; ≤ this is iPhone (FR-J2 lists 393pt as an iPhone width). */
export const PHONE_MAX_WIDTH = 480;
/** Inclusive iPad ceiling; ≤ this (and above the phone ceiling) is iPad (FR-J3 11" landscape). */
export const IPAD_MAX_WIDTH = 1024;

/** Pure: classify a viewport width into a device surface. Total over all widths. */
export function surfaceForWidth(width: number): Surface {
  if (width <= PHONE_MAX_WIDTH) return "iphone";
  if (width <= IPAD_MAX_WIDTH) return "ipad";
  return "desktop";
}

/**
 * Live device surface for the current viewport. SSR-safe: before the first
 * client measurement it returns `fallback` (default "desktop", the sidebar
 * shell) so the server render is deterministic; the effect corrects it on mount
 * and on every resize.
 */
export function useSurface(fallback: Surface = "desktop"): Surface {
  const [surface, setSurface] = React.useState<Surface>(fallback);

  React.useEffect(() => {
    // Subscribing to the live viewport is a genuine external-system sync — one
    // of the sanctioned useEffect cases (§14): the resize event is not React-aware.
    const measure = () => setSurface(surfaceForWidth(window.innerWidth));
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  return surface;
}
