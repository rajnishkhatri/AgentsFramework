# Gen2 quality follow-up — leak repair + Z1.4 acceptance sampling

Generated 2026-07-17 · follows `synthetic-data-pipeline` Steps 3→5 · corpus:
`research/synthetic_data_pipeline_handover/docs/questionbank/coach-item-bank-gen2.promoted.json`
+ `coach-bank-hints-gen2.json` · prior scorecard: `docs/questionbank/coach-bank-gen2-qa-report.md`.

> **Law:** `reviewed=true` is earned only at Step 5 acceptance sampling. This doc plans repair + sampling; it does not promote.

---

## A. Leak-repair plan (30 items / 35 hint hits)

Re-lint used the checked-in predicate `components.hint_leakage.check_rung_leakage` against every Gen2 hint.
Result: **35 hits across 30 items (3.0%)**. Under c=0 these are critical — quarantine from the acceptance lot until repaired and re-linted green.

### A.1 Disposition

| Bucket | Items | Action |
|---|---:|---|
| A — rewrite (recital) | 13 | Rewrite flagged rung(s); re-run leak lint |
| A — rewrite (quote label) | 14 | Rewrite flagged rung(s); avoid key-label embedding |
| A — rewrite (assertive, likely real) | 1 | Rewrite to remove letter reveal |
| B — recheck FP | 2 | Human confirms; rewrite opener if FP, else treat as A |
| **Total quarantine** | **30** | Stay `reviewed=false`; excluded from AQL lot until green |

### A.2 Repair procedure (per item)

1. Load item + its 12 hints; edit **only** the flagged `(choice_letter, rung)` rows listed below (unless a rewrite forces ladder coherence changes).
2. Re-run `check_rung_leakage(body, item)` on **all 12** hints for that item (regression on siblings).
3. Also re-check rung-4 never quotes the key label (normalized, len≥6) and never assertive-names the key letter.
4. Keep `reviewed=false`. Do not touch `generated_by`.
5. After all 30 are green, re-run the full Step-3 gate set on the lot (leak + dedup vs *today’s* live bank) before Step 5.

**Rewrite recipes**

- **why_correct_recital:** rung 4 may name the *rule/procedure* and why the *chosen distractor* fails; it must not recycle ≥80% of `why_correct_md` content words. Prefer: name the test → apply to the distractor → “re-choose.”
- **quote_label:** if the key is a short word (`return`, `finished`, `because`), discuss the *property* (“direction already inside the verb”) without embedding the key surface form; quote the *distractor* wording instead.
- **assertive_letter:** ban “answer/correct/pick/choose/select + key letter.” Sentence-initial “A …” when key=A is a known lint false-positive — rewrite to “The …” / “Any …” rather than waiving.

### A.3 Item tickets

| question_id | skill | d | key | classes | flagged rungs | action |
|---|---|---:|---|---|---|---|
| `ti-gen-7b69ae0f83310c12` | s-org | 3 | D (`Coral bleaching unfolds in stages, each `) | assertive_letter | Br3 | rewrite_assertive |
| `ti-gen-41dcd251ddce7265` | s-gram | 2 | D (`winding`) | quote_label | Br3 | rewrite_quote |
| `ti-gen-c67b10fd632d6801` | s-gram | 4 | D (`flashed`) | quote_label | Br3 | rewrite_quote |
| `ti-gen-2de182a5812c71c7` | s-org | 4 | C (`Sentence 4`) | quote_label | Dr1 | rewrite_quote |
| `ti-gen-b76fdeb9c3cce36e` | s-org | 4 | A (`Sentence 4`) | quote_label | Cr1 | rewrite_quote |
| `ti-gen-1a827341845d348b` | s-punc | 4 | D (`must bring`) | quote_label | Ar3 | rewrite_quote |
| `ti-gen-9dc5902d366e222f` | s-punc | 2 | B (`wanted`) | quote_label | Cr3,Dr4 | rewrite_quote |
| `ti-gen-f5f46cf813260d1a` | s-punc | 4 | D (` sacks of grain, boxed rations, and a bu`) | quote_label | Br3 | rewrite_quote |
| `ti-gen-3c570ac19b6c03e6` | s-style | 2 | C (`before`) | quote_label | Ar1 | rewrite_quote |
| `ti-gen-6ce1824d9d1c682e` | s-style | 1 | C (`because`) | quote_label | Dr3 | rewrite_quote |
| `ti-gen-8014f7bd65dd1add` | s-style | 3 | B (`finished`) | quote_label | Ar3,Cr3,Cr4,Dr3 | rewrite_quote |
| `ti-gen-b8067145180c87a5` | s-style | 2 | C (`at night`) | quote_label | Ar3 | rewrite_quote |
| `ti-gen-b83b0f5d79a219f8` | s-style | 4 | C (`now scarce`) | quote_label | Dr3 | rewrite_quote |
| `ti-gen-bab2d25358817f93` | s-style | 2 | B (`collaborate`) | quote_label | Ar1 | rewrite_quote |
| `ti-gen-d6571d2d53b36fc3` | s-style | 1 | C (`return`) | quote_label | Ar3,Dr3 | rewrite_quote |
| `ti-gen-54d1e04fc64fc59f` | s-gram | 4 | C (`supplies`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-8026889d0496f2cc` | s-gram | 5 | C (`reports`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-9430a02f91aeb502` | s-gram | 1 | A (`NO CHANGE`) | why_correct_recital | Br4 | rewrite_recital |
| `ti-gen-aef13fb2e7641129` | s-gram | 4 | C (`was`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-af28702318d403e6` | s-org | 2 | B (`As a result,`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-624805558434ba37` | s-punc | 2 | D (`After the rain stopped, birders gathered`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-79e23eca45d07dfe` | s-punc | 3 | D (`flavor is`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-85a7f2259e04e208` | s-punc | 4 | D (`—a bundle of thousands of pencil-thin wi`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-c06011f4e642c4d6` | s-punc | 2 | A (`NO CHANGE`) | why_correct_recital | Dr4 | rewrite_recital |
| `ti-gen-b81966658a7e0cdf` | s-rhet | 4 | B (`stark`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-466117fc76ab1be0` | s-sent | 4 | D (`the planners were frustrated by the low `) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-49aca528aa893263` | s-style | 4 | A (`NO CHANGE`) | why_correct_recital | Br4 | rewrite_recital |
| `ti-gen-4fa3adf87962d08c` | s-style | 3 | C (`because`) | why_correct_recital | Ar4 | rewrite_recital |
| `ti-gen-825d7eb858c5e8c4` | s-rhet | 3 | A (`Yes, because it extends the paragraph's `) | assertive_letter | Br4 | recheck_fp |
| `ti-gen-f8d37c7f1a8d0af8` | s-sent | 3 | A (`NO CHANGE`) | assertive_letter | Dr4 | recheck_fp |

### A.4 Hit-level detail (for editors)

<details><summary>35 hint hits (expand)</summary>

| question_id | wrong | rung | class | body (truncated) |
|---|---|---:|---|---|
| `ti-gen-1a827341845d348b` | A | 3 | quote_label | 'Applicants for the Courier's summer internship must bring' — is that finished, or is the verb still |
| `ti-gen-2de182a5812c71c7` | D | 1 | quote_label | Read Sentence 4 aloud — which topic is it introducing? |
| `ti-gen-3c570ac19b6c03e6` | A | 1 | quote_label | Do 'first' and 'before' tell the reader two different things or the same thing? |
| `ti-gen-41dcd251ddce7265` | B | 3 | quote_label | Try reading 'practiced to winding' aloud slowly — which of the two little grammatical signals is doi |
| `ti-gen-466117fc76ab1be0` | A | 4 | why_correct_recital | An introductory participial phrase must be followed immediately by its doer; here it attaches to a s |
| `ti-gen-49aca528aa893263` | B | 4 | why_correct_recital | That verb belongs to offhand human awareness, but the sentence describes an instrument registering s |
| `ti-gen-4fa3adf87962d08c` | A | 4 | why_correct_recital | 'Due to the fact that' is a stock inflation of a simple causal link; when a phrase can collapse with |
| `ti-gen-54d1e04fc64fc59f` | A | 4 | why_correct_recital | A verb must agree with its grammatical subject, not with whatever noun happens to sit closest; here  |
| `ti-gen-624805558434ba37` | A | 4 | why_correct_recital | An introductory dependent clause takes a comma at its boundary, and no comma may split a subject fro |
| `ti-gen-6ce1824d9d1c682e` | D | 3 | quote_label | Once 'because' is present, what does 'of the fact that' add? |
| `ti-gen-79e23eca45d07dfe` | A | 4 | why_correct_recital | A subject and its verb form one unit that punctuation may not divide; the comma here severs them for |
| `ti-gen-7b69ae0f83310c12` | B | 3 | assertive_letter | Your pick promises a discussion of multiple dangers. Do the body sentences cover many threats, or do |
| `ti-gen-8014f7bd65dd1add` | A | 3 | quote_label | Can work be finished but not completely so? Can it be finished but not in its entirety? |
| `ti-gen-8014f7bd65dd1add` | C | 3 | quote_label | Is there a version of 'finished' that is only partial — or does the verb already promise completion? |
| `ti-gen-8014f7bd65dd1add` | C | 4 | quote_label | 'Finished' is an absolute, so the intensifier before it restates what the verb already means; the do |
| `ti-gen-8014f7bd65dd1add` | D | 3 | quote_label | If the work is finished, is any part of it left undone — and if not, what is the trailing phrase for |
| `ti-gen-8026889d0496f2cc` | A | 4 | why_correct_recital | A verb must agree with its subject, not with nearby nouns; the subject here is the singular 'array,' |
| `ti-gen-825d7eb858c5e8c4` | B | 4 | assertive_letter *(likely FP)* | A correct action with a trivial rationale fails these items; the sentence belongs because it adds an |
| `ti-gen-85a7f2259e04e208` | A | 4 | why_correct_recital | Paired punctuation must match: whatever mark opens an aside must also close it, and mixing two diffe |
| `ti-gen-9430a02f91aeb502` | B | 4 | why_correct_recital | 'Every' makes its noun singular on this test, and a plural pronoun cannot stand in for a singular an |
| `ti-gen-9dc5902d366e222f` | C | 3 | quote_label | Can 'wanted its deck to flex slightly underfoot' function as its own complete sentence? |
| `ti-gen-9dc5902d366e222f` | D | 4 | quote_label | Dashes set off interruptions or sharp turns, but 'wanted' is not an interruption — it is the predica |
| `ti-gen-aef13fb2e7641129` | A | 4 | why_correct_recital | With neither/nor, the verb agrees with the nearer subject — here the singular 'manual' — so a plural |
| `ti-gen-af28702318d403e6` | A | 4 | why_correct_recital | Contrast transitions belong between opposing ideas; here the second sentence states the direct outco |
| `ti-gen-b76fdeb9c3cce36e` | C | 1 | quote_label | What work does Sentence 4 do for the sentences that come after it? |
| `ti-gen-b8067145180c87a5` | A | 3 | quote_label | Do 'at night' and 'after dark' point to different times, or to the very same one? |
| `ti-gen-b81966658a7e0cdf` | A | 4 | why_correct_recital | The goal demands a word that asserts harsh magnitude, and this adjective only flags the gap as worth |
| `ti-gen-b83b0f5d79a219f8` | D | 3 | quote_label | Would an edited magazine print 'being that they are now scarce' — and what does your answer suggest? |
| `ti-gen-bab2d25358817f93` | A | 1 | quote_label | In your own words, what does 'collaborate' mean all by itself? |
| `ti-gen-c06011f4e642c4d6` | D | 4 | why_correct_recital | A nonrestrictive clause takes its comma before the pronoun, not inside the clause where it would spl |
| `ti-gen-c67b10fd632d6801` | B | 3 | quote_label | Would you say 'the operators have flashed the news in 1869'? What does attaching a definite past dat |
| `ti-gen-d6571d2d53b36fc3` | A | 3 | quote_label | If returning already means coming back to a place once more, what do the two trailing words contribu |
| `ti-gen-d6571d2d53b36fc3` | D | 3 | quote_label | Does 'make their return back' say anything that a single verb fails to say? |
| `ti-gen-f5f46cf813260d1a` | B | 3 | quote_label | Can 'sacks of grain, boxed rations, and a bundle of new pick handles' stand alone as a sentence? Wha |
| `ti-gen-f8d37c7f1a8d0af8` | D | 4 | assertive_letter *(likely FP)* | A vague pronoun right after the modifier leaves both the balancing and the angling without a clear a |

</details>

### A.5 Exit criteria for repair phase

- [x] `check_rung_leakage` = **0 hits** on all 12,000 hints *(2026-07-17 repair: 35 bodies rewritten in `research/synthetic_data_pipeline_handover/docs/questionbank/coach-bank-hints-gen2.json`; `reviewed`/`generated_by` untouched)*
- [x] Rung-4 key-label quote lint = **0** *(and rung-4 assertive key-letter = 0)*
- [x] Dedup vs live bank still **0** (re-run on `context_html` exact + Jaccard ≥0.85 vs `docs/plan/coach-item-bank-live.promoted.json`)
- [x] Step-4 solve-consistency complete — contamination **PASS**; multi-family solve **816 pass / 184 quarantine** (`docs/questionbank/coach-bank-gen2-step4-scorecard.md`)
- [x] Step-5 AQL — N=**816**, n=80 redrawn, **ACCEPT** (0 critical / 3 minor) → `reviewed=true` on 816 items + 9,792 hints (`docs/questionbank/coach-bank-gen2-step5-scorecard.md`)

**Step 5 lot composition:** N=**816** (leak-green ∩ solve-PASS). Sample redrawn post Step 4 (§B.5).

---

## B. Z1.4 acceptance-sampling worksheet

### B.1 Lot plan

| Parameter | Value |
|---|---|
| Standard | ISO 2859-1 / ANSI-ASQ Z1.4 attributes |
| Lot | Gen2 items after leak quarantine/repair |
| Lot size N | **816** (leak-green ∩ solve-PASS; 184 Step-4 quarantines excluded). Pre-solve frame was 1000/970. |
| Inspection level | General **II** |
| Code letter | **J** (N 501–1200) |
| Sample size n | **80** |
| Critical defects | AQL **0** → Ac=**0** / Re=**1** (one critical rejects the lot) |
| Minor defects | AQL **2.5** → Ac=**5** / Re=**6** |
| Sampling unit | **Item** = stem+choices+rationales + **all 12 hints** |
| `reviewed=true` flip | **Per accepted lot/shard only** — never per-item, never by cascade |
| Sample artifact | `docs/questionbank/coach-bank-gen2-aql-sample.json` + review packet `coach-bank-gen2-step5-review-packet.json` |

**Sequencing (mandatory):** finish §A repair → re-run Step 3 on 100% → run Step 4 solve-consistency → **then** draw/use this sample for Step 5. Drawing humans before machines clear criticals wastes review budget.

### B.2 Defect taxonomy (reviewers use this only)

**Critical (any one → reject lot):**

1. Wrong or indefensible key
2. Hint leaks the answer (letter, key wording, unique narrowing, rung-4 states the key)
3. Schema/structure break (missing rationale, wrong ladder shape)
4. Duplicate of a served live-bank item
5. Rung-4 states the key

**Minor (count toward AQL 2.5):**

- Stylistic infelicity / awkward prose
- Weak-but-valid distractor
- Opener repetition / flat ladder escalation
- Misconception label fuzzy but still pedagogically ok

**Do NOT re-check by hand:** schema, letter balance, NO-CHANGE rate, exact/Jaccard dedup, deterministic leak lint — machines own those on 100% of rows.

### B.3 Reviewer checklist (per sampled item)

```
Item ID: _______________  Reviewer: _______________  Date: ________

[ ] Key is uniquely defensible (would you stake the answer key?)
[ ] Each distractor maps to a named misconception / error type
[ ] Rationales explain *why wrong*, not just “incorrect”
[ ] Read ALL 12 hints as one unit (3 letters × 4 rungs)
[ ] Ladder escalates: pump → hint → prompt → assertion
[ ] No rung uniquely identifies the key (human judgment beyond lint)
[ ] Rung 4 states the rule / why *this distractor* fails — not the key

Verdict:  PASS  |  MINOR (describe)  |  CRITICAL (class #___ + evidence)
Notes:
```

### B.4 Lot disposition rules

| Sample outcome | Lot decision |
|---|---|
| 0 critical AND ≤5 minor | **ACCEPT** → flip `reviewed=true` on the whole eligible lot (**816** solve-PASS) |
| ≥1 critical | **REJECT** → repair/quarantine; tighten inspection on next shard (Z1.4 switching); do not patch-one-and-ship |
| 0 critical AND ≥6 minor | **REJECT** on minor AQL |

After ACCEPT: emit via `scripts/emit_test_item_bank.py` / `emit_hint_bank.py` (ADR-0035). Done: live bank is Gen1∪reviewed-Gen2.

### B.5 Stratified sample (n=80, seed=20260717) — redrawn post Step 4

Drawn from the **816** leak-green ∩ solve-PASS items (184 Step-4 quarantines excluded). Proportional by skill (largest remainder), round-robin easy/mid/hard within skill. Machine lists: `coach-bank-gen2-aql-sample.json`, review packet `coach-bank-gen2-step5-review-packet.json`.

| skill | n |
|---|---:|
| s-gram | 11 |
| s-org | 16 |
| s-punc | 8 |
| s-rhet | 18 |
| s-sent | 9 |
| s-style | 18 |
| **total** | **80** |

Difficulty mix: {1: 3, 2: 25, 3: 27, 4: 14, 5: 11} · types: {'underlined-span-mc': 58, 'rhetorical-mc': 22}

| seq | question_id | skill | std | d | type | key |
|---:|---|---|---:|---:|---|---|
| 1 | `ti-gen-1f9624c3292b98e5` | s-gram | 17 | 1 | underlined-span-mc | B |
| 2 | `ti-gen-2f27b759b69745cb` | s-gram | 22 | 2 | underlined-span-mc | B |
| 3 | `ti-gen-710a3599e4abf52e` | s-gram | 3 | 2 | underlined-span-mc | D |
| 4 | `ti-gen-7a31749e549850b4` | s-gram | 7 | 2 | underlined-span-mc | D |
| 5 | `ti-gen-008e6e42275f539a` | s-gram | 23 | 3 | underlined-span-mc | B |
| 6 | `ti-gen-842a62e017e2bdd1` | s-gram | 11 | 3 | underlined-span-mc | B |
| 7 | `ti-gen-d6c59e93c9aa7df3` | s-gram | 27 | 3 | underlined-span-mc | C |
| 8 | `ti-gen-f0f3698908251c91` | s-gram | 18 | 3 | underlined-span-mc | C |
| 9 | `ti-gen-62b1c68bb839c79c` | s-gram | 11 | 4 | underlined-span-mc | D |
| 10 | `ti-gen-6fae17a2143e9de6` | s-gram | 18 | 4 | underlined-span-mc | D |
| 11 | `ti-gen-95b3cf2541e5b0b8` | s-gram | 28 | 4 | underlined-span-mc | A |
| 12 | `ti-gen-0f348f00c49c85ab` | s-org | 36 | 2 | rhetorical-mc | B |
| 13 | `ti-gen-5bdbf65db2d82245` | s-org | 36 | 2 | rhetorical-mc | D |
| 14 | `ti-gen-791e41888777d68d` | s-org | 36 | 2 | rhetorical-mc | B |
| 15 | `ti-gen-ae1d260e0e7bb1fa` | s-org | 1 | 2 | underlined-span-mc | C |
| 16 | `ti-gen-af28702318d403e6` | s-org | 1 | 2 | underlined-span-mc | B |
| 17 | `ti-gen-edeee013f8460122` | s-org | 36 | 2 | rhetorical-mc | D |
| 18 | `ti-gen-288ef204e430f47f` | s-org | 38 | 3 | rhetorical-mc | B |
| 19 | `ti-gen-5a6cb4caa45e8765` | s-org | 1 | 3 | underlined-span-mc | B |
| 20 | `ti-gen-78da321a18e5e6b8` | s-org | 36 | 3 | rhetorical-mc | B |
| 21 | `ti-gen-c03b2eb630d29e75` | s-org | 37 | 3 | rhetorical-mc | B |
| 22 | `ti-gen-ec85fced0c9cb680` | s-org | 36 | 3 | rhetorical-mc | C |
| 23 | `ti-gen-13a120b7f1bf5f0e` | s-org | 36 | 4 | rhetorical-mc | C |
| 24 | `ti-gen-3d75a81048059e7b` | s-org | 1 | 4 | underlined-span-mc | A |
| 25 | `ti-gen-117c48a1e211290f` | s-org | 1 | 5 | underlined-span-mc | A |
| 26 | `ti-gen-56613d5d0dccbfa1` | s-org | 1 | 5 | underlined-span-mc | D |
| 27 | `ti-gen-98e39f81c158b40a` | s-org | 38 | 5 | rhetorical-mc | B |
| 28 | `ti-gen-41fc759996b6afc0` | s-punc | 29 | 2 | underlined-span-mc | C |
| 29 | `ti-gen-6af713b67368333e` | s-punc | 29 | 2 | underlined-span-mc | A |
| 30 | `ti-gen-d79b7be26ed8021b` | s-punc | 24 | 2 | underlined-span-mc | B |
| 31 | `ti-gen-3afe53bbd07a0e82` | s-punc | 41 | 3 | underlined-span-mc | C |
| 32 | `ti-gen-3eb5738a961ab620` | s-punc | 40 | 3 | underlined-span-mc | C |
| 33 | `ti-gen-a76732e69d259db0` | s-punc | 30 | 3 | underlined-span-mc | C |
| 34 | `ti-gen-08cfb045497c4c57` | s-punc | 24 | 4 | underlined-span-mc | A |
| 35 | `ti-gen-6b1982b311bbf5fd` | s-punc | 40 | 5 | underlined-span-mc | D |
| 36 | `ti-gen-0113496a8c005fe7` | s-rhet | 34 | 2 | rhetorical-mc | B |
| 37 | `ti-gen-086013df3cc9c3f6` | s-rhet | 33 | 2 | rhetorical-mc | C |
| 38 | `ti-gen-98597c95afd267a6` | s-rhet | 2 | 2 | underlined-span-mc | C |
| 39 | `ti-gen-add134b6fe11490b` | s-rhet | 33 | 2 | rhetorical-mc | D |
| 40 | `ti-gen-eddb33388adf6eda` | s-rhet | 35 | 2 | rhetorical-mc | C |
| 41 | `ti-gen-ff453e5783b1bca1` | s-rhet | 34 | 2 | rhetorical-mc | C |
| 42 | `ti-gen-37e641442920347a` | s-rhet | 33 | 3 | rhetorical-mc | A |
| 43 | `ti-gen-51dabb91f4950f88` | s-rhet | 4 | 3 | underlined-span-mc | A |
| 44 | `ti-gen-877a39fb3e4eb82b` | s-rhet | 2 | 3 | underlined-span-mc | A |
| 45 | `ti-gen-a66ffaa6114e62b5` | s-rhet | 33 | 3 | rhetorical-mc | D |
| 46 | `ti-gen-d0caa0dcd1ef208c` | s-rhet | 2 | 3 | underlined-span-mc | C |
| 47 | `ti-gen-ee066093eaaed416` | s-rhet | 33 | 3 | rhetorical-mc | A |
| 48 | `ti-gen-0b9f10d3a8d17637` | s-rhet | 2 | 4 | underlined-span-mc | C |
| 49 | `ti-gen-a0058c52245d7aea` | s-rhet | 33 | 4 | rhetorical-mc | C |
| 50 | `ti-gen-1df2022022bbb6ac` | s-rhet | 33 | 5 | rhetorical-mc | C |
| 51 | `ti-gen-4dd01927285711b4` | s-rhet | 33 | 5 | rhetorical-mc | C |
| 52 | `ti-gen-5dc0512ec0ce5162` | s-rhet | 2 | 5 | underlined-span-mc | C |
| 53 | `ti-gen-bf2f0097cfdd29e9` | s-rhet | 34 | 5 | rhetorical-mc | B |
| 54 | `ti-gen-b92e1e2c56840572` | s-sent | 10 | 1 | underlined-span-mc | C |
| 55 | `ti-gen-77155fe8b8724aa8` | s-sent | 25 | 2 | underlined-span-mc | C |
| 56 | `ti-gen-fbab9de9458c9c07` | s-sent | 15 | 2 | underlined-span-mc | B |
| 57 | `ti-gen-28af8f2f93f40156` | s-sent | 25 | 3 | underlined-span-mc | D |
| 58 | `ti-gen-66617fd8e162d976` | s-sent | 39 | 3 | underlined-span-mc | A |
| 59 | `ti-gen-6cbc25a928512301` | s-sent | 21 | 3 | underlined-span-mc | A |
| 60 | `ti-gen-41d49644ac23ae91` | s-sent | 20 | 4 | underlined-span-mc | B |
| 61 | `ti-gen-a42b5cacf649a56f` | s-sent | 39 | 4 | underlined-span-mc | B |
| 62 | `ti-gen-850ac543a78e429f` | s-sent | 39 | 5 | underlined-span-mc | A |
| 63 | `ti-gen-672521a75dc49fe0` | s-style | 9 | 1 | underlined-span-mc | C |
| 64 | `ti-gen-0cae2ba3f5c992eb` | s-style | 42 | 2 | underlined-span-mc | D |
| 65 | `ti-gen-2c333a5e989049b3` | s-style | 9 | 2 | underlined-span-mc | C |
| 66 | `ti-gen-3b65d25513ef6927` | s-style | 6 | 2 | underlined-span-mc | D |
| 67 | `ti-gen-843fad2b5de8bf22` | s-style | 8 | 2 | underlined-span-mc | B |
| 68 | `ti-gen-ca729512b2a3c613` | s-style | 8 | 2 | underlined-span-mc | B |
| 69 | `ti-gen-1a09c7cb7471f71e` | s-style | 8 | 3 | underlined-span-mc | B |
| 70 | `ti-gen-3d6b6d45ecb6d445` | s-style | 42 | 3 | underlined-span-mc | D |
| 71 | `ti-gen-68bc818dbb54d0e0` | s-style | 8 | 3 | underlined-span-mc | A |
| 72 | `ti-gen-702a4ea3471dd966` | s-style | 9 | 3 | underlined-span-mc | B |
| 73 | `ti-gen-891be373652d0cc6` | s-style | 6 | 3 | underlined-span-mc | B |
| 74 | `ti-gen-b37b2b5e45edd9f9` | s-style | 5 | 3 | underlined-span-mc | B |
| 75 | `ti-gen-5aa213e50a0c59c1` | s-style | 8 | 4 | underlined-span-mc | C |
| 76 | `ti-gen-6a9e74b956a1a566` | s-style | 43 | 4 | underlined-span-mc | B |
| 77 | `ti-gen-70f61537f01421d5` | s-style | 5 | 4 | underlined-span-mc | B |
| 78 | `ti-gen-8d6fa09255742d03` | s-style | 5 | 4 | underlined-span-mc | B |
| 79 | `ti-gen-61af7a4ba8314159` | s-style | 42 | 5 | underlined-span-mc | C |
| 80 | `ti-gen-a07a23176fd0a16a` | s-style | 42 | 5 | underlined-span-mc | B |

### B.6 Open human decisions (do not default)

1. **Review budget** — closed for this shard (n=80 inspected 2026-07-17 → ACCEPT).
2. **Lot composition** — closed: Step-5 lot = leak-green ∩ solve-PASS (**N=816**); 184 Step-4 quarantines held out.
3. **Timed-test contamination corpus** — set to Test-01 English (`_test01_english_corpus.ts`, 48 items); contamination PASS 2026-07-17.
4. **Standards 33–43 in product demand?** — 388 Gen2 items sit on them.
5. **Path A/B/C adoption** — pipeline does not choose; see eng-coach-gen2-v2-adoption docs.
6. **Step 6 emit + moment router** — done 2026-07-17: reviewed Gen2 merged into live seeds (171+816 items; 513+7,344 wire hints); banks regenerated. Quiz moment router passes wrong-letter into `loadHintLadder` / `hintRepo.list` and `setCoachChoiceLetter` → `sendCoachAsk` → `coach_context.choice_letter` (ADR-0035).

### B.7 Companion machine-readable lists

| Artifact | Path |
|---|---|
| Leak tickets | `docs/questionbank/coach-bank-gen2-leak-tickets.json` |
| AQL sample (N=816 frame) | `docs/questionbank/coach-bank-gen2-aql-sample.json` |
| Review packet | `docs/questionbank/coach-bank-gen2-step5-review-packet.json` |
| Inspection + verdicts | `docs/questionbank/coach-bank-gen2-step5-inspection.json` |
| Step-5 scorecard | `docs/questionbank/coach-bank-gen2-step5-scorecard.md` |
