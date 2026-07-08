/**
 * The ACT-English syllabus plane (D3 syllabus-substrate spec FR-9) —
 * GENERATED FILE — do not edit by hand. Emitted from the canonical
 * docs/plan/act-english-syllabus.seed.json (the human-gated 32-topic
 * extraction of docs/ACT-syllabus/act-english.pdf, brainstorm
 * docs/plan/act-english-full-bank.brainstorm.md). Regenerate (emits this
 * file AND components/act_english_syllabus.py):
 *
 *   .venv/bin/python scripts/emit_syllabus.py
 *
 * DATA PLANE ONLY until the D4 topic-taxonomy spec wires it into the wire
 * kernel and scheduler (docs/plan/act-english-topic-taxonomy.spec.md).
 * Nothing imports this module today; standard names/order for any future
 * surface come from HERE, never a duplicated list.
 */

export interface ActEnglishStandard {
  readonly standard_id: number;
  readonly name: string;
  readonly category: "production" | "knowledge" | "conventions";
  readonly bands: readonly number[];
  readonly app_skill: string;
}

export const ACT_ENGLISH_SYLLABUS: readonly ActEnglishStandard[] = [
  {
      "standard_id": 1,
      "name": "Topic and organization (topic/concluding sentences, transitions, passage development, thesis, argument tracing)",
      "category": "production",
      "bands": [
          1,
          2,
          3,
          4,
          5
      ],
      "app_skill": "s-org"
  },
  {
      "standard_id": 2,
      "name": "Purpose (text purpose, connotation, audience, ethos/pathos/logos)",
      "category": "production",
      "bands": [
          2,
          3,
          4
      ],
      "app_skill": "s-rhet"
  },
  {
      "standard_id": 3,
      "name": "Common word errors",
      "category": "knowledge",
      "bands": [
          1
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 4,
      "name": "Style and tone (formality, tone comparison, figures of speech)",
      "category": "knowledge",
      "bands": [
          2,
          3,
          4
      ],
      "app_skill": "s-rhet"
  },
  {
      "standard_id": 5,
      "name": "Redundancy",
      "category": "knowledge",
      "bands": [
          3
      ],
      "app_skill": "s-style"
  },
  {
      "standard_id": 6,
      "name": "Shades of meaning (related words, connotation)",
      "category": "knowledge",
      "bands": [
          3
      ],
      "app_skill": "s-style"
  },
  {
      "standard_id": 7,
      "name": "Correlative conjunctions",
      "category": "knowledge",
      "bands": [
          3,
          4
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 8,
      "name": "Word nuance (precision, connotation/denotation, revisions)",
      "category": "knowledge",
      "bands": [
          4
      ],
      "app_skill": "s-style"
  },
  {
      "standard_id": 9,
      "name": "Word usage (foreign expressions, related words, redundancy, revisions)",
      "category": "knowledge",
      "bands": [
          5
      ],
      "app_skill": "s-style"
  },
  {
      "standard_id": 10,
      "name": "Joining simple clauses (coordinating/subordinating conjunctions, compound sentences)",
      "category": "conventions",
      "bands": [
          1
      ],
      "app_skill": "s-sent"
  },
  {
      "standard_id": 11,
      "name": "Inappropriate shifts in verb tense",
      "category": "conventions",
      "bands": [
          1,
          2
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 12,
      "name": "Irregular past tense and past participle",
      "category": "conventions",
      "bands": [
          1
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 13,
      "name": "Comparative and superlative adjectives/adverbs",
      "category": "conventions",
      "bands": [
          1,
          3
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 14,
      "name": "Commas (series, dates/places, addresses, introductory, compound/complex, coordinate adjectives, nonrestrictive, antithetical)",
      "category": "conventions",
      "bands": [
          1,
          2,
          3,
          4,
          5
      ],
      "app_skill": "s-punc"
  },
  {
      "standard_id": 15,
      "name": "Sentences, fragments and run-ons",
      "category": "conventions",
      "bands": [
          2,
          3,
          4
      ],
      "app_skill": "s-sent"
  },
  {
      "standard_id": 16,
      "name": "Adjectives vs. adverbs",
      "category": "conventions",
      "bands": [
          2
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 17,
      "name": "Subject-verb agreement (incl. compound subjects, indefinite pronouns)",
      "category": "conventions",
      "bands": [
          2,
          3,
          5
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 18,
      "name": "Pronoun-antecedent agreement",
      "category": "conventions",
      "bands": [
          2
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 19,
      "name": "Frequently confused words",
      "category": "conventions",
      "bands": [
          2,
          5
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 20,
      "name": "Adjective placement",
      "category": "conventions",
      "bands": [
          3
      ],
      "app_skill": "s-sent"
  },
  {
      "standard_id": 21,
      "name": "Misplaced and dangling modifiers",
      "category": "conventions",
      "bands": [
          3,
          4
      ],
      "app_skill": "s-sent"
  },
  {
      "standard_id": 22,
      "name": "Relative pronouns (who/whom/whose/which/that)",
      "category": "conventions",
      "bands": [
          3,
          5
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 23,
      "name": "Idiomatic expressions",
      "category": "conventions",
      "bands": [
          3
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 24,
      "name": "Apostrophes (plural vs possessive, compound/joint possession)",
      "category": "conventions",
      "bands": [
          3,
          4,
          5
      ],
      "app_skill": "s-punc"
  },
  {
      "standard_id": 25,
      "name": "Parallelism / parallel structure",
      "category": "conventions",
      "bands": [
          4,
          5
      ],
      "app_skill": "s-sent"
  },
  {
      "standard_id": 26,
      "name": "Verb and pronoun consistency (shifts in number/person/tense, active vs passive)",
      "category": "conventions",
      "bands": [
          4,
          5
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 27,
      "name": "Verb tense (progressive, perfect, past review)",
      "category": "conventions",
      "bands": [
          4
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 28,
      "name": "Pronouns (vague reference, subject/object, reflexive, who)",
      "category": "conventions",
      "bands": [
          4,
          5
      ],
      "app_skill": "s-gram"
  },
  {
      "standard_id": 29,
      "name": "Colons and semicolons (lists, joining clauses)",
      "category": "conventions",
      "bands": [
          4,
          5
      ],
      "app_skill": "s-punc"
  },
  {
      "standard_id": 30,
      "name": "Parenthetical elements (appositives, dashes, relative-clause combining)",
      "category": "conventions",
      "bands": [
          4
      ],
      "app_skill": "s-punc"
  },
  {
      "standard_id": 31,
      "name": "Restrictive and nonrestrictive elements",
      "category": "conventions",
      "bands": [
          5
      ],
      "app_skill": "s-punc"
  },
  {
      "standard_id": 32,
      "name": "Advanced sentence revision (double/illogical comparisons, modifier + parallel-structure review)",
      "category": "conventions",
      "bands": [
          5
      ],
      "app_skill": "s-sent"
  },
];
