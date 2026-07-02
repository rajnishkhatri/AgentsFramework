/**
 * coach_session_marker repo (ADR-0012 Amendment; agent spec §4) — L2.
 *
 * The marker store is the mode-derivation source of truth: monotonic (once
 * submitted, always post-feedback for that item — no unmark API exists, a
 * type-level fact), keyed {user_id, question_id}, written fire-and-forget
 * from the quiz submit path and read by the coach stream route.
 *
 * Failure/isolation paths first: unknown marker ⇒ false (fail-closed to
 * pre-submit), and user A's submits never leak into user B's mode.
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  InMemoryCoachMarkerRepo,
  selectCoachMarkerRepo,
  _resetInMemoryCoachMarkers,
} from "./marker_repo";

beforeEach(() => {
  _resetInMemoryCoachMarkers();
});

describe("marker semantics — fail-closed + isolation first", () => {
  it("unknown {user, question} ⇒ false (derives pre_submit, fail-closed)", async () => {
    const repo = new InMemoryCoachMarkerRepo();
    expect(await repo.isSubmitted("maya", "q-punc-1")).toBe(false);
  });

  it("user isolation: A's submit never flips B's mode", async () => {
    const repo = new InMemoryCoachMarkerRepo();
    await repo.markSubmitted("maya", "q-punc-1");
    expect(await repo.isSubmitted("liam", "q-punc-1")).toBe(false);
  });

  it("question isolation: submitting q1 says nothing about q2", async () => {
    const repo = new InMemoryCoachMarkerRepo();
    await repo.markSubmitted("maya", "q-punc-1");
    expect(await repo.isSubmitted("maya", "q-gram-1")).toBe(false);
  });

  it("markSubmitted is monotonic and idempotent", async () => {
    const repo = new InMemoryCoachMarkerRepo();
    await repo.markSubmitted("maya", "q-punc-1");
    await repo.markSubmitted("maya", "q-punc-1"); // double-tap harmless
    expect(await repo.isSubmitted("maya", "q-punc-1")).toBe(true);
  });
});

describe("dev-server sharing — the per-route-bundle gap regression pin", () => {
  it("two repo instances share the same backing store (globalThis)", async () => {
    // Next dev compiles each route into its own module registry copy; a
    // plain module-level Map would give the marker-write route and the
    // coach stream route two DIFFERENT stores (the thread-repo lesson).
    const writeSide = new InMemoryCoachMarkerRepo();
    const readSide = new InMemoryCoachMarkerRepo();
    await writeSide.markSubmitted("maya", "q-punc-1");
    expect(await readSide.isSubmitted("maya", "q-punc-1")).toBe(true);
  });
});

describe("selectCoachMarkerRepo — composition seam", () => {
  it("no DATABASE_URL ⇒ in-memory (dev/shadow)", () => {
    expect(selectCoachMarkerRepo({})).toBeInstanceOf(InMemoryCoachMarkerRepo);
  });

  it("DATABASE_URL set ⇒ drizzle-backed repo (lazy: no connection yet)", () => {
    const repo = selectCoachMarkerRepo({
      DATABASE_URL: "postgres://user:pw@localhost:5432/app",
    });
    expect(repo).not.toBeInstanceOf(InMemoryCoachMarkerRepo);
  });
});
