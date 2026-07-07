/**
 * The governed practice item bank (ADR-0021) — cascade-promoted TestItem rows.
 *
 * PROVENANCE. Every row here was EARNED through the Python verifier cascade
 * (components/test_item_generation.py: schema -> independent-solver key gate ->
 * duplicate) via `scripts/generate_test_items.py --import-seed` from the
 * Claude-authored seed `docs/plan/coach-item-bank-live.seed.json` — see
 * docs/plan/coach-item-bank-live.impl.md for the run evidence (run 2,
 * passage-aware solver; 8 promoted / 4 quarantined-and-adjudicated).
 * `generated_by` carries the promoting run's "<model>@<run_id>" stamp
 * (ADR-0015 clause 6); tests/architecture/test_test_item_provenance_confinement.py
 * scans THIS file — a hand-edited reviewed=true row without cascade provenance
 * fails it. DO NOT edit rows by hand; re-run the promotion instead.
 *
 * SERVING. Loaded by the browser composition root (dev guard, the _dev_seed
 * precedent) into the test_item table; the practice quiz reads it ONLY through
 * TestItemQuestionRepo over TestItemRepo.listReviewed (reviewed rows only).
 * JSON-quoted keys are deliberate: the provenance detector matches the quoted
 * form.
 */

import type { TestItem } from "../../wire/engine_entities";
import type { InMemoryEngineDb } from "./db/in_memory_engine_db";

export const TEST_ITEM_BANK: readonly TestItem[] = [
  {
    "id": "ti-gen-eb8028a2b674681d",
    "subject": "act-english",
    "skill_id": "s-punc",
    "difficulty": 2,
    "context_html": "The recipe calls for three <u>ingredients flour</u>, sugar, and butter.",
    "stem_md": "Which choice correctly punctuates the introduction of the list?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "ingredients: flour",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "ingredients; flour",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "ingredients', flour",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "With no punctuation, the list runs into the noun it names — readers can't tell where 'ingredients' ends and the list begins.",
      "B": "A colon after a complete statement introduces the list it promises: three ingredients — then names them.",
      "C": "A semicolon separates two independent clauses; it cannot introduce a list.",
      "D": "'ingredients'' adds a possessive apostrophe nothing in the sentence calls for."
    },
    "why_correct_md": "A **colon** follows a complete statement to introduce the list it announces.",
    "why_tempted_md": "The sentence reads smoothly aloud, so the missing punctuation is easy to skate past.",
    "rule_md": "Use a colon — never a semicolon — after a complete clause to introduce a list.",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-99e05e271a9f6c92",
    "subject": "act-english",
    "skill_id": "s-gram",
    "difficulty": 3,
    "context_html": "By the time the bus finally arrived, Maria <u>waits</u> at the corner for over an hour.",
    "stem_md": "Which verb form best completes the sentence?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "had been waiting",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "is waiting",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "will wait",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "Present-tense 'waits' clashes with the past-tense 'arrived' that anchors the sentence.",
      "B": "'Had been waiting' places the hour of waiting BEFORE the past arrival — exactly the sequence the sentence describes.",
      "C": "'Is waiting' is present tense; the arrival already happened.",
      "D": "'Will wait' pushes the waiting into the future, after the bus arrived — backwards."
    },
    "why_correct_md": "An action ongoing **before** a past event takes the past perfect (progressive): *had been waiting*.",
    "why_tempted_md": "Each verb form sounds fine alone; only checking it against 'arrived' exposes the clash.",
    "rule_md": "Match verb tense to the sentence's time anchors; 'by the time X happened' demands past perfect.",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-2fddf2bbbfb1b061",
    "subject": "act-english",
    "skill_id": "s-gram",
    "difficulty": 2,
    "context_html": "The results were consistent <u>to</u> the team's hypothesis.",
    "stem_md": "Which choice completes the idiom correctly?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "with",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "for",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "about",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "English pairs 'consistent' with 'with', never 'to'.",
      "B": "'Consistent with' is the standard idiom.",
      "C": "'Consistent for' is not an English idiom.",
      "D": "'Consistent about' describes a person's habits, not agreement between findings and a hypothesis."
    },
    "why_correct_md": "Idioms are fixed pairings: **consistent with** is the only standard form here.",
    "why_tempted_md": "'To' feels connective, and many adjectives do take 'to' (similar to, equal to).",
    "rule_md": "Learn preposition pairings as fixed units — 'consistent with', 'capable of', 'preoccupied with'.",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-c49644db17cedd1b",
    "subject": "act-english",
    "skill_id": "s-sent",
    "difficulty": 3,
    "context_html": "The coach praised the team for practicing daily, playing fairly, and <u>that they communicated</u> clearly.",
    "stem_md": "Which choice keeps the series parallel?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "communicating",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "to communicate",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "they communicated",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "'That they communicated' breaks the -ing pattern set by 'practicing' and 'playing'.",
      "B": "'Communicating' matches the two -ing verbs, keeping the series parallel.",
      "C": "The infinitive 'to communicate' mismatches the -ing forms.",
      "D": "'They communicated' inserts a full clause where the series expects a single -ing verb."
    },
    "why_correct_md": "Items in a series must share one grammatical form — here the **-ing** form.",
    "why_tempted_md": "Each option is grammatical in isolation; only the series pattern exposes the mismatch.",
    "rule_md": "Match every item in a list to the form the first items establish (parallel structure).",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-9fb6fd5eaae7fdf9",
    "subject": "act-english",
    "skill_id": "s-rhet",
    "difficulty": 2,
    "context_html": "The committee reached a <u>consensus of opinion</u> after two hours of debate.",
    "stem_md": "Which choice is the most concise without losing meaning?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "consensus",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "consensus of shared opinion",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "unanimous consensus of opinion",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "A consensus IS an agreement of opinion — 'of opinion' repeats what the word already says.",
      "B": "'Consensus' alone carries the full meaning.",
      "C": "'Shared' stacks a third redundancy onto the phrase.",
      "D": "'Unanimous' adds yet another layer of the same idea."
    },
    "why_correct_md": "The ACT rewards the **shortest** option that preserves the meaning — 'consensus' says it all.",
    "why_tempted_md": "Longer phrases feel more formal and thorough.",
    "rule_md": "Cut words that restate what another word already contains.",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-949378b918123353",
    "subject": "act-english",
    "skill_id": "s-rhet",
    "difficulty": 3,
    "context_html": "In the lab report's discussion section, the experiment's results were <u>super weird</u>, prompting a full review of the method.",
    "stem_md": "Which choice best matches the passage's formal tone?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "unexpected",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "totally bizarre",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "kind of strange",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "'Super weird' is casual slang — jarring inside a formal lab report.",
      "B": "'Unexpected' states the same fact in the register a lab report uses.",
      "C": "'Totally bizarre' swaps one informality for another.",
      "D": "'Kind of strange' keeps the conversational hedge the context forbids."
    },
    "why_correct_md": "Word choice must match the **register** of the surrounding passage — formal here.",
    "why_tempted_md": "The informal options are vivid and natural in speech.",
    "rule_md": "Check the passage's tone before judging a word: formal context → formal diction.",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-abe42cfc107b3d34",
    "subject": "act-english",
    "skill_id": "s-org",
    "difficulty": 2,
    "context_html": "Ella trained all winter for the marathon. <u>In contrast</u>, she finished in her best time ever.",
    "stem_md": "Which transition names the actual relationship between the sentences?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "As a result",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "For instance",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "On the other hand",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "'In contrast' promises opposition, but the best-ever finish FOLLOWS FROM the training.",
      "B": "The record finish is the outcome of the winter of training — cause and effect.",
      "C": "'For instance' promises an example, not an outcome.",
      "D": "'On the other hand' signals the same false contrast as 'In contrast'."
    },
    "why_correct_md": "The second sentence is the **result** of the first — the transition must say so.",
    "why_tempted_md": "Any transition reads smoothly if you don't test the logic it claims.",
    "rule_md": "Name the real relationship (cause, example, contrast, time) before picking a transition.",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  },
  {
    "id": "ti-gen-95b88bbdaeda2910",
    "subject": "act-english",
    "skill_id": "s-style",
    "difficulty": 2,
    "context_html": "Each morning, she would <u>rise up</u> at dawn to water the garden.",
    "stem_md": "Which choice removes the redundant word?",
    "choices": [
      {
        "letter": "A",
        "label": "NO CHANGE",
        "is_no_change": true
      },
      {
        "letter": "B",
        "label": "rise",
        "is_no_change": false
      },
      {
        "letter": "C",
        "label": "rise upward",
        "is_no_change": false
      },
      {
        "letter": "D",
        "label": "get up to rise",
        "is_no_change": false
      }
    ],
    "answer_letter": "B",
    "per_choice_rationale": {
      "A": "'Rise' already means to move up — 'up' repeats it.",
      "B": "'Rise' alone carries the full meaning.",
      "C": "'Upward' is the same redundancy in a longer word.",
      "D": "'Get up to rise' says the same thing twice in two ways."
    },
    "why_correct_md": "The direction is **inside the verb**: rising is upward by definition.",
    "why_tempted_md": "'Rise up' is common in speech and song, so it sounds idiomatic.",
    "rule_md": "Drop particles that repeat the verb's built-in direction (rise up, descend down, return back).",
    "item_type": "underlined-span-mc",
    "reviewed": true,
    "generated_by": "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"
  }
];

/** Load the promoted bank into the browser-safe engine DB (composition-only). */
export function seedTestItemBank(db: InMemoryEngineDb): void {
  db.seedTestItems([...TEST_ITEM_BANK]);
}
