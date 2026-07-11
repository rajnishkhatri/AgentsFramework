---
type: research
title: ACT English Question-Bank Authoring & QA Playbook (Enhanced ACT + PreACT)
description: Authoring and quality-assurance playbook for the ACT English bank — answer balancing, misconception distractors, no-leak hint ladders, and the validation pipeline. The QA discipline the tutorial-generation cascade (Epic E B2) mirrors.
tags: [research, eng-coach, content-generation, qa]
---

# ACT English Question-Bank Authoring & QA Playbook (Enhanced ACT + PreACT Secure)

## TL;DR
- Build a single 1,000+ item bank tagged to the **three official ACT reporting categories** and a **6-bucket drill taxonomy**, then serve it through two switchable weight profiles: `enhanced-act` (Production of Writing 38–43%, Knowledge of Language 18–23%, Conventions 38–43%) and `preact-secure` (Conventions 50–56%, Production 28–33%, Knowledge of Language 14–19%) — both ranges taken verbatim from ACT's official blueprint tables.
- Fix the four identified defects by construction: enforce a **near-uniform answer-key distribution (~25%/option)** and a **NO CHANGE-correct rate of ~25–33%** via a batch-level position-balancing algorithm; encode **every distractor as a documented misconception** with a `misconception_tag`; and attach a **per-(question_id, chosen_letter) escalating hint ladder** (pump→hint→prompt→assertion) with an automated `leaks()` lint.
- Generate at scale with an LLM but gate every item through structural, single-defensible-answer, distractor-functionality, key-balance, NO CHANGE, leakage, duplicate, and reading-level checks, plus an **8-dimension LLM-as-judge** rubric calibrated against a human gold set — because LLM judges correlate poorly (often negatively) with human pedagogy labels and cannot be trusted unsupervised.

## Key Findings

**1. The Enhanced ACT rebalanced English toward rhetoric.** Official ACT blueprint (Table 2, "Comparison of the English Section (Legacy and Enhanced)"): Enhanced ACT English = 50 items in 35 minutes (40 scored + 10 embedded field-test), with reporting-category ranges Production of Writing 38–43% (15–17 items), Knowledge of Language 18–23% (7–9 items), Conventions of Standard English 38–43% (15–17 items). Legacy ACT English = 75 items in 45 min, with Production 29–32% (22–24), Knowledge of Language 15–17% (11–13), Conventions 52–55% (39–41). The headline shift: Conventions dropped from a majority of the section to co-equal with Production, so mastering low-level grammar is no longer "more than half the battle."

**2. PreACT Secure keeps the legacy (Conventions-heavy) weighting.** Per the ACT PreACT Secure Technical Manual, Table 3.2 ("Specification Ranges by Reporting Category for English"), the English test has 48 items (36 scored + 12 field-test) in 35 min, distributed as Production of Writing 28–33% (10–12 items), Knowledge of Language 14–19% (5–7 items), Conventions of Standard English 50–56% (18–20 items). This divergence is exactly why one bank must expose two weight profiles.

**3. NO CHANGE is correct ~25–33% of the time on the real test, not 8%.** Independent analyses of released forms find NO CHANGE correct between ~26.6% and 37.5% across forms; prep consensus (PrepScholar, Piqosity, Albert) is "at least 25%, often more." The prior bank's ~8% NO CHANGE rate (with the skewed key A:16/B:54/C:52/D:49 and NO CHANGE=A in 166/171 items) is a position-bias defect that must be corrected algorithmically.

**4. Assessment literature gives hard design rules.** Haladyna, Downing & Rodriguez (2002, *Applied Measurement in Education* 15(3):309–334) validated a 31-guideline item-writing taxonomy. Rodriguez (2005, *Educational Measurement: Issues and Practice* 24(2):3–13): "More 3-option items can be administered than 4- or 5-option items per testing time while improving content coverage, without detrimental effects on psychometric quality of test scores" — most 4th/5th distractors are non-functional. Tarrant, Ware & Mohammed (2009, *BMC Medical Education* 9:40) define a **non-functioning distractor as one chosen by <5% of examinees**; across 514 items / 2,056 options, "the proportion of items containing 0, 1, 2, and 3 functioning distractors was 12.3%, 34.8%, 39.1%, and 13.8% respectively" — i.e., only 13.8% of four-option items had all three distractors working. Ebel & Frisbie discrimination bands: ≥0.40 excellent, 0.30–0.39 good, 0.20–0.29 marginal, <0.20 poor; negatives flag removal.

**5. Tutoring/feedback science defines the hint ladder.** VanLehn (2011, *Educational Psychologist* 46(4):197–221): intelligent tutoring systems reach **d=0.76** vs. no tutoring for step-based feedback (substep-based d=0.40), "nearly as effective as human tutoring," which the review found to be only **d=0.79** (not the long-assumed d=2.0). AutoTutor's **pump→hint→prompt→assertion** dialogue sequence (Graesser et al.); Hattie & Timperley's feed-up/feed-back/feed-forward; Shute (2008) on elaborated, response-specific feedback; Bisra et al. (2018) self-explanation meta-analysis (g=0.55). MathDial (Macina et al. 2023, arXiv:2305.14536) documents the core anti-pattern: asked to tutor as a teacher, "ChatGPT directly reveals the solution 66% of times and provides incorrect feedback 59% of times." Maurya et al. (2025, MRBench, arXiv:2412.09416) provide an 8-dimension pedagogical rubric (192 instances: 60 Bridge + 132 MathDial) and show that LLM judges (Prometheus2) correlate poorly — often negatively — with human labels.

## Details

### Section 1 — ACT English blueprint (both forms) + switchable weight profiles

**Structure.** Both forms are passage-embedded, editor's-task MC with an underlined/highlighted span or a whole-paragraph/passage prompt; four options; "NO CHANGE" is option A/F on span items. The Enhanced ACT adds an explicit question stem to *every* item and drops "identify the error"/negative framing and explicit idiom testing.

**Official reporting-category elements (ACT):**
- **Production of Writing** → *Topic Development* (purpose of parts, whether a text meets its goal, relevance of material); *Organization, Unity, and Cohesion* (logical order, transitions, effective introductions/conclusions).
- **Knowledge of Language** → precision/concision in word choice; consistency of style and tone.
- **Conventions of Standard English** → *Sentence Structure and Formation*; *Usage*; *Punctuation*.

**6-bucket drill taxonomy mapping:**

| Drill bucket | Maps to reporting category | Element(s) |
|---|---|---|
| Rhetoric (purpose/goal, add-delete, relevance) | Production of Writing | Topic Development |
| Organization (order, transitions, intro/conclusion) | Production of Writing | Organization, Unity, Cohesion |
| Conciseness (redundancy, wordiness) | Knowledge of Language | Precision/concision |
| Style/Tone (word nuance, register) | Knowledge of Language | Style & tone |
| Sentence Structure (fragments, run-ons, comma splices, modifiers, parallelism) | Conventions | Sentence Structure & Formation |
| Punctuation (commas, apostrophes, semicolons, colons, dashes) | Conventions | Punctuation |
| Usage/Grammar (S-V agreement, pronouns, verbs, adj/adv, comparisons) | Conventions | Usage |

Note: Conciseness and Style/Tone both roll up to Knowledge of Language; the 6-bucket scheme splits KoL into two drills for pedagogy while the reporting rollup recombines them.

**Weight-profile spec (target midpoints within official ranges) and item counts at n=1,000:**

| Reporting category | `enhanced-act` % (target) | items @1000 | `preact-secure` % (target) | items @1000 |
|---|---|---|---|---|
| Production of Writing | 40% | 400 | 30% | 300 |
| Knowledge of Language | 20% | 200 | 16% | 160 |
| Conventions of Standard English | 40% | 400 | 54% | 540 |

**Per-bucket targets (derived; keeps each profile inside official category ranges):**

| Drill bucket | `enhanced-act` items | `preact-secure` items |
|---|---|---|
| Rhetoric | 210 | 155 |
| Organization | 190 | 145 |
| Conciseness | 110 | 90 |
| Style/Tone | 90 | 70 |
| Sentence Structure | 150 | 200 |
| Punctuation | 140 | 190 |
| Usage/Grammar | 110 | 150 |
| **Total** | **1000** | **1000** |

Implementation: store *one* pool of ≥1,000 items each tagged with `reporting_category` and `skill_bucket`; the profile is a selector that samples to hit the target percentages. To serve *both* profiles well from one bank, over-build the union: aim for ~1,200–1,300 items so Conventions is deep enough for `preact-secure` (540) while Production is deep enough for `enhanced-act` (400).

### Section 2 — Full standard taxonomy + coverage matrix

**41 granular standards** (id · reporting category · bucket · difficulty band):

*Production of Writing — Rhetoric:*
1. `POW-TD-purpose` essay/passage purpose · d2–5
2. `POW-TD-add` add a sentence for relevance/support · d2–5
3. `POW-TD-delete` delete a sentence (discourse-level relevance/redundancy) · d2–5
4. `POW-TD-goal` "the writer wants to…" accomplish-the-goal · d2–5
5. `POW-TD-relevance` relevance of a detail to focus · d2–4
6. `POW-TD-yesno` yes/no + best-reason justification · d3–5

*Production of Writing — Organization:*
7. `POW-OUC-transition` logical transitions/conjunctive adverbs · d2–5
8. `POW-OUC-order` sentence sequencing within a paragraph · d3–5
9. `POW-OUC-placement` best placement of a given sentence · d3–5
10. `POW-OUC-intro` effective introduction · d2–4
11. `POW-OUC-conclusion` effective conclusion · d2–4
12. `POW-OUC-division` where to divide/start a new paragraph · d3–5
13. `POW-OUC-cohesion` pronoun/lexical cohesion across sentences · d3–5

*Knowledge of Language — Conciseness:*
14. `KOL-CON-redundancy` redundancy elimination · d1–4
15. `KOL-CON-wordiness` wordiness/verbosity · d1–4
16. `KOL-CON-empty` empty/filler-phrase removal · d1–3

*Knowledge of Language — Style/Tone:*
17. `KOL-STY-tone` tone/register consistency · d2–5
18. `KOL-STY-style` stylistic-pattern maintenance · d3–5
19. `KOL-STY-precision` precision/word-choice/word-nuance · d2–5
20. `KOL-STY-formality` formal vs. colloquial appropriateness · d2–4

*Conventions — Sentence Structure & Formation:*
21. `CSE-SS-fragment` fragments · d1–4
22. `CSE-SS-runon` run-ons/fused sentences · d2–4
23. `CSE-SS-commasplice` comma splices · d2–4
24. `CSE-SS-clause` coordination/subordination & clause logic · d2–5
25. `CSE-SS-parallel` parallel structure · d2–5
26. `CSE-SS-modifier` misplaced/dangling modifiers (**Sentence Structure, NOT Organization**) · d3–5
27. `CSE-SS-verbtense` verb tense/sequence consistency · d2–5
28. `CSE-SS-verbform` verb form (participle/infinitive) · d2–4

*Conventions — Usage:*
29. `CSE-US-svagr` subject-verb agreement · d1–5
30. `CSE-US-pronagr` pronoun-antecedent agreement · d1–4
31. `CSE-US-proncase` pronoun case (who/whom, I/me) · d2–5
32. `CSE-US-pronambig` ambiguous/vague pronoun reference · d3–5
33. `CSE-US-adjadv` adjective vs. adverb · d1–3
34. `CSE-US-comparison` comparatives/superlatives & illogical comparison · d2–4
35. `CSE-US-worddiff` commonly confused words (their/there, its/it's, than/then) · d1–3

*Conventions — Punctuation:*
36. `CSE-PU-comma` comma usage (nonrestrictive, series, intro) · d1–4
37. `CSE-PU-apostrophe` apostrophes/possessives · d1–4
38. `CSE-PU-semicolon` semicolons · d2–4
39. `CSE-PU-colon` colons · d3–5
40. `CSE-PU-dashparen` dashes & parentheses (parenthetical pairs) · d2–5
41. `CSE-PU-unnecessary` unnecessary/intrusive punctuation · d2–4

Standards 1–6 and the add/delete pair, essay/passage purpose (1), intro/conclusion (10–11), logical ordering (8), style/tone (17–18), modifier placement (26, correctly under Sentence Structure), colons (39), and precision/word-nuance (19) explicitly fill the gaps flagged as missing/thin in the prior bank analysis.

**Coverage matrix (allocation across standards × difficulty).** Rule: within each standard, distribute items across difficulty 1–5 on a center-weighted curve (roughly 15/25/30/20/10% for d1–d5), then shift the whole curve up for inherently harder standards (colons, modifiers, ordering) and down for mechanical ones (adj/adv, confused words). Example rows (enhanced-act profile):

| Standard | d1 | d2 | d3 | d4 | d5 | total |
|---|---|---|---|---|---|---|
| POW-TD-goal | 0 | 12 | 20 | 16 | 8 | 56 |
| POW-OUC-transition | 4 | 12 | 14 | 10 | 5 | 45 |
| KOL-CON-redundancy | 8 | 12 | 8 | 4 | 0 | 32 |
| CSE-US-svagr | 8 | 14 | 12 | 8 | 3 | 45 |
| CSE-PU-comma | 8 | 14 | 10 | 5 | 0 | 37 |
| CSE-PU-colon | 0 | 3 | 8 | 8 | 5 | 24 |
| CSE-SS-modifier | 0 | 4 | 10 | 10 | 6 | 30 |

Aggregate the per-standard rows to confirm the bucket totals and category percentages in Section 1. For `preact-secure`, apply the same per-standard curves but scale the Conventions standards up (~+35%) and Production standards down (~−25%). Store the target matrix as a config table; the bank-health job (Section 10) diffs live counts against it.

### Section 3 — Item design & writing rules

**Grounding.** Follow the Haladyna/Downing/Rodriguez (2002) 31-guideline taxonomy; use Rodriguez (2005) to justify keeping distractors *functional* rather than padding — but the ACT format is fixed at 4 options, so the operative rule is: **at least 2 strong, misconception-grounded distractors per item; never pad with a 4th non-functional option.**

Rules:
- **Single-skill stem targeting.** Each item's `standard_id` names exactly one primary skill; the correct/incorrect contrast must turn on that skill. No "double-barreled" items where two independent errors must both be fixed.
- **Two item classes, written differently:**
  - *Grammar/usage/mechanics items* — exactly **one defensible correct answer**; distractors are grammatically/mechanically wrong. Stem is often the Enhanced generic "Which choice makes the sentence most grammatically acceptable?"
  - *Rhetorical/goal items* — **all four options are grammatical**; the correct one best serves an explicitly stated purpose. Stem MUST state the goal ("The writer wants to emphasize X. Which choice best accomplishes this?"). Distractors are grammatical but fail the goal (off-topic, wrong emphasis, redundant).
- **Equally-right-equally-wrong guard.** Never let two options be functionally identical (e.g., period vs. semicolon joining the same two independent clauses) unless both are meant to be wrong. An automated check flags option pairs that are grammatically equivalent.
- **Passage-embedded vs. standalone.** Prefer passage-embedded for release-fidelity; standalone (single-sentence) items are acceptable for drilling mechanical standards but must still carry ≥1 sentence of context.
- **ACT conventions.** Underlined-span format; **"NO CHANGE"** as the first option on span-revision items; **"DELETE the underlined portion"** as an option where deletion is plausibly best (a real, occasionally-correct choice, not filler).
- **Originality.** All passages/items must be original prose — never reproduce copyrighted ACT test content.

### Section 4 — Answer-key balancing & position-bias prevention

**The defect.** Prior bank: A:16, B:54, C:52, D:49 with NO CHANGE=A in 166/171 items → NO CHANGE correct ~8% vs. real ~25–33%. This biases learners (teaches "avoid A") and corrupts any model trained/evaluated on the bank (a model can score well by exploiting position priors rather than grammar — a construct-irrelevant shortcut).

**Targets.**
- Correct-answer letter distribution: **~25% each** of A/B/C/D (tolerance ±3 pts at n≥1000; χ² test against uniform, fail if p<0.01).
- **NO CHANGE correct rate: 28% target, acceptable 25–33%.** Applies to the subset of span-revision items that carry a NO CHANGE option (goal/whole-passage items don't).

**Algorithm (batch-level, content-preserving):**
1. Author each item with its correct-answer content and its distractor set, independent of position.
2. For NO CHANGE eligibility: mark whether "no change" is the correct, grammatically-clean original. Target that ~28% of NO CHANGE-bearing items have NO CHANGE as the key; for the rest, the original contains the tested error.
3. Run a constrained assignment/shuffle: treat letter assignment as an optimization that minimizes deviation from uniform key distribution AND the NO CHANGE-rate target, subject to constraints: NO CHANGE (when present) stays in slot A/F; the DELETE option, if present, conventionally sits last; options that must preserve length-ordering for a redundancy item keep their relative order.
4. Re-balance whenever a batch is promoted; recompute global counts and re-shuffle *newly added* items' free positions to pull the aggregate back toward 25/25/25/25.
5. Never change item content or correctness to hit the target — only the *position* of options and the *proportion of items for which the clean original is the key.*

### Section 5 — Distractor design via misconception library

Every distractor encodes one diagnosable error. Tag schema per distractor: `{choice, misconception_tag, error_type, plausibility}`.

**Misconception library (excerpt; extend to all 41 standards):**

| Standard | misconception_tag | error_type (student thinks…) |
|---|---|---|
| S-V agreement | `sv_nearest_noun` | agrees verb with nearest noun, not true subject |
| S-V agreement | `sv_prep_phrase` | treats object of intervening prepositional phrase as subject |
| S-V agreement | `sv_collective` | treats collective noun as plural |
| Verb tense | `tense_local_only` | matches adjacent clause, ignores passage timeline |
| Pronoun case | `case_hypercorrect` | "between you and I" hypercorrection |
| Pronoun ref | `ref_ambiguous_ok` | accepts a pronoun with two possible antecedents |
| Comma | `comma_splice` | joins two independent clauses with a comma |
| Comma | `comma_before_that` | inserts comma before a restrictive clause |
| Apostrophe | `its_contraction` | uses "it's" for the possessive |
| Apostrophe | `plural_apostrophe` | adds an apostrophe to a simple plural |
| Semicolon | `semicolon_fragment` | uses a semicolon before a dependent clause |
| Colon | `colon_midclause` | inserts a colon where no complete clause precedes |
| Modifier | `dangling_subject` | leaves an introductory modifier attached to the wrong subject |
| Parallelism | `parallel_mixed_form` | mixes gerund and infinitive in a series |
| Transition | `transition_wrong_logic` | picks a contrast word for an additive relationship |
| Redundancy | `redundant_synonym` | keeps two synonyms ("annual…yearly") |
| Word choice | `confused_homophone` | their/there, than/then, affect/effect |
| Word choice | `ear_spelling` | "could of" for "could have" |
| Add/delete | `add_offtopic` | adds an accurate-but-irrelevant detail |
| Goal | `goal_wrong_emphasis` | picks a grammatical choice that emphasizes the wrong idea |

Rules:
- **Plausibility.** Each distractor must be tempting to a student who holds the tagged misconception. Avoid options no real student would pick.
- **The <5% rule (Tarrant et al. 2009).** Once usage data exists, any distractor chosen by <5% of examinees is non-functional → revise or replace. Empirically, only 13.8% of four-option items have all three distractors functioning, so aggressive replacement is normal, not exceptional.
- **2 strong beat 3–4 weak.** Rodriguez (2005): a 4th distractor rarely functions. Write 2 high-quality misconception distractors + a 3rd only if genuinely diagnostic; don't manufacture a filler 4th.

### Section 6 — Per-distractor "maximum-signal, no-leak" hint ladder (core deliverable)

**Grounding.** AutoTutor **pump→hint→prompt→assertion**; VanLehn inner loop (per-step scaffolding, d=0.76 for step-based ITS); Hattie & Timperley (feed-up/back/forward); Shute (2008) elaborated, response-specific feedback; least-to-most graduated prompting; self-explanation (Bisra et al. 2018, g=0.55). MathDial/Khanmigo establish the guardrail: never reveal the answer (ChatGPT leaked solutions in 66% of tutoring turns when unconstrained).

**(a) Rung structure & content contract:**

| Rung | Move | May contain | May NOT contain |
|---|---|---|---|
| 0 | **Pump** | generic re-engagement ("Say more about why you picked that.") | any content about the answer |
| 1 | **Hint** | name the *category* of check to run ("Check what the subject of this verb actually is."); a self-explanation prompt | the correct option, its content words, the answer letter |
| 2 | **Prompt** | a targeted question isolating the specific misconception drawn from `per_choice_rationale` ("Is 'data' here singular or plural?") | the fully-stated rule verbatim; the correct answer; a give-away like "so it must be the singular one" |
| 3 | **Assertion** | states the rule/procedure and *why the chosen option is wrong*; still routes the student to re-choose rather than announcing the letter | the answer letter (unless the system has decided to reveal after repeated failure) |

**(b) Key hints on `(question_id, chosen_letter)`, not per question.** Each wrong option has its own ladder targeting *its* misconception (from `per_choice_rationale[chosen_letter]`). A student who chose the comma-splice distractor gets clause-boundary scaffolding; one who chose the redundancy distractor gets a concision prompt. This is the inner-loop, misconception-targeted remediation that distinguishes a coach from an answer key.

**(c) Hard no-leak definition + `leaks()` check.** A rung *leaks* if its text (case/whitespace-normalized) contains: the correct option's content words (minus stopwords/shared words); the answer letter/position ("A", "option B", "the first one"); or an indirect give-away that uniquely identifies the key ("pick the singular verb," "the shortest one is right"). `leaks(text, item)` returns true on any match; it runs on **every rung of every ladder** at generation time and blocks promotion. Target leakage rate: **0%.**

**(d) Keep rung-2 prompts from over-revealing.** Rung 2 asks a *diagnostic question*; it may reference the rule's *topic* but not state the rule as an imperative that resolves the item. Lint: reject rung-2 strings containing the item's correct-answer tokens or an imperative template ("just use…", "the rule is…").

**(e) Opener diversity.** The prior bank had 95% of rung-1 hints starting "What do you think." Enforce an **opener-diversity constraint**: no single rung-1 opener template used by >20% of items; maintain a rotation pool of ≥10 openers per rung; a bank-health metric tracks opener entropy.

**(f) Rules as re-runnable PROCEDURES, not bare facts.** `rule_md` must be a step sequence the coach can scaffold one step at a time — e.g., S-V agreement: (1) Find the verb; (2) Cross out any prepositional phrase after the noun before it; (3) Identify the true subject; (4) Decide singular/plural; (5) Match the verb. A procedure gives rungs 1–3 distinct steps to reveal progressively; a bare fact ("subjects and verbs must agree") forces reveal-or-restate with no middle ground.

**(g) Worked examples.**

*Example A — S-V agreement (`CSE-US-svagr`, `sv_prep_phrase`).* Stem: "The **collection** of rare coins **were** displayed…" Student picks distractor "were displayed" (misconception: verb agrees with "coins").
- Rung 0: "Walk me through why you chose 'were.'"
- Rung 1: "Before checking the verb, make sure you've found the real subject of this sentence."
- Rung 2: "There's a phrase between the subject and the verb — 'of rare coins.' What's the actual noun doing the being-displayed?"
- Rung 3: "'Collection' is the subject; 'of rare coins' is just a prepositional phrase. A singular subject needs a singular verb. Which option matches a singular subject?" (still no letter)

*Example B — Transition (`POW-OUC-transition`, `transition_wrong_logic`).* Two sentences in an additive relationship; student picks "However."
- Rung 0: "What relationship did you see between these two sentences?"
- Rung 1: "Name the logical relationship first: is the second sentence *contrasting* the first, or *adding* to it?"
- Rung 2: "The second sentence gives another example in the same direction. Does 'however' signal same-direction or opposite-direction?"
- Rung 3: "These sentences build in the same direction, so you need an additive transition, not a contrast one. Reconsider your choice."

*Example C — Add-a-sentence (`POW-TD-add`, `add_offtopic`).* Goal stem: the paragraph is about *bee navigation*; student picks a sentence adding an accurate fact about *honey production*.
- Rung 0: "Why does that sentence feel like it belongs here?"
- Rung 1: "Check the paragraph's focus before deciding — what one idea is every other sentence about?"
- Rung 2: "Your sentence is true, but is honey production the same topic as how bees find their way?"
- Rung 3: "A detail can be accurate and still not belong if it's off the paragraph's focus. This paragraph is about navigation. Does the sentence you picked keep that focus?"

### Section 7 — Difficulty calibration

**A priori difficulty (1–5) drivers:** linguistic complexity of the sentence; distractor closeness to the key (near-synonym distractors = harder); sentence length & clause embedding (distance between subject and verb, number of intervening phrases); number of solution steps (a 1-step comma rule = easy; a modifier item requiring a full clause re-parse = hard); how much passage context must be integrated (span-local = easier, cross-paragraph = harder).

**Difficulty ramp for adaptive sequencing:** within a standard, order items d1→d5; mastery-gate advancement (Section 9). Early rungs of a standard use d1–d2 to build the procedure; d4–d5 add distractor closeness and embedding.

**Empirical validation (once usage data exists):**
- *p-value (difficulty)* = proportion correct; target spread 0.30–0.90; mastery items may sit 0.80–1.00, discriminating items 0.30–0.70.
- *Discrimination:* point-biserial, or D = P(upper 27%) − P(lower 27%) (Kelley's 27% rule). Ebel & Frisbie bands: ≥0.40 excellent, 0.30–0.39 good, 0.20–0.29 marginal/review, <0.20 poor; **negative → pull the item.**
- *Non-functioning distractor detection:* any distractor <5% selection → revise.
- Reconcile a-priori vs. empirical difficulty; large mismatches trigger review.

**Pre-calibration heuristics (before data):** score each item on the five drivers above (1–5 each), average, and bin; require sign-off from a second reviewer for any d4–d5 item, since inflated difficulty ratings are the most common a-priori error.

### Section 8 — LLM-assisted generation + automated validation pipeline

**Generation prompt pattern (per target `(standard, difficulty, misconception-set)`):**
```
Role: expert ACT English item writer.
Target: standard=CSE-US-svagr, difficulty=3, reporting_category=Conventions,
         bucket=Usage.
Write an ORIGINAL passage-embedded item (no copyrighted ACT content).
Underline one span. Provide 4 options; option A = NO CHANGE.
The correct answer must be the ONLY grammatically defensible option.
Each distractor MUST instantiate one misconception from this set:
  [sv_nearest_noun, sv_prep_phrase, sv_collective].
Return JSON: stem, passage, options[], answer_letter, per_choice_rationale{},
  misconception_tag per distractor, rule_md (as numbered PROCEDURE),
  why_correct_md, why_tempted_md, hints{chosen_letter:{rung0..3}}.
Difficulty controls: place an intervening prepositional phrase between subject
  and verb; distractor 'were' agrees with the nearest plural noun.
```
Control difficulty by dictating structural features (embedding, distractor closeness). Force misconception-grounded distractors by passing the tag set and requiring a tag per distractor. Use **overgenerate-and-rank** (Feng et al. 2024; McNichols et al. 2023): generate n candidates and rank/filter against the misconception library — because LLMs reliably generate valid distractors but are "less adept at anticipating common errors or misconceptions among real students," ranking is essential.

**Validation gates (every item must pass before promotion):**
1. **Structural schema validation** — all required fields present & typed.
2. **Exactly-one-defensible-answer** — an independent solver LLM + rule checks confirm one and only one option is defensible (reject if 0 or ≥2).
3. **Distractor plausibility / misconception coverage** — each distractor carries a valid `misconception_tag`; ≥2 strong distractors.
4. **Answer-key position balancing** — batch χ² against uniform (Section 4).
5. **NO CHANGE rate** — running rate stays in 25–33%.
6. **`leaks()` lint** — on all hint rungs of all ladders.
7. **Duplicate/near-duplicate detection** — embedding cosine similarity against the existing bank; flag > threshold (e.g., 0.92) for human review.
8. **Reading-level/register checks** — passage grade level and formality within the ACT band.
9. **LLM-as-judge acceptance rubric** (item quality + hint pedagogy), borrowing MRBench's 8 dimensions: (1) mistake identification, (2) mistake location, (3) revealing of the answer (must be "No"), (4) providing guidance, (5) actionability, (6) coherence, (7) tutor tone, (8) human-likeness.
10. **Human-in-the-loop triggers** — route to human review when: any judge dimension falls below threshold; a duplicate flag fires; the single-defensible-answer check disagrees; a new standard or the first N items of a batch; or empirical stats fall out of band after deployment.

**LLM-judge reliability caveat & calibration.** Maurya et al. (2025) found Prometheus2's pedagogical annotations correlate poorly — often negatively — with human labels on MRBench across the eight dimensions, so the judge cannot be trusted unsupervised. Calibrate: maintain a human-annotated **gold set** (≥100–200 items/hints across standards), measure judge–human agreement (Cohen's κ / correlation) per dimension, auto-accept only on dimensions where agreement is adequate, and route the rest to humans. Re-calibrate on any judge/base-model upgrade. Note that item-correctness gates (single-defensible-answer) are inherently more reliable than pedagogy-quality gates.

### Section 9 — Metadata schema & adaptive sequencing

**Per-item schema:**
```json
{
  "id": "eng-000123",
  "subject": "english",
  "skill_bucket": "Usage",
  "standard_id": "CSE-US-svagr",
  "reporting_category": "Conventions of Standard English",
  "difficulty": 3,
  "weight_profiles": ["enhanced-act","preact-secure"],
  "passage": "…",
  "stem": "Which choice makes the sentence most grammatically acceptable?",
  "options": {"A":"NO CHANGE","B":"…","C":"…","D":"…"},
  "answer_letter": "C",
  "per_choice_rationale": {"A":"…","B":"…","C":"…","D":"…"},
  "misconception_tags": {"A":"sv_prep_phrase","B":"sv_collective","D":"sv_nearest_noun"},
  "error_types": {"A":"…","B":"…","D":"…"},
  "rule_md": "1. Find the verb… 2. Cross out prepositional phrases… …",
  "rule_type": "procedure",
  "why_correct_md": "…",
  "why_tempted_md": {"A":"…","B":"…","D":"…"},
  "hints": {
    "A": {"rung0":"…","rung1":"…","rung2":"…","rung3":"…"},
    "B": {"…"}, "D": {"…"}
  },
  "has_no_change": true,
  "has_delete_option": false,
  "stats": {"p_value": null, "point_biserial": null, "distractor_pct": {}}
}
```

**Outer-loop selection** uses `reporting_category` + `weight_profiles` for content balancing to the active profile; `difficulty` for targeting; `standard_id` for mastery-gating (advance a standard only after k consecutive corrects at difficulty ≥ target); spacing/interleaving across standards and buckets to avoid blocking. **Inner-loop coaching** uses `per_choice_rationale[chosen_letter]` + the keyed `hints[chosen_letter]` ladder + the `rule_md` procedure to remediate the specific misconception. This is a direct implementation of VanLehn's two-loop architecture: the outer loop selects the next task; the inner loop scaffolds each step.

### Section 10 — QA checklist & bank-health metrics

| Metric | Target / threshold | Remediation if breached |
|---|---|---|
| Category coverage vs. active profile | within ±2 pts of profile target per category | generate/retire items in under/over-filled category |
| Per-standard coverage | ≥ matrix target (no standard <60% of target) | commission items for thin standards |
| Answer-key letter distribution | 25% ±3 pts; χ² p≥0.01 | re-run position-balancing shuffle |
| NO CHANGE-correct rate | 28% (25–33%) | rebalance the NO CHANGE-key proportion |
| Distractor functionality | <5% of distractors non-functional (each <5% selection) | revise/replace flagged distractors |
| Difficulty distribution per standard | matches target curve (±1 item/cell) | add items at missing difficulty cells |
| Duplicate/near-duplicate rate | <2% of pairs above cosine 0.92 | merge/retire duplicates |
| Hint leakage rate | **0%** (`leaks()` must pass) | block item; regenerate hint |
| Hint opener diversity | no opener >20% of items; entropy above floor | rotate opener templates |
| Rule-type mix | ≥80% procedures (vs. bare fact) | rewrite fact rules as procedures |
| Per-distractor hint completeness | 100% of wrong options have a full rung 0–3 ladder | generate missing ladders |
| Point-biserial (post-deployment) | ≥0.20; pull negatives | review/retire low-discrimination items |

## Recommendations

**Stage 0 — Schema & config first (week 1–2).** Freeze the metadata schema (Section 9), the 41-standard taxonomy + misconception library (Sections 2, 5), and the two weight-profile config tables + coverage matrix (Sections 1–2). Build `leaks()`, the schema validator, and the position-balancer as standalone, unit-tested functions before generating at scale.

**Stage 1 — Golden seed set (week 3–5).** Hand-author or heavily human-edit ~150 items spanning every standard × difficulty, with full misconception tags and hint ladders. This becomes both the **few-shot prompt library** and the **human gold set** for judge calibration. Do not scale generation until the judge's per-dimension agreement with this gold set is measured.

**Stage 2 — Generate-and-gate to 1,000+ (week 6–12).** Run the overgenerate-and-rank pipeline per `(standard, difficulty, misconception-set)`; enforce all 10 gates; require human review on every item until the false-accept rate on audited samples is <5%, then move to sample-auditing. Balance keys and NO CHANGE at each batch promotion.

**Stage 3 — Deploy, then calibrate empirically (ongoing).** Once ≥200 responses/item accrue, compute p-value, point-biserial, and distractor selection; retire negatives, revise non-functioning distractors, and reconcile a-priori vs. empirical difficulty.

**Benchmarks that change the plan:**
- If judge–human κ <0.4 on a dimension → keep that dimension fully human-reviewed.
- If NO CHANGE rate drifts outside 25–33% or key χ² fails → halt promotion until rebalanced.
- If a standard's mean point-biserial <0.20 → freeze it for redesign.
- If duplicate rate >2% → raise the similarity threshold and prune before adding more.
- If hint leakage >0% in any audit → treat as a release blocker, not a warning.

## Caveats
- **Percentage midpoints are design choices inside official ranges.** ACT publishes *ranges* (e.g., Production 38–43%); the single-number targets (40%, 20%, 40%) are my allocation to hit those ranges, not ACT-published points. Independent analyses of released Enhanced forms (Piqosity) suggest Production/Organization may run near the top of its range (~half the section), so audit against real released forms and adjust.
- **PreACT Secure figures are from the current (2026-dated) ACT technical manual** at the ACT URL; ACT replaced the file at that path, so an older "legacy" edition may differ slightly. The three-category structure and the Conventions-heavy weighting (50–56%) are stable and match the legacy ACT English profile.
- **NO CHANGE ~25–33%** comes from prep-provider analyses of released forms plus ACT's statement that "many questions offer NO CHANGE"; ACT does not publish an official NO CHANGE-correct frequency. Treat 28% as a defensible engineering target, not an ACT specification.
- **LLM-as-judge is emerging and contested.** The poor (often negative) judge–human correlation finding (MRBench) is recent; do not over-automate pedagogy acceptance. Correctness gates are more reliable than pedagogy-quality gates.
- **Three-options-optimal (Rodriguez 2005) is well-established, but the ACT format is fixed at four options**, so apply it as "make ≥2 distractors truly functional; never pad," not as "drop to 3 options."
- **d=0.76 (ITS, step-based) and d=0.79 (human tutoring) from VanLehn (2011), and g=0.55 (self-explanation, Bisra et al. 2018)** are meta-analytic effects from other domains (physics, math, statistics); they justify the scaffolding design but are not ACT-English-specific evidence.
- **The Tarrant et al. (2009) distractor-functionality statistics** come from health-science MCQs; the <5% non-functioning threshold is domain-general and widely applied, but exact functioning rates on ACT-English items will differ and should be measured on your own usage data.