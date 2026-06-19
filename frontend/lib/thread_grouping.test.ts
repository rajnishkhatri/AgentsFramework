/**
 * groupThreadsByTime tests. Deterministic clock injected (no Date.now()).
 * Edge cases first (FD6): empty, unparsable dates, boundary days.
 */

import { describe, expect, it } from "vitest";
import { groupThreadsByTime, filterThreadsByTitle } from "./thread_grouping";
import type { ThreadState } from "./wire/agent_protocol";

// Fixed "now": 2026-06-17T12:00:00Z. todayStart depends on local tz, but the
// assertions use offsets relative to the same `now`, so they're tz-stable.
const NOW = Date.parse("2026-06-17T12:00:00Z");
const DAY = 24 * 60 * 60 * 1000;

function thread(id: string, updatedMsAgo: number): ThreadState {
  const iso = new Date(NOW - updatedMsAgo).toISOString();
  return {
    thread_id: id,
    user_id: "u",
    title: `title ${id}`,
    messages: [],
    created_at: iso,
    updated_at: iso,
    archived_at: null,
  };
}

describe("groupThreadsByTime", () => {
  it("returns no groups for an empty list", () => {
    expect(groupThreadsByTime([], NOW)).toEqual([]);
  });

  it("omits empty buckets and orders Today→Older", () => {
    const groups = groupThreadsByTime(
      [thread("today", 1000), thread("old", 30 * DAY)],
      NOW,
    );
    expect(groups.map((g) => g.label)).toEqual(["Today", "Older"]);
  });

  it("buckets into Today / Yesterday / Previous 7 days / Older", () => {
    const groups = groupThreadsByTime(
      [
        thread("t", 60 * 1000), // a minute ago → Today
        thread("y", DAY + 60 * 1000), // ~yesterday
        thread("w", 4 * DAY), // within previous 7 days
        thread("o", 20 * DAY), // older
      ],
      NOW,
    );
    const byLabel = Object.fromEntries(
      groups.map((g) => [g.label, g.threads.map((t) => t.thread_id)]),
    );
    expect(byLabel["Today"]).toContain("t");
    expect(byLabel["Yesterday"]).toContain("y");
    expect(byLabel["Previous 7 days"]).toContain("w");
    expect(byLabel["Older"]).toContain("o");
  });

  it("sorts newest-first within a group", () => {
    const groups = groupThreadsByTime(
      [thread("older", 5 * 60 * 1000), thread("newer", 60 * 1000)],
      NOW,
    );
    expect(groups[0]?.threads.map((t) => t.thread_id)).toEqual([
      "newer",
      "older",
    ]);
  });

  it("treats an unparsable date as epoch (lands in Older, never crashes)", () => {
    const broken: ThreadState = {
      thread_id: "broken",
      user_id: "u",
      title: "broken",
      messages: [],
      created_at: "not-a-date",
      updated_at: "not-a-date",
      archived_at: null,
    };
    const groups = groupThreadsByTime([broken], NOW);
    expect(groups[0]?.label).toBe("Older");
  });
});

// ── filterThreadsByTitle (UI refresh Phase 4 — inline search) ──────────

function titled(id: string, title: string): ThreadState {
  return {
    thread_id: id,
    user_id: "u",
    title,
    messages: [],
    created_at: "2026-06-17T00:00:00Z",
    updated_at: "2026-06-17T00:00:00Z",
    archived_at: null,
  };
}

describe("filterThreadsByTitle — edge cases first", () => {
  const threads = [
    titled("t1", "Plan my trip to Rome"),
    titled("t2", "Font identification"),
    titled("t3", "Credit card analysis"),
  ];

  it("returns ALL threads for an empty query (no filter active)", () => {
    expect(filterThreadsByTitle(threads, "")).toHaveLength(3);
  });

  it("returns ALL threads for a whitespace-only query", () => {
    expect(filterThreadsByTitle(threads, "   ")).toHaveLength(3);
  });

  it("returns an empty array when nothing matches", () => {
    expect(filterThreadsByTitle(threads, "zzz")).toEqual([]);
  });

  it("matches a case-insensitive substring of the title", () => {
    const out = filterThreadsByTitle(threads, "FONT");
    expect(out.map((t) => t.thread_id)).toEqual(["t2"]);
  });

  it("trims surrounding whitespace from the query before matching", () => {
    const out = filterThreadsByTitle(threads, "  card  ");
    expect(out.map((t) => t.thread_id)).toEqual(["t3"]);
  });

  it("can match multiple threads", () => {
    const out = filterThreadsByTitle(
      [titled("a", "trip one"), titled("b", "trip two"), titled("c", "other")],
      "trip",
    );
    expect(out.map((t) => t.thread_id)).toEqual(["a", "b"]);
  });

  it("preserves input order of the surviving threads", () => {
    const out = filterThreadsByTitle(threads, "i"); // matches all three
    expect(out.map((t) => t.thread_id)).toEqual(["t1", "t2", "t3"]);
  });

  it("tolerates a missing/empty title without throwing", () => {
    const t = { ...titled("x", ""), title: "" };
    expect(filterThreadsByTitle([t], "anything")).toEqual([]);
    expect(filterThreadsByTitle([t], "")).toHaveLength(1);
  });
});
