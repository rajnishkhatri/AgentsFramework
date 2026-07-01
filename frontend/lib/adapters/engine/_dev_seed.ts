/**
 * Dev-only corpus for the browser engine substrate (the plan's "Maya" fixtures).
 *
 * WHY THIS EXISTS. `browserEngineAdapters()` (composition_engine_browser.ts)
 * builds an EMPTY `InMemoryEngineDb`. That is correct for tests — they inject
 * their own seeded bag via the `engineDb` option / `EngineProvider bag` prop —
 * but it makes the live `/learn` surface unusable in a dev preview: the
 * Dashboard renders six 0% buckets and the Quiz route throws
 * `no reviewed question for skill '<id>'` from `openQuizItem`, because the
 * scheduler seeds a skill_state row per skill and then asks `QuestionRepo` for a
 * reviewed question the empty store cannot supply. This module supplies a small
 * hand-authored corpus so the loop (Dashboard → Quiz → Summary) is exercisable
 * in the browser during development.
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
 *
 * INVARIANT (why the Quiz route stops throwing). Every skill in `DEV_SKILLS` has
 * at least one `reviewed: true` question in `DEV_QUESTIONS`. The FSRS scheduler
 * seeds a skill_state row for EVERY skill (FR-A7) and then picks the weakest+due
 * one; whichever it lands on, `QuestionRepo.nextReviewed` finds a reviewed item.
 * If you add a skill here, add a reviewed question for it too — otherwise the
 * loop reintroduces the exact `no reviewed question` crash this file fixes.
 */

import type { InMemoryEngineDb } from "./db/in_memory_engine_db";
import {
  DEFAULT_SUBJECT,
  type Question,
  type Skill,
  type SkillState,
} from "../../wire/engine_entities";

const SUBJECT = DEFAULT_SUBJECT; // "act-english"

/** The plan's single Phase-1 learner (hard-coded in the /learn pages). */
export const DEV_LEARNER_ID = "maya";

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
    name: "Grammar & Usage",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-grammar",
    description: "Subject–verb agreement, pronouns, verb tense, idioms.",
    order: 2,
  },
  {
    id: "s-sent",
    subject: SUBJECT,
    key: "sentence",
    name: "Sentence Structure",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-sentence",
    description: "Fragments, run-ons, modifiers, and parallelism.",
    order: 3,
  },
  {
    id: "s-rhet",
    subject: SUBJECT,
    key: "rhetoric",
    name: "Rhetorical Skills",
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
    name: "Style",
    share_of_test_pct: 10,
    accent_var: "--color-bucket-style",
    description: "Redundancy, wordiness, and consistent register.",
    order: 6,
  },
];

/**
 * A `reviewed: true` question for EACH skill (see the INVARIANT note above).
 * Each is a real ACT-style underlined-span multiple-choice item so the Quiz and
 * Feedback views render believable content, not lorem.
 */
export const DEV_QUESTIONS: readonly Question[] = [
  {
    id: "q-punc-1",
    subject: SUBJECT,
    skill_id: "s-punc",
    difficulty: 2,
    context_html:
      'The museum, <u>which opened in 1974 has</u> welcomed millions of visitors.',
    stem: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "which opened in 1974, has", is_no_change: false },
      { letter: "C", label: "which opened in 1974; has", is_no_change: false },
      { letter: "D", label: "which, opened in 1974 has", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: {
      A: "Leaves the nonrestrictive clause unclosed — it needs a comma before 'has'.",
      B: "Closes the nonrestrictive clause 'which opened in 1974' with a comma.",
      C: "A semicolon can't sit inside a nonrestrictive clause like this.",
      D: "Misplaces the comma, splitting 'which' from its clause.",
    },
    why_correct_md:
      "A nonrestrictive clause set off by an opening comma must be **closed** by a comma too.",
    why_tempted_md:
      "A looks fine if you read past the missing second comma.",
    rule_md: "Nonrestrictive clauses are bracketed by a **pair** of commas.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "dev-seed",
  },
  {
    id: "q-gram-1",
    subject: SUBJECT,
    skill_id: "s-gram",
    difficulty: 3,
    context_html:
      "Each of the runners <u>have</u> trained for months before the race.",
    stem: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "have been", is_no_change: false },
      { letter: "C", label: "has", is_no_change: false },
      { letter: "D", label: "having", is_no_change: false },
    ],
    answer_letter: "C",
    per_choice_rationale: {
      A: "'Each' is singular, so it takes a singular verb.",
      B: "Still plural, and adds a needless tense shift.",
      C: "'Each … has' — the singular subject 'each' agrees with 'has'.",
      D: "'having' leaves the sentence without a main verb.",
    },
    why_correct_md:
      "**Each** is always singular; the prepositional phrase 'of the runners' doesn't change the subject.",
    why_tempted_md:
      "The nearby plural 'runners' makes 'have' sound right.",
    rule_md: "Ignore the words between subject and verb; **each/every** is singular.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "dev-seed",
  },
  {
    id: "q-sent-1",
    subject: SUBJECT,
    skill_id: "s-sent",
    difficulty: 3,
    context_html:
      "Walking to the store, <u>the rain soaked Maria's jacket</u>.",
    stem: "Which choice best fixes the misplaced modifier?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "Maria's jacket was soaked by the rain", is_no_change: false },
      { letter: "C", label: "Maria was soaked by the rain", is_no_change: false },
      { letter: "D", label: "the rain had soaked the jacket of Maria", is_no_change: false },
    ],
    answer_letter: "C",
    per_choice_rationale: {
      A: "'Walking' dangles — the rain wasn't walking.",
      B: "A jacket can't walk to the store either.",
      C: "'Maria' is who was walking, so she must follow the modifier.",
      D: "Still leaves 'walking' attached to 'the rain'.",
    },
    why_correct_md:
      "An introductory participial phrase must modify the **subject that follows it**.",
    why_tempted_md:
      "A reads smoothly until you ask *who* was walking.",
    rule_md: "The noun right after an opening '-ing' phrase must be its **doer**.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "dev-seed",
  },
  {
    id: "q-rhet-1",
    subject: SUBJECT,
    skill_id: "s-rhet",
    difficulty: 2,
    context_html:
      "The report was <u>very extremely</u> thorough in its analysis.",
    stem: "Which choice is most concise?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "very", is_no_change: false },
      { letter: "C", label: "extremely", is_no_change: false },
      { letter: "D", label: "very much extremely", is_no_change: false },
    ],
    answer_letter: "C",
    per_choice_rationale: {
      A: "'very extremely' stacks two intensifiers redundantly.",
      B: "Acceptable, but 'extremely' is the stronger single word for 'thorough'.",
      C: "One precise intensifier — concise and idiomatic.",
      D: "Adds even more redundancy.",
    },
    why_correct_md:
      "The ACT rewards the **most concise** option that keeps the meaning.",
    why_tempted_md:
      "Two intensifiers *feel* more emphatic, but they're redundant.",
    rule_md: "Prefer **one** intensifier; drop redundant modifiers.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "dev-seed",
  },
  {
    id: "q-org-1",
    subject: SUBJECT,
    skill_id: "s-org",
    difficulty: 3,
    context_html:
      "The bridge took years to build. <u>Also</u>, it became a symbol of the city.",
    stem: "Which transition best fits the relationship between the sentences?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "Eventually", is_no_change: false },
      { letter: "C", label: "However", is_no_change: false },
      { letter: "D", label: "For example", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: {
      A: "'Also' just adds a fact; the sentences are sequential in time.",
      B: "'Eventually' signals the outcome that followed the long build.",
      C: "'However' implies contrast, but there is none.",
      D: "'For example' promises an illustration that doesn't follow.",
    },
    why_correct_md:
      "The second sentence is the **result over time** of the first — a temporal transition fits.",
    why_tempted_md:
      "'Also' is a safe-sounding default that ignores the time relationship.",
    rule_md: "Pick the transition that names the **actual** logical relationship.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "dev-seed",
  },
  {
    id: "q-style-1",
    subject: SUBJECT,
    skill_id: "s-style",
    difficulty: 2,
    context_html:
      "She returned the book <u>back</u> to the library.",
    stem: "Which choice removes the redundancy?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "back again", is_no_change: false },
      { letter: "C", label: "DELETE the underlined portion", is_no_change: false },
      { letter: "D", label: "back once more", is_no_change: false },
    ],
    answer_letter: "C",
    per_choice_rationale: {
      A: "'return … back' is redundant — 'return' already means 'give back'.",
      B: "Adds a second redundant word.",
      C: "Deleting 'back' leaves 'returned the book to the library' — clean.",
      D: "More redundancy, not less.",
    },
    why_correct_md:
      "'Return' already contains 'back'; the extra word is **redundant**.",
    why_tempted_md:
      "'return back' is common in speech, so it sounds acceptable.",
    rule_md: "Cut words whose meaning is already carried by the verb.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "dev-seed",
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
 * Load the dev corpus into a fresh browser-safe `InMemoryEngineDb`. Called ONCE
 * by the composition root behind a dev guard (never in tests, never in prod).
 */
export function seedDevCorpus(db: InMemoryEngineDb): void {
  db.seedSkills([...DEV_SKILLS]);
  db.seedQuestions([...DEV_QUESTIONS]);
  db.seedSkillStates([...DEV_SKILL_STATES]);
}
