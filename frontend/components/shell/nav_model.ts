/**
 * Navigation model for the PreACT English Coach shell (FR-B1/B3/B5).
 *
 * Per F-R1 the shell components (`AppNav`, `FocusModeChrome`) own NO domain
 * logic. Everything about *where you can go* — the screen catalog, their routes,
 * per-surface visibility (desktop/iPad sidebar vs iPhone 3-tab), the numbered
 * flow-step pills, the focus-screen set that hides the iPhone tab bar, and which
 * controls are wired vs "coming soon" — is decided here, in a pure, React-free,
 * dependency-free module (imports nothing). This is the shell analogue of the
 * `openQuizItem`/`runQuizSubmit` split in use_quiz.ts: the logic is testable in
 * node with no React, and the components just render what the model returns.
 *
 * FR-B5 (no dead controls) is a structural property of this model: a screen with
 * no wired destination is marked `comingSoon` and surfaces as a *disabled*
 * control, never as a live link. Screens 6/7 (Skill detail, Progress) are
 * `comingSoon` until the second ADR-0006 amendment lands (plan D1).
 */

/** The three device surfaces the shell renders for (design-spec §8 / UI-spec §8.1). */
export type Surface = "desktop" | "ipad" | "iphone";

/** Stable screen identifiers — used for active-state matching and the focus set. */
export type ScreenId =
  | "dashboard"
  | "quiz"
  | "feedback"
  | "coach"
  | "summary"
  | "test"
  | "skill"
  | "progress";

export interface Screen {
  readonly id: ScreenId;
  /** App-absolute route under the (coach) route group. */
  readonly route: string;
  /** Sidebar/tab label (Home for dashboard, Practice for quiz — prototype copy). */
  readonly navLabel: string;
  /**
   * No wired destination yet → renders disabled ("coming soon"), never a live
   * link (FR-B5). Screens 6/7 stay true until the second ADR-0006 amendment.
   */
  readonly comingSoon: boolean;
  /**
   * iPhone focus screen: while active, the bottom tab bar is hidden and a "✕"
   * close returns to the prior screen (FR-B2).
   */
  readonly isFocusScreen: boolean;
}

/**
 * The base segment for the whole coach surface. It lives under `/learn` so it
 * coexists with the chat landing page at `/` (app/page.tsx) — Next.js route
 * groups add nothing to the URL, so two pages both resolving to `/` would be a
 * build-time collision. Every screen route is anchored here.
 */
export const COACH_BASE = "/learn";

/**
 * The seven screens (design-spec §8). Order is the canonical presentation order.
 * `route` values are the App Router paths under `COACH_BASE`; the Dashboard is
 * the base itself (`/learn`).
 */
export const SCREENS: readonly Screen[] = [
  { id: "dashboard", route: COACH_BASE, navLabel: "Home", comingSoon: false, isFocusScreen: false },
  { id: "quiz", route: `${COACH_BASE}/quiz`, navLabel: "Practice", comingSoon: false, isFocusScreen: true },
  { id: "feedback", route: `${COACH_BASE}/feedback`, navLabel: "Feedback", comingSoon: false, isFocusScreen: true },
  { id: "coach", route: `${COACH_BASE}/coach`, navLabel: "Coach", comingSoon: false, isFocusScreen: true },
  { id: "summary", route: `${COACH_BASE}/summary`, navLabel: "Summary", comingSoon: false, isFocusScreen: true },
  // Test Mode — a fixed, timed section (Test-01 English), DECOUPLED from the
  // adaptive quiz. A focus screen (hide the iPhone tab bar while the clock runs).
  { id: "test", route: `${COACH_BASE}/test`, navLabel: "Test", comingSoon: false, isFocusScreen: true },
  // Screens 6/7 — subjective/tutorial plane. Skill is live (E1a / ADR-0028);
  // Progress stays comingSoon until its surface ships.
  { id: "skill", route: `${COACH_BASE}/skill`, navLabel: "Skill", comingSoon: false, isFocusScreen: false },
  { id: "progress", route: `${COACH_BASE}/progress`, navLabel: "Progress", comingSoon: true, isFocusScreen: false },
];

const SCREEN_BY_ID: ReadonlyMap<ScreenId, Screen> = new Map(
  SCREENS.map((s) => [s.id, s]),
);

/** Look up a screen by id (throws on an unknown id — a wiring mistake, not a runtime input). */
export function screen(id: ScreenId): Screen {
  const s = SCREEN_BY_ID.get(id);
  if (s == null) throw new Error(`unknown screen id: ${id}`);
  return s;
}

/** A single global-navigation control (sidebar item on desktop/iPad, tab on iPhone). */
export interface NavItem {
  readonly screenId: ScreenId;
  readonly label: string;
  /** App-absolute route; empty only when `disabled` (a coming-soon control). */
  readonly href: string;
  readonly disabled: boolean;
  readonly comingSoon: boolean;
}

// Per-surface nav membership by screen id (FR-B1 + §8.1 iPhone 3-tab supersede).
//   desktop / ipad sidebar: Home / Practice / Coach / Skill / Progress
//   iphone bottom tab bar : Home / Practice / Skill / Progress  (Coach is contextual)
const NAV_MEMBERSHIP: Readonly<Record<Surface, readonly ScreenId[]>> = {
  desktop: ["dashboard", "quiz", "coach", "skill", "progress"],
  ipad: ["dashboard", "quiz", "coach", "skill", "progress"],
  iphone: ["dashboard", "quiz", "skill", "progress"],
};

function toNavItem(s: Screen): NavItem {
  return {
    screenId: s.id,
    label: s.navLabel,
    // A coming-soon control has no destination — it must not ship as a live link
    // (FR-B5). Enabled controls carry their real route.
    href: s.comingSoon ? "" : s.route,
    disabled: s.comingSoon,
    comingSoon: s.comingSoon,
  };
}

/** The ordered global-nav controls for a surface (FR-B1). */
export function navItemsForSurface(surface: Surface): readonly NavItem[] {
  return NAV_MEMBERSHIP[surface].map((id) => toNavItem(screen(id)));
}

/** A numbered desktop flow-step pill (FR-B3): 1 Dashboard · 2 Quiz · … jump-nav. */
export interface FlowStepPill {
  readonly step: number;
  readonly screenId: ScreenId;
  readonly label: string;
  readonly href: string;
}

// The five core-loop steps, in flow order (FR-B3/B4).
const FLOW_STEP_IDS: readonly ScreenId[] = [
  "dashboard",
  "quiz",
  "feedback",
  "coach",
  "summary",
];

/** The numbered flow-step pills for the desktop shell (FR-B3). */
export function flowStepPills(): readonly FlowStepPill[] {
  return FLOW_STEP_IDS.map((id, i) => {
    const s = screen(id);
    return {
      step: i + 1,
      screenId: id,
      // Pills use the screen name, not the sidebar label (Dashboard, not Home).
      label: screenTitle(id),
      href: s.route,
    };
  });
}

// Human-facing screen titles (flow-step pills + focus-mode chrome heading).
const SCREEN_TITLES: Readonly<Record<ScreenId, string>> = {
  dashboard: "Dashboard",
  quiz: "Quiz",
  feedback: "Feedback",
  coach: "Coach",
  summary: "Summary",
  test: "Timed test",
  skill: "Skill detail",
  progress: "Progress",
};

export function screenTitle(id: ScreenId): string {
  return SCREEN_TITLES[id];
}

/** The screen ids that are iPhone focus screens (hide the tab bar; FR-B2). */
export function focusScreenIds(): readonly ScreenId[] {
  return SCREENS.filter((s) => s.isFocusScreen).map((s) => s.id);
}

/** Match a pathname to a screen id for active-state highlighting (longest-prefix). */
export function activeScreenId(pathname: string): ScreenId | null {
  // Exact-match the Dashboard base (`/learn`) first; otherwise the longest deeper
  // route that prefixes the pathname wins (so `/learn/quiz/anything` highlights
  // Quiz, not Dashboard, even though Dashboard's route also prefixes it).
  if (pathname === COACH_BASE) return "dashboard";
  let best: Screen | null = null;
  for (const s of SCREENS) {
    if (s.route === COACH_BASE) continue;
    if (pathname === s.route || pathname.startsWith(`${s.route}/`)) {
      if (best == null || s.route.length > best.route.length) best = s;
    }
  }
  return best?.id ?? null;
}
