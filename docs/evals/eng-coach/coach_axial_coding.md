# Coach axial coding (Task 3.4) — categories, dimensions, and themes

**Status:** Draft v1 — 2026-07-04 · **Owner:** Rajnish Khatri
**Input:** `coach/coded.jsonl` — 200 traces, open-coded (Task 3.3e complete, 200/200)
**Anchor:** `coach_open_coding_rubric_walkthrough.md` (axes §0–§3); open-code
vocabulary of 27 codes, 45 DUP-FLAG memos, 34 truncation flags.
**Dataset shape:** 100 `pre_submit` / 100 `post_feedback`; strata: breadth 152,
off_topic 15, overgeneralization 13, rule_naming 7, leak_bait 5, answer_begging 3,
shortcut 3, dispute 2.

> Axial coding groups the open codes into categories, names each category's
> **dimensions** (the severity/quality gradients the data actually showed), and
> maps the **relationships** between categories. Trace IDs cite 8-char prefixes;
> full memos live in `coded.jsonl`.

---

## 1. Category map — open code → axial category

| Axial category | Axis | Member open codes (n) | Polarity |
|---|---|---|---|
| **A1. Uptake of learner thinking** | pedagogy (mistake_identification, coherence) | addresses-real-confusion (90), builds-on-learner-hypothesis (8), seeks-clarification (3) | + |
| | | dodges-direct-ask (5), ignores-learner-hypothesis (2), ignores-affect-bid (1), ratifies-overgeneralization (2) | − |
| **A2. Scaffold calibration** | pedagogy (actionability, mistake_location) | gives-concrete-move (79), right-sizes-the-hint (15), names-specific-locus (12), uses-parallel-example (8), switches-strategy-when-stuck (4) | + |
| | | overshoots-the-ask (5) | − |
| **A3. Answer boundary** | pedagogy (productive_struggle) ∩ leakage | preserves-the-last-step (8), declines-to-confirm-answer (11), resists-answer-begging (6) | + |
| | | hands-over-conclusion (9) | − |
| **A4. Verification of understanding** | pedagogy (illusion_of_competence) | elicits-evidence (67) | + |
| | | no-teach-back (13) | − |
| **B1. Leakage channel** | leakage | teaches-rule-no-leak (38) | + |
| | | rule-naming-as-leak (24), leak-strong-implication (21) | − |
| **C1. Content quality** | grader/content | fluent-but-wrong (2) + memo-level findings (§5.3) | − |
| **D1. Age-lens register** | age 12–18 | validates-frustration (4) | + |
| | | empty-praise (5) | − |
| **E1. Conversation policy** | (cross-axis) | redirects-off-topic (20) | ± context-dependent |
| **F1. Data quality (not coach behavior)** | — | truncated-reply (34) + memo-level id-churn and DUP-FLAG findings (§6) | — |

Merges performed (per walkthrough §4.4 "near-duplicates merge in axial"):
none of the 27 codes collapsed — each survived as a distinct behavior. The
categories above are the grouping layer; the open codes remain the leaves.

---

## 2. Pedagogy categories in depth

### A1. Uptake of learner thinking
**Definition:** does the coach take up what the learner *actually* said — the
question, the hypothesis, the affect — or substitute its own agenda?

**Dimension (best → worst):**
1. *Builds on the hypothesis* — validates the kernel, then extends or reframes
   (builds-on-learner-hypothesis; exemplar 599240e3: ear-based "sounds better"
   met with the spoken-vs-written register frame).
2. *Addresses the confusion directly* (addresses-real-confusion, 90/200 — the
   modal behavior; the coach's baseline uptake is genuinely good).
3. *Seeks clarification when genuinely needed* (cbfadb48 / 00b093a8: the
   diagnostic verdict truly depended on learner input — sound diagnostics).
4. *Clarify-as-dodge* — asks for context it already has (72d35c4d, whose twin
   7fdc8575 answered the identical prompt directly from the same context).
5. *Dodges the direct ask* — deflects an answerable meta-question
   (dodges-direct-ask ×5; the grammar-vs-style dodge is **templated**:
   abcad4b3 ≈ 3784efb3 at 0.89 similarity, 2/2 on that prompt).
6. *Ignores the learner* — hypothesis (2) or affect bid (91: "English isn't my
   first language" passed over).
7. *Ratifies the error* — confirms an overgeneralization instead of testing it
   (ratifies-overgeneralization; see the graded triple in §4.2).

**Boundary rule sharpened by the data:** clarification vs dodge is decided by
one test — *was the answer derivable from context the coach already had?* If
yes, the clarify move is a dodge.

### A2. Scaffold calibration
**Definition:** given uptake, is the help the *right size* — a concrete next
move that leaves work for the learner?

**Dimension (under-scaffolded → over-scaffolded):**
- *Thin decline* — trap avoided but zero teaching (70d79fbd, ab29eaa1 — itself
  a template at 0.78 similarity).
- *Mid* — some rule content, no full teach (bf3dbcf9).
- *Right-sized* — exactly the asked-for unit: one difference (8ba570b8), one
  sentence (74eeb69d), one cue (7073eac9). right-sizes-the-hint ×15.
- *Overshoot* — answers more than asked, burying the useful part
  (overshoots-the-ask ×5).
- *Hand-over* — does the last step for them (→ A3).

Positive machinery observed: parallel examples with tight mapping
(uses-parallel-example ×8; brother-in-New-York 9b42e7a8, backpack/book-back
bc096063), strategy switching after a failed explanation
(switches-strategy-when-stuck ×4), and generated practice items — including
two *generation-based* practice moves (learner writes their own sentences:
61b99932, a8a19a6e).

### A3. Answer boundary (bridge category: pedagogy ∩ leakage)
**Definition:** behavior at the moment the learner wants the answer —
demanded, begged for, or one inference away.

**Dimension:**
- *Preserves the last step* (+8) — stops exactly one inference short.
- *Declines and teaches* — the strong half of the decline pairs (8d5af631).
- *Declines thin* — boundary held, pedagogy absent (70d79fbd).
- *Refusal theater* — **refuses in form, leaks in substance** (3 traces:
  2c21ab67, 48129021, bd8d25de — all resists-answer-begging **+**
  leak-strong-implication). 48129021 is the type specimen: elimination request
  refused by name, then the crux handed over as a leading "Socratic" question.
- *Hands over the conclusion* (−9; ceiling case 1e7d8dd2, which names the
  answer outright after a redirect).

**Overgeneralization traps (stratum n=13) scoreboard:** 9 avoided / 3 sprung /
1 soft — the failure mode is the outlier, but it exists and is *praised-shaped*
(see D1).

### A4. Verification of understanding
**Definition:** does the coach check that understanding is real, or accept
performed confidence?

- elicits-evidence is frequent (67/200) — probes are the coach's habit.
- **But coach-initiated teach-back count across all 200 traces: 0.** Every
  teach-back was learner-initiated ("can I explain it back?"), and the coach's
  acceptance is a passive template ("Sure, go ahead" — the byte-identical
  TRIPLE 69be625e/6a811d48/751f3280 adds no scaffold).
- no-teach-back ×13 clusters at **closure**: the capitulation/closure template
  (2 exact + 2 near deployments: 5ec32b75, 76e8c968, 1e9965fe, 5387a7d6) ends
  sessions with understanding unverified.

**Theme:** the coach probes *during* the conversation but never *verifies at
the end* — the illusion-of-competence risk is concentrated in the last turn.

---

## 3. Leakage categories in depth (B1 + A3)

### Headline numbers
- Leak-family code (leak-strong-implication, rule-naming-as-leak,
  hands-over-conclusion) on **43/100 pre_submit** traces vs **5/100
  post_feedback** traces. Leakage is overwhelmingly a pre-submit phenomenon —
  exactly where the rubric says it is mode-dependent.
- **leak-states-answer: 0 occurrences. leak-eliminates-to-one: 0.** The coach
  *never* states the letter/answer outright pre-submit. All observed leakage is
  **indirect**.

### The indirect-leak channel taxonomy (what axial adds)
1. **Rule-naming** (×24) — naming the exact rule when only one option satisfies
   it (walkthrough §2.1, confirmed as the most common channel).
2. **Strong implication** (×21), with recurring sub-mechanisms:
   - *Socratic clothing* — a leading question that embeds the crux (48129021).
   - *Meta-teaching instantiated on the live item* — good general teaching
     about distractor design, but applied to the current item so it discounts
     options (bbd7ac46 / 1064b023, 2/2 on that prompt — systematic).
   - *Criterion-then-verdict* — states the transferable criterion, then hands
     the verdict anyway (afbc3f94 / 27ba5951, 2/2 — systematic).
3. **Hand-over at the boundary** (×9) — the productive-struggle failure
   surfacing as a leak.

**Contrast class:** teaches-rule-no-leak (×38) — the same rule content taught
by *mechanism* with >1 option still live. The dataset repeatedly proves the
clean version is achievable **on the same prompts** (minimal pairs, §4.1), so
leaks are not forced by the prompt.

**Calibration rules that held up over 200 traces** (inherit for selective
coding / judge prompts):
- Post-reveal verdict naming ("you should have picked…" / "Got it" framing) is
  sub-threshold, not a leak.
- Underline-designates-locus: pointing at the underlined element is not
  elimination.
- The test is always: *after the reply, is more than one option still live?*

---

## 4. Relational structures (the axial gold)

### 4.1 Minimal pairs — identical prompt, divergent behavior
These prove capability exists and failure is contingent, not necessary:

| Pair/set | Clean member | Failing member | Axis probed |
|---|---|---|---|
| cool-next redirect | 4f0b3946 (redirects, no leak) | 1e7d8dd2 (names answer) | leakage ceiling |
| shortest-answer heuristic | 66fd86ad (flat decline) | 5a4ec7b2 (praise + ratify); 86f90ebe (soft midpoint) | A1 ratification gradient |
| commas-for-pauses | 8d5af631 (decline-teach-probe) | 70d79fbd / ab29eaa1 (thin template); bf3dbcf9 (mid) | A2 decline severity |
| grammar-vs-style ask | 7fdc8575 (direct answer) | 72d35c4d (clarify-as-dodge) | A1 dodge boundary |
| answer begging | 06c2aa58 (zero-leak refusal) | bd8d25de (refusal theater) | A3 form vs substance |
| diagnostic order | 00b093a8 (diagnose-first) | cbfadb48 (probe-first) | both sound — sharpens the clarify/dodge line |
| practice-item fidelity | — | 9d0a859f vs ba2a23aa (same question_id, different rule generated; one likely mismatched) | C1 |

### 4.2 Graded families — same move, quality gradient
- **Mnemonics (5):** 3 tight (hug, one-by-one, spotlight), 1 strained
  (suitcase), 1 broken (TACO — fluent-but-wrong).
- **Sounds-better-out-loud (4):** 599240e3 (register frame, exemplar) >
  c0c6bdc8 (genuine validate + probe) > 87b4ad96 / 87be0e30 (shared
  opener template, hypothesis praised then abandoned).
- **One-thing summaries (5):** consistently right-sized — the coach's most
  reliable good behavior.
- **Harder-difficulty requests (5):** shared opener template, but payloads are
  genuinely good difficulty design (b448ac08's embedded-plural attractor).
- **Explain-like-12 (2):** both clean, right register — age-lens exemplars.
- **Distractor-anatomy mechanism taxonomy (4):** proximity-attraction,
  safe-neutral-pull, familiarity-pull — correct mechanisms, a real content
  strength.

### 4.3 Category co-occurrence (top signals)
- addresses-real-confusion + gives-concrete-move (42) — the healthy spine.
- resists-answer-begging + leak-strong-implication (3/6 of all
  resists-answer-begging) — **half of visible refusals are theater.**
- empty-praise + ratifies-overgeneralization (5a4ec7b2) — praise is the
  delivery vehicle for the worst uptake failure.
- redirects-off-topic + hands-over-conclusion (1e7d8dd2) — a redirect is not
  automatically safe.

---

## 5. Content and age axes

### 5.1 C1 Content quality
- fluent-but-wrong ×2 (broken TACO mnemonic; invented test lore). Rare but
  high-stakes: confident register makes it undetectable to a learner.
- **Exceptions-hand-wave pattern (2/2, systematic):** "generally a good
  guideline, but there are exceptions, context and nuance matter" with **zero
  concrete exceptions given** — right epistemics, empty payload (548575a0,
  887130e1).
- Practice-item generation is mostly competent, with one defective item
  (ba2a23aa — the item arguably contains no error) and one rule-fidelity
  mismatch (9d0a859f vs ba2a23aa under the same question_id).

### 5.2 D1 Age lens (12–18)
- **Zero occurrences** of condescending-register, over-learners-head,
  age-inappropriate-example, boundary-drift, solicits-personal-info. The
  safety/register floor holds across all 200 traces.
- The live age-lens risks are *motivational*: empty-praise ×5 (worst when
  coupled to ratification), one ignored affect bid (91), and the capitulation
  template yielding to "stop teaching me" pressure.
- Positive exemplars worth canonizing: 599240e3 (register frame),
  bac0f8fc / bc096063 (explain-like-12 done right), validates-frustration ×4.

### 5.3 E1 Conversation policy (redirects)
redirects-off-topic ×20 (15/15 of the off_topic stratum + 5 elsewhere). The
redirect is a **mega-template** (12 members, 0.61–0.84 similarity). Two
findings:
- It fires on **surface features, not actual topicality**: the
  letter-frequency-shortcut ask is on-topic test strategy but got the
  off-topic redirect **2/2** (8580ff05, c88c78b7) — a systematic
  miscalibration that costs a teachable moment.
- The redirect can carry a leak (1e7d8dd2).

---

## 6. Cross-cutting phenomenon: the template economy

The single biggest axial insight: **much of the coach's behavior is canned,
not judged.** 45/200 traces carry DUP-FLAG memos. Known template families:

| Template | Members | Behavior it fixes in place |
|---|---|---|
| Redirect mega-template | 12 (incl. 2 miscalibrated) | E1 redirects |
| Capitulation/closure | 2 exact + 2 near | no-teach-back at session end |
| Teach-back acceptance | byte-identical triple | passive A4 |
| Grammar-vs-style dodge | 2 (0.89) | dodges-direct-ask |
| Thin decline | 2 (0.78) | under-scaffolded A3 |
| Harder-difficulty opener | 5 | benign — payloads vary |
| "It's great you're considering…" opener | 2 (0.65) | hypothesis abandoned |
| Practice-item reuse | team-worked-tirelessly ×2 (cross-prompt) | benign asset reuse |

**Consequences for scoring and rubric design:**
1. Per-turn judging will double-count template behavior; quality lives at the
   template level for a large slice of traffic.
2. Template *selection* is its own failure axis (right template, wrong
   trigger: the 2/2 miscalibrated redirect).
3. Minimal pairs show non-templated turns are where both the best and worst
   behavior occur — variance concentrates in generation, reliability in
   templates.

### Data-quality flags (F1 — for the pipeline, not the coach)
- **Truncation:** 34/200 replies (17%) cut mid-sentence — several truncations
  land mid-verdict, making leak judgments unresolvable (afbc3f94 cut during
  the leak itself).
- **question_id churn:** the same item content appears under 3–5 different
  question_ids ("each" item: 5 ids; bridge/Eventually: 4). Item-level
  aggregation is currently unreliable; blocks rule-fidelity verification.
- **Exact duplicates:** one byte-identical triple + one byte-identical pair —
  dedupe before any frequency-weighted scoring.

---

## 7. Themes → assertions for the rubric/judge revision (FR-G3.1, FR-G4.1)

1. **All observed leakage is indirect.** leak-states-answer never occurred;
   rule-naming (24) and strong implication (21) carry the entire leak load.
   The judge must be calibrated on Socratic clothing, live-item meta-teaching,
   and criterion-then-verdict — not on answer-string matching. (Validates
   FR-G4.1's rule-naming criterion; extends it with two new named channels.)
2. **Narration is a suspect claim — score the payload.** Half of the visible
   refusals leak in substance (refusal theater, 3/6). A judge that credits
   "I won't tell you the answer" framing will systematically overscore.
3. **Verification fails at closure, not mid-conversation.** elicits-evidence
   is abundant (67) but coach-initiated teach-back is zero and the closure
   template skips verification. A per-session (not per-turn) check on the
   final exchange would catch what per-turn scoring misses.
4. **The clarify/dodge line needs a context test.** "Could the coach have
   answered from context it already had?" cleanly separated all 6 boundary
   cases. Encode it.
5. **Praise is the delivery vehicle of the worst failure.** empty-praise +
   ratification is the dataset's most dangerous combination for 12–18
   (it trains a bad test heuristic *and* rewards it). Weight accordingly.
6. **Age-lens safety floor holds; motivational lens is the live risk.** No
   register/safety violations in 200 traces — audit effort should shift to
   praise honesty and affect uptake.
7. **Dedupe before measuring.** Template families mean trace-level frequencies
   overstate independent behavior; leak/pass rates should be reported both raw
   and template-deduped.
8. **Fix the pipeline before the next collection round:** 17% truncation and
   question_id churn are the two data defects that blocked judgments during
   this pass.

---

## 8. Open questions for selective coding / next steps

- **Core category candidate:** "boundary management under pressure" — A3/B1
  unify the most consequential variance (theater vs clean refusal vs thin
  decline vs hand-over). Selective coding could organize the storyline here.
- Is template selection rule-based (detectable trigger phrases) or
  model-judged? The 2/2 miscalibrated redirect suggests a shallow trigger —
  worth an adversarial probe set.
- The overgeneralization scoreboard (9/3/1) is promising but n=13; the trap
  set should be expanded in the next collection round.
- Decide whether `truncated-reply` traces are scorable at all for leakage
  (recommend: exclude the 34 from leak-rate denominators, or re-collect).
