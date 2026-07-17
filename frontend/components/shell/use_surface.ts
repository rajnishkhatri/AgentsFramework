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
 *
 * Quiz host decisions use `coachMode` (ADR-0035 / Direction 2b) — not a
 * pin-aware degrade ladder.
 */

"use client";

import * as React from "react";
import type { Surface } from "./nav_model";

/** Inclusive phone ceiling; ≤ this is iPhone (FR-J2 lists 393pt as an iPhone width). */
export const PHONE_MAX_WIDTH = 480;
/** Inclusive iPad ceiling; ≤ this (and above the phone ceiling) is iPad (FR-J3 11" landscape). */
export const IPAD_MAX_WIDTH = 1024;

/**
 * Min content width (px left after the sidebar) for an inline quiz+coach split
 * (ADR-0035 / FR-1/10). Below this → drawer (non-iphone).
 */
export const SPLIT_MIN_CONTENT_WIDTH = 900;
/** Expanded sidebar = Tailwind `w-56` (14rem @ 16px). Locked §1. */
export const RAIL_EXPANDED = 224;
/** Collapsed icon rail width (locked §2 — 64px). */
export const RAIL_COLLAPSED = 64;

/** @deprecated Prefer RAIL_EXPANDED — kept for call-site migration. */
export const SIDEBAR_EXPANDED_PX = RAIL_EXPANDED;
/** @deprecated Prefer RAIL_COLLAPSED — kept for call-site migration. */
export const SIDEBAR_COLLAPSED_PX = RAIL_COLLAPSED;

export type CoachMode = "inline" | "drawer" | "fullscreen";

/**
 * One decision rule for quiz coach chrome (locked §1 / FR-1/10/18).
 * iPhone never hosts inline or drawer; otherwise contentWidth ≥ 900 → inline.
 */
export function coachMode(
  surface: Surface,
  viewportWidth: number,
  sidebarWidth: number,
): CoachMode {
  if (surface === "iphone") return "fullscreen";
  const contentWidth = viewportWidth - sidebarWidth;
  return contentWidth >= SPLIT_MIN_CONTENT_WIDTH ? "inline" : "drawer";
}

/** Pure: classify a viewport width into a device surface. Total over all widths. */
export function surfaceForWidth(width: number): Surface {
  if (width <= PHONE_MAX_WIDTH) return "iphone";
  if (width <= IPAD_MAX_WIDTH) return "ipad";
  return "desktop";
}

/** Wide = desktop or iPad — nav helpers only; quiz uses `coachMode`. */
export function isWideSurface(s: Surface): boolean {
  return s !== "iphone";
}

/** Content width available beside the sidebar (viewport − sidebar). */
export function contentWidthAfterSidebar(
  viewportWidth: number,
  sidebarCollapsed: boolean,
): number {
  const sidebar = sidebarCollapsed ? RAIL_COLLAPSED : RAIL_EXPANDED;
  return viewportWidth - sidebar;
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

/** Live wide predicate for nav chrome gating. */
export function useIsWide(): boolean {
  return isWideSurface(useSurface());
}
