// B1: 'use client' required — this shell reads the live device surface
// (useSurface → window.innerWidth/resize) and the current pathname
// (usePathname) to decide the chrome (sidebar vs 3-tab vs focus mode). Those are
// client-only signals; the screens it wraps stay presentational. It also mounts
// the EngineProvider so screen hooks can read the engine bag via useEngine() (C3).
"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { EngineProvider } from "@/app/engine-provider";
import { AppNav } from "@/components/shell/AppNav";
import { FocusModeChrome } from "@/components/shell/FocusModeChrome";
import { useSurface } from "@/components/shell/use_surface";
import { activeScreenId, screen, COACH_BASE } from "@/components/shell/nav_model";

/**
 * The (coach) route-group shell (FR-B1/B2). Composes the surface-appropriate
 * navigation chrome around the active screen:
 *   - iPhone + focus screen (Quiz/Feedback/Coach/Summary): FocusModeChrome
 *     (tab bar hidden, "✕" close) — FR-B2.
 *   - iPhone + non-focus (Dashboard/Progress): bottom tab bar (AppNav).
 *   - desktop / iPad: persistent sidebar (AppNav) beside the content — FR-B1.
 */
export default function CoachLayout(props: {
  children: React.ReactNode;
}): React.JSX.Element {
  const pathname = usePathname() ?? COACH_BASE;
  const surface = useSurface();

  const activeId = activeScreenId(pathname);
  const onFocusScreen = activeId != null && screen(activeId).isFocusScreen;

  return (
    <EngineProvider>
      <CoachShell surface={surface} pathname={pathname} onFocusScreen={onFocusScreen}>
        {props.children}
      </CoachShell>
    </EngineProvider>
  );
}

function CoachShell(props: {
  surface: ReturnType<typeof useSurface>;
  pathname: string;
  onFocusScreen: boolean;
  children: React.ReactNode;
}): React.JSX.Element {
  const { surface, pathname, onFocusScreen, children } = props;
  const activeId = activeScreenId(pathname);

  // iPhone focus screen: dedicated focus chrome, no tab bar (FR-B2). The ✕
  // returns to the Dashboard (COACH_BASE), not the site root (which is the chat
  // landing, a different app).
  if (surface === "iphone" && onFocusScreen && activeId != null) {
    return (
      <FocusModeChrome screenId={activeId} returnTo={COACH_BASE}>
        {children}
      </FocusModeChrome>
    );
  }

  // iPhone non-focus: content above a persistent bottom tab bar.
  if (surface === "iphone") {
    return (
      <div className="flex min-h-dvh flex-col">
        <main className="flex-1 overflow-y-auto">{children}</main>
        <AppNav surface={surface} pathname={pathname} />
      </div>
    );
  }

  // desktop / iPad: persistent sidebar beside the content (FR-B1).
  return (
    <div className="flex min-h-dvh">
      <aside className="w-56 shrink-0 border-r border-border">
        <AppNav surface={surface} pathname={pathname} />
      </aside>
      <main className="mx-auto w-full max-w-[1180px] flex-1 px-6 py-6">
        {children}
      </main>
    </div>
  );
}
