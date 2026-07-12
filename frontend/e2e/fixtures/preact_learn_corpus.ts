/**
 * Shared PreAct `/learn` e2e corpus (synthetic learners + question bank + walks).
 *
 * WHY A SEPARATE MODULE. The production dev-seed
 * (`frontend/lib/adapters/engine/_dev_seed.ts`) is the tiny hand-authored "Garvit"
 * corpus that makes the live `/learn` preview usable in dev. The e2e specs want a
 * LARGER, deterministic corpus (several reviewed items per skill + a scripted
 * answer walk) without coupling the tests to prod seed content or bloating it.
 * This module is that e2e-owned fixture; a spec injects it into the browser
 * engine via the non-prod seed-override hook in `composition_engine_browser.ts`
 * (see `installE2ESeed` below), driven by `page.addInitScript`.
 *
 * DETERMINISM. The FSRS scheduler serves the weakest+due skill each round and
 * `nextReviewed` returns the lowest-difficulty-then-id reviewed item for a skill,
 * so the exact question ORDER across a live adaptive session is FSRS-dynamic. The
 * specs therefore do NOT hard-code which question appears when — they read the
 * served item at runtime and apply a scripted DECISION (answer correct / wrong).
 * The Summary score is a function of the spec's own decisions
 * (`EXPECTED_SCORE = correctCount / answeredCount`), so it is byte-stable
 * run-to-run regardless of scheduling order.
 *
 * SHAPES. Every row matches `lib/wire/engine_entities.ts` (`Skill`, `Question`,
 * `SkillState`) 1:1 — snake_case, `reviewed: true` on every question (the hard
 * gate `nextReviewed` enforces). Imports `wire/` only; no SDK, no Playwright.
 *
 * INVARIANT (mirrors _dev_seed.ts): every skill in `LEARN_SKILLS` has ≥1
 * `reviewed: true` question in `LEARN_QUESTIONS`, or the scheduler throws
 * `no reviewed question for skill '<id>'`.
 */

import {
  DEFAULT_SUBJECT,
  type Hint,
  type Question,
  type Skill,
  type SkillState,
} from "../../lib/wire/engine_entities";

const SUBJECT = DEFAULT_SUBJECT; // "act-english"

/** The Phase-1 learner id hard-coded in the /learn pages — the seed MUST use it. */
export const LEARN_LEARNER_ID = "Garvit";

/** The six ACT-English taxonomy buckets (parity with the dashboard SIX_SKILLS). */
export const LEARN_SKILLS: readonly Skill[] = [
  { id: "s-punc", subject: SUBJECT, key: "punctuation", name: "Punctuation", share_of_test_pct: 15, accent_var: "--color-bucket-punctuation", description: "Commas, semicolons, colons, dashes, apostrophes.", order: 1 },
  { id: "s-gram", subject: SUBJECT, key: "grammar", name: "Usage", share_of_test_pct: 20, accent_var: "--color-bucket-usage", description: "Agreement, pronouns, verb tense, idioms.", order: 2 },
  { id: "s-sent", subject: SUBJECT, key: "sentence", name: "Sentence Structure", share_of_test_pct: 20, accent_var: "--color-bucket-sentence-structure", description: "Fragments, run-ons, modifiers, parallelism.", order: 3 },
  { id: "s-rhet", subject: SUBJECT, key: "rhetoric", name: "Rhetoric", share_of_test_pct: 20, accent_var: "--color-bucket-rhetoric", description: "Word choice, tone, conciseness.", order: 4 },
  { id: "s-org", subject: SUBJECT, key: "organization", name: "Organization", share_of_test_pct: 15, accent_var: "--color-bucket-organization", description: "Transitions, sentence order.", order: 5 },
  { id: "s-style", subject: SUBJECT, key: "style", name: "Conciseness", share_of_test_pct: 10, accent_var: "--color-bucket-conciseness", description: "Redundancy, wordiness, register.", order: 6 },
];

function q(over: Partial<Question> & Pick<Question, "id" | "skill_id" | "difficulty" | "context_html" | "stem" | "choices" | "answer_letter" | "per_choice_rationale">): Question {
  return {
    subject: SUBJECT,
    why_correct_md: "The corrected option follows the rule for this skill.",
    why_tempted_md: "The original reads smoothly until you apply the rule.",
    rule_md: "Apply the skill's rule, not what merely *sounds* right.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "e2e-corpus",
    ...over,
  };
}

/** Four A–D choices; A is "NO CHANGE" (the ACT convention, `is_no_change`). */
const CH = (a: string, b: string, c: string, d: string): Question["choices"] => [
  { letter: "A", label: a, is_no_change: true },
  { letter: "B", label: b, is_no_change: false },
  { letter: "C", label: c, is_no_change: false },
  { letter: "D", label: d, is_no_change: false },
];

/**
 * ~3 reviewed items per skill so a session is a real multi-item walk. Difficulty
 * spreads 2..4 so `nextReviewed`'s lowest-difficulty-first pick is deterministic
 * per skill.
 */
export const LEARN_QUESTIONS: readonly Question[] = [
  // --- punctuation ---
  q({ id: "q-punc-1", skill_id: "s-punc", difficulty: 2, context_html: "The museum, <u>which opened in 1974 has</u> welcomed millions.", stem: "Which choice best fixes the underlined portion?", choices: CH("NO CHANGE", "which opened in 1974, has", "which opened in 1974; has", "which, opened in 1974 has"), answer_letter: "B", per_choice_rationale: { A: "Leaves the nonrestrictive clause unclosed.", B: "Closes the clause with a comma.", C: "A semicolon can't sit inside this clause.", D: "Misplaces the comma." } }),
  q({ id: "q-punc-2", skill_id: "s-punc", difficulty: 3, context_html: "She packed three things<u>,</u> a map, a compass, and water.", stem: "Which choice best fixes the underlined portion?", choices: CH("NO CHANGE", ":", ";", " —"), answer_letter: "B", per_choice_rationale: { A: "A comma is too weak to introduce a list.", B: "A colon introduces the list after a complete clause.", C: "A semicolon separates clauses, not a lead-in.", D: "A dash is possible but less precise here." } }),
  q({ id: "q-punc-3", skill_id: "s-punc", difficulty: 4, context_html: "The dog wagged <u>its'</u> tail happily.", stem: "Which choice best fixes the underlined portion?", choices: CH("NO CHANGE", "its", "it's", "its's"), answer_letter: "B", per_choice_rationale: { A: "'its'' is never a word.", B: "'its' is the possessive form.", C: "'it's' means 'it is'.", D: "Not a word." } }),
  // --- grammar ---
  q({ id: "q-gram-1", skill_id: "s-gram", difficulty: 2, context_html: "Each of the runners <u>have</u> trained for months.", stem: "Which choice best fixes the underlined portion?", choices: CH("NO CHANGE", "has", "have been", "having"), answer_letter: "B", per_choice_rationale: { A: "'Each' is singular.", B: "'Each … has' agrees.", C: "Still plural + tense shift.", D: "Leaves no main verb." } }),
  q({ id: "q-gram-2", skill_id: "s-gram", difficulty: 3, context_html: "Neither the coach nor the players <u>was</u> ready.", stem: "Which choice best fixes the underlined portion?", choices: CH("NO CHANGE", "were", "is", "has been"), answer_letter: "B", per_choice_rationale: { A: "With 'nor', the verb agrees with the nearer subject 'players'.", B: "'players … were' agrees.", C: "Wrong number and tense.", D: "Wrong number." } }),
  q({ id: "q-gram-3", skill_id: "s-gram", difficulty: 4, context_html: "The results were better than <u>we</u>.", stem: "Which choice best fixes the underlined portion?", choices: CH("NO CHANGE", "ours", "us", "our"), answer_letter: "B", per_choice_rationale: { A: "'we' compares to a subject, not the results.", B: "'than ours' compares like with like.", C: "Object pronoun doesn't fit.", D: "Possessive adjective needs a noun." } }),
  // --- sentence ---
  q({ id: "q-sent-1", skill_id: "s-sent", difficulty: 2, context_html: "Walking to the store, <u>the rain soaked Maria's jacket</u>.", stem: "Which choice best fixes the misplaced modifier?", choices: CH("NO CHANGE", "Maria was soaked by the rain", "Maria's jacket was soaked", "the rain had soaked the jacket"), answer_letter: "B", per_choice_rationale: { A: "'Walking' dangles.", B: "Maria was walking, so she follows the modifier.", C: "A jacket can't walk.", D: "Still dangles." } }),
  q({ id: "q-sent-2", skill_id: "s-sent", difficulty: 3, context_html: "The team practiced hard<u>, they</u> lost anyway.", stem: "Which choice best fixes the run-on?", choices: CH("NO CHANGE", ", but they", " they", "; but they"), answer_letter: "B", per_choice_rationale: { A: "Comma splice.", B: "A coordinating conjunction joins the clauses.", C: "Fused sentence.", D: "Redundant semicolon + conjunction." } }),
  q({ id: "q-sent-3", skill_id: "s-sent", difficulty: 4, context_html: "She likes hiking, swimming, and <u>to bike</u>.", stem: "Which choice keeps the list parallel?", choices: CH("NO CHANGE", "biking", "bikes", "a bike"), answer_letter: "B", per_choice_rationale: { A: "Breaks the -ing parallelism.", B: "'biking' matches 'hiking, swimming'.", C: "Wrong form.", D: "Wrong form." } }),
  // --- rhetoric ---
  q({ id: "q-rhet-1", skill_id: "s-rhet", difficulty: 2, context_html: "The report was <u>very extremely</u> thorough.", stem: "Which choice is most concise?", choices: CH("NO CHANGE", "extremely", "very", "very much extremely"), answer_letter: "B", per_choice_rationale: { A: "Two stacked intensifiers.", B: "One precise intensifier.", C: "Weaker single word here.", D: "More redundancy." } }),
  q({ id: "q-rhet-2", skill_id: "s-rhet", difficulty: 3, context_html: "The scientist's tone was <u>super chill</u> in the lecture.", stem: "Which choice best fits the formal register?", choices: CH("NO CHANGE", "measured", "totally laid-back", "kinda calm"), answer_letter: "B", per_choice_rationale: { A: "Too casual for a lecture.", B: "'measured' fits the register.", C: "Slangy.", D: "Slangy + vague." } }),
  q({ id: "q-rhet-3", skill_id: "s-rhet", difficulty: 4, context_html: "The essay makes a point that is <u>important and significant</u>.", stem: "Which choice removes the redundancy?", choices: CH("NO CHANGE", "significant", "important, significant,", "very important and significant"), answer_letter: "B", per_choice_rationale: { A: "'important' and 'significant' repeat.", B: "One word carries the meaning.", C: "Adds a comma splice.", D: "More redundancy." } }),
  // --- organization ---
  q({ id: "q-org-1", skill_id: "s-org", difficulty: 2, context_html: "The bridge took years to build. <u>Also</u>, it became a symbol.", stem: "Which transition best fits?", choices: CH("NO CHANGE", "Eventually", "However", "For example"), answer_letter: "B", per_choice_rationale: { A: "'Also' ignores the time relationship.", B: "'Eventually' names the outcome over time.", C: "No contrast exists.", D: "No illustration follows." } }),
  q({ id: "q-org-2", skill_id: "s-org", difficulty: 3, context_html: "Sales rose sharply. <u>Therefore</u>, the weather was cold.", stem: "Which transition best fits?", choices: CH("NO CHANGE", "Meanwhile", "As a result", "Because"), answer_letter: "B", per_choice_rationale: { A: "'Therefore' implies the wrong causation.", B: "'Meanwhile' fits two parallel facts.", C: "Reverses the causation.", D: "Fragments the sentence." } }),
  q({ id: "q-org-3", skill_id: "s-org", difficulty: 4, context_html: "<u>In conclusion, first</u> we must gather the data.", stem: "Which opener best fits a first step?", choices: CH("NO CHANGE", "First", "Finally", "In summary"), answer_letter: "B", per_choice_rationale: { A: "'In conclusion' contradicts 'first'.", B: "'First' fits the opening step.", C: "'Finally' signals the last step.", D: "'In summary' closes, not opens." } }),
  // --- style ---
  q({ id: "q-style-1", skill_id: "s-style", difficulty: 2, context_html: "She returned the book <u>back</u> to the library.", stem: "Which choice removes the redundancy?", choices: CH("NO CHANGE", "DELETE the underlined portion", "back again", "back once more"), answer_letter: "B", per_choice_rationale: { A: "'return … back' is redundant.", B: "Deleting 'back' leaves a clean sentence.", C: "Adds redundancy.", D: "More redundancy." } }),
  q({ id: "q-style-2", skill_id: "s-style", difficulty: 3, context_html: "At <u>this point in time</u>, we should decide.", stem: "Which choice is most concise?", choices: CH("NO CHANGE", "now", "the current present moment", "this current time"), answer_letter: "B", per_choice_rationale: { A: "Wordy cliché.", B: "'now' says it in one word.", C: "Even wordier.", D: "Still wordy." } }),
  q({ id: "q-style-3", skill_id: "s-style", difficulty: 4, context_html: "The plan was a <u>true and honest</u> attempt.", stem: "Which choice removes the redundancy?", choices: CH("NO CHANGE", "genuine", "true, honest,", "really true and honest"), answer_letter: "B", per_choice_rationale: { A: "'true' and 'honest' overlap.", B: "One precise word.", C: "Comma splice.", D: "More redundancy." } }),
];

const PAST = "2020-01-01T00:00:00.000Z";
const FUTURE = "2999-01-01T00:00:00.000Z";

function state(over: Partial<SkillState> & Pick<SkillState, "skill_id">): SkillState {
  return {
    subject: SUBJECT,
    learner_id: LEARN_LEARNER_ID,
    mastery: 0.5,
    last_seen: "2026-06-25T00:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: FUTURE,
    fsrs_card: null,
    ...over,
  };
}

/**
 * A mastery spread with punctuation clearly weakest + due (→ dashboard focus +
 * first served skill), so the Dashboard renders a real spread and the walk has a
 * predictable starting bucket.
 */
export const LEARN_SKILL_STATES: readonly SkillState[] = [
  state({ skill_id: "s-punc", mastery: 0.24, due_at: PAST }), // weakest + due → focus
  state({ skill_id: "s-gram", mastery: 0.52, due_at: PAST }),
  state({ skill_id: "s-sent", mastery: 0.61, due_at: FUTURE }),
  state({ skill_id: "s-rhet", mastery: 0.73, due_at: FUTURE }),
  state({ skill_id: "s-org", mastery: 0.40, due_at: PAST }),
  state({ skill_id: "s-style", mastery: 0.85, due_at: FUTURE }),
];

/**
 * Reviewed hint ladders (ADR-0014) — three rungs per question so the iPad
 * panel's two-tier nudge (FR-J3a) has rungs 2/3 on WHICHEVER item the FSRS
 * scheduler serves. Bodies are deliberately generic + answer-free (rung 1 probe
 * / rung 2 conceptual / rung 3 directive — the same discipline the verifier
 * cascade enforces on generated ladders); the `Nudge N:` prefixes give the
 * ipad spec a stable, non-leaking assertion target.
 */
export const LEARN_HINTS: readonly Hint[] = LEARN_QUESTIONS.flatMap((qn) =>
  ([1, 2, 3] as const).map(
    (r): Hint => ({
      id: `h-${qn.id}-${r}`,
      subject: SUBJECT,
      question_id: qn.id,
      rung: r,
      body_md:
        r === 1
          ? "What is this sentence really testing?"
          : r === 2
            ? "Nudge 2: name the rule in play before you compare the choices."
            : "Nudge 3: find the exact spot where the choices differ and test each against the rule.",
      reviewed: true,
      generated_by: "e2e-corpus",
    }),
  ),
);

/**
 * The serializable corpus a spec hands to the browser via the seed-override hook.
 * Plain arrays (JSON-safe) so `page.addInitScript` can pass it across the boundary.
 */
export interface LearnSeedCorpus {
  readonly skills: readonly Skill[];
  readonly questions: readonly Question[];
  readonly skillStates: readonly SkillState[];
  readonly hints: readonly Hint[];
}

export const LEARN_SEED_CORPUS: LearnSeedCorpus = {
  skills: LEARN_SKILLS,
  questions: LEARN_QUESTIONS,
  skillStates: LEARN_SKILL_STATES,
  hints: LEARN_HINTS,
};

/** The global key the seed-override hook reads (kept in one place, shared with the app). */
export const LEARN_SEED_GLOBAL_KEY = "__PREACT_E2E_SEED__";

/**
 * A scripted answer DECISION walk for a fixed-length session. The spec answers N
 * items; for each, it either answers the item's own `answer_letter` (correct) or
 * a deliberately-wrong letter, per this pattern. The Summary score is then
 * `correctCount / SCRIPTED_WALK.length`, independent of scheduling order.
 *
 * Pattern: 3 correct, 2 wrong → expected Summary score "3/5".
 */
export const SCRIPTED_WALK: readonly ("correct" | "wrong")[] = [
  "correct",
  "wrong",
  "correct",
  "correct",
  "wrong",
];

export const EXPECTED_SCORE_CORRECT = SCRIPTED_WALK.filter((d) => d === "correct").length; // 3
export const EXPECTED_SCORE_TOTAL = SCRIPTED_WALK.length; // 5
export const EXPECTED_SCORE_TILE = `${EXPECTED_SCORE_CORRECT}/${EXPECTED_SCORE_TOTAL}`; // "3/5"
