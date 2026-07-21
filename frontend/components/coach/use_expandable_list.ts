/**
 * use_expandable_list — one generic expand/collapse hook for hint ladder rows
 * and conversation turns (ADR-0035 / Q-C5 / FR-3/4/7/13/14).
 *
 * Pure fold is node-testable; the hook is a thin React wrapper.
 */

"use client";

import * as React from "react";

export interface ExpandableListState {
  readonly manual: ReadonlyMap<string, boolean>;
  /** Ids observed on the previous derive — used by autoExpandNewest. */
  readonly seenIds: readonly string[];
}

export type ExpandableListAction =
  | { type: "toggle"; id: string }
  | { type: "reset" }
  | { type: "syncIds"; ids: readonly string[]; autoExpandNewest: boolean };

export interface DeriveExpandedOpts {
  readonly ids: readonly string[];
  readonly manual: ReadonlyMap<string, boolean>;
  // `| undefined` on the optional fields is required under
  // exactOptionalPropertyTypes: callers forward values that are already
  // `T | undefined` (a hook prop with no default, `opts.foo`), which the
  // present-or-absent `?:` form rejects. The destructuring below still supplies
  // the real defaults, so an undefined here behaves identically to absent.
  readonly forceExpandedIds?: ReadonlySet<string> | undefined;
  /** Conversation: newest open; prior non-forced collapse (FR-13). */
  readonly autoCollapseOnComplete?: boolean | undefined;
  /** Ladder: newly appearing id opens; others retain via manual (FR-14). */
  readonly autoExpandNewest?: boolean | undefined;
  /** Prior id list for detecting newly appearing ids (FR-14). */
  readonly previousIds?: readonly string[] | undefined;
}

/**
 * Pure: which ids should render expanded.
 */
export function deriveExpandedIds(
  opts: DeriveExpandedOpts,
): ReadonlySet<string> {
  const {
    ids,
    manual,
    forceExpandedIds = new Set(),
    autoCollapseOnComplete = false,
    autoExpandNewest = false,
    previousIds = [],
  } = opts;

  if (ids.length === 0) return new Set();

  const expanded = new Set<string>();
  const newestId = ids[ids.length - 1]!;
  const previousSet = new Set(previousIds);
  // FR-14: only count "new" when we already had a prior list (not first paint).
  const newlyAppeared =
    previousIds.length > 0
      ? new Set(ids.filter((id) => !previousSet.has(id)))
      : new Set<string>();

  for (const id of ids) {
    if (forceExpandedIds.has(id)) {
      expanded.add(id);
      continue;
    }
    if (manual.has(id)) {
      if (manual.get(id)) expanded.add(id);
      continue;
    }
    // FR-14: newly revealed row opens before sync commits it into manual.
    if (autoExpandNewest && newlyAppeared.has(id)) {
      expanded.add(id);
      continue;
    }
    // FR-13 / first paint: open newest when no manual yet.
    if (
      (autoCollapseOnComplete ||
        (autoExpandNewest && previousIds.length === 0)) &&
      id === newestId
    ) {
      expanded.add(id);
    }
  }

  return expanded;
}

export interface ReduceOpts {
  readonly ids: readonly string[];
  // See DeriveExpandedOpts — same exactOptionalPropertyTypes forwarding contract.
  readonly forceExpandedIds?: ReadonlySet<string> | undefined;
  readonly autoCollapseOnComplete?: boolean | undefined;
  readonly autoExpandNewest?: boolean | undefined;
}

export function reduceExpandableList(
  state: ExpandableListState,
  action: ExpandableListAction,
  opts: ReduceOpts,
): ExpandableListState {
  if (action.type === "reset") {
    return { manual: new Map(), seenIds: [...opts.ids] };
  }

  if (action.type === "syncIds") {
    const prev = new Set(state.seenIds);
    const newly = action.ids.filter((id) => !prev.has(id));
    let manual = state.manual;
    if (action.autoExpandNewest && newly.length > 0) {
      const next = new Map(state.manual);
      for (const id of newly) {
        if (!next.has(id)) next.set(id, true);
      }
      manual = next;
    }
    const sameIds =
      state.seenIds.length === action.ids.length &&
      state.seenIds.every((id, i) => id === action.ids[i]);
    if (manual === state.manual && sameIds) return state;
    return { manual, seenIds: [...action.ids] };
  }

  const force = opts.forceExpandedIds ?? new Set();
  if (force.has(action.id)) {
    return state; // FR-3/4: toggle ignored while forced
  }
  const current = deriveExpandedIds({
    ids: opts.ids,
    manual: state.manual,
    forceExpandedIds: force,
    autoCollapseOnComplete: opts.autoCollapseOnComplete,
    autoExpandNewest: opts.autoExpandNewest,
    previousIds: state.seenIds,
  });
  const nextExpanded = !current.has(action.id);
  const manual = new Map(state.manual);
  manual.set(action.id, nextExpanded);
  return { manual, seenIds: state.seenIds };
}

export interface UseExpandableListOpts {
  readonly ids: readonly string[];
  readonly forceExpandedIds?: ReadonlySet<string>;
  readonly autoCollapseOnComplete?: boolean;
  readonly autoExpandNewest?: boolean;
}

/**
 * Hook: `{ isExpanded(id), toggle(id), expandedIds }`.
 * Force-expanded ids ignore toggle (FR-3/4).
 */
export function useExpandableList(opts: UseExpandableListOpts): {
  isExpanded: (id: string) => boolean;
  toggle: (id: string) => void;
  expandedIds: ReadonlySet<string>;
} {
  const {
    ids,
    forceExpandedIds,
    autoCollapseOnComplete,
    autoExpandNewest = false,
  } = opts;

  const [state, setState] = React.useState<ExpandableListState>({
    manual: new Map(),
    seenIds: [],
  });

  // Commit newly appeared ladder rows into manual so FR-14 retention survives
  // the next render after seenIds catches up.
  React.useEffect(() => {
    setState((s) =>
      reduceExpandableList(
        s,
        { type: "syncIds", ids, autoExpandNewest },
        { ids },
      ),
    );
  }, [ids, autoExpandNewest]);

  const expandedIds = React.useMemo(
    () =>
      deriveExpandedIds({
        ids,
        manual: state.manual,
        forceExpandedIds,
        autoCollapseOnComplete,
        autoExpandNewest,
        previousIds: state.seenIds,
      }),
    [
      ids,
      state.manual,
      state.seenIds,
      forceExpandedIds,
      autoCollapseOnComplete,
      autoExpandNewest,
    ],
  );

  const isExpanded = React.useCallback(
    (id: string) => expandedIds.has(id),
    [expandedIds],
  );

  const toggle = React.useCallback(
    (id: string) => {
      setState((s) =>
        reduceExpandableList(
          s,
          { type: "toggle", id },
          {
            ids,
            forceExpandedIds,
            autoCollapseOnComplete,
            autoExpandNewest,
          },
        ),
      );
    },
    [ids, forceExpandedIds, autoCollapseOnComplete, autoExpandNewest],
  );

  return { isExpanded, toggle, expandedIds };
}
