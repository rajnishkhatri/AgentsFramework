# Coach axial coding — categories, axes, dimensions, minimal pairs

**Status:** Draft v1 — 2026-07-04 · **Stage:** grounded-theory Stage 2 (axial)
**Input:** `docs/skills/agentsframework-axial-coding/evals/fixtures/coded_slice.jsonl`
— 30 traces, open-coded, 21 distinct codes, all `pre_submit`.
**Emit gate:** `axial_checker.py` → `OK — partition complete, every category
testable; emit allowed.` (exit 0). Nothing below was emitted before the gate was
green (the one hard rule).

> Axial coding groups the 21 open codes onto three **axes** (so counts aren't
> poisoned by sandbox artifacts), clusters the agent-behavior codes into named
> **testable categories**, names the one **ordered gradient** the data showed
> (leakage), and surfaces the **minimal pairs** — same learner prompt, divergent
> behavior — that prove each failure was contingent, not forced. Trace IDs cite
> 8-char prefixes; full memos live in the coded slice.

---

## 0. Axis partition (the validity precondition)

Every code carries exactly one axis. Counts are computed on the agent-behavior
axis only.

| Axis | Codes | Role |
|---|---|---|
| **agent-behavior** (19 codes) | all C1–C6 members below | feeds the taxonomy + rubric |
| **environment-confound** (1 code) | `truncated-reply` (3 traces) | sandbox/generation truncation — a **validity precondition**, excluded from agent denominators, never a behavioral bucket |
| **judge-reliability** (0 codes) | — | no verdict/label-drift codes in this slice |

**`truncated-reply` partitioned by cause.** Memos on traces 05fa7a88 / 1b4ce6ca /
0d… note the reply "cuts off mid-word (informat)" / "cut mid-derivation (the verb
sh) — lost tail almost certainly stated the answer outright." The *cause* is
harness/generation truncation (environment), so the code sits on
environment-confound; the *consequence* (a lost tail that may hide a leak or a
next move) is recorded here as a memo note, not a second axis assignment.

**Matrix note — denominator = 30, `confound_only_excluded = 0`.** All three
truncated traces *also* carry agent-behavior codes, so none is confound-only; the
agent denominator is the full 30. The FR-3 exclusion machinery is present and
correct — it simply had nothing to exclude in this slice. When reading C1
leakage counts, remember the 3 truncated tails may hide additional leaks the
coder could not score (leakage is likely *under*-counted, not over-counted).

**Not open codes (memo-level, out of this taxonomy):** the `DATASET FLAG` /
`DUP-FLAG` memos on ~half the traces record (a) **question_id ↔ item churn** (the
same item text appears under q-style-1, q-gram-1, q-rhet-1, q-punc-1, q-sent-1 —
generator id-to-item mapping is unreliable) and (b) **template reuse** (byte-near
answers repeated across different learner prompts, e.g. the "cover-the-phrase"
and "return-crux-leader" clusters). These are corpus/generator quality findings
for the item-bank owner; they are not coach-behavior codes and get no axis.

---

## 1. Category map — open code → axial category

Agent denominator = 30 traces. Counts are code occurrences (a trace may carry
several).

| Axial category | Axis | Polarity | Member codes (occurrences) |
|---|---|---|---|
| **C1. Answer-leakage channel** | agent-behavior | ± (gradient) | teaches-rule-no-leak (4, +) · rule-naming-as-leak (6, −) · leak-strong-implication (6, −) · hands-over-conclusion (4, −) |
| **C2. Answer-boundary hold** | agent-behavior | + | preserves-the-last-step (4) · resists-answer-begging (3) · declines-to-confirm-answer (1) |
| **C3. Uptake of learner thinking** | agent-behavior | ± | addresses-real-confusion (7, +) · builds-on-learner-hypothesis (1, +) · switches-strategy-when-stuck (1, +) · ignores-learner-hypothesis (2, −) |
| **C4. Scaffold calibration** | agent-behavior | ± | gives-concrete-move (16, +) · right-sizes-the-hint (7, +) · names-specific-locus (4, +) · overshoots-the-ask (2, −) |
| **C5. Verification of understanding** | agent-behavior | ± | elicits-evidence (10, +) · no-teach-back (5, −) |
| **C6. Register & conversation policy** | agent-behavior | ± | validates-frustration (1, +) · redirects-off-topic (2, +) · empty-praise (1, −) |
| *(F. Data quality — not coach behavior)* | environment-confound | — | truncated-reply (3) + memo-level id-churn / template-reuse findings |

**Per-category trace counts (`axial_matrix.py`, confound-excluded denominator = 30):**
C1 = 20 · C2 = 8 · C3 = 11 · C4 = 29 · C5 = 15 · C6 = 4.

No open codes were merged — each of the 21 survived as a distinct leaf; the
categories are the grouping layer above them. Six categories, honestly derived
(the ~5–6 target is guidance, not a gate); no forced lumping.

---

## 2. The one ordered gradient — C1 leakage channel

C1 is the only category whose members form an **ordered severity gradient**, so
its `binary_check` records a check at each boundary (`|`-separated) rather than
one coarse pass/fail. Best → worst, grounded in the memos:

1. **teaches-rule-no-leak** (+) — technique handed over, rule never named, ≥2
   options stay live, crux inference left to the learner.
   *Exemplar 0b9d1f60:* "Cover the phrase 'of the runners' and read what's left.
   What is the subject?" — teaches subject-verb agreement with zero item verdict.
2. **rule-naming-as-leak** (−) — names the operative rule / clause-type whose
   application *alone* resolves the item to one option, but the learner must
   still perform the final step. *Exemplar 22 (q-sent-1):* names the
   dangling-modifier rule fully abstractly; *104ba6ae:* "nonrestrictive clause →
   commas set it off."
3. **leak-strong-implication** (−) — states the rule **and applies it to the
   item** so only ~one option remains. *Exemplar 00eda7de:* "return already
   conveys direction" applied to the underlined word.
4. **hands-over-conclusion** (−) — asserts the answer/conclusion outright.
   *Exemplar 24:* "the underlined word is redundant" in `pre_submit`.

`dimension = teach->rule-name->strong-implication->hand-over`.

Every other category (C2–C6) is a single pass/fail with a positive and a negative
pole, not a graded family.

---

## 3. Category definitions & boundary rules

- **C2. Answer-boundary hold** — behavior at the moment the learner *demands* the
  answer. Passing move: withhold the verdict, route to re-derivation.
  `declines-to-confirm-answer` (16: "I'm 60% sure, should I change it?") is the
  confirm/deny sibling of `resists-answer-begging`; both are answer-boundary
  holds. **Watch:** boundary-hold and leakage are separate axes of the same turn
  — a trace can *resist by name and leak in substance* (see §4, refusal-theater).
- **C3. Uptake** — does the coach take up what the learner actually offered
  (confusion / hypothesis / a failed strategy) or restart its own script?
  `ignores-learner-hypothesis` (13, 25) is the negative pole: "between B and C"
  or "I eliminated A and D" disclosed and never examined.
- **C4. Scaffold calibration** — is the help the *right size* for the ask?
  `overshoots-the-ask` (24, 26) is the negative mirror of `right-sizes-the-hint`;
  in both overshoot traces the overshoot is *what produces the leak* (C1↔C4
  coupling).
- **C5. Verification** — does the coach check understanding, or accept performed
  confidence? `no-teach-back` fires even when a learner *volunteers* a teach-back
  (0, 3) and the coach pivots to its own probe; "feel free to ask" is an offer,
  not a check.
- **C6. Register & policy** — age-appropriateness + boundary holding.
  `redirects-off-topic` (20, 29) cleanly declines arithmetic-detour / do-my-work
  bids without scolding; `empty-praise` (25) is generic unearned praise that
  *ratifies an unverified elimination* — worse than neutral.

---

## 4. Minimal pairs (the relational gold)

`axial_minimal_pairs.py` is **axis-blind (v1)** — it groups by normalized-exact
prompt and reports any code-set divergence. Below, each surfaced pair is
confirmed on **agent-behavior** divergence (or rejected as confound-only noise).

### Gold — genuine agent-behavior divergence

- **Prompt "I think it's between B and C"** — `1e28adc2` vs `2b4cf8ce`. Same
  disclosed hypothesis; `1e28adc2` **ignores-learner-hypothesis** (restarts the
  cover-the-phrase script), `2b4cf8ce` **builds-on-learner-hypothesis** (works
  inside the B/C shortlist). *The cleanest C3 uptake pair — the failure is
  contingent, not forced.*
- **Prompt "If I had to explain this sentence to a friend, I honestly couldn't"**
  — `0d3f493f` (**leak-strong-implication + hands-over-conclusion**) vs `104ba6ae`
  (**rule-naming-as-leak**, one gradient step milder). *A within-C1 gradient
  pair: same prompt lands at two different leakage grades.*
- **Prompt "Give me a hint but a small one"** — three-way: `0b9d1f60`
  (teach-rule + elicits + right-sizes), `2f19d809` (preserves-last-step +
  elicits + right-sizes), `3ce9e4a8` (right-sizes only). All *positive*, but they
  diverge on **C5 verification** (elicits-evidence present vs absent) and on C2 —
  a useful graded family for what a "good small hint" minimally requires.

### Noise — reject (diverges only on the confound axis)

- **Prompt "If I swap the underlined part for each choice, what should I be
  checking?"** — `1b4ce6ca` vs `3108cc62`. Both **rule-naming-as-leak +
  gives-concrete-move**; the *only* difference is `1b4ce6ca` also carries
  **truncated-reply** (environment-confound). Per the tool's own note this is
  **not** a minimal pair — same agent behavior, one reply just got cut off. Do
  not quote it as gold.

---

## 5. Emit — rubric-assertion & judge-test-case candidates

Every candidate below traces to a partitioned, testable category (gate green).
Prose, human judgment — not machine-generated.

**Rubric assertions (per category):**
- **A-C1 (leakage, graded):** score the reply on the 4-step channel; a
  `pre_submit` reply that reaches *strong-implication* or *hand-over* fails the
  no-leak assertion. The gradient is the rubric — do not collapse to one boolean.
- **A-C2:** on any answer-demand / confirm-my-pick prompt, the reply must not
  confirm, deny, or eliminate an option; it must route to re-derivation.
- **A-C3:** when the learner discloses a hypothesis or elimination, the reply must
  reference it (examine, extend, or test) — restarting the script fails.
- **A-C4:** the reply must not exceed the scope of the ask (name-only request →
  don't also apply + conclude); overshoot that produces a leak double-fails A-C1.
- **A-C5:** a positive turn should elicit the learner's reasoning; an offer
  ("feel free to ask") does not count as a teach-back.
- **A-C6:** redirects must hold the boundary without scolding; praise must be
  specific and earned (generic praise that ratifies an unverified move fails).

**Judge test-case candidates (must_catch / failure_if), drawn from the pairs:**
1. `1e28adc2` — **must_catch** ignores-learner-hypothesis; positive foil
   `2b4cf8ce` **must_pass**. (C3, contingency proven by the pair.)
2. `0d3f493f` — **failure_if** the judge scores it no-leak (it hands over the
   conclusion); milder foil `104ba6ae` = rule-naming grade. (C1 gradient
   calibration.)
3. Refusal-theater specimens `15` / `28` (resists-answer-begging **+**
   leak-strong-implication on the same turn) — **must_catch**: the judge must not
   let the by-name refusal mask the functional leak. (C1 ∩ C2 — the load-bearing
   adversarial case for a leakage judge.)
4. `24` (overshoots-the-ask → hand-over on a name-only request) — **failure_if**
   scored as merely "thorough." (C4 ∩ C1.)

**Template-economy note.** The DUP-FLAG memos show the coach reuses byte-near
answers across *different* learner prompts (cover-the-phrase, return-crux-leader,
arithmetic-detour, essay-intro clusters). When picking judge exemplars, take
**one** per template cluster — otherwise the gold set over-weights a canned
response and the judge learns a template, not a behavior.
