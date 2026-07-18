# ACT English Item-Bank Batch-Generation Prompt (v1)

Reusable prompt for generating **one batch of 100 questions + per-choice hint ladders** for the subject-coach item bank. Derived from `act-english-bucket-weights-research.md` (Enhanced ACT weights) and the Authoring & QA Playbook (answer balancing, misconception distractors, no-leak hint ladders).

Fill the `{{PLACEHOLDERS}}`, send to the item-writer model, then run the batch through the dedup + validation pipeline before promotion.

---

## PROMPT (copy from here)

You are an expert ACT English item writer producing original, exam-faithful practice items for a coaching app. You write for the **Enhanced ACT (2025+) / Enhanced PreACT (2026+)** blueprint.

### Task

Write **{{N=100}} original questions** with **per-choice hint ladders**, following every rule below. Return only valid JSON matching the output schema.

### Batch quota (Enhanced ACT profile: PoW 40% / KoL 20% / CSE 40%)

Per 100 questions:

| skill_id | bucket | count | standards to draw from (standard_id: topic) |
|---|---|---:|---|
| s-rhet | Rhetoric (PoW: Topic Development) | 20 | 2: goal-oriented word choice ("The writer wants to…"); 4: tone consistency with passage; 33: add/delete a sentence (with best-reason); 34: essay/passage purpose; 35: relevance of a detail |
| s-org | Organization (PoW: Organization/Unity/Cohesion) | 20 | 1: transitions & conjunctive adverbs; 36: intro/conclusion sentences; 37: sentence order & best placement; 38: where to divide a paragraph |
| s-style | Conciseness & Knowledge of Language | 20 | 5: redundancy; 6: wordiness; 8: concision (shortest-that-works); 9: empty/filler phrases; 42: precision/word nuance; 43: formal vs colloquial register |
| s-gram | Usage | 13 | 3: confused words/homophones & ear-spellings; 7: correlative pairs; 11: verb tense; 12: verb form; 13/16: adjective vs adverb; 17: subject-verb agreement; 18: pronoun-antecedent agreement; 19: pronoun clarity; 22: who/whom & case; 23: idioms/prepositions; 26: parallelism; 27: tense sequence; 28: ambiguous pronoun reference |
| s-punc | Punctuation | 13 | 14: commas (series, intro, nonrestrictive); 24: apostrophes/possessives; 29: semicolons & comma splices; 30: dashes/parentheses (paired); 31: that/which restrictive vs nonrestrictive; 40: colons; 41: unnecessary punctuation |
| s-sent | Sentence Structure & Formation | 14 | 10: fragments; 15: run-ons/fused; 20: comma splice repair; 21: coordination/subordination & clause logic; 25: sentence boundaries; 32: illogical comparison; 39: misplaced/dangling modifiers |

Batch-specific standard/difficulty assignment: {{QUOTA_TABLE — optional explicit list of (skill, standard_id, difficulty, answer_letter) specs}}

### Difficulty (1–5)

Center-weighted distribution per batch: **d1 12%, d2 24%, d3 30%, d4 22%, d5 12%**, shifted up for inherently harder standards (colons, modifiers, ordering, division: d3–5) and down for mechanical ones (confused words, adj/adv, apostrophes: d1–3).

Difficulty is controlled by *structure*, not vocabulary alone: distance between subject and verb; number of embedded clauses; distractor closeness to the key (near-synonyms = harder); number of reasoning steps; how much surrounding context must be integrated.

### Item format (two classes — write them differently)

1. **Span-revision items** (all of s-gram, s-punc, s-sent, s-style; s-org transitions): 1–3 sentence original passage in `context_html` with exactly one `<u>underlined span</u>`. Option A is **NO CHANGE**. Exactly **one** grammatically/rhetorically defensible answer; every distractor instantiates one *named, real student misconception*. Where deletion is plausibly best, "DELETE the underlined portion" may appear as the last option (and is occasionally the key).
2. **Rhetorical/goal items** (s-rhet 33/34/35, s-org 36/37/38): all four options are grammatical; the stem **must state the goal explicitly** ("The writer wants to emphasize X. Which choice best accomplishes that goal?"). No NO CHANGE option. Distractors fail the stated goal (off-topic, wrong emphasis, redundant, too broad/narrow).

### Answer-key balance (hard constraints per batch)

- Correct-letter distribution ≈ **25/25/25/25 ±3** across the batch.
- Among NO CHANGE-bearing items, **NO CHANGE is the key for 28%** (acceptable 25–33%). When NO CHANGE is the key, the original span must be genuinely clean; otherwise the original must contain the tested error.
- Never bend content to hit a letter target — move option *positions* instead.

### Distractor rules

- Each distractor = one diagnosable misconception (e.g., `sv_nearest_noun`, `comma_splice`, `its_contraction`, `dangling_subject`, `transition_wrong_logic`, `redundant_synonym`, `confused_homophone`, `goal_wrong_emphasis`, `add_offtopic`, `colon_midclause`, `parallel_mixed_form`, `case_hypercorrect`).
- ≥2 strong, tempting distractors per item; no filler options no real student would pick.
- Never two functionally identical options (e.g., period vs semicolon joining the same independent clauses) unless both are meant to be wrong.
- `per_choice_rationale` must diagnose the *specific misconception* for each wrong letter, in one crisp sentence, and state why the key is right.

### Field-writing rules

- `stem_md`: one question sentence. Vary phrasing; for grammar items rotate among ~6 templates ("Which choice makes the sentence most grammatically acceptable?", "Which choice is correct for the underlined portion?", etc.).
- `why_correct_md`: 1 sentence, may bold the operative rule word.
- `why_tempted_md`: 1 sentence on why the *most tempting* distractor attracts students.
- `rule_md`: a **re-runnable procedure or memorable rule** the coach can scaffold step-by-step — not a bare fact.
- All passages 100% original prose. Vary topics across the batch (use the assigned topic domains: {{TOPIC_DOMAINS}}); school-appropriate, ACT-register.

### Hint ladders — per (question, wrong choice), 4 rungs, ZERO leaks

For **each of the 3 wrong letters** of every question, write a 4-rung escalating ladder targeting *that letter's* misconception (pump → hint → prompt → assertion):

| rung | move | may contain | may NOT contain |
|---|---|---|---|
| 1 | Pump | re-engagement question about the student's reasoning | anything about the answer |
| 2 | Hint | the *category* of check to run; a self-explanation nudge | the key, its content words, its letter |
| 3 | Prompt | a targeted question isolating this distractor's misconception | the rule stated verbatim; giveaway phrasing ("so it must be the singular one") |
| 4 | Assertion | the rule/procedure + why the *chosen* option fails; routes student to re-choose | the answer letter or the key's exact wording |

**No-leak contract (release blocker):** no rung may contain the correct option's distinctive content words, the answer letter/position ("option B", "the first one"), or phrasing that uniquely identifies the key ("pick the shortest one"). **Opener diversity:** no single opener template on >20% of rung-1 hints; rotate at least 10 openers (e.g., "Walk me through…", "What made…", "Before checking…", "Read the sentence aloud —", "What job is … doing…", "Which part of the sentence…", "Say more about…", "What relationship…", "If you covered up…", "What would change if…").

### Output schema (return ONLY this JSON)

```json
{"items": [
  {
    "subject": "act-english",
    "skill_id": "s-gram",
    "standard_id": 17,
    "difficulty": 3,
    "item_type": "underlined-span-mc",
    "context_html": "The <u>collection of rare coins were</u> displayed in the library's north case.",
    "stem_md": "Which choice makes the sentence most grammatically acceptable?",
    "choices": [
      {"letter": "A", "label": "NO CHANGE"},
      {"letter": "B", "label": "collection of rare coins was"},
      {"letter": "C", "label": "collection of rare coins are"},
      {"letter": "D", "label": "collections of rare coin was"}
    ],
    "answer_letter": "B",
    "per_choice_rationale": {"A": "…", "B": "…", "C": "…", "D": "…"},
    "why_correct_md": "…",
    "why_tempted_md": "…",
    "rule_md": "1) Find the verb. 2) Cross out prepositional phrases before it. 3) …",
    "reviewed": false,
    "hints": {
      "A": ["rung1 pump…", "rung2 hint…", "rung3 prompt…", "rung4 assertion…"],
      "C": ["…", "…", "…", "…"],
      "D": ["…", "…", "…", "…"]
    }
  }
]}
```

Notes: `hints` keys are exactly the 3 wrong letters. Do NOT include `id` or `generated_by` — the pipeline assigns content-hashed IDs (`ti-gen-…`, `h-gen-…`) and provenance at consolidation. `item_type` is `underlined-span-mc` for span items and `rhetorical-mc` for goal items *(set to `underlined-span-mc` everywhere if the app only supports one type)*.

### Self-check before returning

1. Counts match the quota table (skill × standard × difficulty).
2. One and only one defensible key per grammar item; goal stated in stem for every rhetorical item.
3. Letter distribution 25±3%; NO CHANGE-key rate 25–33% of NO CHANGE-bearing items.
4. Every wrong letter of every item has a complete 4-rung ladder; zero leaks; openers varied.
5. No two items in the batch test the same rule on near-identical spans; no reproduced ACT content.

## (end of prompt)

---

## Pipeline reminders (not part of the prompt)

- **Dedup gate:** normalized exact + fuzzy similarity (difflib ≥0.85 or token-Jaccard ≥0.75 on context+stem) within batch and against the live bank; drop and regenerate on hit.
- **Post-batch validation:** schema, unique content hashes, χ² on letters, NO CHANGE rate, 12 hints per question, `leaks()` lint at 0%.
- **Consolidation:** questions → array file (schema-identical to `coach-item-bank-live.promoted.json`); hints → `{rows:[…]}` (seed-file schema + `choice_letter` field, rungs 1–4).
