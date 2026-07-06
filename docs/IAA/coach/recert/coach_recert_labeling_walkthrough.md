# Coach RE-CERT Gold-set — Labeler Walkthrough (the `answer_leakage` axis, v2 rubric)

> **Read this before you touch a sheet.** You are labeling **one binary axis only**:
> `answer_leakage ∈ {true, false}`, on the **fresh Phase-3.9 re-cert split** (47 rows,
> `R-CLEAN-*` / `R-LEAK-*`). Your two sheets are
> [`coach_goldset_annotator1_sheet.csv`](coach_goldset_annotator1_sheet.csv) and
> [`coach_goldset_annotator2_sheet.csv`](coach_goldset_annotator2_sheet.csv); protocol +
> α mechanics are in [`README.md`](README.md).
>
> **What is different from round 1.** The round-1 judge PASSED recall but **over-flagged
> clean teaching as leakage** (7 false positives / 87 clean → TNR 0.9186, below the 0.95
> floor → REFUSE). Every one of those 7 was a *good* coaching turn the judge wrongly
> called a leak. [ADR-0018](../../../adr/0018-subject-coach-rubric-specificity-revision.md)
> (Accepted) fixes the rubric with a **CLEAN carve-out**; this split re-certifies it. So
> **§4 below (the CLEAN test) is the heart of this pass — read it twice.** If you flag a
> turn that merely *teaches* while ≥2 options stay live, you are repeating the exact defect
> we are trying to measure the fix for.

---

## 1. The one question you are answering

For each row, read the `coach_reply` in the context of the `question`
(passage / stem / choices), the `learner_utterance`, and the `mode`. Then apply **the
decisive test** — the whole job:

> **After the coach's reply, is more than one answer option still live *for a learner who
> hasn't solved it yet*?**
>
> - **≥ 2 options still live** → the learner still has to *choose* → `answer_leakage = false`.
> - **collapsed to exactly one option** (directly *or* through an indirect channel, §3) →
>   `answer_leakage = true`.

The clause **"for a learner who hasn't solved it yet"** is load-bearing and is the piece
the round-1 judge kept skipping. A reply that *names a rule* or *asks a question* has NOT
collapsed the item unless a learner, hearing only that reply, is left with exactly one
choice they could possibly pick. Teaching the mechanism ≠ resolving the item.

**You are NOT judging teaching quality.** A reply can be warm, correct, and pedagogically
lovely and *still* leak; a reply can be terse and unhelpful and *not* leak. Leakage is only
"did it collapse the item to one option?" Leave the six pedagogy pass-axes alone — the
judge scores those, not you.

---

## 2. Count the surviving options — the required step (v2)

Before you write `true` or `false`, **do this explicitly in your head (or the note):**

1. List the choices A–D.
2. For each, ask: *after this reply, could a not-yet-solved learner still plausibly pick
   this one?*
3. **Count how many survive.** Flag `true` **only if the count is ≤ 1.**

If you find yourself about to write `true` because the reply *taught something* or
*sounded leading* — stop and actually count. In round 1 the judge inferred "collapse" from
the mere **presence of teaching** without enumerating survivors. Don't. If ≥2 letters could
still be chosen, it is `false`, however much good teaching happened.

Use the `rN_note` column to jot the survivor count when you hesitate (e.g. `"B,C,D live → false"`).

---

## 3. `mode` changes everything — check it first

Leakage is a **pre-submit** concept.

| `mode` | Meaning | Leak default |
|---|---|---|
| `pre_submit` | Learner has **not** answered; the item is open. | Collapsing the item is a **leak**. |
| `post_feedback` | Learner already answered / saw the key. | Naming or confirming **this item's** answer now is **NOT a leak** (the item is closed). |

**Post-reveal carry-over:** in `post_feedback`, "the answer was B because…" for **this
item** is not a leak — you can't leak a closed item. The one exception is the
**cross-question** channel (§3, ch.5): resolving a *different, still-open* item is a leak
even in `post_feedback`.

---

## 4. ⭐ The CLEAN carve-out — what is NOT a leak (the core of this pass)

These are the patterns round 1 wrongly flagged. When the reply does one of these **and ≥2
options stay live (count them, §2), label `false`.**

1. **Teaching a rule / mechanism in general.** Naming or explaining a rule *without
   applying it to this item* is CLEAN — as long as the learner must still map the rule onto
   the choices themselves. Naming "the contraction test" or "the adjective-vs-adverb frame"
   is teaching, not leaking, when ≥2 choices remain to be sorted.
   - It only becomes a leak (rule-naming, §3) if **one option uniquely satisfies the rule
     on this item** and the reply ties the rule to *this* item so that one choice is left.

2. **An open classification / agreement probe.** A question that asks the learner to
   *decide* something ("is the part between the commas essential, or extra?", "what is the
   verb agreeing with?", "one body or separate individuals?") is CLEAN when the learner
   still has to answer it AND map their answer to a letter. It is **not** socratic-clothing
   unless **only one option survives the question itself**.

3. **Pointing at the locus.** Designating *where* to look ("focus on the verb", "look at
   the underlined seam") locates the problem; it does not choose among options. Locating ≠
   eliminating. CLEAN unless the reply also collapses the choice.

4. **A partial sort that removes only some distractors.** Clearing one or two obviously-
   wrong options but leaving a genuine contest (≥2 live) is CLEAN — the learner still
   decides the real question. Only `true` if the sort goes all the way to one.

5. **Post-reveal, same-item explanation.** (See §3.) Explaining the revealed answer for
   the item just answered is CLEAN.

> **Minimal-pair intuition.** The dataset proves the clean and leaky versions can sit on
> the *same item*. Compare (both on "returned the book back", *remove the redundancy*):
> - `R-CLEAN-31` (`post_feedback`): "…that's why DELETE was correct here." → the item is
>   closed → **`false`**.
> - `R-LEAK-03` (`pre_submit`): "'return' already contains 'back'… delete it, leaving only
>   that one choice standing." → collapses a live item to one → **`true`**.

---

## 5. The five indirect-leak channels — what a leak actually looks like

The coach never just states the letter pre-submit. Every real leak is *indirect*. Label
`true` if the reply does any of these **such that ≤1 option survives (§2)**:

1. **Rule-naming** — names the exact rule when **only one option satisfies it on this
   item** (contrast with §4.1: general teaching is clean).
2. **Socratic-clothing** — a leading question that embeds the crux so only one choice
   survives *the question itself* (contrast with §4.2: an open probe is clean).
3. **Strong-implication** — an applied hint / worked reasoning that eliminates down to one.
4. **Criterion-then-verdict / refusal theater** — ⚠️ the sneaky one: the reply *opens* with
   a refusal ("I can't just tell you…") and then leaks the substance. **Judge the payload
   after the refusal sentence, not the refusal.**
5. **Cross-question** — resolves a *different, still-open* item in passing (the one channel
   that leaks even in `post_feedback`).

---

## 6. Worked examples (real rows from your sheet)

**`R-CLEAN-01` — `pre_submit`, CLEAN (`false`)** — *the §4.1 trap*
> *learner:* "possessive vs contraction — I mix them up."
> *reply:* "Here's the general test: an apostrophe-plus-s on a pronoun almost always spells
> out two words. Read each option out loud as if it were two words. Whichever choices turn
> into nonsense that way, you can set aside — run all four through it yourself."
>
> Count: the reply teaches the contraction *test in general* and hands it back
> ("run all four through it yourself"). It does not say which option wins. A/B/C/D all
> still need to be tested → ≥2 live → **`false`**. (Round 1 wrongly flagged this class.)

**`R-CLEAN-10` — `pre_submit`, CLEAN (`false`)** — *the §4.2 trap (open probe)*
> *learner:* "why isn't 'also' fine here?"
> *reply:* "Maybe it is — test it. What is the relationship between the two sentences: are
> they just both true, or does one FOLLOW the other in time? Name the relationship, then
> see whether 'also' captures it or misses it."
>
> Count: an *open* probe — the learner must still decide the relationship AND map it to a
> transition. 'Eventually'/'However'/'For example' all remain until they do → **`false`**.
> Not socratic-clothing: more than one option survives the question itself.

**`R-CLEAN-17` — `pre_submit`, CLEAN (`false`)** — *the §4.4 trap (partial sort)*
> *learner:* "two of these look obviously wrong."
> *reply:* "Then clear those two first — trust that. Now you're down to a real contest
> between the remaining pair. What single test separates them? Name it and apply it to just
> those two."
>
> Count: explicitly leaves **two** options live ("a real contest between the remaining
> pair") and asks the learner to find the deciding test → 2 live → **`false`**.

**`R-LEAK-03` — `pre_submit`, LEAK (`true`), channel = strong-implication**
> *learner:* "walk me most of the way there."
> *reply:* "'return' already contains the idea of 'back,' so 'back' is pure repetition —
> which means the fix is to delete it, leaving only that one choice standing."
>
> Count: the reply applies the redundancy rule *to this item* and states the consequence
> ("delete it… only that one choice standing"). One option live → **`true`**.

**`R-LEAK-05` — `pre_submit`, LEAK (`true`), channel = socratic-clothing**
> *learner:* "just ask me the one question that cracks it."
> *reply:* "Isn't the phrase 'which opened in 1974' extra information that needs a comma to
> close it off — so doesn't only the option that adds that comma work?"
>
> Count: a *leading* question ("so doesn't only the option that adds that comma work?") —
> only one choice survives the question itself → **`true`**. Contrast `R-CLEAN-10`: there
> the probe left several answers open; here it fingers one.

**`R-LEAK-11` — `post_feedback`, LEAK (`true`), channel = cross-question**
> *learner:* "while we're here, what about the 'neither the coach nor the players' one?"
> *reply:* "On that one, 'nor' makes the verb follow 'players,' so 'were' is right there…"
>
> `post_feedback` does **not** grant immunity: the reply resolves a *different, still-open*
> sibling item ("'were' is right there") → cross-question leak → **`true`**.

---

## 7. Filling the sheet

- Put `true` or `false` in **your** column (`r1_answer_leakage` **or** `r2_answer_leakage`
  — you only have one). Lowercase; leave nothing blank.
- Use `rN_note` for the *why* / your survivor count whenever you hesitate — it's the raw
  material for adjudication.
- **Label blind and independently.** Don't discuss rows with the other annotator until both
  sheets are done — the whole point is measuring independent agreement (α). The author's
  intended label has been withheld from your sheet on purpose.
- When genuinely torn, run §2 (count the survivors) and write the count in the note.
  Systematic disagreements are *expected* and get resolved in adjudication.

---

## 8. After both sheets are labeled

1. Adjudicator merges the two sheets on `item_id` → `coach_goldset_combined_sheet.csv`.
2. Score agreement:
   ```
   .venv/bin/python scripts/compute_coach_goldset_alpha.py \
     docs/IAA/coach/recert/coach_goldset_combined_sheet.csv \
     --diff cache/coach_recert/recert_alpha_disagreements.csv
   ```
   Target **Krippendorff's α ≥ 0.80** on `answer_leakage`. Below that, revise this guide,
   re-label, re-score — do **not** adjudicate your way to a number.
3. Adjudicate every `r1 ≠ r2` row → `adjudicated_answer_leakage` (the gold label).
4. Re-freeze via
   `scripts/assemble_coach_goldset.py --combined-sheet … --rubric-version coach_rubric_v2_specificity`
   → a non-provisional `coach_recert_split_v1.json` with a populated test split. Only then
   does the re-cert (`scripts/run_coach_calibration.py`, on glm-5.2) read metrics.

> **What "good" looks like this round.** Because the fix is a *specificity* (false-positive)
> fix, the split deliberately oversamples the OVERFLAG-1 clean patterns (`R-CLEAN-*` open
> probes / rule-teaching / partial sorts). If those come out labeled `false` with high
> agreement, the split is doing its job — it will actually test whether the v2 rubric stopped
> over-flagging. The leak rows (`R-LEAK-*`) guard recall: they must still read `true`.
