/**
 * AppNav — the global-navigation control (FR-B1/B5).
 *
 * Presentational only (F-R1): it takes the current `surface` + `pathname` and
 * renders the nav items the pure `nav_model` returns for that surface. The
 * desktop/iPad shape is a sidebar (Home / Practice / Coach / Progress); iPhone
 * is a 3-tab bottom bar (Home / Practice / Progress — Coach is contextual, §8.1).
 *
 * FR-B5 (no dead controls): an enabled item is a real <Link href>; a coming-soon
 * item (Screens 6/7 until the second ADR-0006 amendment) renders as a DISABLED
 * <span> — never an anchor with a live destination. State rides `data-*` (§13).
 */

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  navItemsForSurface,
  activeScreenId,
  type Surface,
} from "./nav_model";

export function AppNav(props: {
  surface: Surface;
  pathname: string;
}): React.JSX.Element {
  const { surface, pathname } = props;
  const items = navItemsForSurface(surface);
  const active = activeScreenId(pathname);
  const isTabBar = surface === "iphone";

  return (
    <nav
      aria-label="Primary"
      data-surface={surface}
      className={cn(
        isTabBar
          ? "flex items-stretch justify-around border-t border-border bg-surface"
          : "flex flex-col gap-1 p-3",
      )}
    >
      {items.map((item) => {
        const isActive = active === item.screenId;
        const shared =
          "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium " +
          "data-[active=true]:bg-selected data-[active=true]:text-fg";

        if (item.disabled) {
          // Coming soon: a legible, non-interactive control (FR-B5) — not a link.
          return (
            <span
              key={item.screenId}
              data-screen={item.screenId}
              data-coming-soon="true"
              aria-disabled="true"
              title="Coming soon"
              className={cn(shared, "cursor-not-allowed text-muted opacity-60")}
            >
              {item.label}
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
            className={cn(shared, "text-muted hover:text-fg")}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
