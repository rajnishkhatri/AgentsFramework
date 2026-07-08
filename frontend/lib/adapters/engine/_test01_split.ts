/**
 * D2 Test-01 practice/test split (docs/plan/test01-practice-split.spec.md).
 *
 * The committed `docs/plan/test01-split-manifest.json` is the AUDIT source of
 * truth for every corpus row's fate; these arrays are its TS consumption
 * mirror, pinned byte-for-byte by `_test01_split.test.ts` (drift fails CI).
 * Changing a fate = edit the manifest JSON + this mirror in one reviewable
 * diff, then re-run the split tests.
 *
 * The timed test serves ONLY `test_only` rows (FR-6): the generated corpus
 * file stays untouched (do-not-edit respected); this pure module applies the
 * manifest at the consumption boundary. `promoted` rows leave through the
 * Phase B fold → cascade → bank pipeline instead — never from here — and the
 * FR-1 exclusivity guard (`stemOverlap`) keeps the two surfaces disjoint
 * forever.
 */

import type { Question } from "../../wire/engine_entities";
import {
  TEST01_ENGLISH_MINUTES,
  TEST01_ENGLISH_QUESTIONS,
} from "./_test01_english_corpus";

/** Rows folded into the practice seed (FR-5) — NEVER served by the test. */
export const TEST01_PROMOTED_IDS: readonly string[] = [
  "t01-eng-1",
  "t01-eng-2",
  "t01-eng-4",
  "t01-eng-5",
  "t01-eng-6",
  "t01-eng-7",
  "t01-eng-13",
  "t01-eng-14",
  "t01-eng-15",
  "t01-eng-16",
  "t01-eng-19",
  "t01-eng-22",
  "t01-eng-23",
  "t01-eng-24",
  "t01-eng-27",
  "t01-eng-30",
  "t01-eng-31",
  "t01-eng-33",
  "t01-eng-36",
  "t01-eng-37",
  "t01-eng-39",
  "t01-eng-40",
  "t01-eng-45",
  "t01-eng-47",
];

/** Rows that remain exclusive to the timed test. */
export const TEST01_TEST_ONLY_IDS: readonly string[] = [
  "t01-eng-3",
  "t01-eng-8",
  "t01-eng-9",
  "t01-eng-10",
  "t01-eng-11",
  "t01-eng-12",
  "t01-eng-17",
  "t01-eng-18",
  "t01-eng-20",
  "t01-eng-21",
  "t01-eng-25",
  "t01-eng-26",
  "t01-eng-28",
  "t01-eng-29",
  "t01-eng-32",
  "t01-eng-34",
  "t01-eng-35",
  "t01-eng-38",
  "t01-eng-41",
  "t01-eng-42",
  "t01-eng-43",
  "t01-eng-44",
  "t01-eng-46",
  "t01-eng-48",
];

const TEST_ONLY = new Set<string>(TEST01_TEST_ONLY_IDS);

/** The timed test's served subset — corpus order preserved (FR-6). */
export const TEST01_SERVED_QUESTIONS: readonly Question[] =
  TEST01_ENGLISH_QUESTIONS.filter((q) => TEST_ONLY.has(q.id));

/**
 * Section minutes scaled to the served count at the corpus's own pace
 * (35 min / 48 q), rounded UP so the split never quickens the clock.
 */
export const TEST01_SERVED_MINUTES: number = Math.ceil(
  (TEST01_ENGLISH_MINUTES * TEST01_SERVED_QUESTIONS.length) /
    TEST01_ENGLISH_QUESTIONS.length,
);

/**
 * FR-1 exclusivity detector: normalized-stem intersection between two
 * surfaces. Whitespace-collapsed, lowercased — the same normalization the
 * cascade's duplicate gate keys on, so a stem the guard passes is one the
 * cascade would also treat as distinct.
 */
export function stemOverlap(
  aStems: readonly string[],
  bStems: readonly string[],
): string[] {
  const normalize = (stem: string): string =>
    stem.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
  const a = new Set(aStems.map(normalize));
  return [...new Set(bStems.map(normalize))].filter((stem) => a.has(stem));
}

// FR-7: a mis-curated manifest must fail at build/test time, never render a
// blank timed section at runtime.
if (TEST01_SERVED_QUESTIONS.length === 0) {
  throw new Error(
    "_test01_split: the manifest left the timed test with zero questions",
  );
}
