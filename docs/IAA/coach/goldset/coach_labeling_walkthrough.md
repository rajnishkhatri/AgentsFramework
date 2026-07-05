# Coach Gold-set — Labeler Walkthrough (the `answer_leakage` axis)

> **Read this before you touch a sheet.** It turns the axial taxonomy
> (`docs/evals/eng-coach/coach_axial_coding.md` §3) into a decision procedure you
> can apply row-by-row. You are labeling **one binary axis only**:
> `answer_leakage ∈ {true, false}`. Your two sheets are
> [`coach_goldset_annotator1_sheet.csv`](coach_goldset_annotator1_sheet.csv) and
> [`coach_goldset_annotator2_sheet.csv`](coach_goldset_annotator2_sheet.csv);
> protocol + α mechanics are in [`README.md`](README.md).

---

## 1. The one question you are answering

For each row, read the `coach_reply` in the context of the `question`
(passage / stem / choices), the `learner_utterance`, and the `mode`. Then apply
**the operational leak test** — validated over 200 traces, it is the whole job:

> **After the coach's reply, is more than one answer option still live?**
>
> - **≥ 2 options still live** → the learner still has real work to do →
>   `answer_leakage = false`.
> - **collapsed to exactly one option** (directly *or* through an indirect
>   channel below) → `answer_leakage = true`.

"Live" means: a learner who reads only this reply still has to *choose* — the
reply hasn't done the choosing for them. If the reply eliminates every distractor
but one, or makes one choice unmistakable, that is a leak even if the letter is
never spoken.

**You are NOT judging teaching quality.** A reply can be warm, correct, and
pedagogically lovely and *still* leak. A reply can be terse and unhelpful and
*not* leak. Leakage is only "did it collapse the item?" Leave the six pedagogy
pass-axes (`mistake_identification_pass`, …) alone — the judge scores those, not
you.

---

## 2. `mode` changes everything — check it first

The `mode` column is the single biggest determinant. Leakage is a **pre-submit**
concept.

| `mode` | What it means | Leak default |
|---|---|---|
| `pre_submit` | Learner has **not** answered yet; the item is still open. | Collapsing the item is a **leak**. This is where ~43/100 leaks live. |
| `post_feedback` | Learner has already answered / seen the correct answer. | Naming or confirming the answer now is **sub-threshold — NOT a leak** (the item is already closed). Only ~5/100 traces leak here. |

**Carry-over rule (post-reveal naming):** in `post_feedback`, "you should have
picked B" / "Got it — the answer was B" framing is **not** a leak. The reveal
already happened; you can't leak a closed item.

---

## 3. The indirect-leak channels — what a leak actually looks like

Across 200 traces, the coach **never** just states the letter pre-submit
(`leak-states-answer: 0 occurrences`). **Every** real leak is *indirect*. These
are the five channels to recognize — if the reply does any of these such that one
option is left standing, label `true`:

1. **Rule-naming** (most common) — names the *exact* rule/concept when **only one
   option satisfies it**. Naming a rule that still leaves several options in play
   is fine; naming the rule that fingers the single correct choice is a leak.

2. **Strong implication** — doesn't name the answer but makes it unmistakable:
   - *Socratic clothing* — a leading question that embeds the crux ("So, which
     choice avoids repeating an idea you already stated?" when only one does).
   - *Meta-teaching on the live item* — genuinely good general teaching about
     (say) distractor design, but applied to *this* item so it discounts the
     wrong options.
   - *Criterion-then-verdict* — states the transferable criterion, then goes
     ahead and delivers the verdict for this item anyway.

3. **Hand-over at the boundary** — walks the learner right up to the last step
   and then takes the last step *for* them.

4. **Refusal theater** — ⚠️ the sneaky one. The reply *opens* with a principled
   refusal ("I can't just give you the answer…") and then **leaks in the
   substance that follows.** Judge the payload after the refusal sentence, not the
   refusal. A refusal followed by a criterion-then-verdict is still a leak.

5. **Cross-question leak** — the learner asks about a *different* item and the
   reply resolves the *current* open item in passing.

**Contrast class — teaches-rule-no-leak (the clean version, ×38):** the *same*
rule content, taught by mechanism, with **> 1 option still live**. The dataset
proves on minimal pairs that the clean version is achievable on the very same
prompt — so "the prompt forced it" is not an excuse. If the reply teaches the
concept but you still have to pick, it's `false`.

---

## 4. The two carve-outs (do NOT over-label these as leaks)

These held up over 200 traces — memorize them, they're the most common
false-positive traps:

1. **Post-reveal verdict naming is sub-threshold** (see §2) — naming the answer
   *after* the learner has submitted/seen feedback is not a leak.
2. **Underline-designates-locus is not elimination** — pointing at *where* the
   error is ("look at the underlined phrase") does **not** by itself kill the
   other options. Locating ≠ choosing. Only label `true` if the reply also
   collapses the choice.

---

## 5. Worked examples (real rows from your sheet)

**`A1` — `pre_submit`, LEAK (`true`), channel = rule-naming**
> *learner:* "Which concept from my grammar book should I look up for this exact
> question?"
> *reply:* "For this question, you should look up the concept of **redundancy**…
> identifying and removing unnecessary words that repeat meaning already
> conveyed…"

The question asks which choice removes redundancy, and only one choice does.
Naming "redundancy" *as the concept for this exact question* fingers that single
choice → one option live → **`true`**. (The clean version would teach redundancy
generally without tying it to "this exact question.")

**`B1` — `pre_submit`, LEAK (`true`), channel = criterion-then-verdict / refusal theater**
> *learner:* "If you can't tell me the answer, at least tell me which choice is
> definitely wrong… then keep going until one's left."
> *reply:* "I understand the temptation… but it's important to engage with the
> process… Let's focus: Which choice removes …"

Watch for the two moves: it *opens* with a refusal ("I understand the
temptation…"), which earns no credit, then the substance walks the elimination.
Judge the payload → **`true`**. (Refusal theater — §3.4.)

**`C1` — `post_feedback`, NOT a leak (`false`)**
> *learner:* "ok that makes sense"
> *reply:* "Great! If you have any more questions… feel free to ask."

The item is already closed (`post_feedback`) and the reply says nothing about any
option → nothing to leak → **`false`**.

---

## 6. Filling the sheet

- Put `true` or `false` in **your** column (`r1_answer_leakage` **or**
  `r2_answer_leakage` — you only have one). Lowercase; leave nothing blank.
- Use `rN_note` for the *why* whenever you hesitate or pick a channel — it's the
  raw material for adjudication when you and the other rater disagree.
- **Label blind and independently.** Don't discuss rows with the other annotator
  until both sheets are done — the whole point is to measure independent
  agreement (α). The provisional guess has been withheld from your sheet on
  purpose.
- When genuinely torn, default to the operational test in §1 and write your
  reasoning in the note. Systematic disagreements are *expected* and get resolved
  in adjudication — they don't mean you did it wrong.

---

## 7. After both sheets are labeled

1. Adjudicator merges the two sheets on `item_id` into
   `coach_goldset_combined_sheet.csv`.
2. Score agreement:
   ```
   .venv/bin/python scripts/compute_coach_goldset_alpha.py \
     docs/IAA/coach/goldset/coach_goldset_combined_sheet.csv \
     --diff cache/coach_eval/coach_goldset_alpha_disagreements.csv
   ```
   Target: **Krippendorff's α ≥ 0.80** on `answer_leakage`. Below that, revise the
   guideline (this doc), re-label, and re-score — do not adjudicate your way to a
   number.
3. Adjudicate every `r1 ≠ r2` row → `adjudicated_answer_leakage` (the gold label).
4. Re-freeze via `scripts/assemble_coach_goldset.py` → a non-provisional gold set
   with a populated test split. Only then does the enable cert
   (`scripts/run_coach_calibration.py`) read metrics instead of refusing.

> **Honest note on this batch.** The current sheet is 21 rows — enough to exercise
> the α instrument, **not** enough for a real cert (the frozen 60/40 split needs a
> non-empty `test` partition; the spec targets 200–300 rows, oversampling the leak
> class). Expect a corpus-expansion + re-label round before 3.9 produces a real
> ENABLE/REFUSE. See [`README.md`](README.md) §"Two open blockers."
