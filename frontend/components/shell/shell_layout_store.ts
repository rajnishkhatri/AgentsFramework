/**
 * shell_layout_store — Home/Progress sidebar + inline panel dismiss (ADR-0035).
 *
 * Module singleton + useSyncExternalStore (coach_thread_store precedent).
 * Persistence:
 *   - sidebarCollapsed → localStorage["preact.shell.sidebar"] (Home/Progress only)
 *   - panelDismissed → sessionStorage["preact.shell.panelDismissed"]
 *
 * Content screens (Quiz/Coach/Skill/Test) own collapse in layout-local state
 * (Q-C3) — not here. Session pin removed (FR-9).
 */

export const SIDEBAR_STORAGE_KEY = "preact.shell.sidebar";
export const PANEL_DISMISSED_KEY = "preact.shell.panelDismissed";

export interface ShellLayoutState {
  readonly sidebarCollapsed: boolean;
  readonly panelDismissed: boolean;
}

function readStorage(kind: "local" | "session", key: string): string | null {
  try {
    const store = kind === "local" ? globalThis.localStorage : globalThis.sessionStorage;
    return store?.getItem(key) ?? null;
  } catch {
    // G9: private mode / SSR — treat as empty; never fabricate a preference.
    return null;
  }
}

function writeStorage(
  kind: "local" | "session",
  key: string,
  value: string | null,
): void {
  try {
    const store = kind === "local" ? globalThis.localStorage : globalThis.sessionStorage;
    if (store == null) return;
    if (value == null) store.removeItem(key);
    else store.setItem(key, value);
  } catch {
    // G9: quota / private mode — in-memory state still updates.
  }
}

function hydrate(): ShellLayoutState {
  const sidebarRaw = readStorage("local", SIDEBAR_STORAGE_KEY);
  const dismissed = readStorage("session", PANEL_DISMISSED_KEY) === "1";
  return {
    sidebarCollapsed: sidebarRaw === "collapsed",
    panelDismissed: dismissed,
  };
}

let state: ShellLayoutState = hydrate();
const listeners = new Set<() => void>();

function emit(next: ShellLayoutState): void {
  state = next;
  for (const notify of listeners) notify();
}

export function getShellLayoutSnapshot(): ShellLayoutState {
  return state;
}

export function subscribeShellLayout(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

/** Tests + explicit reset: re-hydrate from current storage. */
export function resetShellLayoutStore(): void {
  emit(hydrate());
}

export function setSidebarCollapsed(collapsed: boolean): void {
  writeStorage(
    "local",
    SIDEBAR_STORAGE_KEY,
    collapsed ? "collapsed" : "expanded",
  );
  emit({ ...state, sidebarCollapsed: collapsed });
}

/** Toggle collapse for Home/Progress (writes localStorage). */
export function toggleSidebarCollapsed(): void {
  setSidebarCollapsed(!state.sidebarCollapsed);
}

export function setPanelDismissed(dismissed: boolean): void {
  writeStorage("session", PANEL_DISMISSED_KEY, dismissed ? "1" : null);
  emit({ ...state, panelDismissed: dismissed });
}
