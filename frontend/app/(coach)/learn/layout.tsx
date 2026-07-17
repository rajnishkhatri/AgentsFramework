// B1: 'use client' required — this shell reads the live device surface
// (useSurface → window.innerWidth/resize) and the current pathname
// (usePathname) to decide the chrome (sidebar vs 3-tab vs focus mode). Those are
// client-only signals; the screens it wraps stay presentational. It also mounts
// the EngineProvider so screen hooks can read the engine bag via useEngine() (C3).
"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { EngineProvider } from "@/app/engine-provider";
import { ThemeToggle } from "@/components/chat/ThemeToggle";
import { AppNav } from "@/components/shell/AppNav";
import { FocusModeChrome } from "@/components/shell/FocusModeChrome";
import {
  getShellLayoutSnapshot,
  subscribeShellLayout,
  toggleSidebarCollapsed,
} from "@/components/shell/shell_layout_store";
import {
  RAIL_COLLAPSED,
  RAIL_EXPANDED,
  useIsWide,
  useSurface,
} from "@/components/shell/use_surface";
import {
  activeScreenId,
  screen,
  COACH_BASE,
  type ScreenId,
} from "@/components/shell/nav_model";
import { cn } from "@/lib/utils";

/**
 * The (coach) route-group shell (FR-B1/B2 + ADR-0035 wide-layout Direction 2b).
 *   - iPhone + focus screen: FocusModeChrome (tab bar hidden).
 *   - iPhone + non-focus: bottom tab bar.
 *   - desktop / iPad: collapsible sidebar (64px icon rail) + height-locked shell.
 *
 * Q-C3: content screens always mount collapsed (layout-local); Home/Progress
 * use shell_layout_store ↔ localStorage.
 */

/** Content-heavy screens — always-collapsed rail; toggle is in-memory only. */
const CONTENT_SCREENS: ReadonlySet<ScreenId> = new Set([
  "quiz",
  "coach",
  "skill",
  "test",
]);

export default function CoachLayout(props: {
  children: React.ReactNode;
}): React.JSX.Element {
  const pathname = usePathname() ?? COACH_BASE;
  const surface = useSurface();

  const activeId = activeScreenId(pathname);
  const onFocusScreen = activeId != null && screen(activeId).isFocusScreen;

  return (
    <EngineProvider>
      <CoachShell
        surface={surface}
        pathname={pathname}
        onFocusScreen={onFocusScreen}
        activeId={activeId}
      >
        {props.children}
      </CoachShell>
    </EngineProvider>
  );
}

function useShellLayout() {
  return React.useSyncExternalStore(
    subscribeShellLayout,
    getShellLayoutSnapshot,
    getShellLayoutSnapshot,
  );
}

/** Screens that keep page-level scroll under the h-dvh shell (Home / Progress). */
function needsPageScroll(activeId: ScreenId | null): boolean {
  return activeId === "dashboard" || activeId === "progress";
}

function isContentScreen(activeId: ScreenId | null): boolean {
  return activeId != null && CONTENT_SCREENS.has(activeId);
}

function CoachShell(props: {
  surface: ReturnType<typeof useSurface>;
  pathname: string;
  onFocusScreen: boolean;
  activeId: ScreenId | null;
  children: React.ReactNode;
}): React.JSX.Element {
  const { surface, pathname, onFocusScreen, activeId, children } = props;
  const persisted = useShellLayout();
  const isWide = useIsWide();
  const content = isContentScreen(activeId);

  // Q-C3 / FR-9: content screens always init collapsed; mid-session expand is
  // layout-local only (no LS write). Remount / navigate resets to collapsed.
  const [contentCollapsed, setContentCollapsed] = React.useState(true);
  React.useEffect(() => {
    if (content) setContentCollapsed(true);
  }, [content, activeId]);

  const collapsed = content ? contentCollapsed : persisted.sidebarCollapsed;

  const toggleCollapse = React.useCallback(() => {
    if (content) {
      setContentCollapsed((c) => !c);
      return;
    }
    toggleSidebarCollapsed();
  }, [content]);

  // FR-8 / B1: `[` toggles sidebar (ignore when typing).
  React.useEffect(() => {
    if (!isWide) return;
    function onKey(e: KeyboardEvent): void {
      if (e.key !== "[") return;
      const t = e.target;
      if (
        t instanceof HTMLElement &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      toggleCollapse();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isWide, toggleCollapse]);

  if (surface === "iphone" && onFocusScreen && activeId != null) {
    return (
      <FocusModeChrome screenId={activeId} returnTo={COACH_BASE}>
        {children}
      </FocusModeChrome>
    );
  }

  if (surface === "iphone") {
    return (
      <div className="flex min-h-dvh flex-col">
        <header className="flex items-center justify-end border-b border-border px-2 py-1">
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
        <AppNav surface={surface} pathname={pathname} />
      </div>
    );
  }

  const sidebarPx = collapsed ? RAIL_COLLAPSED : RAIL_EXPANDED;
  const pageScroll = needsPageScroll(activeId);

  return (
    <div
      data-testid="coach-shell"
      data-sidebar={collapsed ? "collapsed" : "expanded"}
      className="flex h-dvh overflow-hidden"
    >
      <aside
        data-testid="coach-sidebar"
        style={{
          width: sidebarPx,
          transition: "width 180ms cubic-bezier(0.4, 0, 0.2, 1)",
        }}
        className={cn(
          // z-20 + bg keeps the rail above main paint and always tappable.
          "relative z-20 flex shrink-0 flex-col border-r border-border bg-surface",
          "motion-reduce:!transition-none",
        )}
      >
        <div
          className={cn(
            "flex shrink-0 items-center gap-1 px-2 pt-2",
            collapsed ? "flex-col" : "justify-between",
          )}
        >
          <button
            type="button"
            data-testid="sidebar-toggle"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            onClick={toggleCollapse}
            className="flex size-10 items-center justify-center rounded-md text-muted hover:bg-selected hover:text-fg"
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
        {/* No overflow scroll trap around Links — ThemeToggle sticks via mt-auto. */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <AppNav
            surface={surface}
            pathname={pathname}
            collapsed={collapsed}
            showThemeToggle
          />
        </div>
      </aside>
      <main
        data-testid="coach-main"
        className={cn(
          "mx-auto flex w-full max-w-[1180px] min-h-0 min-w-0 flex-1 flex-col px-6 py-6",
          pageScroll ? "overflow-y-auto" : "overflow-hidden",
        )}
      >
        {children}
      </main>
    </div>
  );
}
