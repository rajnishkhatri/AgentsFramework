/**
 * AppNav — the global-navigation control (FR-B1/B5 + wide-layout B1/B3).
 *
 * Presentational only (F-R1): it takes the current `surface` + `pathname` and
 * renders the nav items the pure `nav_model` returns for that surface. The
 * desktop/iPad shape is a sidebar (Home / Practice / Coach / Skill / Progress);
 * iPhone is a 4-tab bottom bar. Collapsed desktop/iPad = 64px icon rail (ADR-0035).
 *
 * FR-B5 (no dead controls): an enabled item is a real <Link href>; a coming-soon
 * item renders as a DISABLED <span> — never an anchor with a live destination.
 * State rides `data-*` (§13).
 *
 * FR-6: ThemeToggle is always the last rail item (collapsed and expanded).
 * Sign out sits above it so every /learn screen can clear the WorkOS session
 * and re-auth to exercise cross-session resume (FR-B1).
 */

"use client";

import * as React from "react";
import Link from "next/link";
import {
  BookOpen,
  ChartColumnIncreasing,
  ClipboardList,
  GraduationCap,
  Home,
  MessagesSquare,
  type LucideIcon,
} from "lucide-react";
import { ThemeToggle } from "@/components/chat/ThemeToggle";
import { SignOutLink } from "@/components/shell/SignOutLink";
import { cn } from "@/lib/utils";
import {
  navItemsForSurface,
  activeScreenId,
  type Surface,
  type ScreenId,
} from "./nav_model";

/** Lucide icons for the rail — distinct glyphs (letter fallback made two "P"s). */
const RAIL_ICONS: Readonly<Record<ScreenId, LucideIcon>> = {
  dashboard: Home,
  quiz: BookOpen,
  feedback: BookOpen,
  coach: MessagesSquare,
  summary: ChartColumnIncreasing,
  test: BookOpen,
  skill: GraduationCap,
  progress: ChartColumnIncreasing,
  exam: ClipboardList,
};

/** Locked §2 visual: 38×38 circular glyph; hit target is the full rail row (≥44px). */
const RAIL_GLYPH =
  "flex size-[38px] items-center justify-center rounded-full";

export function AppNav(props: {
  surface: Surface;
  pathname: string;
  /** Desktop/iPad only — ignored for iPhone tab bar. */
  collapsed?: boolean;
  /** Desktop/iPad: render ThemeToggle as last rail item (FR-6). */
  showThemeToggle?: boolean;
  /** Desktop/iPad: Sign out above ThemeToggle (cross-session resume testing). */
  showSignOut?: boolean;
}): React.JSX.Element {
  const {
    surface,
    pathname,
    collapsed = false,
    showThemeToggle = false,
    showSignOut = false,
  } = props;
  const items = navItemsForSurface(surface);
  const active = activeScreenId(pathname);
  const isTabBar = surface === "iphone";
  const isRail = !isTabBar && collapsed;

  return (
    <nav
      aria-label="Primary"
      data-surface={surface}
      data-collapsed={isRail ? "true" : "false"}
      className={cn(
        isTabBar
          ? "flex items-stretch justify-around border-t border-border bg-surface"
          : isRail
            ? "flex h-full flex-col items-stretch gap-1 px-1 py-2"
            : "flex flex-col gap-1 p-3",
      )}
    >
      {items.map((item) => {
        const isActive = active === item.screenId;
        const Icon = RAIL_ICONS[item.screenId];
        const shared = cn(
          "flex items-center text-sm font-medium",
          "data-[active=true]:bg-selected data-[active=true]:text-fg",
          isTabBar && "min-h-11 justify-center gap-2 rounded-md px-3 py-2",
          // Full-rail ≥44px hit target; visual glyph stays 38×38 inside.
          isRail &&
            "min-h-11 w-full justify-center rounded-md hover:bg-selected hover:text-fg",
          !isTabBar && !isRail && "gap-2 rounded-md px-3 py-2",
        );

        const railGlyph = (
          <span
            aria-hidden="true"
            className={cn(
              RAIL_GLYPH,
              isActive && "bg-selected text-fg",
              !isActive && "text-muted",
            )}
          >
            <Icon className="size-4" strokeWidth={1.75} />
          </span>
        );

        if (item.disabled) {
          return (
            <span
              key={item.screenId}
              data-screen={item.screenId}
              data-coming-soon="true"
              aria-disabled="true"
              title="Coming soon"
              className={cn(shared, "cursor-not-allowed text-muted opacity-60")}
            >
              {isRail ? railGlyph : item.label}
            </span>
          );
        }

        return (
          <Link
            key={item.screenId}
            href={item.href}
            data-screen={item.screenId}
            data-active={isActive ? "true" : "false"}
            aria-current={isActive ? "page" : undefined}
            aria-label={isRail ? item.label : undefined}
            title={isRail ? item.label : undefined}
            className={cn(shared, !isRail && "text-muted hover:text-fg")}
          >
            {isRail ? railGlyph : item.label}
          </Link>
        );
      })}
      {(showSignOut || showThemeToggle) && !isTabBar ? (
        <>
          <div
            role="separator"
            aria-hidden="true"
            className={cn(
              "mt-auto border-t border-border",
              isRail ? "mx-auto my-3 w-6" : "my-3",
            )}
          />
          {showSignOut ? (
            <div
              data-testid="nav-sign-out"
              className={cn(
                isRail && "flex justify-center",
                !isRail && "flex items-center px-1",
              )}
            >
              <SignOutLink iconOnly={isRail} />
            </div>
          ) : null}
          {showThemeToggle ? (
            <div
              data-testid="nav-theme-toggle"
              className={cn(
                isRail && "flex justify-center pb-1",
                !isRail && "flex items-center px-1",
              )}
            >
              <ThemeToggle />
            </div>
          ) : null}
        </>
      ) : null}
    </nav>
  );
}
