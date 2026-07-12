/**
 * Dev-only Maya fixtures for the browser engine substrate: SKILLS + MASTERY
 * SPREAD only (ADR-0021 / spec FR-B2a).
 *
 * WHY THIS EXISTS. `browserEngineAdapters()` (composition_engine_browser.ts)
 * builds an EMPTY `InMemoryEngineDb`. That is correct for tests — they inject
 * their own seeded bag via the `engineDb` option / `EngineProvider bag` prop —
 * but it makes the live `/learn` Dashboard unusable in a dev preview (six 0%
 * buckets, no focus anchor). This module seeds the skill taxonomy and a varied
 * skill_state spread so the Dashboard renders real content in development.
 *
 * QUESTIONS + HINTS REMOVED (ADR-0021). The practice quiz now serves the
 * governed, cascade-promoted item bank (`_test_item_bank.ts`) through
 * `TestItemQuestionRepo` — the six hand-authored `DEV_QUESTIONS` and their
 * `DEV_HINTS` ladders were deleted with it (the bank is the sole quiz-question
 * source; bank items ship without authored hint ladders this increment, so the
 * hint panel falls back to its generic nudge). The backend persona asset
 * (`components/subject_coach_hints.py::AUTHORED_RUNGS`) remains the single
 * hint source; the ADR-0014 two-plane parity pin retired with the second copy.
 *
 * WHY THE `_` PREFIX. This is a dev/test fixture, not a port adapter. The `_`
 * prefix keeps it out of the adapter-conformance PAIRS scan
 * (`test_adapter_conformance.test.ts`, which skips `f.startsWith("_")`) — it has
 * no `lib/ports/` interface to conform to.
 *
 * LAYERING. Lives in the `adapters` ring and imports ONLY the `wire` shapes plus
 * the browser-safe `InMemoryEngineDb` type — no `pg`, no driver, no composition
 * import (the `adapters` ring forbids reaching back into `composition`). The
 * composition root is the ONE caller (guarded to dev), so this data never enters
 * a test bag or the production on-device path.
 */

import type { InMemoryEngineDb } from "./db/in_memory_engine_db";
import {
  DEFAULT_SUBJECT,
  type Skill,
  type SkillState,
} from "../../wire/engine_entities";

const SUBJECT = DEFAULT_SUBJECT; // "act-english"

/** The plan's single Phase-1 learner (hard-coded in the /learn pages). */
export const DEV_LEARNER_ID = "Garvit";

/**
 * The six ACT-English taxonomy buckets (mirrors the dashboard's SIX_SKILLS).
 * `share_of_test_pct` reflects the real ACT English weighting; `accent_var`
 * matches the `--color-bucket-*` tokens the BucketCard renders.
 */
export const DEV_SKILLS: readonly Skill[] = [
  {
    id: "s-punc",
    subject: SUBJECT,
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 15,
    accent_var: "--color-bucket-punctuation",
    description: "Commas, semicolons, colons, dashes, and apostrophes.",
    order: 1,
  },
  {
    id: "s-gram",
    subject: SUBJECT,
    key: "grammar",
    name: "Usage",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-usage",
    description: "Subject–verb agreement, pronouns, verb tense, idioms.",
    order: 2,
  },
  {
    id: "s-sent",
    subject: SUBJECT,
    key: "sentence",
    name: "Sentence Structure",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-sentence-structure",
    description: "Fragments, run-ons, modifiers, and parallelism.",
    order: 3,
  },
  {
    id: "s-rhet",
    subject: SUBJECT,
    key: "rhetoric",
    name: "Rhetoric",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-rhetoric",
    description: "Word choice, tone, and conciseness in context.",
    order: 4,
  },
  {
    id: "s-org",
    subject: SUBJECT,
    key: "organization",
    name: "Organization",
    share_of_test_pct: 15,
    accent_var: "--color-bucket-organization",
    description: "Transitions, sentence order, and opening/closing sentences.",
    order: 5,
  },
  {
    id: "s-style",
    subject: SUBJECT,
    key: "style",
    name: "Conciseness",
    share_of_test_pct: 10,
    accent_var: "--color-bucket-conciseness",
    description: "Redundancy, wordiness, and consistent register.",
    order: 6,
  },
];


/**
 * Pre-seeded mastery for Maya so the Dashboard shows a real spread (varied
 * bars + one weak, due bucket to anchor "today's focus") instead of six 0%
 * cards. `due_at` in the past = due now; a far-future date = not due. Punctuation
 * is the weakest + due, so it becomes the focus banner and the first Quiz item.
 *
 * These are the ONLY rows the read path (`learnerRead.listSkillState`, ADR-0011)
 * needs; the scheduler still owns all *writes* during a session.
 */
const PAST = "2020-01-01T00:00:00.000Z";
const FUTURE = "2999-01-01T00:00:00.000Z";

function devSkillState(over: Partial<SkillState> & Pick<SkillState, "skill_id">): SkillState {
  return {
    subject: SUBJECT,
    learner_id: DEV_LEARNER_ID,
    mastery: 0.5,
    last_seen: "2026-06-25T00:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: FUTURE,
    fsrs_card: null,
    ...over,
  };
}

export const DEV_SKILL_STATES: readonly SkillState[] = [
  devSkillState({ skill_id: "s-punc", mastery: 0.28, due_at: PAST }), // weakest + due → focus
  devSkillState({ skill_id: "s-gram", mastery: 0.55, due_at: PAST }), // due
  devSkillState({ skill_id: "s-sent", mastery: 0.61, due_at: FUTURE }),
  devSkillState({ skill_id: "s-rhet", mastery: 0.74, due_at: FUTURE }),
  devSkillState({ skill_id: "s-org", mastery: 0.4, due_at: PAST }), // due
  devSkillState({ skill_id: "s-style", mastery: 0.82, due_at: FUTURE }),
];


/**
 * Load the dev fixtures (skills + mastery spread ONLY — ADR-0021) into a fresh
 * browser-safe `InMemoryEngineDb`. Called ONCE by the composition root behind a
 * dev guard (never in tests, never in prod); the quiz-question source is the
 * governed bank, seeded separately via `seedTestItemBank`.
 */
export function seedDevCorpus(db: InMemoryEngineDb): void {
  db.seedSkills([...DEV_SKILLS]);
  db.seedSkillStates([...DEV_SKILL_STATES]);
}
