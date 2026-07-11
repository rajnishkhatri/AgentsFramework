/**
 * The governed practice item bank (ADR-0021) — cascade-promoted TestItem rows.
 *
 * GENERATED FILE — do not edit rows by hand; re-run the promotion +
 * this emitter instead. Every row was EARNED through the Python
 * verifier cascade (components/test_item_generation.py: schema ->
 * independent-solver key gate -> duplicate) driven by
 * scripts/generate_test_items.py; `generated_by` carries the promoting
 * run's "<model>@<run_id>" stamp (ADR-0015 clause 6);
 * tests/architecture/test_test_item_provenance_confinement.py scans
 * THIS file. Regenerate (reads
 * docs/plan/coach-item-bank-live.promoted.json, emits this file):
 *
 *   .venv/bin/python scripts/emit_test_item_bank.py
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
      "id": "ti-gen-0ef8644e50886b15",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "By the time we reached the trailhead, the sun had already <u>rose</u> over the ridge.",
      "stem_md": "Which choice is the correct form after 'had'?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "raised",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "rised",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "risen",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Rose' is the simple past — 'had' needs the past participle.",
          "B": "'Raised' comes from 'raise' (to lift something) — the sun rises on its own.",
          "C": "'Rised' isn't a form of this irregular verb.",
          "D": "'Had risen' pairs the helper with the participle."
      },
      "why_correct_md": "After 'had', irregular verbs use their **past participle**: had risen.",
      "why_tempted_md": "The simple past 'rose' is the form we say most often.",
      "rule_md": "Rise-rose-risen; raise-raised-raised. Helpers (have/had) take the third form.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-115a1f54729c0934",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "I <u>seen</u> the meteor shower from the roof of the parking garage.",
      "stem_md": "Which choice is the correct past form of the verb?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "saw",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "have saw",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "seed",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Seen' is a participle — it can't stand alone without 'have' or 'had'.",
          "B": "'Saw' is the simple past and needs no helper.",
          "C": "'Have saw' pairs the helper with the wrong form.",
          "D": "'Seed' isn't a verb form at all here."
      },
      "why_correct_md": "Alone, the past of 'see' is **saw**; 'seen' only works with a helper.",
      "why_tempted_md": "'I seen it' is common in casual speech.",
      "rule_md": "See-saw-seen: 'saw' stands alone; 'seen' rides with have/has/had.",
      "item_type": "underlined-span-mc",
      "misconception": "using casual 'seen' for the past participle",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-3d7b1786e115d2ae",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "We <u>could of</u> caught the earlier bus if the drills had ended on time.",
      "stem_md": "Which choice is the correct form of the verb phrase?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "could",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "could off",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "could have",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Of' is a preposition — it can't help a verb.",
          "B": "Dropping the helper changes the meaning from missed chance to plain ability.",
          "C": "'Off' makes it worse, not better.",
          "D": "The helper is 'have': could have caught."
      },
      "why_correct_md": "The contraction 'could've' spells out as **could have** — never 'could of'.",
      "why_tempted_md": "'Could've' SOUNDS exactly like 'could of'.",
      "rule_md": "Would/could/should pair with HAVE; the '-of' spelling is always an ear-spelling error.",
      "item_type": "underlined-span-mc",
      "misconception": "hearing 'could've' as 'could of'",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-4ae6a4ffb48ec23d",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "Yesterday the choir <u>sung</u> the national anthem, and the whole stadium rose to its feet.",
      "stem_md": "Which choice fits the time the sentence describes?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "singed",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "sang",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "sings",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Sung' is the past participle and needs a helping verb ('had sung'); alone it cannot serve as the simple past.",
          "B": "'Singed' means lightly burned; it is not a form of 'sing'.",
          "C": "'Sang' is the simple past of 'sing' — exactly what 'Yesterday' calls for.",
          "D": "'Sings' is present tense, clashing with 'Yesterday'."
      },
      "why_correct_md": "Irregular verb: sing → **sang** (simple past) → sung (participle, needs a helper).",
      "why_tempted_md": "'Sung' sounds vaguely past-tense, and the sung/sang pair is easy to swap.",
      "rule_md": "Use the simple past form alone; save the participle (sung, swum, begun) for perfect tenses with 'have/had'.",
      "item_type": "underlined-span-mc",
      "misconception": "swapping sang/sung after a helper",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@641234d1808d41ec98477ba4961d06d7"
  },
  {
      "id": "ti-gen-61a600f134c0969a",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "The council debated <u>weather</u> to repave Main Street before winter.",
      "stem_md": "Which choice is the correct word for the underlined portion?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "wether",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "whether",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "wheather",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Weather' means atmospheric conditions, not a choice between options.",
          "B": "'Wether' is a castrated ram — a real word, but not this one.",
          "C": "'Whether' introduces the choice the council is weighing.",
          "D": "'Wheather' is not a word; it misspells 'whether'."
      },
      "why_correct_md": "**'Whether'** introduces alternatives ('whether X or Y'); 'weather' is the sky.",
      "why_tempted_md": "'Weather' and 'whether' sound identical, so the everyday spelling slips in.",
      "rule_md": "Match the homophone to its meaning: whether = if/choice, weather = climate.",
      "item_type": "underlined-span-mc",
      "misconception": "confusing weather/whether by sound",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-689be41bb9faba70",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "The second week of practice went <u>more smooth</u> than the first.",
      "stem_md": "Which choice compares the two weeks correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "more smoothly",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "smoother",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "most smoothly",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Went' needs an adverb — 'smooth' is the adjective.",
          "B": "'More smoothly' is the comparative ADVERB the verb needs.",
          "C": "'Smoother' compares two nouns, but here we're describing how practice WENT.",
          "D": "'Most' is the superlative — there are only two weeks."
      },
      "why_correct_md": "Comparing how something happened takes a **comparative adverb**: more smoothly.",
      "why_tempted_md": "'Smooth' and 'smoother' sound fine because the adjective is so familiar.",
      "rule_md": "Modify a verb with an adverb; compare two with 'more + adverb', not the bare adjective.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-b21cca2fbc4a3c98",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "Passage I — Learning to Sail — The summer I turned fourteen, my uncle <u>teached</u> me to sail. His old wooden boat, named the <em>Osprey</em>, had belonged to my grandfather. On our first morning out, the wind was calm, and we drifted lazily across the bay. However, by noon a stiff breeze had risen, and the <em>Osprey</em> leaned hard against it. My uncle showed me how to read the wind by watching the surface of the water. \"Dark patches mean gusts,\" he said, \"and you must be ready.\" At first I was nervous, gripping the lines too tightly. But after an hour, I begun to relax. By the end of the day, I could steer the boat myself. Although I still had much to learn, I felt a new confidence. Sailing, I realized, was not about controlling the wind but about working with it.",
      "stem_md": "Which choice corrects the underlined verb's past-tense form?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "taught",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "teaches",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "had teached",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "This option leaves or introduces an error under the tested rule.",
          "B": "Past tense of \"teach\" is \"taught.\"",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Past tense of \"teach\" is \"taught.\"",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Conventions (irregular verb)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@2e145cb2f5514579b1cae251b777cff0"
  },
  {
      "id": "ti-gen-e8caf2efaea6d18c",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 1,
      "context_html": "Last night the power flickered twice, and the smoke alarm <u>chirps</u> until Dad changed its battery.",
      "stem_md": "Which choice keeps the sentence in one time frame?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "chirped",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "chirping",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "will chirp",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Last night' and 'changed' set the past — present 'chirps' jumps the track.",
          "B": "Past 'chirped' matches 'flickered' and 'changed'.",
          "C": "'Chirping' leaves the clause without a real verb.",
          "D": "Future tense contradicts a finished story."
      },
      "why_correct_md": "Stay in the tense the sentence establishes — here, the **past**.",
      "why_tempted_md": "The alarm's chirping is easy to picture as happening 'now'.",
      "rule_md": "Match every verb to the sentence's time markers unless the meaning truly changes time.",
      "item_type": "underlined-span-mc",
      "misconception": "the alarm's chirping is easy to picture as happening 'now'",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-029593c1fe5291ac",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "Each kayak in the rental fleet has <u>their</u> own numbered paddle.",
      "stem_md": "Which pronoun matches the word it stands for?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "there",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "his",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "its",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Each kayak' is singular; 'their' is plural.",
          "B": "'There' is a place word, not a possessive.",
          "C": "A kayak isn't a person.",
          "D": "One kayak at a time → 'its' paddle."
      },
      "why_correct_md": "'Each' keeps the antecedent **singular** — one kayak, its paddle.",
      "why_tempted_md": "The plural 'fleet' nearby pulls the pronoun plural.",
      "rule_md": "Each/every + noun stays singular no matter what plural stands nearby.",
      "item_type": "underlined-span-mc",
      "misconception": "letting a nearby plural noun pull agreement",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0dcd672f1f8d3b8a",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "Peanut butter and jelly <u>makes</u> a decent trail lunch when the cooler ice runs out.",
      "stem_md": "Which choice agrees with the compound subject?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "has made",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "is making",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "make",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "Two foods joined by 'and' form a plural subject — 'makes' is singular.",
          "B": "'Has made' is singular and shifts the general claim into a finished past.",
          "C": "'Is making' is still singular and adds a progressive the sentence doesn't need.",
          "D": "'And' builds a plural subject, and 'make' agrees with it."
      },
      "why_correct_md": "Subjects joined by **'and' are plural** — they take a plural verb.",
      "why_tempted_md": "The pair feels like one sandwich, so a singular verb sounds natural.",
      "rule_md": "X and Y → plural verb, unless the pair names a single fixed unit (macaroni and cheese IS).",
      "item_type": "underlined-span-mc",
      "misconception": "treating a compound subject as singular",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-2347e23051258ddd",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
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
              "label": "will wait",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "is waiting",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "had been waiting",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "Present-tense 'waits' clashes with the past-tense 'arrived' that anchors the sentence.",
          "B": "'Will wait' pushes the waiting into the future, after the bus arrived — backwards.",
          "C": "'Is waiting' is present tense; the arrival already happened.",
          "D": "'Had been waiting' places the hour of waiting BEFORE the past arrival — exactly the sequence the sentence describes."
      },
      "why_correct_md": "An action ongoing **before** a past event takes the past perfect (progressive): *had been waiting*.",
      "why_tempted_md": "Each verb form sounds fine alone; only checking it against 'arrived' exposes the clash.",
      "rule_md": "Match verb tense to the sentence's time anchors; 'by the time X happened' demands past perfect.",
      "item_type": "underlined-span-mc",
      "misconception": "each verb form sounds fine alone; only checking it against 'arrived'…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-293cc0b3217916e9",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "The library extended <u>their</u> weekend hours during exam season.",
      "stem_md": "Which pronoun agrees with 'the library'?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "it's",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "its",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "there",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Their' is plural, but 'the library' is one thing.",
          "B": "'It's' means 'it is' — not a possessive.",
          "C": "Singular, non-person antecedent → 'its'.",
          "D": "'There' points to a place; it can't possess hours."
      },
      "why_correct_md": "A singular thing takes the singular possessive **'its'**.",
      "why_tempted_md": "Organizations feel like the people inside them, so 'their' slips in.",
      "rule_md": "Match the pronoun to the antecedent's number: one library → its.",
      "item_type": "underlined-span-mc",
      "misconception": "treating an organization as plural 'their'",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-36ee7811583ee9f3",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "Every morning the ferry leaves at six, crosses the sound in forty minutes, and <u>docked</u> beside the fish market.",
      "stem_md": "Which choice keeps the daily routine consistent?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "docks",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "was docking",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "had docked",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Docked' drops one leg of a present-tense routine into the past.",
          "B": "Present 'docks' matches 'leaves' and 'crosses' — a habit, not a memory.",
          "C": "'Was docking' shifts to a past scene mid-list.",
          "D": "'Had docked' reaches even further back than the plain past."
      },
      "why_correct_md": "A routine described in present tense keeps **every verb present**.",
      "why_tempted_md": "Any single leg of the trip can be remembered as a past event.",
      "rule_md": "Verbs in a series share the sentence's time frame — don't shift without a reason.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-5c506f2cebb6e381",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "Passage IV — Night Shift at the Observatory — My first night as a volunteer at the observatory, I expected glamour. Instead, I found cold floors, humming machines, and a long checklist. The astronomer on duty, Dr. Okafor, greeted me warmly but immediately put me to work. <u>Their</u> were dozens of small tasks: calibrating instruments, logging temperatures, and to check the dome's rotation. None of it looked like the dramatic discoveries I had imagined. Yet as the hours passed, I began to understand that this quiet, careful labor was the real work of science. Around 2 a.m., Dr. Okafor called me over. On the screen was a faint smudge of light — a distant galaxy. \"It isn't much to look at,\" she said, \"but light from there left before humans existed.\" In that moment, the cold floors and checklists seemed worth it.",
      "stem_md": "Which choice uses the correct word for the underlined homophone?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "There",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "They're",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "There're",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "This option leaves or introduces an error under the tested rule.",
          "B": "\"There were dozens\" — \"There,\" not \"Their/They're.\"",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "\"There were dozens\" — \"There,\" not \"Their/They're.\"",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Conventions (homophone)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6d1b683baf09e036",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "The understudy performed so <u>good</u> on opening night that the director rewrote the schedule.",
      "stem_md": "Which choice correctly describes how the understudy performed?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "well",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "goodly",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "great",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Good' is an adjective; 'performed' needs an adverb.",
          "B": "'Well' is the adverb that tells HOW she performed.",
          "C": "'Goodly' is archaic and means 'sizable', not 'skillfully'.",
          "D": "'Great' is another adjective in an adverb's slot."
      },
      "why_correct_md": "Describe a verb with an **adverb**: performed well.",
      "why_tempted_md": "'Did good' is everywhere in casual speech.",
      "rule_md": "Good describes nouns; well describes verbs (except health: 'I feel well').",
      "item_type": "underlined-span-mc",
      "misconception": "using 'good' where an adverb is required",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-b71faa75b88c9e90",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "Tighten the strap so the helmet doesn't come <u>lose</u> on the downhill.",
      "stem_md": "Which choice is the right word for the strap's problem?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "loose",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "loosen",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "lost",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Lose' is a verb (to misplace); the sentence needs a describing word.",
          "B": "'Loose' (rhymes with 'goose') means not tight.",
          "C": "'Loosen' is an action, and 'come loosen' isn't English.",
          "D": "'Come lost' garbles the idiom 'come loose'."
      },
      "why_correct_md": "**Loose** = not tight; **lose** = to misplace or be defeated.",
      "why_tempted_md": "One letter apart and pronounced almost alike, the pair swaps constantly.",
      "rule_md": "Loose rhymes with goose (adjective); lose rhymes with snooze (verb).",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-eeedf6557d108a36",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "The new policy will <u>affect</u> how employees request time off.",
      "stem_md": "Which choice uses the right word for the sentence's meaning?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "effect",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "affects",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "effected",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "'Affect' is the verb meaning to influence — 'will affect how employees request time off' is already correct.",
          "B": "'Effect' as a verb means to bring something about ('effect change'); it cannot take 'how employees request' as its object.",
          "C": "'Will affects' stacks a conjugated verb after 'will', which requires the base form.",
          "D": "'Will effected' is doubly wrong: wrong word and wrong form after 'will'."
      },
      "why_correct_md": "To influence something = **affect** (verb); the sentence already uses it correctly.",
      "why_tempted_md": "The affect/effect pair is so notorious that a correct 'affect' invites second-guessing.",
      "rule_md": "Affect = verb (to influence); effect = noun (a result) — and check before you 'fix' what isn't broken.",
      "item_type": "underlined-span-mc",
      "misconception": "second-guessing affect/effect",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-fb64033d78c6ae8e",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 2,
      "context_html": "The engine ran <u>quiet</u> after the mechanic replaced the worn belt.",
      "stem_md": "Which choice correctly modifies how the engine ran?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "quietly",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "quieter",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "most quiet",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Quiet' is an adjective; it can't describe the verb 'ran'.",
          "B": "'Quietly' is the adverb that correctly modifies how the engine ran.",
          "C": "'Quieter' is a comparative with nothing being compared here.",
          "D": "'Most quiet' is a superlative, also uncalled for and still adjectival."
      },
      "why_correct_md": "An action is described by an **adverb** — 'ran quietly', not 'ran quiet'.",
      "why_tempted_md": "In casual speech 'ran quiet' is common, so the adjective sounds acceptable.",
      "rule_md": "Use an adverb (usually -ly) to modify a verb; save the adjective for a noun.",
      "item_type": "underlined-span-mc",
      "misconception": "using an adjective where an adverb is required",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-01bcf552622af4e7",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "Switching to the aluminum bat made Dev's swing <u>more faster</u> through the strike zone.",
      "stem_md": "Which choice states the comparison without doubling it?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "more fast",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "faster",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "fastest",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'More faster' marks the comparison twice — once with 'more', once with '-er'.",
          "B": "'More fast' uses the wrong marker for a one-syllable adjective.",
          "C": "'Faster' carries the whole comparison in one form.",
          "D": "'Fastest' is the superlative — only two swings are being compared."
      },
      "why_correct_md": "Use **one** comparative marker: -er OR 'more', never both.",
      "why_tempted_md": "Doubling the marker feels like extra emphasis.",
      "rule_md": "Short adjectives take -er/-est; longer ones take more/most; never stack the two.",
      "item_type": "underlined-span-mc",
      "misconception": "doubling a tense/aspect marker for emphasis",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-03e8dc4d409295fc",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "Each of the drones <u>carry</u> a spare battery, while the pilots on the ground track them all at once.",
      "stem_md": "Which choice matches the true subject of the sentence?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "carries",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "are carrying",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "have carried",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "The subject is 'each', not 'drones' — and 'each' is singular.",
          "B": "'Each' takes a singular verb no matter what plural follows 'of'.",
          "C": "'Are carrying' agrees with the nearby plural, not the actual subject.",
          "D": "'Have carried' is plural and abandons the present-tense description."
      },
      "why_correct_md": "**'Each' is singular** — the 'of the drones' phrase can't change that.",
      "why_tempted_md": "The plural noun sits right next to the verb and pulls it plural.",
      "rule_md": "Indefinite pronouns each/either/neither/everyone are singular; ignore the 'of the ___' phrase.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@641234d1808d41ec98477ba4961d06d7"
  },
  {
      "id": "ti-gen-12bb79b0de650b29",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "The volunteer <u>which</u> organized the coat drive spoke at Friday's assembly.",
      "stem_md": "Which choice correctly refers to the volunteer?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "what",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "whom",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "who",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Which' refers to things, not people.",
          "B": "'What' can't introduce a clause about a person.",
          "C": "'Whom' is the object form — but the volunteer is the one organizing.",
          "D": "'Who' refers to a person doing the action of the clause."
      },
      "why_correct_md": "People take **who/whom**; things take which/that.",
      "why_tempted_md": "'Which' feels formal enough to fit anywhere.",
      "rule_md": "Person → who (subject) / whom (object); thing → which/that.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-2b9ae16d270c28ea",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "The box of winter clothes <u>were</u> stored in the attic all summer.",
      "stem_md": "Which choice makes the subject and verb agree?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "have been",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "was",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "are",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Were' agrees with the nearby plural 'clothes', but the subject is the singular 'box'.",
          "B": "'Have been' is also plural — same trap, plus a tense shift the sentence doesn't need.",
          "C": "The subject is 'box' (singular); 'was' agrees with it.",
          "D": "'Are' is plural AND present tense; the sentence describes the past summer."
      },
      "why_correct_md": "The verb agrees with the head noun **box**, not with the closer noun in the 'of' phrase.",
      "why_tempted_md": "The plural 'clothes' sits right next to the verb, luring the ear toward 'were'.",
      "rule_md": "Strip the prepositional phrase to find the true subject before choosing the verb.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-2fddf2bbbfb1b061",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
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
      "misconception": "picking 'to' because it feels connective",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-42a0f73fda4c2917",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "Passage II — The Science of Sourdough — Bread may seem simple, but sourdough is surprisingly complex. Unlike breads made with packaged yeast, sourdough rises using wild yeast and bacteria captured from the air. Bakers maintain a \"starter,\" a mixture of flour and water that they feed regularly. The starter, it ferments over several days. During fermentation, the microbes produce carbon dioxide, which makes the dough rise. They also produce acids, giving sourdough its tangy flavor. <u>Because of these</u> reactions, no two starters taste exactly alike. Some bakers, claim that a starter's flavor reflects the place where it was made. A San Francisco starter, for instance, may taste different from one in Paris. Whether or not that is true, sourdough remains a small marvel of biology and patience.",
      "stem_md": "Which choice gives the idiomatic form of the underlined connective phrase?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Because, of these",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Because these",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Being of these",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "This option leaves or introduces an error under the tested rule.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "\"Because these reactions…\" — \"Because of these\" needs a noun, but the sentence has a clause → \"Because these.\"",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "\"Because these reactions…\" — \"Because of these\" needs a noun, but the sentence has a clause → \"Because these.\"",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Conventions (idiom/structure)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-45cb88c727550efa",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "Of the two routes up the mountain, the eastern trail is the <u>most</u> challenging.",
      "stem_md": "Which choice is correct for comparing the two routes?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "very",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "much",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "more",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Most' is the superlative — it needs three or more routes to pick from.",
          "B": "'Very challenging' drops the comparison the sentence explicitly sets up.",
          "C": "'The much challenging' is not idiomatic before a bare adjective.",
          "D": "Exactly two things compare with the comparative: the eastern trail is the MORE challenging of the two."
      },
      "why_correct_md": "Two items → **comparative** ('more'); three or more → superlative ('most').",
      "why_tempted_md": "Superlatives are so common in speech that 'most challenging' sounds natural even for a pair.",
      "rule_md": "With exactly two things, use -er/'more'; save -est/'most' for three or more.",
      "item_type": "underlined-span-mc",
      "misconception": "reaching for a superlative when a comparative fits",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-81857f7ae5f6aa04",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "Passage I — Learning to Sail — The summer I turned fourteen, my uncle teached me to sail. His old wooden boat, named the <em>Osprey</em>, had belonged to my grandfather. On our first morning out, the wind was calm, and we drifted lazily across the bay. However, by noon a stiff breeze had risen, and the <em>Osprey</em> leaned hard against it. My uncle showed me how to read the wind <u>by watching</u> the surface of the water. \"Dark patches mean gusts,\" he said, \"and you must be ready.\" At first I was nervous, gripping the lines too tightly. But after an hour, I begun to relax. By the end of the day, I could steer the boat myself. Although I still had much to learn, I felt a new confidence. Sailing, I realized, was not about controlling the wind but about working with it.",
      "stem_md": "Which choice gives the idiomatic phrasing of the underlined verb-plus-preposition?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "by watch",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "for watching",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "to watching",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "\"read the wind by watching\" — correct gerund form.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "\"read the wind by watching\" — correct gerund form.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Conventions (idiom)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ccb0cbb911db934d",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "Riders are prohibited <u>to bring</u> glass bottles onto the pool deck.",
      "stem_md": "Which choice completes the expression idiomatically?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "of bringing",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "from bringing",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "against bring",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Prohibited to bring' crosses idioms — 'forbidden TO' but 'prohibited FROM'.",
          "B": "'Prohibited of' isn't an English pattern.",
          "C": "'Prohibited from + -ing' is the fixed pairing.",
          "D": "'Against bring' mangles both the preposition and the verb form."
      },
      "why_correct_md": "The idiom is **prohibited from doing**, not 'prohibited to do'.",
      "why_tempted_md": "The parallel idiom 'forbidden to do' bleeds into this one.",
      "rule_md": "Learn preposition idioms as units: prohibited from, forbidden to, capable of, insist on.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ea7b624cd42ec31e",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 3,
      "context_html": "The mural committee wanted a design that was not only colorful <u>but</u> durable enough for the north wall.",
      "stem_md": "Which choice completes the paired conjunction correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "yet",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "and also",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "but also",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Not only' promises its full partner — bare 'but' breaks the pair.",
          "B": "'Yet' signals contrast, and the pair still goes unfinished.",
          "C": "'And also' isn't the partner 'not only' takes.",
          "D": "'Not only ... but also' is the complete correlative pair."
      },
      "why_correct_md": "Correlative conjunctions come in **fixed pairs**: not only ... but also.",
      "why_tempted_md": "'But' alone carries most of the meaning, so the missing 'also' is easy to drop.",
      "rule_md": "Complete the pair: either/or, neither/nor, both/and, not only/but also.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0c1789eb6711c6f2",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "The docent led us through the fossil hall, pointed out the juvenile triceratops, and <u>explains</u> how the dig team dated the site.",
      "stem_md": "Which choice keeps the tour's verbs consistent?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "explaining",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "explained",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "will explain",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Two past verbs then a present one — the last leg jumps time frames.",
          "B": "'Explaining' breaks the parallel finite-verb series.",
          "C": "'Explained' completes the past-tense series 'led ... pointed ... explained'.",
          "D": "Future tense contradicts a tour already being narrated."
      },
      "why_correct_md": "Verbs in one narrated sequence stay in **one tense**.",
      "why_tempted_md": "The explanation feels ongoing, so present tense sneaks in.",
      "rule_md": "Series of actions by one subject: keep every verb in the frame the first verbs set.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-49ef91abd4738e50",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "Jordan texted Marcus every day while <u>he</u> was at wilderness camp.",
      "stem_md": "Which choice makes clear who was away at camp?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "him",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Marcus",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "himself",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'He' could be Jordan or Marcus — the reader can't tell who left.",
          "B": "'Him' is the wrong case for a subject and no clearer.",
          "C": "Repeating the name removes the ambiguity.",
          "D": "'Himself' needs a matching subject in its own clause."
      },
      "why_correct_md": "When a pronoun could point at **either person**, use the name.",
      "why_tempted_md": "The writer knows who went to camp, so the pronoun feels clear.",
      "rule_md": "A pronoun must have exactly ONE possible antecedent — otherwise name the person.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-50b4dfc045bf65f3",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "By the time the judges reached our booth, the glue <u>dried</u> and the bridge model held its full load.",
      "stem_md": "Which choice shows the drying happened before the judges arrived?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "had dried",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "has dried",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "was drying",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "Plain past puts the drying and the arrival at the same moment.",
          "B": "Past perfect 'had dried' sets the drying BEFORE the past arrival.",
          "C": "'Has dried' ties the drying to the present, not to that past moment.",
          "D": "'Was drying' means the glue was still wet — the opposite of the point."
      },
      "why_correct_md": "**Past perfect** ('had' + participle) marks the earlier of two past events.",
      "why_tempted_md": "Simple past feels sufficient because both events are over.",
      "rule_md": "'By the time X happened, Y HAD happened' — the earlier past takes 'had'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9b3b4144fc30cdf2",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "You can <u>either submit the form online or</u> mail it to the district office.",
      "stem_md": "Which choice places the paired conjunction so the options match?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "submit either the form online or",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "either submit the form online, or",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "submit the form either online or",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Either' sits before the verb but 'or' introduces only a place — the halves don't match.",
          "B": "'Either the form' pairs a noun with a place — still lopsided.",
          "C": "The mismatch stays, and the comma adds nothing.",
          "D": "'Either online or [by] mail' — both arms of the pair now offer the same kind of thing."
      },
      "why_correct_md": "Place correlatives so the words after each arm are **grammatically parallel**.",
      "why_tempted_md": "The sentence sounds fine aloud because the meaning is guessable.",
      "rule_md": "Whatever follows 'either' must mirror what follows 'or' — noun/noun, verb/verb, place/place.",
      "item_type": "underlined-span-mc",
      "misconception": "the sentence sounds fine aloud because the meaning is guessable",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ba5da13ef71e6085",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "Passage III — The Mapmaker's Daughter — Marie Tharp was a geologist who helped change how we see the ocean floor. In the 1950s, working alongside her colleague Bruce Heezen, she plotted thousands of depth measurements <u>collected from</u> ships crossing the Atlantic. At the time, many scientists believed the ocean floor was mostly flat. Tharp's maps revealed something remarkable, a vast underwater mountain range running down the middle of the Atlantic. This discovery, which supported the then-controversial theory of continental drift, was at first dismissed by Heezen as \"girl talk.\" Eventually, the evidence became impossible to ignore. Tharp's careful work helped establish the theory of plate tectonics. Today, her once-doubted maps are considered landmarks of earth science.",
      "stem_md": "Which choice keeps the underlined verb consistent with the sentence's other verbs?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "collecting from",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "collects from",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "which collected from",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "'collected from ships' is a past participle modifying 'measurements' — consistent with the passage's past narration.",
          "B": "'collecting from' is a present participle, wrongly making the measurements do the collecting.",
          "C": "'collects from' is present tense, clashing with the passage's past-tense story.",
          "D": "'which collected from' turns the phrase into a clause whose subject illogically collects."
      },
      "why_correct_md": "The past participle **'collected from'** modifies 'measurements' and matches the past-tense narration.",
      "why_tempted_md": "Each alternative changes the verb form just enough to sound plausible in isolation.",
      "rule_md": "Rule focus: Conventions (verb form)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f1be4f7a34c291a1",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "The volunteer <u>whom</u> organized the food drive received an award.",
      "stem_md": "Which pronoun is correct here?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "who",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "which",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "whose",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Whom' is an object pronoun, but this pronoun is the SUBJECT of 'organized'.",
          "B": "The pronoun performs the verb 'organized', so the subject form 'who' is required.",
          "C": "'Which' refers to things; the volunteer is a person.",
          "D": "'Whose' shows possession — nothing is being possessed here."
      },
      "why_correct_md": "Subject of the verb → **who**; object of a verb or preposition → whom.",
      "why_tempted_md": "'Whom' sounds more formal, so it gets sprinkled in where 'who' belongs.",
      "rule_md": "Test with he/him: 'HE organized the drive' → who; 'the drive was organized by HIM' → whom.",
      "item_type": "underlined-span-mc",
      "misconception": "'Whom' sounds more formal, so it gets sprinkled in where 'who' belongs",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-fef10b2484a7f035",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 4,
      "context_html": "By the time the credits rolled, we <u>watch</u> the entire trilogy in one sitting.",
      "stem_md": "Which choice places the underlined action correctly in time?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "watches",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "will watch",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "had watched",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Watch' is present tense, clashing with the past-time frame 'by the time the credits rolled'.",
          "B": "'Watches' is present tense too, and doesn't agree with 'we'.",
          "C": "'Will watch' points to the future, but the viewing already finished.",
          "D": "'Had watched' correctly marks an action completed before another past moment."
      },
      "why_correct_md": "An action finished **before** another past event takes the past perfect ('had watched').",
      "why_tempted_md": "The present 'watch' feels immediate, but the sentence's time markers are all past.",
      "rule_md": "'By the time X happened, Y had happened' — the earlier past action takes 'had'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-725c2513c059a420",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 5,
      "context_html": "From the coach's silence after tryouts, the players <u>implied</u> that the roster would shrink.",
      "stem_md": "Which choice is the right verb for what the players did?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "applied",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "implicated",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "inferred",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "Speakers imply; listeners infer. The players were on the receiving end.",
          "B": "'Applied' belongs to forms and ointments, not conclusions.",
          "C": "'Implicated' means shown to be involved in wrongdoing.",
          "D": "Drawing a conclusion from evidence is 'inferring'."
      },
      "why_correct_md": "The sender **implies**; the receiver **infers**.",
      "why_tempted_md": "The two verbs describe the same conversation from opposite ends.",
      "rule_md": "Imply = hint outward; infer = conclude inward. Ask which direction the meaning travels.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-7ac43692a538ced7",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 5,
      "context_html": "The mentor <u>who</u> Amara credits for her scholarship still teaches night classes.",
      "stem_md": "Which choice is correct for the person Amara credits?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "whose",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "which",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "whom",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "Inside the clause, Amara credits HIM — an object, so 'who' is the wrong case.",
          "B": "'Whose' is possessive — nothing is owned here.",
          "C": "'Which' can't refer to a person.",
          "D": "'Whom' is the object of 'credits': Amara credits whom."
      },
      "why_correct_md": "Test with him/her: 'Amara credits HIM' → **whom**.",
      "why_tempted_md": "'Who' sounds natural at the head of any clause about a person.",
      "rule_md": "He/she fits → who; him/her fits → whom.",
      "item_type": "underlined-span-mc",
      "misconception": "'Who' sounds natural at the head of any clause about a person",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-a5c4bc79eb059ac0",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 5,
      "context_html": "Any questions about the field trip should go to Ms. Rivera or <u>myself</u> before Friday.",
      "stem_md": "Which choice is correct for the second contact person?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "I",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "me",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "mine",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Myself' is reflexive — it needs 'I' earlier in the clause to reflect.",
          "B": "'I' is the subject form in an object slot.",
          "C": "Questions go TO someone: the object form 'me'.",
          "D": "'Mine' shows possession, which nothing here calls for."
      },
      "why_correct_md": "No earlier 'I' to reflect → plain **me**, not 'myself'.",
      "why_tempted_md": "'Myself' sounds extra polite in requests and announcements.",
      "rule_md": "Reflexives (-self) only echo a subject already in the clause: 'I hurt myself', never 'contact myself'.",
      "item_type": "underlined-span-mc",
      "misconception": "'Myself' sounds extra polite in requests and announcements",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-dcfcdb4223eef909",
      "subject": "act-english",
      "skill_id": "s-gram",
      "difficulty": 5,
      "context_html": "When one trains at altitude for a few weeks, <u>you</u> notice the difference at sea level immediately.",
      "stem_md": "Which choice keeps the sentence's point of view consistent?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "one notices",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "they notice",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "we noticed",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "The sentence opens with 'one' and then swerves to 'you'.",
          "B": "'One ... one notices' holds a single point of view.",
          "C": "'They' invents a third party the sentence never introduced.",
          "D": "'We noticed' changes both person and tense."
      },
      "why_correct_md": "Pick a person — 'one' or 'you' — and **stay in it**.",
      "why_tempted_md": "'One' and 'you' both speak generally, so they feel interchangeable mid-sentence.",
      "rule_md": "Don't shift person (one → you → they) inside a sentence or passage.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-518721c8b8fb1534",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 1,
      "context_html": "The museum added a rooftop cafe last spring. <u>Also,</u> it now stays open until nine on Fridays, and it has doubled its evening attendance.",
      "stem_md": "Which choice best introduces the sentence as another item in a running list of the museum's additions?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "In addition,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Instead,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "For example,",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Also' signals addition but is abrupt and informal at the head of a sentence opening a formal list.",
          "B": "'In addition' opens the sentence as the next entry in the list of additions, matching the passage's register.",
          "C": "'Instead' signals replacement, but the late hours are added to the cafe, not a substitute for it.",
          "D": "'For example' promises an instance of the cafe, but longer hours are a separate addition, not an example."
      },
      "why_correct_md": "For the next item in a list, use a full **additive** opener ('in addition') rather than the abrupt sentence-initial 'also'.",
      "why_tempted_md": "'Also' does mean addition, so it seems right until you weigh how it reads opening a listed sentence.",
      "rule_md": "Match the transition to its POSITION and register: a sentence that adds a list item takes a full additive opener, not a bare 'also'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-08dfeed4155da2ed",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 2,
      "context_html": "First, soak the beans overnight. <u>In other words</u>, rinse them and set them to simmer.",
      "stem_md": "Which transition fits the step-by-step sequence?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "For instance",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Next",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "In contrast",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'In other words' promises a restatement, but rinsing and simmering are NEW steps, not the soaking rephrased.",
          "B": "'For instance' promises an example of soaking — rinsing isn't one.",
          "C": "The passage is a sequence of steps; 'Next' moves it to step two.",
          "D": "'In contrast' claims the steps oppose each other; they simply follow each other."
      },
      "why_correct_md": "Instructions advance step by step — the transition must mark **sequence**.",
      "why_tempted_md": "Restatement transitions sound explanatory, which feels helpful in instructions.",
      "rule_md": "In a procedure, use sequence transitions (first, next, then, finally) between steps.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-5b62aae3d773b227",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 2,
      "context_html": "The science fair had three rounds. First came the written proposal, and next the judges toured each booth. <u>First,</u> the finalists presented to the whole auditorium.",
      "stem_md": "Which transition correctly marks the final round in the sequence?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Finally,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "For instance,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "In contrast,",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'First' can't introduce the third and last round; it contradicts the sequence.",
          "B": "'Finally' correctly signals the last step after 'first' and 'next'.",
          "C": "'For instance' would introduce an example, not the closing step.",
          "D": "'In contrast' signals opposition, which the sequence doesn't call for."
      },
      "why_correct_md": "In a step sequence, the last item takes a **closing transition** like 'finally'.",
      "why_tempted_md": "Repeating 'first' echoes the paragraph's opening word, which can feel intentional.",
      "rule_md": "Sequence transitions must track order: first → next → finally, never two 'firsts'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-71d01781ee685ec2",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 2,
      "context_html": "Passage I — Learning to Sail — The summer I turned fourteen, my uncle teached me to sail. His old wooden boat, named the <em>Osprey</em>, had belonged to my grandfather. On our first morning out, the wind was calm, and we drifted lazily across the bay. <u>However,</u> by noon a stiff breeze had risen, and the <em>Osprey</em> leaned hard against it. My uncle showed me how to read the wind by watching the surface of the water. \"Dark patches mean gusts,\" he said, \"and you must be ready.\" At first I was nervous, gripping the lines too tightly. But after an hour, I begun to relax. By the end of the day, I could steer the boat myself. Although I still had much to learn, I felt a new confidence. Sailing, I realized, was not about controlling the wind but about working with it.",
      "stem_md": "Which transition, in the underlined spot, best fits the shift from calm to a stiff breeze?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Therefore,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "For example,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Similarly,",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "Contrast: calm morning vs. breeze by noon → \"However.\"",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Contrast: calm morning vs. breeze by noon → \"However.\"",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Knowledge of Language (transition)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-b21513cab961e3f7",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 2,
      "context_html": "Ella trained all winter for the marathon. <u>In contrast</u>, she finished in her best time ever. Her coach had predicted exactly this payoff.",
      "stem_md": "Which transition fits the logic connecting the two sentences?",
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
      "why_correct_md": "Read what the second sentence actually does to the first, then choose the transition whose promise matches that link — not one that merely reads smoothly.",
      "why_tempted_md": "Any transition reads smoothly if you don't test the logic it claims.",
      "rule_md": "Name the real relationship (cause, example, contrast, time) before picking a transition.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@641234d1808d41ec98477ba4961d06d7"
  },
  {
      "id": "ti-gen-84bd26e843217d93",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 3,
      "context_html": "Our town's farmers' market started with four vendors in a parking lot. <u>In conclusion,</u> it now fills two blocks every Saturday with more than sixty stalls.",
      "stem_md": "Which transition best fits the contrast between the market's past and present?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Because of this,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "For example,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Today,",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'In conclusion' signals a summary, but this sentence contrasts then with now.",
          "B": "'Because of this' invents a cause-effect tie between the four vendors and the sixty stalls.",
          "C": "'For example' would need the second sentence to illustrate the first, not update it.",
          "D": "'Today' cleanly marks the shift from the market's origins to its current size."
      },
      "why_correct_md": "The sentences contrast **past and present**, so a time-shift transition ('today') is right.",
      "why_tempted_md": "The sentence sits at a paragraph's end, so 'in conclusion' feels structurally natural.",
      "rule_md": "Position doesn't dictate the transition — the logical relationship does.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-93dab2fe84ba3929",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 3,
      "context_html": "The vote passed by a wide margin. <u>Similarly,</u> a small group of residents has already filed an appeal.",
      "stem_md": "Which transition best captures the relationship between the two sentences?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Therefore,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Likewise,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Still,",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Similarly' claims the appeal resembles the wide-margin vote; it actually opposes it.",
          "B": "'Therefore' implies the appeal results from the margin, which it doesn't.",
          "C": "'Likewise' also signals similarity, the wrong direction.",
          "D": "'Still' concedes that, despite the wide margin, opposition remains — the true relationship."
      },
      "why_correct_md": "The second sentence **pushes against** the first, so a concessive transition ('still') fits.",
      "why_tempted_md": "Both sentences describe reactions to the vote, so 'similarly' feels plausible.",
      "rule_md": "Decide whether sentence two agrees, opposes, or results — then match the transition to that.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ab12f0a5a507e9ac",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 3,
      "context_html": "The club spent the fall repairing trail signs and clearing brush. By spring, hikers reported the easiest navigation in years. <u>Trail mix is a popular snack among hikers.</u>",
      "stem_md": "Which choice best concludes the paragraph by tying its details together?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Some hikers prefer to explore without any map at all.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "The club's steady work had clearly paid off.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Brush can grow back quickly in a wet season.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Trail mix has nothing to do with the club's trail work — it's irrelevant.",
          "B": "Map-free hiking introduces a new, unrelated idea instead of concluding.",
          "C": "It sums up the cause (the work) and the effect (easier navigation), closing the paragraph.",
          "D": "This undercuts the paragraph's point rather than wrapping it up."
      },
      "why_correct_md": "A conclusion should **draw the paragraph's details to a close**, which 'paid off' does.",
      "why_tempted_md": "Trail mix mentions hikers, the paragraph's subject, so it feels loosely on-topic.",
      "rule_md": "A concluding sentence gathers what came before — reject choices that add new or off-topic ideas.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-b149168609a7069d",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 3,
      "context_html": "The paragraph argues that city parks improve public health. <u>Downtown rents have risen sharply over the past decade.</u> Studies link green space to lower stress and more daily exercise.",
      "stem_md": "The writer wants every sentence to support the paragraph's point about parks and health. The underlined sentence should be:",
      "choices": [
          {
              "letter": "A",
              "label": "KEPT, because it mentions the downtown area near the parks",
              "is_no_change": false
          },
          {
              "letter": "B",
              "label": "KEPT, because rising rents prove parks are valuable",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "DELETED, because it introduces an unrelated point about rents",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "DELETED, because it repeats the previous sentence",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "A shared location doesn't make rent relevant to a health argument.",
          "B": "Rising rents don't establish anything about health benefits; the link is invented.",
          "C": "The sentence about rents is off the paragraph's topic (parks and health) and should go.",
          "D": "It isn't a repeat — it's a new, unrelated claim."
      },
      "why_correct_md": "Every sentence must serve the paragraph's point; the rent sentence **strays off-topic**, so delete it.",
      "why_tempted_md": "'Downtown' overlaps with where parks are, making the sentence feel connected.",
      "rule_md": "Test each sentence against the paragraph's main claim; cut whatever doesn't advance it.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-bd8de98582eeb065",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 3,
      "context_html": "The trail was steep and poorly marked. <u>In fact</u>, the view from the summit repaid every step.",
      "stem_md": "Which transition acknowledges the concession the passage makes?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "For example",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "As a result",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Even so",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'In fact' intensifies what came before; the second sentence pivots away from the complaint instead.",
          "B": "'For example' promises an instance of steepness; a rewarding view isn't one.",
          "C": "'As a result' claims the great view was CAUSED by bad trail markings.",
          "D": "'Even so' concedes the hard climb, then asserts the reward despite it — exactly the move the passage makes."
      },
      "why_correct_md": "Hardship conceded, reward asserted anyway → a **concession** transition ('even so', 'nevertheless').",
      "why_tempted_md": "'In fact' is a common intensifier, and the sentence pair reads fine until the logic is tested.",
      "rule_md": "When sentence two says 'despite that', the transition must carry the concession.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-d5cf1d16bc41eae4",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 3,
      "context_html": "<u>Volcanic soil is rich in minerals.</u> Farmers on the island's slopes harvest three crops a year, and their coffee sells at a premium overseas. Even the roadside wildflowers grow thick and bright.",
      "stem_md": "Which choice is the most effective topic sentence for the paragraph?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Coffee is the island's most valuable export.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "The island's volcanic soil makes it remarkably fertile.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Volcanoes can be dangerous to nearby communities.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Rich in minerals' is true but narrower than the paragraph, which is about overall fertility.",
          "B": "Coffee is only one detail; a topic sentence can't hinge on a single example.",
          "C": "'Remarkably fertile' covers crops, coffee, and wildflowers alike — the whole paragraph.",
          "D": "Danger is never mentioned in the body; this choice is off-topic."
      },
      "why_correct_md": "A topic sentence must **cover every detail** that follows — here, fertility does.",
      "why_tempted_md": "The mineral fact (A) opens the same subject, so it feels like a natural lead — but it's too narrow.",
      "rule_md": "Read the body first; the best topic sentence is the umbrella the details already argue for.",
      "item_type": "underlined-span-mc",
      "misconception": "the mineral fact (A) opens the same subject, so it feels like a natur…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0547a2126a9a3834",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "The essay claims that public libraries remain essential in the digital age. A strong body paragraph would most likely develop this claim by <u>listing the founding dates of several famous libraries.</u>",
      "stem_md": "Which choice best develops the essay's claim about libraries' ongoing importance?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "explaining how printing presses worked in the fifteenth century.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "describing the free internet access and job-search help libraries now provide.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "recounting the architecture of a famous reading room.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Founding dates speak to history, not present-day essentialness.",
          "B": "Fifteenth-century printing is unrelated to the digital-age argument.",
          "C": "Modern services like internet access and job help directly show why libraries still matter.",
          "D": "Architecture is decorative detail that doesn't support the claim of essentialness."
      },
      "why_correct_md": "Development must **advance the specific claim** — here, current relevance, which modern services demonstrate.",
      "why_tempted_md": "History and famous rooms feel 'library-related', so they seem supportive.",
      "rule_md": "Choose supporting detail that proves the exact point being argued, not merely the general topic.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-130d46cb6e004cef",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "<u>The bakery on Fifth Street sells excellent bread.</u> This essay will argue that small local businesses deserve tax incentives because they anchor neighborhoods, create jobs, and keep profits circulating in the community.",
      "stem_md": "Which choice is the strongest thesis statement for the essay?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Tax policy is a complicated and often controversial subject.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "There are many small businesses in our town.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Small local businesses deserve tax incentives because they strengthen neighborhoods, employ residents, and reinvest their earnings locally.",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "One bakery's bread is a narrow anecdote, not a thesis the essay can defend.",
          "B": "Calling the topic 'complicated' announces no stance at all.",
          "C": "A bare fact about quantity takes no position and previews no argument.",
          "D": "It states a clear claim (incentives) plus the three reasons the essay will develop."
      },
      "why_correct_md": "A thesis makes an **arguable claim and previews the support** — B names the claim and its three reasons.",
      "why_tempted_md": "The bakery sentence is concrete and vivid, which can masquerade as a strong opening.",
      "rule_md": "A thesis states a debatable position and maps the essay's reasons — not a fact or a vague topic label.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-26b65ee2ba3d6de6",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "The report opens by describing the drought's toll on the reservoir. It then details the new conservation rules. <u>Rainfall totals vary widely from year to year.</u>",
      "stem_md": "Which choice best concludes the report by reinforcing its purpose?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "With these measures in place, the town hopes to weather the next dry spell.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "The reservoir was built more than fifty years ago.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Many households own more than one car.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "A generic fact about rainfall variability doesn't close the report's argument.",
          "B": "It ties the conservation rules to the goal of surviving future droughts, fulfilling the report's purpose.",
          "C": "The reservoir's age is a stray detail unrelated to the conclusion.",
          "D": "Car ownership has nothing to do with drought conservation."
      },
      "why_correct_md": "A purposeful conclusion **links the body's content to the document's goal** — surviving drought.",
      "why_tempted_md": "Rainfall variability is on-theme with drought, so it feels like a fitting close.",
      "rule_md": "A conclusion should advance the piece's purpose, not merely mention its subject.",
      "item_type": "underlined-span-mc",
      "misconception": "rainfall variability is on-theme with drought, so it feels like a fit…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-4026afc5e8d79eba",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "The article traces the comeback of the peregrine falcon: a pesticide ban in the 1970s, captive-breeding programs in the 1980s, and <u>the invention of the modern telescope.</u>",
      "stem_md": "Which choice best continues the article's line of argument about the falcon's recovery?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "the protection of nesting sites on city skyscrapers.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "the popularity of birdwatching as a hobby.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "the history of falconry in medieval Europe.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "Telescopes have no bearing on why falcon populations recovered.",
          "B": "Protecting nesting sites is a genuine recovery cause, continuing the article's chain of factors.",
          "C": "Birdwatching's popularity is a side effect, not a cause of the comeback.",
          "D": "Medieval falconry is unrelated to the modern recovery being traced."
      },
      "why_correct_md": "Argument-tracing requires the next item to be **another cause in the same chain** — nesting-site protection is.",
      "why_tempted_md": "Options C and D both mention birds, so they feel connected to the falcon topic.",
      "rule_md": "When a passage builds a causal list, each addition must belong to that same causal thread.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-545e646d68ef68ad",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "<u>Honey has been harvested for thousands of years.</u> Bees pollinate roughly a third of the crops humans eat, and almond growers truck hives across entire states each spring. Without managed colonies, many orchards would produce almost nothing.",
      "stem_md": "Which choice provides the best topic sentence for the paragraph?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Beekeepers wear protective suits for good reason.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Honey comes in many colors and flavors.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Bees are essential partners in modern agriculture.",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "The paragraph is about pollination and farming, not the history of honey harvesting.",
          "B": "Protective suits never come up — the body is about crops and orchards.",
          "C": "Honey varieties are irrelevant to pollination statistics and trucked hives.",
          "D": "Every body sentence — the crop share, the trucked hives, the barren orchards — supports bees as agricultural partners."
      },
      "why_correct_md": "A topic sentence must be the claim **every body sentence supports**.",
      "why_tempted_md": "Honey feels on-topic because bees make it — adjacency masquerades as relevance.",
      "rule_md": "Read the body first; the right topic sentence is the one the details already argue for.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-8f419a733dbba475",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "Passage II — The Science of Sourdough — Bread may seem simple, but sourdough is surprisingly complex. Unlike breads made with packaged yeast, sourdough rises using wild yeast and bacteria captured from the air. Bakers maintain a \"starter,\" a mixture of flour and water that they feed regularly. The starter, it ferments over several days. During fermentation, the microbes produce carbon dioxide, which makes the dough rise. They also produce acids, giving sourdough its tangy flavor. Because of these reactions, no two starters taste exactly alike. Some bakers, claim that a starter's flavor reflects the place where it was made. A San Francisco starter, for instance, may taste different from one in Paris. Whether or not that is true, sourdough remains a small marvel of biology and patience.",
      "stem_md": "Should the sentence about San Francisco and Paris be kept or deleted, and why?",
      "choices": [
          {
              "letter": "A",
              "label": "Kept, because it gives a concrete example illustrating the preceding claim.",
              "is_no_change": false
          },
          {
              "letter": "B",
              "label": "Kept, because it explains the chemistry of fermentation.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Deleted, because it repeats the essay's opening.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Deleted, because it introduces an unrelated topic.",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "The example illustrates the claim → keep.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "The example illustrates the claim → keep.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Production (keep/delete w/ reasoning)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-af530f347820d781",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 4,
      "context_html": "Paragraph 2 explains how the tide pools form at low water. Paragraph 3 lists the animals that shelter there. <u>Meanwhile,</u> the guide leads visitors from the parking lot down to the rocks.",
      "stem_md": "Which choice best opens a sentence that should logically come between paragraphs 2 and 3?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Once the water recedes, a whole community of creatures emerges.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "The parking lot fills quickly on summer weekends.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Tides are caused by the pull of the moon and sun.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Meanwhile' plus a parking-lot detail doesn't bridge how pools form to which animals live there.",
          "B": "It links the low-tide formation (para 2) to the sheltering animals (para 3) — a true bridge.",
          "C": "The parking lot is unrelated to the pools-to-animals transition.",
          "D": "Restating what causes tides steps backward instead of moving toward the animals."
      },
      "why_correct_md": "A bridging sentence must **connect the idea before it to the idea after it** — formation to inhabitants.",
      "why_tempted_md": "'Meanwhile' signals a transition, so option A looks structurally correct at a glance.",
      "rule_md": "A transition sentence should echo the prior paragraph and point toward the next one.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0ec8f45b9028b6c6",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 5,
      "context_html": "A late frost destroyed half the orchard's trees<u>; consequently,</u> the annual cider festival went on as planned.",
      "stem_md": "Which transition matches the relationship between the frost and the festival?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "; for example,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "; nevertheless,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "; in addition,",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Consequently' claims the festival happened BECAUSE of the frost — the frost worked against it.",
          "B": "'For example' would make the festival an instance of frost damage, which it isn't.",
          "C": "The festival proceeded DESPITE the destruction — 'nevertheless' carries exactly that defiance.",
          "D": "'In addition' stacks the festival on top of the frost as more of the same; they pull opposite ways."
      },
      "why_correct_md": "Setback + outcome-despite-it = **nevertheless**, not a cause-effect transition.",
      "why_tempted_md": "'Consequently' sounds authoritative, and both sentences do describe real events in order.",
      "rule_md": "Ask whether the second clause happens because of, despite, or alongside the first — then pick the transition that says so.",
      "item_type": "underlined-span-mc",
      "misconception": "'Consequently' sounds authoritative, and both sentences do describe r…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-1e22163f8445836f",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 5,
      "context_html": "The essay's introduction promises to explain 'why the bridge failed and how the city rebuilt trust.' The first body paragraph covers the engineering flaw. <u>The mayor enjoys sailing on weekends.</u>",
      "stem_md": "Which choice best begins the second body paragraph so it fulfills the introduction's promise?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "To restore public confidence, the city held open hearings and published every inspection report.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "The bridge's steel came from three different suppliers.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Engineering degrees take four years to complete.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "The mayor's hobby is irrelevant to both halves of the essay's promise.",
          "B": "Rebuilding trust through hearings and transparency delivers the second promised topic.",
          "C": "Steel suppliers extend the engineering-flaw topic, not the trust half.",
          "D": "How long degrees take is unrelated to either promised subject."
      },
      "why_correct_md": "The introduction promised two topics; body two must cover the **second one — rebuilding trust**.",
      "why_tempted_md": "Option C stays on bridges, so it feels on-topic even though it repeats paragraph one's theme.",
      "rule_md": "Track the essay's stated plan; each paragraph must deliver the part it's responsible for.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-993e51faa7a5ba14",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 5,
      "context_html": "The essay opens with the image of the lighthouse dark and boarded up. It then recounts the two-year volunteer restoration. <u>Fundraising for the restoration ended in June.</u>",
      "stem_md": "The writer wants a conclusion that returns to the essay's opening image of the lighthouse. Which choice accomplishes this?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Many coastal towns face similar budget shortfalls.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Today the restored beacon sweeps the bay each night, just as it did in 1902.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "The preservation committee will meet again next spring.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "A fundraising date is administrative housekeeping — it never looks back at the lighthouse.",
          "B": "Other towns' budgets point AWAY from this essay's subject entirely.",
          "C": "The lit beacon sweeping the bay answers the opening's dark, boarded-up tower — the frame closes.",
          "D": "A future meeting is logistics, not imagery."
      },
      "why_correct_md": "A framing conclusion must **revisit the opening image** — dark tower then, lit beacon now.",
      "why_tempted_md": "Factually true closers feel legitimate even when they ignore the stated goal.",
      "rule_md": "When the stem names the writer's goal, eliminate every choice that doesn't perform it — truth alone doesn't qualify.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9ecce8513dec92cc",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 5,
      "context_html": "Throughout the memoir, the author returns to the image of her mother's hands kneading dough. The final chapter should, the writer decides, close on that same image. <u>The author later moved to a different city for work.</u>",
      "stem_md": "Which choice best ends the memoir by returning to its central image?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Her mother had always wanted her to attend college.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Now, flouring her own counter at dawn, she feels her mother's hands guiding hers.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "The old family recipes were written on index cards.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Moving cities for work drops the kneading-hands image entirely.",
          "B": "College is a new topic, not a return to the central image.",
          "C": "It revisits the mother's hands and the dough, closing the memoir on its recurring image.",
          "D": "Index cards touch on recipes but abandon the hands-kneading-dough motif."
      },
      "why_correct_md": "When the goal is to **return to a central image**, choose the option that revives it — the hands and dough.",
      "why_tempted_md": "Recipe cards (D) sit near the cooking theme, so they feel like a callback.",
      "rule_md": "A callback conclusion must reawaken the specific image named, not merely the general subject.",
      "item_type": "underlined-span-mc",
      "misconception": "recipe cards (D) sit near the cooking theme, so they feel like a call…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9f104eddac2ff7ae",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 5,
      "context_html": "The op-ed argues that the city should fund after-school programs. It cites falling test scores, rising afternoon crime, and working parents' scheduling struggles. <u>The stadium's new scoreboard cost eight million dollars.</u>",
      "stem_md": "The writer wants each piece of evidence to support the case for after-school funding. The underlined sentence should be:",
      "choices": [
          {
              "letter": "A",
              "label": "KEPT, because it shows the city has money to spend",
              "is_no_change": false
          },
          {
              "letter": "B",
              "label": "KEPT, because stadiums are popular with students",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "DELETED, because it does not support the case for after-school programs",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "DELETED, because it belongs in the introduction instead",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "The scoreboard's cost is a budgeting aside; it doesn't argue that after-school programs are needed.",
          "B": "Stadium popularity says nothing about the need for after-school programs.",
          "C": "The sentence drifts from the op-ed's evidence chain (scores, crime, schedules) and should be cut.",
          "D": "Moving an irrelevant sentence to the introduction doesn't make it relevant."
      },
      "why_correct_md": "Evidence must **support the specific claim**; the scoreboard cost doesn't, so delete it.",
      "why_tempted_md": "'The city has money' feels like a supporting point, but it's a separate spending debate.",
      "rule_md": "Keep only evidence that advances the exact argument; cut tangents even if loosely budget-related.",
      "item_type": "underlined-span-mc",
      "misconception": "'The city has money' feels like a supporting point, but it's a separa…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-cbd3325cb0fd4832",
      "subject": "act-english",
      "skill_id": "s-org",
      "difficulty": 5,
      "context_html": "Sentence 1: The renovation preserved the theater's original plaster ceiling. Sentence 2: Crews reinforced it with hidden steel before the reopening gala. The writer wants to add: 'The ornate medallions had survived a century of leaks.' <u>This sentence would best be placed after sentence 2.</u>",
      "stem_md": "Where should the new sentence about the surviving medallions be placed?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Before sentence 1",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Between sentences 1 and 2",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "The sentence should not be added at all.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "After sentence 2, the medallion detail interrupts the jump from reinforcement to the gala.",
          "B": "Before sentence 1, the medallions are mentioned before the ceiling they belong to is introduced.",
          "C": "Between 1 and 2, the medallion detail elaborates the just-named ceiling before crews reinforce it.",
          "D": "The detail is relevant and vivid, so it should be added, not dropped."
      },
      "why_correct_md": "A supporting detail belongs **right after the idea it elaborates** — the ceiling in sentence 1.",
      "why_tempted_md": "Placing new information last feels safe, but here it breaks the ceiling-to-reinforcement flow.",
      "rule_md": "Insert a detail next to the sentence it develops, keeping the paragraph's logical order intact.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-34265d79953a3867",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 1,
      "context_html": "The camping checklist included a tent<u> a lantern matches</u> and a first-aid kit.",
      "stem_md": "Which choice punctuates the items in the series correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "; a lantern; matches;",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ", a lantern matches,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", a lantern, matches,",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "With no commas, four separate supplies blur into one unreadable run.",
          "B": "Semicolons separate series items only when the items already contain commas.",
          "C": "This leaves 'a lantern matches' fused into one item — a lantern isn't a kind of match.",
          "D": "Commas separate each item in the series of four supplies."
      },
      "why_correct_md": "Commas separate **every item** in a simple series.",
      "why_tempted_md": "Short items read fast aloud, so the missing commas are easy to skate past.",
      "rule_md": "In a series of three or more, put a comma after each item except the last.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-48ea13424888c8b4",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 1,
      "context_html": "My grandparents moved to Tucson<u> Arizona on March 4 1998</u> after the bakery closed.",
      "stem_md": "Which choice punctuates the place and date correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", Arizona, on March 4, 1998,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ", Arizona on March 4, 1998",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", Arizona, on March 4 1998,",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "City-state pairs and day-year pairs both need commas to stay readable.",
          "B": "Commas set off the state and the year on both sides — the full convention.",
          "C": "The state needs a comma on BOTH sides, and the year needs its closing comma too.",
          "D": "The state is handled, but the day and year are left fused."
      },
      "why_correct_md": "State names and years act like interrupters: **commas on both sides**.",
      "why_tempted_md": "The single comma before 'Arizona' looks like it is already doing the job.",
      "rule_md": "City, State, ... and Month Day, Year, ... — the state and the year each take a closing comma.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-3a1b53fce3a96f39",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 2,
      "context_html": "After three straight weekends of tryouts and scrimmages<u> the</u> coach finally posted the roster.",
      "stem_md": "Which choice punctuates the sentence's opening correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ": the",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "; the",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", the",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A long opening phrase runs straight into the main clause without a marked boundary.",
          "B": "A colon needs a complete statement before it, and the opener isn't one.",
          "C": "A semicolon needs a complete clause on its left — the opener has no verb.",
          "D": "A comma after the long introductory phrase shows where the main clause begins."
      },
      "why_correct_md": "A **long introductory phrase** takes a comma before the main clause begins.",
      "why_tempted_md": "Openers without verbs feel too small to deserve punctuation.",
      "rule_md": "After a long opening phrase (four-plus words), set the main clause off with a comma.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6f9c0becf3f197f0",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 2,
      "context_html": "Passage V — A Brief Note on Commas (usage-focused) — Many writers struggle with commas , they are among the trickiest marks of punctuation. A comma can separate items in a list, set off an introductory phrase, or join two clauses with a conjunction. <u>Misusing them, however</u> can confuse a reader. Consider the difference between \"Let's eat, Grandma\" and \"Let's eat Grandma.\" The first invites Grandma to dinner; the second is alarming. Such examples remind us that punctuation, though small, carries real meaning.",
      "stem_md": "Which choice correctly punctuates the underlined conjunctive adverb?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Misusing them, however,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Misusing them however",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Misusing them; however",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "NO CHANGE has only the leading comma; 'however' needs one on each side.",
          "B": "Commas on both sides correctly set off the interrupting 'however'.",
          "C": "No commas at all leaves the conjunctive adverb unpunctuated.",
          "D": "A semicolon wrongly breaks a single clause that has no second independent clause."
      },
      "why_correct_md": "A mid-clause **'however'** is an interrupter — commas on **both** sides: 'Misusing them, however, can confuse.'",
      "why_tempted_md": "The single leading comma looks finished, so the missing second comma is easy to miss.",
      "rule_md": "Rule focus: Conventions (interrupter punctuation)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-85e2987f63fb5449",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 2,
      "context_html": "Passage III — The Mapmaker's Daughter — Marie Tharp was a geologist who helped change how we see the ocean floor. In the 1950s, working alongside her colleague Bruce Heezen, she plotted thousands of depth measurements collected from ships crossing the Atlantic. At the time, many scientists believed the ocean floor was mostly flat. Tharp's maps revealed something remarkable, a vast underwater mountain range running down the middle of the Atlantic. This discovery, which supported the then-controversial theory of continental drift, was at first dismissed by Heezen as \"girl talk.\" <u>Eventually,</u> the evidence became impossible to ignore. Tharp's careful work helped establish the theory of plate tectonics. Today, her once-doubted maps are considered landmarks of earth science.",
      "stem_md": "Which choice correctly punctuates the underlined introductory word?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Eventually",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Eventually;",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Eventually but",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "This option leaves or introduces an error under the tested rule.",
          "B": "\"Eventually\" as a one-word intro takes a comma only if needed; here \"Eventually the evidence…\" is acceptable without — but B (no semicolon, no comma error) is cleanest.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "\"Eventually\" as a one-word intro takes a comma only if needed; here \"Eventually the evidence…\" is acceptable without — but B (no semicolon, no comma error) is cleanest.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Conventions (transition punctuation)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-94e1f8044bd59460",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 2,
      "context_html": "Because the storm had knocked out power across the valley<u> the</u> town meeting moved to the fire hall.",
      "stem_md": "Which choice correctly punctuates the boundary after the opening clause?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "valley, the",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "valley; the",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "valley. The",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "A full dependent clause opens this sentence — running it straight into the main clause hides where one ends and the other begins.",
          "B": "A comma after an introductory dependent clause marks the boundary the reader needs.",
          "C": "A semicolon needs independent clauses on BOTH sides; 'Because ... valley' cannot stand alone.",
          "D": "A period strands 'Because the storm had knocked out power across the valley' as a fragment."
      },
      "why_correct_md": "An introductory dependent clause is set off from the main clause with a **comma**.",
      "why_tempted_md": "Read quickly aloud, the sentence seems to flow fine without any pause.",
      "rule_md": "A dependent clause that OPENS the sentence takes a comma before the main clause — 'Because X happened, Y followed.'",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-df0fe0c126bbe20c",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 2,
      "context_html": "Passage II — The Science of Sourdough — Bread may seem simple, but sourdough is surprisingly complex. Unlike breads made with packaged yeast, sourdough rises using wild yeast and bacteria captured from the air. Bakers maintain a \"starter,\" a mixture of flour and water that they feed regularly. <u>The starter, it ferments</u> over several days. During fermentation, the microbes produce carbon dioxide, which makes the dough rise. They also produce acids, giving sourdough its tangy flavor. Because of these reactions, no two starters taste exactly alike. Some bakers, claim that a starter's flavor reflects the place where it was made. A San Francisco starter, for instance, may taste different from one in Paris. Whether or not that is true, sourdough remains a small marvel of biology and patience.",
      "stem_md": "Which choice best repairs the underlined clause boundary?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "The starter ferments",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "The starter, ferments",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "The starter; it ferments",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "This option leaves or introduces an error under the tested rule.",
          "B": "\"The starter ferments\" removes the comma-splice \"it.\"",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "\"The starter ferments\" removes the comma-splice \"it.\"",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Production (no comma splice/redundant pronoun)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-48ebd8c087d04821",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 3,
      "context_html": "Whiskers meowed until Maya filled the <u>cats</u> bowl.",
      "stem_md": "Which choice punctuates the possessive correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "cats'",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "cat's",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "cats's",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Without an apostrophe, 'cats' is just a plural — nothing shows the bowl belongs to the cat.",
          "B": "The apostrophe after the s claims several cats own the bowl, but only Whiskers is in the sentence.",
          "C": "One cat — Whiskers — owns the bowl, so the singular possessive 'cat's' is correct.",
          "D": "'cats's' is not a standard English form."
      },
      "why_correct_md": "One owner → apostrophe **before** the s: *cat's*.",
      "why_tempted_md": "Plural 'cats' and possessive 'cat's' sound identical aloud, so the missing apostrophe is easy to overlook.",
      "rule_md": "Singular owner → 's; plural owners ending in s → s'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-a37fbfd95df2caef",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 3,
      "context_html": "Our biology teacher<u>, Mr. Alvarez,</u> keeps a terrarium of hissing cockroaches behind his desk.",
      "stem_md": "Which choice punctuates the teacher's name correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", Mr. Alvarez",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Mr. Alvarez,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Mr. Alvarez",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "The name merely renames 'our biology teacher', so a PAIR of commas sets it off.",
          "B": "An interrupter needs commas on both sides — opening one without closing it splices the name into the verb.",
          "C": "Closing the interrupter without opening it makes the comma look like it belongs to the verb phrase.",
          "D": "With no commas the name reads as restrictive — as if several biology teachers had to be told apart."
      },
      "why_correct_md": "A renaming appositive is set off by a **pair of commas** — both sides or neither.",
      "why_tempted_md": "Only one pause is easy to hear aloud, so a single comma feels sufficient.",
      "rule_md": "A nonrestrictive appositive takes commas on BOTH sides; drop both only when the name truly restricts.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-c86b66726f6339df",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 3,
      "context_html": "Rex pulled hard, and the <u>dogs'</u> leash slipped from Maya's hand.",
      "stem_md": "Which choice makes the possessive correct?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "dog's",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "dogs",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "dogss'",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "The apostrophe after the s marks a plural possessive, but only one dog — Rex — is in the sentence.",
          "B": "One dog owns the leash, so the singular possessive 'dog's' is correct.",
          "C": "Without an apostrophe there is no possessive at all — the leash must belong to the dog.",
          "D": "'dogss'' is not a word form in English."
      },
      "why_correct_md": "One owner → apostrophe **before** the s: *dog's*.",
      "why_tempted_md": "Plural and possessive forms sound identical aloud, so the written apostrophe placement is easy to miss.",
      "rule_md": "Singular owner → 's; plural owners ending in s → s'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-eeb2b7c4a9e39f80",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 3,
      "context_html": "The robotics club renamed <u>it's</u> entry an hour before the qualifying round.",
      "stem_md": "Which choice is correct before 'entry'?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "it is",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "its'",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "its",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'It's' means 'it is' — and 'renamed it is entry' collapses.",
          "B": "Expanding the contraction proves it wrong: 'renamed it is entry'.",
          "C": "'Its'' is not a word in any position.",
          "D": "'Its' is the possessive form, written with no apostrophe."
      },
      "why_correct_md": "Possessive 'its' takes **no apostrophe** — the apostrophe version always means 'it is'.",
      "why_tempted_md": "Most possessives DO take apostrophes, so 'it's' looks right.",
      "rule_md": "Test by expanding: if 'it is' fails in the slot, write 'its'.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ef7c83c59dea8738",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 3,
      "context_html": "She pulled on a <u>warm wool</u> sweater and stepped into the sleet.",
      "stem_md": "Which choice handles the adjectives before 'sweater' correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "warm, wool",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "warm, wool,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "warm and wool",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "'Warm' describes the wool sweater as a unit — stacked (cumulative) adjectives take no comma.",
          "B": "The swap test fails ('wool warm sweater'?) — these adjectives aren't coordinate, so no comma.",
          "C": "A comma between the last adjective and its noun is never correct.",
          "D": "'And' only joins adjectives that could trade places — these can't."
      },
      "why_correct_md": "These adjectives **stack**: 'warm' modifies 'wool sweater' as a whole, so no comma.",
      "why_tempted_md": "Two adjectives in a row look like the comma-separated kind at a glance.",
      "rule_md": "Comma only between adjectives that pass the swap/'and' test; cumulative adjectives take none.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0871498e14f92745",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "Marcus finished the marathon<u>, his</u> sister cheered from the finish line.",
      "stem_md": "Which choice best joins the two independent clauses?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ": his",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "; and, his",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "; his",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A comma alone between two independent clauses is a comma splice.",
          "B": "A colon promises that the second clause explains or expands the first; the sister's cheering is a separate event, not an explanation.",
          "C": "A semicolon plus 'and,' piles two joiners (and a stray comma) where one is needed.",
          "D": "A semicolon is the standard way to join two closely related independent clauses."
      },
      "why_correct_md": "Two related independent clauses join with a **semicolon** when no conjunction is used.",
      "why_tempted_md": "The comma splice reads smoothly aloud, so the error hides in plain sight.",
      "rule_md": "Independent clause + independent clause → semicolon, or comma + coordinating conjunction — never a comma alone.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-24344ba26513cfcf",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "Rehearsal ran long<u>, however,</u> nobody left before the final scene was blocked.",
      "stem_md": "Which choice punctuates 'however' between the two statements correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "; however,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "; however",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", however;",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'However' between commas can't hold two clauses together — that's still a splice.",
          "B": "Semicolon before and comma after is how 'however' bridges two clauses.",
          "C": "The comma 'however' takes after itself is missing.",
          "D": "The marks are reversed — the heavy mark goes before the bridge word."
      },
      "why_correct_md": "Clause **; however,** clause — semicolon before, comma after.",
      "why_tempted_md": "'However' feels like 'but', which really does take just a comma.",
      "rule_md": "Conjunctive adverbs (however, therefore, meanwhile) joining clauses take ';' before and ',' after.",
      "item_type": "underlined-span-mc",
      "misconception": "'However' feels like 'but', which really does take just a comma",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-31665b0a1bd7961d",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "The trail's last water source <u>(a spring that runs dry by August</u> sits two miles below the summit.",
      "stem_md": "Which choice handles the parenthetical about the spring correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "(a spring that runs dry by August)",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "a spring that runs dry by August)",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "(a spring that runs dry by August,",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "The opening parenthesis never closes.",
          "B": "Parentheses close what they open — the aside is sealed on both ends.",
          "C": "This closes an aside that never opened.",
          "D": "A comma can't stand in for the closing parenthesis."
      },
      "why_correct_md": "**Parentheses travel in pairs** — every opener needs its closer.",
      "why_tempted_md": "By the end of a long aside it's easy to forget the bracket is still open.",
      "rule_md": "Whatever opens an aside (comma, dash, parenthesis) must be matched at its close.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-3f067badd58987d9",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "The storm knocked out the scoreboard<u>, the</u> referees kept score on a clipboard.",
      "stem_md": "Which choice repairs the join between the two statements?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": " so the",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": " the",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "; the",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A comma alone can't hold two complete thoughts together.",
          "B": "'So' would need a comma before it; bare, it just smears the join.",
          "C": "Removing the comma fuses the sentences outright.",
          "D": "A semicolon joins the two closely related independent clauses."
      },
      "why_correct_md": "Two independent clauses with no conjunction take a **semicolon**.",
      "why_tempted_md": "The clauses are so tightly related that a comma feels sufficient.",
      "rule_md": "Comma-splice fixes: semicolon, period, or comma + FANBOYS — never a comma alone.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-49679201bbbf2fb9",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "The lighthouse<u> built in 1902 by a crew of eleven</u> still guides boats through the narrows.",
      "stem_md": "Which choice sets off the phrase about the lighthouse's construction correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", built in 1902 by a crew of eleven",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ", built in 1902 by a crew of eleven,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": " that was built in 1902 by a crew of eleven,",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Extra history about an already-identified lighthouse needs to be set off.",
          "B": "The interrupter opens with a comma but never closes.",
          "C": "Paired commas mark the phrase as droppable background detail.",
          "D": "'That' frames the detail as restrictive — and still leaves one stray comma."
      },
      "why_correct_md": "The phrase adds droppable background about one specific lighthouse → **paired commas**.",
      "why_tempted_md": "The phrase sits so close to its noun that it feels built in.",
      "rule_md": "Nonrestrictive (extra) modifiers take commas on both sides; restrictive ones take none.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-581a7c98b2ac9090",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
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
              "label": "ingredients; flour",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "ingredients: flour",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "ingredients', flour",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "With no punctuation, the list runs into the noun it names — readers can't tell where 'ingredients' ends and the list begins.",
          "B": "A semicolon separates two independent clauses; it cannot introduce a list.",
          "C": "A colon after a complete statement introduces the list it promises: three ingredients — then names them.",
          "D": "'ingredients'' adds a possessive apostrophe nothing in the sentence calls for."
      },
      "why_correct_md": "A **colon** follows a complete statement to introduce the list it announces.",
      "why_tempted_md": "The sentence reads smoothly aloud, so the missing punctuation is easy to skate past.",
      "rule_md": "Use a colon — never a semicolon — after a complete clause to introduce a list.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-7e0b194c1e8733c7",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "Mr. Okafor<u>, he is the school's athletic trainer,</u> keeps a scrapbook of every season since 1998.",
      "stem_md": "Which choice correctly folds the trainer detail into the sentence?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", the school's athletic trainer,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": " the school's athletic trainer",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", he, the school's athletic trainer,",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Mr. Okafor, he is ...' jams a whole clause where an appositive belongs.",
          "B": "The bare noun phrase renames him cleanly between commas.",
          "C": "Without commas, the phrase collides with the name it renames.",
          "D": "Doubling the subject doubles the clutter."
      },
      "why_correct_md": "To tuck a fact inside a sentence, use an **appositive phrase**, not a full clause.",
      "why_tempted_md": "The original clause is perfectly grammatical — just not inside another sentence.",
      "rule_md": "Rename with a comma-wrapped phrase; save 'he is' for a separate sentence.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-926e040affb783e5",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "<u>Maya and Jonah's</u> podcast about minor-league mascots just passed a hundred episodes.",
      "stem_md": "Which choice is correct for the podcast the two friends share?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Maya's and Jonah's",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Maya's and Jonah",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Maya and Jonahs'",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "One shared podcast → the apostrophe hangs on the LAST owner only.",
          "B": "Separate apostrophes would signal two separate podcasts.",
          "C": "This marks the first owner and strands the second entirely.",
          "D": "'Jonahs'' treats the name as a plural that doesn't exist."
      },
      "why_correct_md": "Joint ownership hangs ONE apostrophe on the **final owner**.",
      "why_tempted_md": "Two owners feel like they deserve two apostrophes.",
      "rule_md": "Shared thing → apostrophe on the last name; separate things → apostrophe on each name.",
      "item_type": "underlined-span-mc",
      "misconception": "two owners feel like they deserve two apostrophes",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-a519014ae187ac76",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "Passage III — The Mapmaker's Daughter — Marie Tharp was a geologist who helped change how we see the ocean floor. In the 1950s, working alongside her colleague Bruce Heezen, she plotted thousands of depth measurements collected from ships crossing the Atlantic. At the time, many scientists believed the ocean floor was mostly flat. Tharp's maps revealed something remarkable, a vast underwater mountain range running down the middle of the Atlantic. <u>This discovery, which supported the then-controversial theory of continental drift,</u> was at first dismissed by Heezen as \"girl talk.\" Eventually, the evidence became impossible to ignore. Tharp's careful work helped establish the theory of plate tectonics. Today, her once-doubted maps are considered landmarks of earth science.",
      "stem_md": "Which choice best handles the underlined parenthetical about the discovery?",
      "choices": [
          {
              "letter": "A",
              "label": "This discovery, which supported the then-controversial theory of continental drift,",
              "is_no_change": false
          },
          {
              "letter": "B",
              "label": "This discovery which supported the then-controversial theory of continental drift",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "This discovery, which supported the then-controversial theory of continental drift",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "This discovery; which supported the then-controversial theory of continental drift,",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "The nonrestrictive clause is correctly set off by a comma on BOTH sides.",
          "B": "With no commas at all, the added detail runs into the sentence unpunctuated.",
          "C": "A leading comma with no closing comma leaves the interrupter half-punctuated.",
          "D": "A semicolon can't attach a dependent 'which' clause; it needs an independent clause."
      },
      "why_correct_md": "A nonrestrictive **'which'** clause is an interrupter — a comma on each side: '..., which supported ..., was ...'.",
      "why_tempted_md": "The single leading comma looks like enough, so the missing closing comma slips by.",
      "rule_md": "Rule focus: Knowledge of Language (NOT-acceptable)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-af86c1bda07ec259",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "The final stretch of the relay<u> the part everyone dreads </u>is a hill with no shade.",
      "stem_md": "Which choice sets off the aside about the relay correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", the part everyone dreads — ",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": " — the part everyone dreads, ",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": " — the part everyone dreads — ",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "The aside needs marks to lift it out of the main sentence.",
          "B": "A comma that opens can't be closed by a dash.",
          "C": "A dash that opens can't be closed by a comma.",
          "D": "Matched dashes frame the interruption on both sides."
      },
      "why_correct_md": "An abrupt aside takes **matched dashes** — the same mark on both sides.",
      "why_tempted_md": "One dash feels dramatic enough, and the closing partner gets forgotten.",
      "rule_md": "Interrupters pair their marks: two commas, two dashes, or two parentheses — never a mix.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ec2124e42f09a80c",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "Every camper packs the same three essentials<u>;</u> water, sun protection, and a whistle.",
      "stem_md": "Which punctuation mark belongs before the list of essentials?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ".",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ",",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ":",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A semicolon needs a complete clause on each side — a list isn't one.",
          "B": "A period strands the list as a fragment.",
          "C": "A comma tangles the list into the clause that announces it.",
          "D": "The complete statement hands off to its promised list with a colon."
      },
      "why_correct_md": "Complete statement + list → **colon** delivers the items the sentence promised.",
      "why_tempted_md": "Semicolons and colons blur together as 'formal marks before lists'.",
      "rule_md": "A colon introduces a list only after a complete statement; a semicolon never introduces a list.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f353d63071548ccf",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 4,
      "context_html": "The <u>dancers costumes</u> hung along the mirror wall, each tagged with a scene number.",
      "stem_md": "Which choice shows that the costumes belong to the dancers?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "dancers' costumes",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "dancer's costumes",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "dancers's costumes",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "Two plain nouns in a row leave the ownership unmarked.",
          "B": "A plural owner ending in s takes its apostrophe after the s.",
          "C": "This puts every costume in the hands of a single dancer.",
          "D": "Adding 's after a plural s ('dancers's') is never correct."
      },
      "why_correct_md": "Plural owners that already end in s add **just the apostrophe**.",
      "why_tempted_md": "The singular 's pattern is so common it gets pasted onto plurals.",
      "rule_md": "Singular owner → 's; plural owners ending in s → s' (apostrophe alone).",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-00d5603f1e869633",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "Passengers<u>, who checked bags,</u> should proceed to carousel four.",
      "stem_md": "Which choice tells only the right passengers to go to carousel four?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", which checked bags,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": " who checked bags",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": " checking bags,",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "The commas make the clause apply to ALL passengers — everyone gets sent to the carousel.",
          "B": "'Which' can't refer to people, and the commas still over-include.",
          "C": "The restrictive clause limits the instruction to passengers who checked bags.",
          "D": "The half-converted participle drags a stray comma with it."
      },
      "why_correct_md": "Dropping the commas makes the clause **restrictive** — only those passengers.",
      "why_tempted_md": "Commas feel harmless, but here they change who is being addressed.",
      "rule_md": "Commas around the clause = applies to all; no commas = only those. Punctuate the MEANING.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-293a6839500a18f6",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "The debate team traveled to Austin<u>, Texas, Portland,</u> Oregon, and Boise, Idaho for the spring circuit.",
      "stem_md": "Which choice keeps the three city-state pairs distinct?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", Texas: Portland,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "; Texas, Portland;",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", Texas; Portland,",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "All-commas makes 'Texas' and 'Portland' read as two separate stops.",
          "B": "A colon can't separate items in a series.",
          "C": "This splits a city from its own state.",
          "D": "Semicolons separate series items that already contain commas."
      },
      "why_correct_md": "When series items contain commas, **semicolons** separate the items.",
      "why_tempted_md": "Plain commas are the series habit even after the items grow internal commas.",
      "rule_md": "Upgrade series separators to semicolons once any item has an internal comma.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-587deb3bbea41fa8",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "It was the current<u> not the wind</u> that pushed the raft off course.",
      "stem_md": "Which choice punctuates the contrast correctly?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", not the wind,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ", not the wind",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "— not the wind",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "The 'not X' contrast is an interrupter and can't run bare into the sentence.",
          "B": "Antithetical phrases are set off by commas on BOTH sides.",
          "C": "Dropping the closing comma splices the contrast into 'that'.",
          "D": "An opening dash with no closing partner leaves the frame unmatched."
      },
      "why_correct_md": "An antithetical phrase ('not the wind') is set off by a **pair of commas**.",
      "why_tempted_md": "The sentence reads smoothly with only the first comma's pause.",
      "rule_md": "Contrastive 'not X' interrupters take commas before AND after.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-88873e730bb625d7",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "Two of the printers jammed before first period<u>,</u> the third ran out of toner by lunch.",
      "stem_md": "Which mark correctly separates the two printer problems?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", moreover",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ":",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ";",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A comma alone splices two complete statements.",
          "B": "'Moreover' after a comma is still a splice; it would need a semicolon in front.",
          "C": "A colon promises that the second clause explains the first — it only adds a parallel mishap.",
          "D": "A semicolon pairs the two related, parallel failures."
      },
      "why_correct_md": "Related complete statements joined without a conjunction take a **semicolon**.",
      "why_tempted_md": "The clauses are short and parallel, so the comma feels light and quick.",
      "rule_md": "Semicolon = related independent clauses, no conjunction; colon = only when the second part explains the first.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-a8faee19068a0769",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "The judges compared <u>Priya and Marcus's</u> essays before choosing a winner.",
      "stem_md": "Which choice is correct for essays each student wrote separately?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Priya's and Marcus's",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Priya and Marcus'",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Priya's and Marcus",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "A single apostrophe on the last name claims one co-written set of essays.",
          "B": "Separately owned essays give EACH owner an apostrophe.",
          "C": "Still one owner marked — and 'Marcus'' drops the s his singular name needs.",
          "D": "The second owner is left with no possessive at all."
      },
      "why_correct_md": "Separately owned things give **each owner** an apostrophe.",
      "why_tempted_md": "The joint-ownership pattern (last name only) gets over-applied to every pair.",
      "rule_md": "Ask shared-or-separate: shared → last owner only; separate → every owner marked.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-a9fe78e59aae3959",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "After the blackout, the theater made one change<u>; battery-powered</u> exit signs in every stairwell.",
      "stem_md": "Which choice correctly introduces what the change was?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ": battery-powered",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ", it added battery-powered",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": " battery-powered",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "A semicolon requires an independent clause on both sides — the right side is a phrase.",
          "B": "The colon presents the change the clause just promised.",
          "C": "'It added ...' after only a comma splices two clauses.",
          "D": "Fusing leaves 'change battery-powered exit signs' unreadable."
      },
      "why_correct_md": "A complete clause announcing something hands off with a **colon** — even to a phrase.",
      "why_tempted_md": "Semicolon and colon look interchangeable at the pivot of a sentence.",
      "rule_md": "Colon: complete clause before, anything after. Semicolon: complete clauses on BOTH sides.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-b848acac3943750d",
      "subject": "act-english",
      "skill_id": "s-punc",
      "difficulty": 5,
      "context_html": "The <u>childrens'</u> mural stretches down the hallway outside the art room.",
      "stem_md": "Which choice is the correct possessive for the young artists?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "children",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "childrens",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "children's",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Childrens' isn't a word — the apostrophe lands after a fake plural.",
          "B": "The bare plural drops the ownership the sentence asserts.",
          "C": "No apostrophe means no possession, and the fake plural remains.",
          "D": "Irregular plurals form possessives with 's, just like singulars."
      },
      "why_correct_md": "Irregular plurals (children, women, mice) form possessives with **'s**, not s'.",
      "why_tempted_md": "The plural-ends-in-s rule (s') gets forced onto plurals that never end in s.",
      "rule_md": "If the plural doesn't end in s, add 's: children's, women's, geese's.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-3b087ff10d6b4c60",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "The abandoned pier stretched into the fog, its planks <u>old</u> and silvered by decades of salt spray.",
      "stem_md": "The writer wants a word that reinforces the eerie, weathered mood. Which choice best does so?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "used",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "weather-beaten",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "aged",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Old' states age plainly without any atmosphere.",
          "B": "'Used' suggests wear from handling, not weathering, and adds no mood.",
          "C": "'Weather-beaten' evokes exposure to the elements, deepening the eerie, storm-worn image.",
          "D": "'Aged' is a small step up from 'old' but still neutral about mood."
      },
      "why_correct_md": "The goal is **mood**, and 'weather-beaten' carries the imagery of long exposure to sea and storm.",
      "why_tempted_md": "'Aged' feels more descriptive than 'old', so it seems like enough of an upgrade.",
      "rule_md": "When the stem asks for a mood or image, pick the word whose connotation paints that picture.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-48ed4ba18f05609d",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "After the flood, neighbors <u>helped</u> one another haul ruined furniture to the curb for weeks.",
      "stem_md": "The writer wants to stress how tirelessly the neighbors worked. Which choice best achieves that?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "assisted",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "were there for",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "labored alongside",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Helped' is accurate but flat — it conveys nothing about effort or endurance.",
          "B": "'Assisted' is even more neutral and formal than 'helped'.",
          "C": "'Were there for' emphasizes emotional support, not hard work.",
          "D": "'Labored alongside' foregrounds sustained, physical effort, exactly the tirelessness the stem asks for."
      },
      "why_correct_md": "The goal is to convey **effort**, and 'labored' names hard, sustained work directly.",
      "why_tempted_md": "Every option is grammatically fine, so the flat synonym 'assisted' looks safe.",
      "rule_md": "For a goal question, grade each choice only against the stated purpose — grammar alone never decides it.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-4b220c8ea4c43178",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "Passage II — The Science of Sourdough — Bread may seem simple, but sourdough is surprisingly complex. Unlike breads made with packaged yeast, sourdough rises using wild yeast and bacteria captured from the air. Bakers maintain a \"starter,\" <u>a mixture of flour and water that they feed regularly.</u> The starter, it ferments over several days. During fermentation, the microbes produce carbon dioxide, which makes the dough rise. They also produce acids, giving sourdough its tangy flavor. Because of these reactions, no two starters taste exactly alike. Some bakers, claim that a starter's flavor reflects the place where it was made. A San Francisco starter, for instance, may taste different from one in Paris. Whether or not that is true, sourdough remains a small marvel of biology and patience.",
      "stem_md": "Which underlined choice conveys the definition most clearly for a general reader?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "a mixture, of flour and water, that they feed on a regular and repeating basis.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "a mixture made of both flour and also water, fed regularly by them.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a mixture of flour and water, which is something they feed regularly and often.",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "Original is the most concise; others are wordy/redundant.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Original is the most concise; others are wordy/redundant.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Knowledge of Language (concision)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-630536b6545d348a",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "The town paper's report on the ceremony noted that the mayor's speech <u>wrapped up</u> with a call for volunteers.",
      "stem_md": "Which choice best suits the article's formal register?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "finished off",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "was done",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "concluded",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Wrapped up' is conversational — out of register in a newspaper report.",
          "B": "'Finished off' is just as casual, with a violent shading besides.",
          "C": "'Was done' is flat and informal, and weakens the sentence's structure.",
          "D": "'Concluded' states the same fact in the neutral, formal register a news report uses."
      },
      "why_correct_md": "Match the diction to the **register** of the surrounding text — formal reporting takes 'concluded'.",
      "why_tempted_md": "The informal options are exactly how the sentence would be spoken aloud.",
      "rule_md": "Identify the passage's register first; then pick the word that belongs to it.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6fee13e7f68d08ea",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "In her thank-you note to the scholarship committee, Dana wrote that their support had <u>meant a ton</u> to her family.",
      "stem_md": "Which choice best fits the sincere yet respectful tone of a thank-you note?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "meant loads",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "been a big deal",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "meant a great deal",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Meant a ton' is casual and a touch flippant for a formal thank-you.",
          "B": "'Meant loads' is informal and better suited to a text than a note to a committee.",
          "C": "'Been a big deal' is conversational and slightly slangy.",
          "D": "'Meant a great deal' is warm and appropriately respectful."
      },
      "why_correct_md": "A thank-you note to a committee wants **respectful warmth**, which 'meant a great deal' delivers.",
      "why_tempted_md": "'Meant a ton' sounds heartfelt, but its casualness undercuts the formal courtesy.",
      "rule_md": "Match the phrasing to both the emotion and the formality the situation calls for.",
      "item_type": "underlined-span-mc",
      "misconception": "'Meant a ton' sounds heartfelt, but its casualness undercuts the form…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-bf29386cecb39137",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "The coach told the rookies that a missed free throw was <u>a bad thing</u> only if they refused to learn from it.",
      "stem_md": "Which choice best fits the coach's encouraging, mentor-like tone?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "a disaster",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "a setback",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a catastrophe",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'A bad thing' is vague and childish, undercutting the mentor's measured tone.",
          "B": "'Disaster' overstates a single miss and clashes with the reassuring message.",
          "C": "'Setback' frames the miss as temporary and surmountable — the encouraging note the coach wants.",
          "D": "'Catastrophe' is hyperbolic, the opposite of the calm reassurance intended."
      },
      "why_correct_md": "The tone is **encouraging**, and 'setback' names a problem while implying it can be overcome.",
      "why_tempted_md": "'Disaster' and 'catastrophe' feel vivid, but their intensity fights the sentence's reassurance.",
      "rule_md": "Match the word's emotional weight to the speaker's intent — don't reach for the most dramatic option.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-dfd75410d01e1797",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "The lifeguard <u>swam</u> toward the struggling swimmer.",
      "stem_md": "The writer wants to emphasize the speed of the rescue. Which choice best accomplishes that goal?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "sprinted through the surf",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "made her way",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "eventually paddled",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Swam' is accurate but neutral — it says nothing about speed.",
          "B": "'Sprinted through the surf' is vivid and fast — exactly the urgency the writer wants.",
          "C": "'Made her way' is leisurely, the opposite of urgent.",
          "D": "'Eventually paddled' makes the rescue sound slow and reluctant."
      },
      "why_correct_md": "When the stem states the writer's goal, pick the choice that **delivers that goal** most strongly.",
      "why_tempted_md": "Accurate-but-bland options like 'swam' feel safe because nothing is wrong with them grammatically.",
      "rule_md": "Goal questions are not grammar questions — grade each choice against the stated purpose alone.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ea7d2862984dd53c",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "The children's picture book explained that when winter comes, the little bear <u>enters a state of dormancy</u> until spring.",
      "stem_md": "Which choice best matches the picture book's audience of young children?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "undergoes seasonal torpor",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "curls up and sleeps",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "reduces its metabolic rate",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Enters a state of dormancy' is technical language a small child won't understand.",
          "B": "'Undergoes seasonal torpor' is even more clinical.",
          "C": "'Curls up and sleeps' is simple, warm, and perfect for young readers.",
          "D": "'Reduces its metabolic rate' is scientific jargon, wrong for the audience."
      },
      "why_correct_md": "A picture book for children needs **simple, concrete language** like 'curls up and sleeps'.",
      "why_tempted_md": "The precise scientific phrasings seem 'more correct', but they miss the young audience entirely.",
      "rule_md": "Register follows audience — for children, choose plain, vivid words over technical accuracy.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f5935917bf02bf12",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 2,
      "context_html": "The grant application stated that the clinic's waiting room was <u>super cramped</u> and needed expansion.",
      "stem_md": "Which choice best matches the formal register of a grant application?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "way too small",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "overcrowded",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a total squeeze",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Super cramped' is casual slang, out of place in a formal application.",
          "B": "'Way too small' is equally colloquial.",
          "C": "'Overcrowded' is precise and formal, fitting the document's register.",
          "D": "'A total squeeze' is idiomatic and informal."
      },
      "why_correct_md": "A grant application requires **formal diction**, and 'overcrowded' is the neutral, professional term.",
      "why_tempted_md": "The casual options feel expressive, but expressiveness isn't what a formal document rewards.",
      "rule_md": "Name the passage's register first, then choose the word that belongs to it.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0965ed6ac4c30558",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "The company's press release announced that after the merger, some employees would <u>get the axe</u> before the end of the quarter.",
      "stem_md": "Which choice best matches the measured, professional tone of a press release?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "be shown the door",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "be let go",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "get canned",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Get the axe' is a harsh idiom unsuited to an official statement.",
          "B": "'Be shown the door' is equally colloquial and blunt.",
          "C": "'Be let go' is the standard, tactful, professional phrasing.",
          "D": "'Get canned' is slang, the least formal option."
      },
      "why_correct_md": "A press release keeps a **professional, tactful register**, which 'be let go' provides.",
      "why_tempted_md": "The idioms are vivid, but vividness reads as unprofessional in a corporate statement.",
      "rule_md": "For official communications, choose the neutral, diplomatic wording over colorful idioms.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-1d1287067e8530e5",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "To persuade the school board, the petition stressed that <u>some people think</u> the crossing is dangerous.",
      "stem_md": "Which choice best strengthens the petition's persuasive appeal?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "three documented accidents this year show",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "it kind of seems like",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a lot of folks feel",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Some people think' is vague opinion that gives the board little reason to act.",
          "B": "Concrete evidence — 'three documented accidents this year' — makes the strongest case.",
          "C": "'It kind of seems like' is tentative and undercuts persuasion.",
          "D": "'A lot of folks feel' is still unsupported opinion, just more casual."
      },
      "why_correct_md": "Persuasion is strongest with **specific evidence** (logos), not vague opinion.",
      "why_tempted_md": "The opinion phrasings feel safe and inoffensive, but they don't move a decision-maker.",
      "rule_md": "To persuade, prefer verifiable facts and figures over hedged 'some people think' claims.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6320e41e5627b12e",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "The nature documentary's narrator called the eagle's dive <u>fast</u>, a plunge that ends in a blur the eye can barely track.",
      "stem_md": "The writer wants to emphasize how astonishing the dive's speed is. Which choice works best?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "quick",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "breathtaking",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "rapid",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Fast' is plain and does nothing to convey astonishment.",
          "B": "'Quick' is if anything weaker than 'fast'.",
          "C": "'Breathtaking' pairs speed with wonder, matching 'a blur the eye can barely track'.",
          "D": "'Rapid' is a formal synonym for fast but still emotionally flat."
      },
      "why_correct_md": "The goal is **astonishment**, and 'breathtaking' fuses the speed with awe.",
      "why_tempted_md": "'Rapid' sounds more sophisticated than 'fast', so it feels like the intended upgrade.",
      "rule_md": "When the aim is to impress or awe, choose the word that adds feeling, not just a fancier synonym.",
      "item_type": "underlined-span-mc",
      "misconception": "'Rapid' sounds more sophisticated than 'fast', so it feels like the i…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-882e189eb5d38d67",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "Dr. Okafor became <u>notorious</u> for her groundbreaking vaccine research.",
      "stem_md": "Which word carries the connotation the sentence needs?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "infamous",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "renowned",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "suspected",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Notorious' means famous for something BAD — it slanders the research it means to praise.",
          "B": "'Infamous' has the same negative charge as 'notorious'.",
          "C": "'Renowned' is fame with a positive glow — right for groundbreaking research.",
          "D": "'Suspected' implies wrongdoing that the sentence never mentions."
      },
      "why_correct_md": "Denotation is 'famous'; the needed **connotation** is positive → *renowned*.",
      "why_tempted_md": "'Notorious' sounds impressive and vaguely means 'well-known'.",
      "rule_md": "Check a word's emotional charge, not just its dictionary meaning, against the sentence's intent.",
      "item_type": "underlined-span-mc",
      "misconception": "'Notorious' sounds impressive and vaguely means 'well-known'",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-8b41ed68ca64cc04",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "The peer-reviewed study reported that the treatment group <u>did way better than</u> the control group across every measure.",
      "stem_md": "Which choice best suits the objective tone of a scientific study?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "outperformed",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "totally crushed",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "beat out",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Did way better than' is casual and imprecise for a research report.",
          "B": "'Outperformed' is precise, neutral, and appropriately formal.",
          "C": "'Totally crushed' is slangy and injects unwanted emotion.",
          "D": "'Beat out' is conversational and less exact than 'outperformed'."
      },
      "why_correct_md": "A scientific study favors **objective, precise diction**, and 'outperformed' states the result cleanly.",
      "why_tempted_md": "'Beat out' is shorter and idiomatic, so it can pass as neutral until you weigh the register.",
      "rule_md": "In objective/academic writing, pick the exact, unemotional verb.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-8f7f2bbc3fc8fffc",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "Writing for an audience of first-time gardeners, the author explained that <u>photosynthetic efficiency governs</u> how fast a seedling grows.",
      "stem_md": "Which choice best suits the beginner audience the passage addresses?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "the plant's ability to turn sunlight into food controls",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "chlorophyll-mediated carbon fixation determines",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "the rate of photosynthate accumulation dictates",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Photosynthetic efficiency governs' is jargon that first-time gardeners won't follow.",
          "B": "Plain phrasing — 'turn sunlight into food' — explains the idea in terms a beginner grasps.",
          "C": "'Chlorophyll-mediated carbon fixation' is even more technical than the original.",
          "D": "'Photosynthate accumulation' is specialist vocabulary, wrong for novices."
      },
      "why_correct_md": "The stem names a **beginner audience**, so the plainest accurate wording wins.",
      "why_tempted_md": "The technical options sound authoritative, which can seem 'more correct' on a test.",
      "rule_md": "Fit the diction to the stated audience — for novices, prefer clarity over technical precision.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
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
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-c42986d0102d9d7d",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "The poem describes the harvest moon as <u>a large orange circle</u> resting on the shoulders of the hills.",
      "stem_md": "The writer wants a vivid figure of speech consistent with the poem's imagery. Which choice is best?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "an orange-colored sphere",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "a big round shape",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a brass coin",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'A large orange circle' is literal and flat — no figurative image.",
          "B": "'An orange-colored sphere' is merely a scientific restatement, not a figure of speech.",
          "C": "'A big round shape' is vaguer than the original, not more vivid.",
          "D": "'A brass coin' is a metaphor whose color and sheen match a harvest moon, extending the poem's imagery."
      },
      "why_correct_md": "The stem asks for a **figure of speech**, and the metaphor 'a brass coin' paints the moon vividly.",
      "why_tempted_md": "'Orange-colored sphere' sounds precise, but precision isn't imagery.",
      "rule_md": "When the goal is figurative vividness, choose the metaphor or simile, not a literal description.",
      "item_type": "underlined-span-mc",
      "misconception": "'Orange-colored sphere' sounds precise, but precision isn't imagery",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-dd0e929d10c612be",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "The history textbook noted that the treaty's terms were <u>a real slap in the face</u> to the smaller nations at the table.",
      "stem_md": "Which choice best fits the neutral, expository tone of a textbook?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "a bum deal for",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "deeply unfavorable to",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a raw deal for",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'A real slap in the face' is a heated idiom that breaks the textbook's neutral tone.",
          "B": "'A bum deal for' is slangy and dismissive.",
          "C": "'Deeply unfavorable to' is measured and expository, matching the register.",
          "D": "'A raw deal for' is idiomatic and informal."
      },
      "why_correct_md": "A textbook aims for **neutral exposition**, so 'deeply unfavorable to' fits where idioms don't.",
      "why_tempted_md": "The idioms convey the unfairness forcefully, but force isn't the textbook's job.",
      "rule_md": "Expository writing stays neutral — replace charged idioms with plain descriptive phrasing.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f42903f54fb3d4b9",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 3,
      "context_html": "The senator's memoir describes her rivals as <u>determined</u> operators who would say anything to win.",
      "stem_md": "Which word best conveys the memoir's clearly critical view of the rivals?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "dedicated",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "scheming",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "spirited",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Determined' is neutral-to-positive and doesn't match 'say anything to win'.",
          "B": "'Dedicated' is admiring, the wrong direction entirely.",
          "C": "'Scheming' carries a distinctly negative charge that fits the critical portrait.",
          "D": "'Spirited' is lively and positive, clashing with the disapproving context."
      },
      "why_correct_md": "The stem signals **criticism**, so choose the word whose connotation is negative — 'scheming'.",
      "why_tempted_md": "'Determined' pairs with 'operators' naturally, hiding that it praises rather than criticizes.",
      "rule_md": "Read the surrounding clues for the writer's stance, then match the word's charge (positive/negative) to it.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-04b3df88a3e00997",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "Compared with the first draft's plain claim that the city was busy, the final essay called downtown <u>a place with a lot going on</u>, drums of traffic and voices layered like a live recording.",
      "stem_md": "The writer wants figurative language that outshines the plain first-draft phrasing. Which choice best does that?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "an active area",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "a restless orchestra",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "a very lively spot",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'A place with a lot going on' is as plain as the first draft it's meant to surpass.",
          "B": "'An active area' is flat, generic, and less vivid, not more.",
          "C": "'A restless orchestra' is a metaphor that matches 'drums of traffic and voices layered like a live recording'.",
          "D": "'A very lively spot' just adds an intensifier without figurative force."
      },
      "why_correct_md": "The stem demands **figurative language**, and 'a restless orchestra' extends the essay's sound imagery.",
      "why_tempted_md": "'A very lively spot' feels like an upgrade because of 'very', but an intensifier isn't imagery.",
      "rule_md": "To surpass plain phrasing, reach for a metaphor tied to the passage's imagery, not a stronger adjective.",
      "item_type": "underlined-span-mc",
      "misconception": "'A very lively spot' feels like an upgrade because of 'very', but an…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-225a988bdbe48711",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "Passage II — The Science of Sourdough — Bread may seem simple, <u>but sourdough is surprisingly complex.</u> Unlike breads made with packaged yeast, sourdough rises using wild yeast and bacteria captured from the air. Bakers maintain a \"starter,\" a mixture of flour and water that they feed regularly. The starter, it ferments over several days. During fermentation, the microbes produce carbon dioxide, which makes the dough rise. They also produce acids, giving sourdough its tangy flavor. Because of these reactions, no two starters taste exactly alike. Some bakers, claim that a starter's flavor reflects the place where it was made. A San Francisco starter, for instance, may taste different from one in Paris. Whether or not that is true, sourdough remains a small marvel of biology and patience.",
      "stem_md": "Which underlined choice best concludes the essay by returning to its opening idea?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE (sourdough remains a small marvel of biology and patience.)",
              "is_no_change": false
          },
          {
              "letter": "B",
              "label": "sourdough is sold in stores.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "people have made bread for centuries.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "flour is a common ingredient.",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "Only A echoes \"may seem simple\" with the \"small marvel\" idea.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Only A echoes \"may seem simple\" with the \"small marvel\" idea.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Production (conclusion tie-back)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-2ec3664d2b4e817b",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "The legal memo advised the client that signing the waiver would <u>pretty much tie your hands</u> in any future dispute.",
      "stem_md": "Which choice best matches the precise, formal tone appropriate to a legal memo?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "seriously limit your options",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "restrict your legal recourse",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "leave you stuck",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Pretty much tie your hands' mixes a hedge ('pretty much') with an idiom, both too casual for a memo.",
          "B": "'Seriously limit your options' is clearer but still colloquial in 'seriously'.",
          "C": "'Restrict your legal recourse' is precise, formal, and uses the exact legal register.",
          "D": "'Leave you stuck' is informal and vague."
      },
      "why_correct_md": "A legal memo demands **precise, formal terminology**, and 'restrict your legal recourse' supplies it.",
      "why_tempted_md": "'Seriously limit your options' feels professional enough, but 'seriously' still lowers the register.",
      "rule_md": "In technical or legal writing, choose the exact domain term over an idiom or hedge.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-49ef4a599004b6c4",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "The eulogy remembered how, in a crowded room, her laughter had always been <u>loud</u>, the first sound anyone noticed and the last they forgot.",
      "stem_md": "The writer wants a description that is affectionate rather than critical. Which choice is best?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "blaring",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "unmistakable",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "noisy",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Loud' is neutral-to-negative and can read as a complaint in a tribute.",
          "B": "'Blaring' is harshly negative, the opposite of affection.",
          "C": "'Unmistakable' turns the volume into something distinctive and cherished — affectionate, as intended.",
          "D": "'Noisy' carries an annoyed connotation."
      },
      "why_correct_md": "The goal is **affection**, and 'unmistakable' recasts the loudness as a beloved, singular trait.",
      "why_tempted_md": "'Loud' is literally accurate, so it seems safe — but in a eulogy it risks sounding like criticism.",
      "rule_md": "Match connotation to the intended feeling; in a tribute, choose the warmly positive word.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-4b2651a209bf761f",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "The travel essay lingered on the market at dawn, where vendors <u>put out</u> pyramids of saffron, mint, and blood oranges under striped awnings.",
      "stem_md": "The writer wants a verb that makes the vendors' display feel vivid and deliberate. Which choice is best?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "arranged",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "had",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "set down",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Put out' is bland and suggests no care or artistry.",
          "B": "'Arranged' implies deliberate, artful placement, matching the vivid pyramids of produce.",
          "C": "'Had' is the flattest possible verb and conveys nothing about the display.",
          "D": "'Set down' suggests dropping items casually, the opposite of a careful display."
      },
      "why_correct_md": "The goal is a sense of **deliberate artistry**, and 'arranged' names purposeful placement.",
      "why_tempted_md": "'Set down' is more specific than 'put out', so it looks like the vivid choice — but it implies carelessness.",
      "rule_md": "Pick the verb whose connotation supplies the exact impression the stem requests.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-64359f35eb3a32c2",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "The obituary honored the volunteer firefighter, noting that for thirty years he had <u>done stuff</u> for a town that never once had to ask.",
      "stem_md": "Which choice best matches the dignified, respectful tone the passage calls for?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "given of himself",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "pitched in",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "lent a hand",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Done stuff' is casual to the point of disrespect in an obituary.",
          "B": "'Given of himself' is elevated and reverent, fitting a tribute to decades of service.",
          "C": "'Pitched in' is warm but too colloquial for the solemn register.",
          "D": "'Lent a hand' is friendly and informal, again below the required dignity."
      },
      "why_correct_md": "The context is an **obituary**, whose reverent register demands elevated diction like 'given of himself'.",
      "why_tempted_md": "'Pitched in' and 'lent a hand' are positive, so they feel appropriate until you weigh the solemn setting.",
      "rule_md": "Let the genre set the register — a tribute or eulogy calls for formal, dignified wording.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-66ffedcdd57fec1a",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "Passage I — Learning to Sail — The summer I turned fourteen, my uncle teached me to sail. His old wooden boat, named the <em>Osprey</em>, had belonged to my grandfather. On our first morning out, the wind was calm, and we drifted lazily across the bay. However, by noon a stiff breeze had risen, and the <em>Osprey</em> leaned hard against it. My uncle showed me how to read the wind by watching the surface of the water. \"Dark patches mean gusts,\" he said, <u>\"and you must be ready.\"</u> At first I was nervous, gripping the lines too tightly. But after an hour, I begun to relax. By the end of the day, I could steer the boat myself. Although I still had much to learn, I felt a new confidence. Sailing, I realized, was not about controlling the wind but about working with it.",
      "stem_md": "Which underlined choice best supports the uncle's warning about sudden gusts?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "\"and the ocean is very large.\"",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "\"and sailing is a popular hobby.\"",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "\"and boats are made of wood.\"",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "Original keeps the practical, instructive voice; others are off-topic. (Form-805 tone item.)",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Original keeps the practical, instructive voice; others are off-topic. (Form-805 tone item.)",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Production (tone/style)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9879e8c22aac3eca",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "The editorial warned that ignoring the levee's cracks was <u>not a good idea</u>, a gamble the city could not afford after two near-floods.",
      "stem_md": "Which choice best conveys the editorial's urgent, cautionary stance?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "reckless",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "less than ideal",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "unwise",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Not a good idea' is mild and conversational, far too weak for a warning.",
          "B": "'Reckless' conveys real danger and blame, matching the urgent 'gamble the city could not afford'.",
          "C": "'Less than ideal' understates the risk almost comically.",
          "D": "'Unwise' is a step up but still restrained for the alarm the passage sounds."
      },
      "why_correct_md": "The stance is **urgent warning**, and 'reckless' carries the force of real, blameworthy danger.",
      "why_tempted_md": "'Unwise' sounds more formal than the original, so it feels sufficient — but it lacks the alarm.",
      "rule_md": "Calibrate intensity to the writer's stance; a cautionary editorial needs a word that signals genuine risk.",
      "item_type": "underlined-span-mc",
      "misconception": "'Unwise' sounds more formal than the original, so it feels sufficient…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-fbd84e33e8d1095c",
      "subject": "act-english",
      "skill_id": "s-rhet",
      "difficulty": 4,
      "context_html": "The scholarship essay closed by describing the applicant's grandmother, whose nightly lessons at the kitchen table were <u>helpful</u> in ways no classroom could match.",
      "stem_md": "The writer wants to convey deep, lasting influence. Which choice best accomplishes that?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "useful",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "nice",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "formative",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Helpful' is generic and understates a life-shaping influence.",
          "B": "'Useful' suggests mere practicality, not deep influence.",
          "C": "'Nice' is weak and vague, conveying no depth.",
          "D": "'Formative' names an experience that shaped who the applicant became — exactly the lasting influence intended."
      },
      "why_correct_md": "The goal is **lasting influence**, and 'formative' means shaping a person's development.",
      "why_tempted_md": "'Useful' feels concrete, but it reduces a profound relationship to convenience.",
      "rule_md": "Choose the word that captures the depth the stem names, not a safe general-purpose synonym.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-38b5fe785ba95a5a",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 1,
      "context_html": "The rain finally <u>stopped the players</u> returned to the field.",
      "stem_md": "Which choice corrects the fused sentence?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "stopped, the players",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "stopped. The players",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "stopped the players,",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Two complete sentences run together with no punctuation at all — a fused sentence.",
          "B": "A comma alone between two independent clauses trades the fused sentence for a comma splice.",
          "C": "A period ends the first complete thought and lets the second begin cleanly.",
          "D": "The comma after 'players' punctuates nothing — the two clauses are still fused."
      },
      "why_correct_md": "Two independent clauses need a real boundary — here, a **period**.",
      "why_tempted_md": "Read quickly, 'the rain stopped the players' parses as one clause, hiding the seam.",
      "rule_md": "Find where one complete thought ends and the next begins; mark that seam with a period, semicolon, or comma + conjunction.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ca301b7240c9a794",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 1,
      "context_html": "The recipe looked simple <u>it took</u> three tries to get right.",
      "stem_md": "Which choice repairs the fused sentence best?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "simple, it took",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "simple it, took",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "simple, but it took",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'The recipe looked simple' and 'it took three tries' are each complete — fused with no punctuation.",
          "B": "A comma with no conjunction leaves a splice.",
          "C": "The comma lands between the subject 'it' and its verb 'took', splitting the wrong pair.",
          "D": "The two thoughts contrast, so comma + 'but' both separates and signals the reversal."
      },
      "why_correct_md": "Comma + a **coordinating conjunction** (here 'but') joins the clauses and shows the contrast.",
      "why_tempted_md": "The sentence reads smoothly, hiding that two full sentences have collided.",
      "rule_md": "Locate where one complete thought ends; mark that seam — a lone comma or nothing won't hold two clauses.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f93b402b9faaa78b",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 1,
      "context_html": "Snow fell all night <u>the plows worked</u> until dawn to clear the pass.",
      "stem_md": "Which choice best fixes the run-on?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "night the plows, worked",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "night; the plows worked",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "night, the plows worked",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Two complete sentences are shoved together with no punctuation at all.",
          "B": "A comma between the subject 'plows' and its verb 'worked' breaks the clause instead of the run-on.",
          "C": "A semicolon links two closely related complete thoughts without a conjunction.",
          "D": "A comma alone between two complete thoughts is a splice."
      },
      "why_correct_md": "A **semicolon** joins two independent clauses that belong together.",
      "why_tempted_md": "The events are so connected that leaving them fused feels natural.",
      "rule_md": "Independent + independent → semicolon, period, or comma + conjunction — never nothing, never a lone comma.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-25b1576fd5f783b9",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 2,
      "context_html": "The power flickered during the storm<u>, the</u> projector shut off mid-scene.",
      "stem_md": "Which choice corrects the run-on between the two statements?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": " and the",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": ", and the",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": " the",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "A comma alone splices 'the power flickered' to 'the projector shut off'.",
          "B": "Dropping the comma before 'and' between two full clauses leaves them under-punctuated.",
          "C": "Comma + 'and' correctly joins the two independent clauses.",
          "D": "Removing all punctuation fuses the two complete thoughts."
      },
      "why_correct_md": "Two independent clauses take a **comma before the coordinating conjunction**.",
      "why_tempted_md": "A single comma looks like enough because a natural pause falls there.",
      "rule_md": "Comma-splice repair: add a conjunction after the comma, or upgrade the comma to a semicolon or period.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-75ffdc935d7018d9",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 2,
      "context_html": "Passage III — The Mapmaker's Daughter — Marie Tharp was a geologist who helped change how we see the ocean floor. In the 1950s, working alongside her colleague Bruce Heezen, she plotted thousands of depth measurements collected from ships crossing the Atlantic. At the time, many scientists believed the ocean floor was mostly flat. Tharp's maps revealed something remarkable, a vast underwater mountain range running down the middle of the Atlantic. This discovery, which supported the then-controversial theory of continental drift, was at first dismissed by Heezen as \"girl talk.\" Eventually, the evidence became impossible to ignore. Tharp's careful work helped establish the theory of plate tectonics. Today, <u>her once-doubted</u> maps are considered landmarks of earth science.",
      "stem_md": "Which choice correctly forms and punctuates the underlined compound modifier?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "her once doubted",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "her once-doubted,",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "hers once-doubted",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "\"once-doubted maps\" correctly hyphenated; no trailing comma.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "\"once-doubted maps\" correctly hyphenated; no trailing comma.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Conventions (hyphenated modifier)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9a237b9f8b5ba000",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 2,
      "context_html": "The museum galleries were packed<u>, we</u> headed to the sculpture garden instead.",
      "stem_md": "Which choice best repairs the comma splice?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", however we",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": " we",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", so we",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A comma alone cannot join two independent clauses — this is a comma splice.",
          "B": "'However' is not a coordinating conjunction; it would need a semicolon before it.",
          "C": "Deleting the comma fuses the clauses — no boundary at all.",
          "D": "Comma + the coordinating conjunction 'so' legally joins the clauses AND names the cause-effect link."
      },
      "why_correct_md": "Comma + **coordinating conjunction** (for, and, nor, but, or, yet, so) is a legal clause joiner.",
      "why_tempted_md": "'However' feels like a conjunction, but it's an adverb — the classic splice non-fix.",
      "rule_md": "Join independent clauses with comma + FANBOYS, a semicolon, or a period — never a bare comma.",
      "item_type": "underlined-span-mc",
      "misconception": "'However' feels like a conjunction, but it's an adverb — the classic…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-010cbb92a190e0e6",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "The waiter served a steak to the guest <u>that was cooked medium-rare.</u>",
      "stem_md": "Which choice places the description next to the word it modifies?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "to the guest, medium-rare being how it was cooked.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "that was cooked medium-rare to the guest.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "to the guest which had been medium-rare.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Placed after 'guest', the clause claims the guest was cooked medium-rare.",
          "B": "The dangling absolute phrase is wordy and still sits away from 'steak'.",
          "C": "Moving the clause beside 'steak' correctly says the steak was cooked medium-rare.",
          "D": "'Which' after 'guest' keeps the description attached to the wrong noun."
      },
      "why_correct_md": "A modifier attaches to the **nearest noun** — put it beside the word it truly describes.",
      "why_tempted_md": "The sentence's meaning is obvious to a human, so the misplacement slips by.",
      "rule_md": "Move a misplaced modifier so it sits directly next to the noun it modifies.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-18702ebe60cf2373",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "<u>Racing to catch the train and forgetting her umbrella on the platform bench.</u>",
      "stem_md": "Which choice turns the fragment into a complete sentence?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Racing to catch the train, and forgetting her umbrella on the platform bench.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "She raced to catch the train, forgetting her umbrella on the platform bench.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Racing to catch the train; forgetting her umbrella on the platform bench.",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "Two '-ing' phrases with no subject and no main verb never form a sentence.",
          "B": "Inserting a comma and 'and' still leaves the string subjectless and verbless.",
          "C": "Adding the subject 'She' and the verb 'raced' supplies a complete main clause.",
          "D": "A semicolon needs a complete clause on each side; both sides here are still fragments."
      },
      "why_correct_md": "A sentence needs a **subject and a finite verb** — an '-ing' phrase alone supplies neither.",
      "why_tempted_md": "The phrase is long and detailed, so it feels like a full sentence.",
      "rule_md": "If the word group has no subject doing a real (finite) verb, it is a fragment — give it one.",
      "item_type": "underlined-span-mc",
      "misconception": "the phrase is long and detailed, so it feels like a full sentence",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-36eb52579d0ef14b",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "<u>Walking to school, the rain soaked Jordan's backpack.</u>",
      "stem_md": "Which revision corrects the modifier error?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "As Jordan walked to school, the rain soaked his backpack.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Walking to school, the rain quickly soaked Jordan's backpack.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Walking to school, Jordan's backpack was soaked by the rain.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Walking to school' has nothing to modify but 'the rain' — and rain doesn't walk.",
          "B": "Rewriting the modifier as a clause with its own subject ('As Jordan walked') puts the walker in the sentence.",
          "C": "Adding 'quickly' changes nothing: the rain is still the one walking.",
          "D": "Now the backpack is walking to school — the modifier still dangles."
      },
      "why_correct_md": "A modifier must attach to the noun that actually performs it — give 'walking' its walker, **Jordan**.",
      "why_tempted_md": "Every option reads smoothly until you ask WHO is walking.",
      "rule_md": "Ask who performs the opening modifier's action; that noun must come immediately after the comma (or be given its own clause).",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-60d11553962fd438",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "Covered in dust and cobwebs, <u>Maya discovered the old bicycle</u> in the back of the shed.",
      "stem_md": "Which choice makes the opening description modify the right noun?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "the old bicycle appeared to Maya",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Maya found that the old bicycle was",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "the old bicycle was discovered by Maya",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "The opening phrase lands on 'Maya', saying she was covered in dust and cobwebs.",
          "B": "'Appeared to Maya' is vague and changes the action from discovering to seeming.",
          "C": "This buries 'bicycle' in a that-clause, so the phrase still points at Maya.",
          "D": "Making 'the old bicycle' the subject right after the comma lets the dusty description land on it."
      },
      "why_correct_md": "The noun an opening modifier describes must be the **subject that follows the comma** — the bicycle, not Maya.",
      "why_tempted_md": "We know the bicycle was dusty, so the sentence 'sounds' fine despite the misattachment.",
      "rule_md": "After an opening descriptive phrase, the very next noun must be the thing it describes.",
      "item_type": "underlined-span-mc",
      "misconception": "we know the bicycle was dusty, so the sentence 'sounds' fine despite…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9b824ee4a3f416d0",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "She <u>almost</u> drove her friends to every practice that season.",
      "stem_md": "Which placement of the modifier fits the sentence's likely meaning?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "drove her friends almost to every practice",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "drove almost her friends to every practice",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "drove her friends to almost every practice",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Almost drove' means she nearly drove but didn't — not the intended sense.",
          "B": "'Almost to every practice' suggests she never quite arrived.",
          "C": "'Almost her friends' nonsensically modifies who the friends were.",
          "D": "'Almost every practice' limits how many practices, which is what the sentence means."
      },
      "why_correct_md": "Place a limiting word like *almost* **directly before the word it limits** — here, 'every practice'.",
      "why_tempted_md": "'Almost' drifts to the front in speech, even when it belongs deeper in the sentence.",
      "rule_md": "only / almost / just / even modify whatever immediately follows them — position them there.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-d695906ab0114f7f",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "<u>Hoping to beat the heat, the hike started before sunrise.</u>",
      "stem_md": "Which revision gives the opening phrase a subject that can perform its action?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Hoping to beat the heat, we started the hike before sunrise.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Hoping to beat the heat, the hike was started before sunrise.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "The hike, hoping to beat the heat, started before sunrise.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "A hike cannot hope — the dangling phrase has no one to attach to.",
          "B": "'We' hoped and 'we' started, so the phrase finally has a doer.",
          "C": "The passive keeps 'the hike' as subject, so the hike is still doing the hoping.",
          "D": "Tucking the phrase mid-sentence still attaches 'hoping' to 'the hike'."
      },
      "why_correct_md": "A dangling modifier needs a **subject capable of the action** placed right after it — a person can hope; a hike cannot.",
      "why_tempted_md": "The intended meaning is clear, so the impossible attachment is easy to miss.",
      "rule_md": "Ask who performs the opening phrase's action; make that noun the subject that follows the comma.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f1a9bd02d9424a66",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 3,
      "context_html": "<u>After studying all weekend, the exam felt easy to Priya.</u>",
      "stem_md": "Which choice corrects the dangling modifier?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "The exam, after studying all weekend, felt easy to Priya.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "After studying all weekend, the exam was easy for Priya.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "After studying all weekend, Priya found the exam easy.",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "The exam did not study all weekend — the phrase dangles.",
          "B": "Relocating the phrase keeps 'the exam' as the studier.",
          "C": "'The exam was easy' still leaves the exam as the one who studied.",
          "D": "'Priya' both studied and found the exam easy, so the modifier attaches correctly."
      },
      "why_correct_md": "The doer of 'studying' (Priya) must be the **subject right after the comma**.",
      "why_tempted_md": "Everyone knows Priya studied, so the sentence feels acceptable as written.",
      "rule_md": "An introductory -ing/-ed phrase modifies the noun that immediately follows it — make that noun the actor.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-31e0a62ecc0b5a4f",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 4,
      "context_html": "A good tour guide is patient, knowledgeable, and <u>speaks with enthusiasm</u>.",
      "stem_md": "Which choice keeps the list of qualities parallel?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "enthusiastic",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "has enthusiasm",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "speaks enthusiastically",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Patient' and 'knowledgeable' are adjectives; 'speaks with enthusiasm' is a verb phrase, breaking the pattern.",
          "B": "'Enthusiastic' is an adjective, matching the first two items.",
          "C": "'Has enthusiasm' is a verb phrase, not an adjective.",
          "D": "'Speaks enthusiastically' is still a verb phrase, out of step with the adjectives."
      },
      "why_correct_md": "Every item in a series must share the **same grammatical form** — three adjectives here.",
      "why_tempted_md": "The verb phrase carries the same idea, so it feels interchangeable with an adjective.",
      "rule_md": "Match each list item to the form the first items set — adjective with adjectives, noun with nouns, verb with verbs.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-65e9643edd0781d7",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 4,
      "context_html": "<u>To qualify for the finals, a clean routine must be landed by every gymnast.</u>",
      "stem_md": "Which revision attaches the infinitive phrase to the ones who must act?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "A clean routine, to qualify for the finals, must be landed by every gymnast.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "To qualify for the finals, a clean routine is what every gymnast must land.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "To qualify for the finals, every gymnast must land a clean routine.",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "A 'clean routine' cannot qualify for the finals; the gymnasts do.",
          "B": "The passive keeps 'a clean routine' as subject, so the phrase still misattaches.",
          "C": "The cleft still leaves 'a clean routine' as the grammatical subject the phrase modifies.",
          "D": "Making 'every gymnast' the subject lets the opening 'to qualify' phrase attach to the ones who act."
      },
      "why_correct_md": "An opening infinitive of purpose ('to qualify…') modifies the **subject that follows** — it must be the one qualifying.",
      "why_tempted_md": "The passive voice sounds formal and 'test-like', masking the misattachment.",
      "rule_md": "After an opening 'to + verb' purpose phrase, name the actor as the subject; avoid a passive that hides them.",
      "item_type": "underlined-span-mc",
      "misconception": "the passive voice sounds formal and 'test-like', masking the misattac…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6cb24370d8242f1b",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 4,
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
              "label": "to communicate",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "communicating",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "they communicated",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'That they communicated' breaks the -ing pattern set by 'practicing' and 'playing'.",
          "B": "The infinitive 'to communicate' mismatches the -ing forms.",
          "C": "'Communicating' matches the two -ing verbs, keeping the series parallel.",
          "D": "'They communicated' inserts a full clause where the series expects a single -ing verb."
      },
      "why_correct_md": "Items in a series must share one grammatical form — here the **-ing** form.",
      "why_tempted_md": "Each option is grammatical in isolation; only the series pattern exposes the mismatch.",
      "rule_md": "Match every item in a list to the form the first items establish (parallel structure).",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-c460b9d55b0b2362",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 4,
      "context_html": "<u>While reviewing the applications, several errors were noticed by the committee.</u>",
      "stem_md": "Which choice fixes the dangling modifier without shifting the meaning?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "Several errors were noticed by the committee while reviewing the applications.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "While reviewing the applications, several errors got noticed by the committee.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "While reviewing the applications, the committee noticed several errors.",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Several errors' were not reviewing the applications; the committee was.",
          "B": "Moving the phrase to the end still leaves 'reviewing' pointing at 'errors'.",
          "C": "Swapping 'were' for 'got' keeps 'errors' as the subject doing the reviewing.",
          "D": "The committee both reviews and notices, so the opening phrase attaches to the right subject."
      },
      "why_correct_md": "The reviewer (the committee) must be the **subject the opening phrase modifies**.",
      "why_tempted_md": "The passive 'were noticed by the committee' names the committee, so it seems attached — but grammatically it isn't the subject.",
      "rule_md": "A 'While + -ing' opener modifies the sentence's subject; make the actor that subject, not a later 'by' phrase.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-cc4452d8304c2c1b",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 4,
      "context_html": "The negotiations dragged on for hours<u>, however, both</u> sides finally signed the agreement.",
      "stem_md": "Which choice correctly punctuates the transition between the two clauses?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", however both",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": " however both",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "; however, both",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'However' is a conjunctive adverb, not a conjunction; a comma before it splices the two complete clauses.",
          "B": "A comma before 'however' still leaves a splice — 'however' cannot join clauses the way 'but' can.",
          "C": "With no punctuation the two complete thoughts fuse.",
          "D": "A semicolon before 'however' and a comma after it correctly links the independent clauses."
      },
      "why_correct_md": "A conjunctive adverb joining two clauses takes a **semicolon before and a comma after**.",
      "why_tempted_md": "'However' feels like 'but', so a comma before it seems to work — but it can't glue clauses.",
      "rule_md": "however / therefore / moreover between two complete clauses ⇒ ; before, , after.",
      "item_type": "underlined-span-mc",
      "misconception": "'However' feels like 'but', so a comma before it seems to work — but…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-edd247e2ef9ff76d",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 4,
      "context_html": "The internship taught her to manage budgets, to draft reports, and <u>public speaking</u>.",
      "stem_md": "Which choice maintains parallel structure in the list?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "how public speaking works",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "she learned public speaking",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "to speak in public",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "The noun phrase 'public speaking' breaks the 'to + verb' pattern set by 'to manage' and 'to draft'.",
          "B": "'How public speaking works' is a clause, not the infinitive the series expects — and it changes the meaning.",
          "C": "'She learned public speaking' inserts a whole new clause into a series of infinitives.",
          "D": "'To speak in public' matches 'to manage' and 'to draft' — three parallel infinitives."
      },
      "why_correct_md": "Every item in the series must repeat the established form — here, the **infinitive** ('to ___').",
      "why_tempted_md": "'Public speaking' is a perfectly natural phrase on its own; only the series pattern exposes it.",
      "rule_md": "Match each list item to the grammatical form the first item establishes.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6ff15380f6fcd522",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 5,
      "context_html": "The new turbines generate more electricity than <u>the old plant</u>, and they do it with half the fuel.",
      "stem_md": "Which choice completes the comparison so like is compared with like?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "the old plant did",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "that of the old plants",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "the old plant's electricity generation was",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "As written, the turbines' electricity is compared to 'the old plant' itself, not to what it generated.",
          "B": "'did' supplies the missing verb, comparing how much the turbines generate to how much the plant generated.",
          "C": "'that of the old plants' is plural and disagrees with the single old plant the sentence names.",
          "D": "This is grammatical but bloated, and the tense 'was' clashes with the active 'generate'."
      },
      "why_correct_md": "Finish the comparison with the **parallel verb** ('did') so 'generate' is measured against 'generated'.",
      "why_tempted_md": "'Than the old plant' sounds complete, hiding that a turbine's output is being set against a building.",
      "rule_md": "Complete a comparison so both sides name the same kind of thing — often by adding the echoing verb (did, does, is).",
      "item_type": "underlined-span-mc",
      "misconception": "'Than the old plant' sounds complete, hiding that a turbine's output…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-888139978be5073c",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 5,
      "context_html": "The pianist's technique is more polished than <u>the other finalists</u>.",
      "stem_md": "Which choice makes the comparison logical?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "the other finalists are",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "that of the other finalists",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "the other finalists' were",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "As written, the sentence compares a TECHNIQUE to PEOPLE — apples to orchestra members.",
          "B": "'Than the other finalists are' still measures the people, not their technique.",
          "C": "'That of the other finalists' compares technique to technique — like to like.",
          "D": "'The other finalists' were' garbles the grammar and shifts tense mid-comparison."
      },
      "why_correct_md": "Comparisons must pair like with like: technique vs **that of** the others.",
      "why_tempted_md": "The shorthand comparison is how people actually talk, so the mismatch hides.",
      "rule_md": "When comparing possessions or attributes, add 'that of' / 'those of' so both sides match.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-8af409b05a85324e",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 5,
      "context_html": "Critics agreed that the sequel's soundtrack was far more inventive than <u>the original film</u>.",
      "stem_md": "Which choice makes the comparison logically consistent?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "in the original film",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "that of the original film",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "the original film was inventive",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "This compares a soundtrack to an entire film, not to the film's soundtrack.",
          "B": "'In the original film' compares the soundtrack to a location, still not to another soundtrack.",
          "C": "'That of the original film' stands in for 'the soundtrack of the original film', matching soundtrack to soundtrack.",
          "D": "Adding 'was inventive' repeats the adjective and produces a lopsided, redundant clause."
      },
      "why_correct_md": "Use **'that of'** so the sequel's soundtrack is compared with the original's soundtrack, not the film.",
      "why_tempted_md": "'Than the original film' is idiomatic-sounding, masking the soundtrack-to-film mismatch.",
      "rule_md": "When comparing an attribute, insert 'that of' / 'those of' so both sides name the same attribute.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-e837d1c29c445707",
      "subject": "act-english",
      "skill_id": "s-sent",
      "difficulty": 5,
      "context_html": "The report explains not only what the drought destroyed <u>but also how communities rebuilt afterward, being resilient.</u>",
      "stem_md": "Which choice makes the two halves of the 'not only … but also' pair parallel?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "but also how communities rebuilt afterward.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "but communities rebuilding afterward with resilience.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "but also the resilient rebuilding done by communities afterward.",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'What the drought destroyed' is a clause; tacking on 'being resilient' unbalances the paired halves.",
          "B": "'How communities rebuilt' mirrors 'what the drought destroyed' — clause matched to clause.",
          "C": "Dropping 'also' breaks the fixed 'not only … but also' pair and switches to a phrase.",
          "D": "The noun phrase 'the resilient rebuilding' no longer matches the 'what …' clause on the other side."
      },
      "why_correct_md": "In 'not only X but also Y', **X and Y must be the same structure** — here, two 'wh-' clauses.",
      "why_tempted_md": "The extra 'being resilient' adds a nice idea, so it's tempting to keep despite breaking the balance.",
      "rule_md": "Correlative pairs (not only/but also, either/or) demand identical grammatical forms on both sides.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0104d697f908031f",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
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
              "label": "get up to rise",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "rise upward",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "rise",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Rise' already means to move up — 'up' repeats it.",
          "B": "'Get up to rise' says the same thing twice in two ways.",
          "C": "'Upward' is the same redundancy in a longer word.",
          "D": "'Rise' alone carries the full meaning."
      },
      "why_correct_md": "The direction is **inside the verb**: rising is upward by definition.",
      "why_tempted_md": "'Rise up' is common in speech and song, so it sounds idiomatic.",
      "rule_md": "Drop particles that repeat the verb's built-in direction (rise up, descend down, return back).",
      "item_type": "underlined-span-mc",
      "misconception": "'Rise up' is common in speech and song, so it sounds idiomatic",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-17fdb4a4ee295f8d",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "Students <u>who are members of</u> the robotics club meet on Tuesdays.",
      "stem_md": "Which choice is most concise while preserving the meaning?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "in",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "who happen to belong to",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "that are being members of",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Who are members of' is grammatical but spends four words on what one preposition can do.",
          "B": "'Students in the robotics club' — same meaning, three words saved.",
          "C": "'Happen to belong to' adds hedging the sentence never asked for.",
          "D": "'That are being members of' is both wordier and ungrammatical."
      },
      "why_correct_md": "The ACT rewards the **shortest choice that keeps the meaning** — here, 'in'.",
      "why_tempted_md": "The longer relative clause sounds more formal and 'complete'.",
      "rule_md": "Try replacing a relative clause with a single preposition; if nothing is lost, the preposition wins.",
      "item_type": "underlined-span-mc",
      "misconception": "the longer relative clause sounds more formal and 'complete'",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-473761e950feceac",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "The detective grew <u>curious</u> when the same gray sedan appeared outside the shop for the third day.",
      "stem_md": "Which word best conveys the wary interest the situation calls for?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "interested",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "nosy",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "suspicious",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Curious' is mild interest, missing the alarm of a car that keeps returning.",
          "B": "'Interested' is even flatter than 'curious'.",
          "C": "'Nosy' implies prying into others' business, the wrong flavor for a detective on alert.",
          "D": "'Suspicious' captures the wary, something-is-wrong reaction the repetition provokes."
      },
      "why_correct_md": "The repeated sedan warrants **wariness**, and only 'suspicious' carries that shade.",
      "why_tempted_md": "'Curious' and 'interested' are true in a loose sense, so they seem adequate.",
      "rule_md": "Pick the related word whose precise connotation fits the situation's emotional cue.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-670a5cc4945b3eb0",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "<u>Due to the fact that</u> the bridge was icy, the road crew closed it overnight.",
      "stem_md": "Which choice trims the wordy opener?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "In light of the fact that",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "Because",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "Being that",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Due to the fact that' spends five words doing one word's job.",
          "B": "'In light of the fact that' is even wordier than the original.",
          "C": "'Because' states the cause directly.",
          "D": "'Being that' is both nonstandard and no shorter in spirit."
      },
      "why_correct_md": "**Because** replaces the five-word scaffold with the one word it means.",
      "why_tempted_md": "The long phrase sounds official, which reads as 'more correct'.",
      "rule_md": "Swap wordy connectors for their one-word equivalents (due to the fact that → because).",
      "item_type": "underlined-span-mc",
      "misconception": "the long phrase sounds official, which reads as 'more correct'",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-6f0cd0d7341e719c",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "After the long climb, the hikers were <u>skinny</u> and ready to collapse in the shade.",
      "stem_md": "Which word best fits the meaning the sentence intends?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "thin",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "spent",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "slim",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Skinny' describes body shape, not the exhaustion the sentence is about.",
          "B": "'Thin' is also about size, missing 'ready to collapse'.",
          "C": "'Spent' means used up and exhausted, which matches collapsing in the shade.",
          "D": "'Slim' likewise refers to being narrow, not tired."
      },
      "why_correct_md": "The context signals **exhaustion**, and among these near-synonyms only 'spent' means worn out.",
      "why_tempted_md": "'Skinny', 'thin', and 'slim' are close cousins, so it's easy to swap one for another.",
      "rule_md": "Related words differ in meaning — pick the one whose sense the sentence actually needs.",
      "item_type": "underlined-span-mc",
      "misconception": "'Skinny', 'thin', and 'slim' are close cousins, so it's easy to swap…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-74185039391e8c26",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "The committee will meet <u>at 9 a.m. in the morning</u> on Thursday.",
      "stem_md": "Which choice cuts the repeated time reference?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "in the morning at 9 a.m.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "at 9 a.m.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "at 9 a.m. in the early morning",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'a.m.' already MEANS morning — 'in the morning' repeats it.",
          "B": "Reordering the phrases doesn't remove the repetition.",
          "C": "'At 9 a.m.' states the time once, completely.",
          "D": "'Early' adds a third layer to the same redundancy."
      },
      "why_correct_md": "'**a.m.**' contains 'morning'; saying both is saying it twice.",
      "why_tempted_md": "The doubled phrase is common in speech, where redundancy aids the listener.",
      "rule_md": "Expand abbreviations mentally (a.m. = morning) to catch hidden repetition.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-87320507356d0f55",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "The referee's <u>firm</u> decision to stop the match drew boos, but replays proved she was right.",
      "stem_md": "Which word best captures a decision that would not be changed?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "hard",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "solid",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "stiff",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "'Firm' means resolute and unwavering — precisely a decision that holds.",
          "B": "'Hard' suggests difficulty or harshness, not resolve.",
          "C": "'Solid' describes reliability of a thing, an awkward fit for 'decision'.",
          "D": "'Stiff' implies rigidity or awkwardness, wrong for a judgment call."
      },
      "why_correct_md": "'Firm' carries the shade of **resolute and final**, which the sentence needs — and it's already correct.",
      "why_tempted_md": "'Hard', 'solid', and 'stiff' all touch firmness physically, so one seems swappable for 'firm'.",
      "rule_md": "Check whether the underlined word already carries the right shade before replacing it.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-97cf1d12c90d64ab",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "The museum's new wing was designed to <u>respect</u> the traditions of the surrounding historic district.",
      "stem_md": "Which word best expresses paying active tribute to those traditions through the design itself?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "notice",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "honor",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "admire",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Respect the traditions' is acceptable but abstract; a building 'honors' traditions more precisely through form.",
          "B": "'Notice' merely means to observe, far too weak.",
          "C": "'Honor' means to embody and pay tribute to, exactly what a sympathetic design does.",
          "D": "'Admire' describes an inward feeling, which a building cannot literally do."
      },
      "why_correct_md": "'Honor' carries the shade of **actively paying tribute**, which a design can do; the others fall short.",
      "why_tempted_md": "'Respect' is a common near-synonym, so leaving it feels safe.",
      "rule_md": "When several related words fit loosely, choose the one whose exact shade the sentence rewards.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9e8e72b34bcb715d",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "The novelist was praised for her <u>childish</u> sense of wonder at the natural world.",
      "stem_md": "Which word best conveys the admiring meaning the sentence intends?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "juvenile",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "immature",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "childlike",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Childish' is an insult, implying petty or silly — wrong for praise.",
          "B": "'Juvenile' also disparages, suggesting silliness.",
          "C": "'Immature' is negative, the opposite of admiration.",
          "D": "'Childlike' admiringly means innocent and openhearted, matching 'praised' and 'wonder'."
      },
      "why_correct_md": "'Childlike' and 'childish' share a root but differ in charge: only **'childlike' is positive**.",
      "why_tempted_md": "The words look almost identical, so the negative one slips in unnoticed.",
      "rule_md": "Related words can carry opposite connotations — match the emotional charge to the context.",
      "item_type": "underlined-span-mc",
      "misconception": "the words look almost identical, so the negative one slips in unnoticed",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-9fb6fd5eaae7fdf9",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
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
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-d177ac4c09a673d3",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 3,
      "context_html": "The twins wore <u>identical matching</u> costumes to the parade.",
      "stem_md": "Which choice eliminates the redundant description?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "identical",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "matching identical",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "identically matching",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Identical' and 'matching' say the same thing — one of them is dead weight.",
          "B": "'Identical' alone carries the full meaning.",
          "C": "Reversing the order keeps both redundant words.",
          "D": "'Identically matching' fuses the two redundancies into one phrase."
      },
      "why_correct_md": "Two words with one meaning → keep **one**.",
      "why_tempted_md": "Doubling adjectives feels emphatic, as if two synonyms are stronger than one.",
      "rule_md": "Cut any word that repeats what a neighboring word already says.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-2e0a772869e0c812",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "The engineer explained that the older bridge design was <u>not very good at</u> handling sudden gusts across the span.",
      "stem_md": "Which choice states the design's shortcoming most precisely?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "unstable in",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "bad with",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "not the best for",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Not very good at' is colloquial and vague about the actual failure mode.",
          "B": "'Unstable in' names the precise engineering problem — instability under wind load.",
          "C": "'Bad with' is casual and imprecise.",
          "D": "'Not the best for' is a soft understatement that hides the real flaw."
      },
      "why_correct_md": "'Unstable' names the **specific technical failure**, unlike the vague hedges.",
      "why_tempted_md": "'Not very good at' sounds appropriately cautious, but caution isn't precision.",
      "rule_md": "In technical description, choose the exact term for the failure over a vague qualifier.",
      "item_type": "underlined-span-mc",
      "misconception": "'Not very good at' sounds appropriately cautious, but caution isn't p…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-2e3eda6d9075d574",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "The surgeon's report noted that the incision had to be <u>very exact</u> to avoid the nerve running beside the joint.",
      "stem_md": "Which choice is the single exact word for the required accuracy?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "precise",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "careful",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "neat",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Very exact' pads an already strong word with a vague intensifier.",
          "B": "'Precise' says exactly what's needed — accurate to a fine tolerance — in one word.",
          "C": "'Careful' describes attitude, not the geometric accuracy of the cut.",
          "D": "'Neat' refers to tidiness, not surgical accuracy."
      },
      "why_correct_md": "'Precise' captures **fine-tolerance accuracy** in a single exact word.",
      "why_tempted_md": "'Very exact' feels emphatic, but the intensifier adds no meaning 'precise' lacks.",
      "rule_md": "Prefer the one word that names the exact quality over an intensifier-plus-adjective.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-60df6286c7916681",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "In her acceptance speech she thanked the mentors who had <u>said good things about</u> her work when no one else would.",
      "stem_md": "Which choice most precisely and concisely expresses their support?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "were nice about",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "liked",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "championed",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Said good things about' is wordy and weak for mentors who backed her against the crowd.",
          "B": "'Were nice about' is vague and casual, understating real advocacy.",
          "C": "'Liked' names a private feeling, not public support.",
          "D": "'Championed' precisely means actively advocated for, matching 'when no one else would'."
      },
      "why_correct_md": "'Championed' packs **active advocacy** into one precise word.",
      "why_tempted_md": "The phrase 'said good things about' sounds specific because it's long, but it's imprecise.",
      "rule_md": "Replace a vague multi-word phrase with the single verb that names the exact action.",
      "item_type": "underlined-span-mc",
      "misconception": "the phrase 'said good things about' sounds specific because it's long…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-742799c550a58e1a",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "The old stone bridge <u>goes over</u> the gorge at a height of ninety meters.",
      "stem_md": "Which choice is the most precise description of the bridge?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "sits over",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "spans",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "happens across",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Goes over' is vague — people go over bridges; bridges do something more specific.",
          "B": "'Sits over' suggests resting on top of something, not stretching across it.",
          "C": "'Spans' is the precise verb for a structure stretching across a gap.",
          "D": "'Happens across' means to encounter by chance — bridges don't do that."
      },
      "why_correct_md": "Precision means the verb built for the job: a bridge **spans** a gorge.",
      "why_tempted_md": "'Goes over' is technically true, and 'true enough' masquerades as 'precise'.",
      "rule_md": "Prefer the specific verb over a general verb + preposition when one exists.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-760a68005523b0ff",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "Passage IV — Night Shift at the Observatory — My first night as a volunteer at the observatory, I expected glamour. Instead, I found cold floors, humming machines, and a long checklist. The astronomer on duty, Dr. Okafor, <u>greeted me warmly but immediately put me to work.</u> Their were dozens of small tasks: calibrating instruments, logging temperatures, and to check the dome's rotation. None of it looked like the dramatic discoveries I had imagined. Yet as the hours passed, I began to understand that this quiet, careful labor was the real work of science. Around 2 a.m., Dr. Okafor called me over. On the screen was a faint smudge of light — a distant galaxy. \"It isn't much to look at,\" she said, \"but light from there left before humans existed.\" In that moment, the cold floors and checklists seemed worth it.",
      "stem_md": "Which underlined choice adds the most relevant detail about the mentor at this point?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "was a tall person with glasses.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "had worked there for many years.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "liked to drink coffee at night.",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "Original best contrasts expectation vs. reality.",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Original best contrasts expectation vs. reality.",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Production (emphasis/contrast)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-89c7ff6378446caf",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "The biographer wrote that the composer <u>made</u> more than forty symphonies before his fortieth birthday.",
      "stem_md": "Which choice is the most precise verb for producing musical works?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "built",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "did",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "composed",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Made' is generic and undersells the craft of writing symphonies.",
          "B": "'Built' suits structures, not symphonies.",
          "C": "'Did' is even vaguer than 'made'.",
          "D": "'Composed' is the exact verb for creating music."
      },
      "why_correct_md": "'Composed' is the **domain-precise verb** for creating musical works.",
      "why_tempted_md": "'Made' is technically true, so it passes unless you reach for the exact term.",
      "rule_md": "Choose the specific verb the field uses over a general-purpose one.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-bdbcbe226d86801b",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "The novel's final chapter<u>, which comes at the end of the book,</u> resolves the mystery.",
      "stem_md": "Which choice best trims the redundant clause?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": ", which is located at the book's end,",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "DELETE the underlined portion",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": ", coming at the end of the book's final pages,",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "A 'final chapter' by definition comes at the end — the clause adds nothing.",
          "B": "Rewording the redundancy doesn't remove it.",
          "C": "Deleting the clause leaves 'The novel's final chapter resolves the mystery' — complete and tighter.",
          "D": "'End of the book's final pages' doubles the redundancy it was meant to fix."
      },
      "why_correct_md": "When a clause restates what 'final' already means, the fix is **deletion**, not rephrasing.",
      "why_tempted_md": "Rewritten versions look like improvements because they change the words — but not the waste.",
      "rule_md": "If a modifier repeats information the noun already carries, delete it entirely.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-d895b6e62645c3d6",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 4,
      "context_html": "Passage II — The Science of Sourdough — Bread may seem simple, <u>but sourdough is surprisingly complex.</u> Unlike breads made with packaged yeast, sourdough rises using wild yeast and bacteria captured from the air. Bakers maintain a \"starter,\" a mixture of flour and water that they feed regularly. The starter, it ferments over several days. During fermentation, the microbes produce carbon dioxide, which makes the dough rise. They also produce acids, giving sourdough its tangy flavor. Because of these reactions, no two starters taste exactly alike. Some bakers, claim that a starter's flavor reflects the place where it was made. A San Francisco starter, for instance, may taste different from one in Paris. Whether or not that is true, sourdough remains a small marvel of biology and patience.",
      "stem_md": "Which underlined choice most precisely completes the contrast the sentence sets up?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "but many people enjoy eating it.",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "but it can be expensive to buy.",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "but bakeries are common.",
              "is_no_change": false
          }
      ],
      "answer_letter": "A",
      "per_choice_rationale": {
          "A": "Only A previews the biological process. (Form-805 intro item.)",
          "B": "This option leaves or introduces an error under the tested rule.",
          "C": "This option leaves or introduces an error under the tested rule.",
          "D": "This option leaves or introduces an error under the tested rule."
      },
      "why_correct_md": "Only A previews the biological process. (Form-805 intro item.)",
      "why_tempted_md": "The original can read smoothly until you apply the rule.",
      "rule_md": "Rule focus: Production (introduction)..",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-0a9808afaaedc6d9",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "The gallery placard noted that the sketches were, so to speak, the artist's <u>day in the sun</u> — quick studies never meant for display.",
      "stem_md": "Which choice replaces the misused idiom with wording that fits the intended meaning?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "raison d'être",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "rough drafts",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "swan song",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Day in the sun' means a moment of glory, contradicting 'never meant for display'.",
          "B": "'Raison d'être' means reason for existing, which quick throwaway studies were not.",
          "C": "'Rough drafts' plainly and correctly describes preliminary studies never meant to be shown.",
          "D": "'Swan song' means a final performance, unrelated to preliminary sketches."
      },
      "why_correct_md": "The sketches were **preliminary**, so 'rough drafts' fits where the glory idiom fails.",
      "why_tempted_md": "A fancy foreign phrase like 'raison d'être' can feel sophisticated enough to be right.",
      "rule_md": "Test an idiom or borrowed phrase against the literal meaning; replace it if the senses clash.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-10f0b02354ecfdf4",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "The chef described the tasting menu as her <u>magnum opus</u>, though she admitted it was just a rough first attempt she might scrap by morning.",
      "stem_md": "Which choice fits the tentative, unfinished nature the sentence describes?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "pièce de résistance",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "trial run",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "tour de force",
              "is_no_change": false
          }
      ],
      "answer_letter": "C",
      "per_choice_rationale": {
          "A": "'Magnum opus' means a crowning masterpiece, contradicting 'rough first attempt'.",
          "B": "'Pièce de résistance' means the standout highlight, again too grand for a draft.",
          "C": "'Trial run' plainly fits a tentative first attempt she might scrap.",
          "D": "'Tour de force' means a feat of brilliance, the opposite of an unfinished experiment."
      },
      "why_correct_md": "The dish is a **tentative draft**, so plain 'trial run' fits where the grand phrases fail.",
      "why_tempted_md": "The elevated phrases sound impressive on a menu, tempting you past their meaning.",
      "rule_md": "When a borrowed superlative clashes with the facts, a plain accurate phrase is the correct fix.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-3d16a3afd16b2422",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "The article called the mayor's abrupt reversal a complete <u>180 degree turn</u> from the position she had defended for years.",
      "stem_md": "Which choice corrects the redundant expression?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "about-face",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "complete 180",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "360 degree turn",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Complete 180 degree turn' is redundant — a 180 is already a complete reversal, and 'complete' repeats it.",
          "B": "'About-face' names a total reversal in one clean term with no redundancy.",
          "C": "'Complete 180' still pairs 'complete' with a figure that already means a full reversal.",
          "D": "A '360 degree turn' returns to the starting point — the opposite of a reversal."
      },
      "why_correct_md": "'About-face' states a **full reversal** without the doubled 'complete' or the mismatched figure.",
      "why_tempted_md": "'180 degree turn' is a familiar way to say reversal, so its built-in redundancy hides.",
      "rule_md": "Cut redundancy in stock phrases, and check that any figure of speech points the right direction.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-c53704861efec902",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "Her memoir revisits, <u>ad nauseam</u>, the single summer that changed everything — each chapter circling back with fresh tenderness.",
      "stem_md": "Which choice best fits the appreciative tone the sentence establishes?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "time and again",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "in perpetuity",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "willy-nilly",
              "is_no_change": false
          }
      ],
      "answer_letter": "B",
      "per_choice_rationale": {
          "A": "'Ad nauseam' means to a sickening excess, clashing with 'fresh tenderness'.",
          "B": "'Time and again' neutrally conveys repeated return, matching the fond, appreciative tone.",
          "C": "'In perpetuity' means forever, a legalistic phrase that doesn't fit revisiting a summer.",
          "D": "'Willy-nilly' means haphazardly, contradicting the deliberate circling back."
      },
      "why_correct_md": "The tone is **affectionate**, so 'time and again' fits where the negative 'ad nauseam' can't.",
      "why_tempted_md": "'Ad nauseam' is a familiar Latin tag for repetition, so it seems apt on the surface.",
      "rule_md": "Weigh a borrowed phrase's connotation against the sentence's tone, not just its literal sense.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-e68996d993ddbf5a",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "The reason the trail closed <u>is because</u> erosion damaged the footbridge.",
      "stem_md": "Which choice corrects the wordy construction after 'reason'?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "is due to the fact that",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "is on account of because",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "is that",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'The reason is because' says 'reason' twice — 'because' already means 'for the reason that'.",
          "B": "'Due to the fact that' swaps one redundancy for five words of another.",
          "C": "'On account of because' stacks two causal phrases — doubly redundant.",
          "D": "'The reason is that' states the cause once, cleanly."
      },
      "why_correct_md": "After 'the reason is', use **that** — 'because' would smuggle in a second 'reason'.",
      "why_tempted_md": "'The reason is because' is extremely common in speech and sounds natural.",
      "rule_md": "Pair 'the reason' with 'that'; pair 'because' with a plain clause — never both.",
      "item_type": "underlined-span-mc",
      "misconception": "'The reason is because' is extremely common in speech and sounds natural",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-f19724b908798592",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "The startup's founders were, in the reporter's words, <u>enfants terribles</u> who quietly followed every industry norm and rarely spoke to the press.",
      "stem_md": "Which choice corrects the expression so it fits the founders described?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "mavericks",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "provocateurs",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "traditionalists",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Enfants terribles' means shocking rule-breakers, contradicting founders who followed every norm.",
          "B": "'Mavericks' means independent nonconformists, contradicting 'followed every industry norm'.",
          "C": "'Provocateurs' means those who deliberately provoke, again the opposite of quiet conformists.",
          "D": "'Traditionalists' matches people who quietly observe industry norms."
      },
      "why_correct_md": "The founders **followed every norm**, so 'traditionalists' fits where the rebel phrase can't.",
      "why_tempted_md": "'Enfants terribles' sounds worldly and startup-flavored, masking that it means the reverse.",
      "rule_md": "Confirm a borrowed phrase's meaning agrees with the surrounding facts before keeping it.",
      "item_type": "underlined-span-mc",
      "misconception": "'Enfants terribles' sounds worldly and startup-flavored, masking that…",
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
  {
      "id": "ti-gen-ffcac62995b325e2",
      "subject": "act-english",
      "skill_id": "s-style",
      "difficulty": 5,
      "context_html": "The critic dismissed the sequel as a <u>fait accompli</u> of clichés, every twist visible from the opening scene.",
      "stem_md": "Which choice corrects the misused expression?",
      "choices": [
          {
              "letter": "A",
              "label": "NO CHANGE",
              "is_no_change": true
          },
          {
              "letter": "B",
              "label": "faux pas",
              "is_no_change": false
          },
          {
              "letter": "C",
              "label": "renaissance",
              "is_no_change": false
          },
          {
              "letter": "D",
              "label": "pastiche",
              "is_no_change": false
          }
      ],
      "answer_letter": "D",
      "per_choice_rationale": {
          "A": "'Fait accompli' means a done deal, which doesn't describe a film full of clichés.",
          "B": "'Faux pas' means a social blunder, not a derivative artwork.",
          "C": "'Renaissance' means a revival, the opposite of a stale sequel.",
          "D": "'Pastiche' means a derivative work stitched from borrowed parts — exactly a predictable cliché-collage."
      },
      "why_correct_md": "'Pastiche' correctly names a **work built from borrowed, familiar parts**, unlike 'fait accompli'.",
      "why_tempted_md": "Both are French borrowings, so one can seem as fitting as the other to an unsure reader.",
      "rule_md": "Match a borrowed expression to its true meaning; sophistication doesn't excuse a misfit.",
      "item_type": "underlined-span-mc",
      "misconception": null,
      "reviewed": true,
      "generated_by": "gpt-4o-mini+gpt-4o>=d2@d5532ef964cc4b0c864e72539eed376c"
  },
];

/** Load the promoted bank into the browser-safe engine DB (composition-only). */
export function seedTestItemBank(db: InMemoryEngineDb): void {
  db.seedTestItems([...TEST_ITEM_BANK]);
}
