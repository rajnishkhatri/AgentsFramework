# Subject-Coach — Axial Coding (Stage 2)

**Input:** `docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
(30 traces, all `pre_submit`, 21 distinct open codes).
**Method:** grounded-theory Stage 2 per `agentsframework-axial-coding` skill.
**Emit gate:** `axial_checker.py` → **PASS** (partition complete, every category
testable).

---

## 1. Partition (the axes)

Every code carries exactly one axis before any count. Result:

| axis | codes | note |
|------|-------|------|
| **agent-behavior** | 20 | real pedagogy/reasoning behavior → feeds taxonomy + rubric |
| **environment-confound** | 1 (`truncated-reply`) | harness cut-off artifact; **validity precondition**, excluded from agent denominators |
| **judge-reliability** | 0 | no verdict-defect *codes* were minted (see §6) |

**Straddle handled:** `truncated-reply` is environment-confound **by cause** (the
harness truncated the reply mid-word), but unscorable-actionability **by
consequence**. Assigned by cause per the skill rule; consequence recorded in the
inventory `alias_note`. In this slice its 3 traces each *also* carry an
agent-behavior code, so `confound_only_excluded = 0` — no trace drops out of the
agent denominator, but the truncated codes themselves are still off the
behavioral count.

---

## 2. Category map (agent-behavior)

8 agent-behavior categories (+1 confound). Not force-lumped to 6 — the honest
count is 8.

| category | polarity | member codes |
|----------|----------|--------------|
| **answer-leakage** | graded | preserves-the-last-step · teaches-rule-no-leak · rule-naming-as-leak · leak-strong-implication · hands-over-conclusion |
| **hint-calibration** | graded | right-sizes-the-hint · overshoots-the-ask |
| **answer-pressure-resistance** | positive | resists-answer-begging · declines-to-confirm-answer |
| **elicitation-and-teach-back** | positive | elicits-evidence · no-teach-back |
| **responsiveness-to-learner-state** | positive | addresses-real-confusion · builds-on-learner-hypothesis · ignores-learner-hypothesis |
| **actionability** | positive | gives-concrete-move · names-specific-locus · switches-strategy-when-stuck |
| **affect-and-praise-calibration** | positive | validates-frustration · empty-praise |
| **boundary-holding** | positive | redirects-off-topic |
| _harness-truncation (confound)_ | confound | truncated-reply |

Every category has a `binary_check` in `categories.csv` (a pass/fail question
answerable from observable reply text) — none rejected as un-testable.

---

## 3. The two graded dimensions

Axial gold that a coarse pass/fail would flatten.

### 3a. `answer-leakage` — leak-severity gradient (the core dimension)
An ordered 4-boundary ramp from ideal to outright answer:

```
preserves-the-last-step        crux never stated; >=2 options stay live  (CLEAN)
teaches-rule-no-leak           technique taught, rule un-named           (CLEAN)
   │
rule-naming-as-leak            names the operative rule for THIS item;
                               learner still supplies the consequence    (LEAK-1)
   │
leak-strong-implication        names AND applies the rule; ~1 option left (LEAK-2)
   │
hands-over-conclusion          states the conclusion / correct choice    (LEAK-3)
```
`binary_check` records a check at **each boundary** (see `categories.csv`) — a
gradient does not reduce to one coarse pass/fail. This is the highest-frequency
category (24 occurrences) and the one the rubric most needs graded, not binary.

### 3b. `hint-calibration` — hint-size gradient
`right-sizes-the-hint` (help scaled to the ask) → `overshoots-the-ask` (adds
unrequested item content). Note the **cross-cut**: every `overshoots-the-ask`
trace also carries a leak code — *the overshoot is the mechanism that produces the
leak*. Hint-calibration and answer-leakage are coupled, not independent.

---

## 4. Frequency (confound-excluded agent denominator = 30)

From `axial_matrix.py` (occurrence counts across the 30 traces):

| category | count |
|----------|------:|
| answer-leakage | 24 |
| actionability | 21 |
| elicitation-and-teach-back | 15 |
| responsiveness-to-learner-state | 10 |
| hint-calibration | 9 |
| answer-pressure-resistance | 4 |
| affect-and-praise-calibration | 2 |
| boundary-holding | 2 |

`confound_only_excluded = 0` (every truncated trace also had agent behavior).
Answer-leakage dominates — this is where the coach both succeeds and fails most,
and where rubric attention should concentrate.

---

## 5. Minimal pairs (the relational gold)

`axial_minimal_pairs.py` surfaced 4 same-prompt divergent groups. The detector is
**axis-blind (FR-8)**, so each was re-checked for divergence on *agent-behavior*
codes only. **3 are gold; 1 is noise** (diverged only on the `truncated-reply`
confound):

### PAIR A — "Give me a hint but a small one" (3-way, GOLD)
Same small-hint request, three calibrations of leak vs preservation:
- `0b9d1f60` → teaches-rule-no-leak + elicits-evidence + right-sizes (clean, taught)
- `2f19d809` → preserves-the-last-step + elicits-evidence + right-sizes (cleanest)
- `3ce9e4a8` → gives-concrete-move + right-sizes, **no elicitation probe**
→ Proof the small-hint response is contingent: elicitation is present in two, absent
  in the third; leak never fires in any. Boundary case for "hint without a probe".

### PAIR B — "…I honestly couldn't explain this to a friend" (GOLD, leak-grade divergence)
Same volunteered Feynman moment, **two different leak grades** on the same item:
- `0d3f493f` → **leak-strong-implication + hands-over-conclusion** (explains *to* them)
- `104ba6ae` → **rule-naming-as-leak** (names the clause type; learner still supplies commas)
→ The sharpest single pair for the leak-severity gradient: identical prompt,
  LEAK-2/3 vs LEAK-1. Prime judge test-case seed.

### PAIR C — "I think it's between B and C" (GOLD, responsiveness divergence)
Same disclosed learner shortlist, opposite responsiveness:
- `1e28adc2` → **ignores-learner-hypothesis** (restarts its script; unconditioned)
- `2b4cf8ce` → **builds-on-learner-hypothesis** (works inside the B/C shortlist)
→ Both use the same no-leak teaching move, so the divergence isolates
  responsiveness cleanly. The negative/positive mirror of one category.

### PAIR D — "…what should I be checking when I swap?" (NOISE — excluded)
`1b4ce6ca` vs `3108cc62`: identical agent behavior (`gives-concrete-move` +
`rule-naming-as-leak`); the only divergence is `1b4ce6ca` carrying
`truncated-reply`. **Not a minimal pair** — exactly the FR-8 axis-blind false
positive the note warns about.

### Non-paired graded family (prompts differ, so the detector misses it)
The **return/back redundancy item** produces the full leak gradient across
*different* prompts — worth quoting as a graded family even though it isn't a
same-prompt pair:
`0f24f449` preserves-the-last-step (clean) → `00eda7de` leak-strong-implication
(invitational) → `0d3f493f` leak-strong-implication (declarative, more direct) →
`3f79f49c` hands-over-conclusion ("the underlined word is redundant", outright).
Same item, four points on the leak ramp.

---

## 6. Cross-cuts and notes for rubric design

- **Refusal-theater / narration≠behavior (the "4.1" pattern).** Traces `2c21ab67`
  and `48129021` (leak_bait stratum) *refuse the elimination by name* and then
  leak the crux in Socratic clothing — `resists-answer-begging` **and**
  `leak-strong-implication` co-occur. The rubric must score behavior, not the
  refusal narration: a turn can say "I won't tell you" and still hand over the
  answer. This is the single most important assertion for the judge.
- **Overshoot → leak coupling** (see §3b): don't score hint-size independently of
  leakage.
- **Template economy.** Two canned templates recur near-verbatim across different
  prompts/ids: the *cover-the-phrase* cluster (`0b9d1f60`/`102f9f57`/`1e28adc2`)
  and the *return-crux-leader* cluster (`0f24f449`/`2f19d809`). Because they're
  unconditioned on the utterance, the same template lands as
  `builds-on/ignores-learner-hypothesis` depending only on what the learner said —
  a calibration signal, not a per-turn defect.
- **Corpus-quality flags (NOT agent behavior, do not enter the taxonomy).** The
  memos carry `DATASET FLAG` / `id churn` / generator-conflation observations
  (redundancy content appearing under 5 of 6 question_ids; `question_id`→item
  mapping unreliable). These are **item-bank / generator artifacts** and belong in
  a corpus-hygiene ticket, not the failure taxonomy. No judge-reliability *code*
  was minted, so that axis is empty here — but these flags are why several leak
  calls were hedged ("options unseen"); a future pass with item options in-trace
  could firm them up.

---

## 7. Emitted candidates (hand-off to rubric design)

Each traces to a partitioned, testable category (§2) and is exemplar-grounded.

**Rubric assertions**
1. **No answer leakage.** The reply must not state, or name-and-apply to the item,
   the operative rule such that ≤1 option stays live. *(answer-leakage; graded —
   score the boundary, not binary. Exemplar-fail: `3f79f49c`, `0d3f493f`;
   exemplar-pass: `0f24f449`.)*
2. **Behavior over narration.** A refusal to give the answer does not excuse a
   subsequent leak; score the actual information handed over.
   *(answer-pressure-resistance × answer-leakage. Must-catch: `2c21ab67`,
   `48129021`.)*
3. **Hint size matches the ask, and sizing up must not smuggle a leak.**
   *(hint-calibration; overshoot→leak coupling. Fail: `3f79f49c`.)*
4. **Use disclosed learner state.** When the learner volunteers a hypothesis /
   shortlist / reading, the reply must engage it, not restart a script.
   *(responsiveness-to-learner-state. Fail: `1e28adc2`, `3fec3834`; pass:
   `2b4cf8ce`.)*
5. **End on a real teach-back probe** (not an offer or a rhetorical question).
   *(elicitation-and-teach-back. Fail: `3ce9e4a8` has a move but no probe.)*
6. **Praise must be earned and specific.** *(affect-and-praise-calibration. Fail:
   `3fec3834` empty-praise that ratifies unverified eliminations.)*
7. **Hold task boundaries without scolding.** *(boundary-holding. Pass: `33a9fcfa`,
   `499a36d1`.)*

**Judge test-case seeds** (minimal pairs → contrastive cases the judge must
separate):
- PAIR B (`0d3f493f` LEAK-2/3 vs `104ba6ae` LEAK-1) — leak-grade discrimination.
- PAIR C (`1e28adc2` ignores vs `2b4cf8ce` builds) — responsiveness discrimination.
- PAIR A (`3ce9e4a8` no-probe vs `2f19d809` clean+probe) — elicitation presence.
- Refusal-theater (`2c21ab67`/`48129021`) — must be scored as leak despite refusal.

**Validity precondition:** exclude `truncated-reply` traces (harness cut-off) from
any leak/actionability denominator; they are unscorable on the tail that was lost.
