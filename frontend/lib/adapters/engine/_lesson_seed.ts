/**
 * Hand-authored lesson seed for ONE skill (E1a / ADR-0028 / FR-2).
 *
 * Non-essential commas under the Punctuation bucket (`s-punc`). Copy is
 * human-leak-checked against the E1a design reference — no answer letter is
 * named in teaching prose; `completion_try.choices[].correct` is the only
 * gradable flag and stays local to the inert interactive (D3).
 *
 * Provenance: `generated_from: "hand:<author>@<date>"` — earned by authoring +
 * leak-check, gated by `test_tutorial_provenance_confinement.py`.
 *
 * WHY THE `_` PREFIX. Dev/fixture module (same posture as `_hint_bank.ts`);
 * skipped by the adapter-conformance PAIRS scan.
 *
 * JSON-quoted keys are deliberate: the provenance detector matches the quoted form.
 */

import type { Tutorial } from "../../wire/engine_entities";
import type { InMemoryEngineDb } from "./db/in_memory_engine_db";
import { DEFAULT_SUBJECT } from "../../wire/engine_entities";

const SUBJECT = DEFAULT_SUBJECT; // "act-english"

export const LESSON_SEED: readonly Tutorial[] = [
  {
    "id": "tut-hand-nec-s-punc",
    "subject": SUBJECT,
    "skill_id": "s-punc",
    "body_md":
      "Run the removal test: lift the clause out of the sentence. If it still stands, the clause is non-essential — fence it with a pair of commas. If the clause pins down which thing you mean, it's essential — no commas.",
    "examples": [
      "My kitchen, which provides an alternative to eating out, is small.",
      "The car that I bought is electric.",
    ],
    "generated_from": "hand:rajnish@2026-07-11",
    "reviewed": true,
    "ground_md":
      "You already use commas every day — to list things, to mark a pause, to keep parts of a sentence from colliding. Nothing here is new machinery; it builds on habits you already have.",
    "pitfall_md":
      "But one clause can need a pair of commas while another needs none — and the wrong choice quietly flips what the sentence means. The clauses that catch people cluster right after words like \"which\" and \"who.\"",
    "question_md": "So how do you tell when a clause actually needs its commas?",
    "self_explain_prompt":
      "Before you read the rule — take a guess. When do you think a clause needs commas around it?",
    "worked_example": {
      "sentence": "My kitchen, which provides an alternative to eating out, is small.",
      "steps": [
        "Remove the clause → \"My kitchen is small.\" Still a complete sentence.",
        "So the clause is extra detail — non-essential.",
        "Non-essential → fence it with a pair of commas.",
      ],
      "answer": "Keep both commas.",
    },
    "completion_try": {
      "sentence": "The teacher, who grades fairly, is popular.",
      "choices": [
        { "text": "Keep both commas", "correct": true },
        { "text": "Delete the commas", "correct": false },
      ],
      "why":
        "Remove \"who grades fairly\" → \"The teacher is popular\" still stands, so the clause is non-essential — keep both commas.",
    },
    "annotated_examples": [
      {
        "pre": "My kitchen",
        "clause": "which provides an alternative to eating out",
        "post": " is small.",
        "essential": false,
        "callouts": [
          "remove it → \"My kitchen is small.\" still works",
          "so → fence with a pair of commas",
        ],
      },
      {
        "pre": "The car ",
        "clause": "that I bought",
        "post": " is electric.",
        "essential": true,
        "callouts": ["identifies which car → essential → no commas"],
      },
    ],
  },
];

/** Seed the in-memory engine with the authored lesson row(s). */
export function seedLessonContent(db: InMemoryEngineDb): void {
  for (const t of LESSON_SEED) {
    db.seedTutorial(t);
  }
}
