# Manual validation — commit-first coach (Phase 3 + residual pass)

**For:** a human validating the fixes by hand in the browser.
**Build under test:** HEAD `07692b9` (T19–T28 + residual R1–R7).
**Evidence trail:** [visual gap register](commit-first-coach.visual-gap-register.md) · [spec](commit-first-coach.spec.md) · [tasks](commit-first-coach.tasks.md)

---

## 0. Launch (once)

The dev server must run with the flag **ON** and auth bypass. Two ways:

```bash
# A) via the preview launch config (flag now baked into .claude/launch.json)
#    — start "frontend-preview" from the app's Run/preview UI.

# B) manual, from the repo root:
cd frontend
NEXT_PUBLIC_FF_COMMIT_FIRST_COACH=1 E2E_BYPASS_AUTH=1 pnpm dev
```

Open **http://localhost:3000/learn/quiz**.

**Flag sanity check (do this first):** the item card footer reads
*"Pick a choice and submit — no hints until you commit."* and there is **no**
"Get a hint" / "Reveal answer" button anywhere. If you see those, the flag is
OFF — stop and fix the launch env.

> Side-by-side option: open the v3 prototype in a second window to compare —
> `docs/plan/gen2-proto-handoff/English Coach - Gen2 Slice v3 -desktop-.html`
> (click the **2 Quiz** tab in its top nav). The app should match its *behavior
> and copy*, not its exact pixels.

Legend: **[ ]** = check it · **→** expected result. A fix ID in `(R#/V#)` links
back to the register.

---

## 1. Idle / pre-commit (item 1)

- [ ] **Purpose card (V11).** A boxed line **"THIS ITEM WAS PICKED ON PURPOSE"**
  sits above the passage → reads like *"Opening in Punctuation at difficulty 1
  — the first of 30 reviewed items."* (a real reason, not bare `Q1 · s-punc`).
- [ ] **No pre-commit help (FR-2).** No hint text, no ladder, no "Reveal".
- [ ] **Coach header id hygiene (R2a/R2b).** Right panel shows
  **"Current item: Q1 · Punctuation"** and **"Sees your history: 0 misses on
  this skill"** → the words **`s-punc`** / **`s-org`** must appear **NOWHERE**.
- [ ] **Idle coach copy (MOM-1).** Conversation shows *"Commit to a choice —
  coaching starts from what you pick. Ask me anything below; I never reveal the
  answer."*
- [ ] **Composer footer (V12).** Under the ask box: *"Coaching starts after you
  submit — it works from what your pick reveals."*

---

## 2. Wrong submit → coached transcript (V1/V2/V3)

Pick **A (NO CHANGE)** — a wrong answer here — and click **Submit answer**.

- [ ] **Committed-wrong marker (V8).** Choice **A** turns red with a filled red
  **A** badge and a **✗** on the right.
- [ ] **It's a transcript, not a box (V1).** The coach panel shows, top to
  bottom, as chat bubbles:
  1. a learner bubble **"I chose A."** (right-aligned)
  2. a coach acknowledgment bubble
  3. a coach **PUMP** bubble
- [ ] **Ack voice (V2).** The ack bubble opens with a verdict and a specific
  diagnosis and hands off — e.g. *"Not quite — and it's a telling miss. …
  So —"*. It must **not** be a flat "Re-read the sentence, what is it testing?"
  generic line, and must **never name the correct letter**.
- [ ] **Ladder rail (V3).** Above the transcript: a **PUMP → HINT → PROMPT**
  rail; **PUMP** is filled/active, the other two dim.
- [ ] **Stage badge (V3).** The pump bubble carries a small
  **"PUMP · no answer"** eyebrow.
- [ ] **Counter honesty (FR-4).** Shows **"1 of 3"** (not "1 of 2").
- [ ] **Both controls from rung 1 (V5).** **"Let me try again"** AND
  **"Show me more →"** are both present now (try-again is not exhaustion-only).
- [ ] **Submit hidden in the loop (V4).** The big "Submit answer" button is gone
  while A stays selected.

---

## 3. Escalate the ladder (V6)

Click **"Show me more →"**.

- [ ] A learner bubble **"I'm still stuck."** appears, then a coach **HINT**
  bubble; the rail advances to fill **HINT**; counter → **"2 of 3"**.
- [ ] **Stable button label (V6).** The escalation button still reads
  **"Show me more →"** — it does **not** relabel to "I'm still stuck →".
- [ ] **Auto-scroll (R1).** The newest bubble + the buttons are in view without
  you scrolling the panel.

Click **"Show me more →"** again.

- [ ] Second **"I'm still stuck."** echo, a **PROMPT** bubble, rail fills
  **PROMPT**, counter → **"3 of 3"**.

---

## 4. Exhaustion (V7 / R1)

You should now be at the exhaustion state (all 3 rungs shown).

- [ ] **Exhaustion copy.** *"That's all three nudges — I don't have more, and I
  never tell the answer…"*
- [ ] **CTA hierarchy (V7).** **"Let me try again"** is the **filled/primary**
  button; **"Walk me through it"** is the **outline/secondary** button below it
  (the answer-revealing path must NOT be the visually dominant one).
- [ ] **Priced cost line.** Under the escape: *"The breakdown shows the answer —
  this one won't count as solved."*
- [ ] **Opaque footer (R1).** The buttons sit on a solid background — you should
  **not** see transcript text bleeding through behind them.

---

## 5. Walked-through feedback (V14/V15/V16/V17/V18)

Click **"Walk me through it"**.

- [ ] **Banner delivers the answer (V14).** The banner names it explicitly:
  *"The answer appears here, not in the chat: it's D. Your last pick was A —
  the cards below unpack both."* (letters will match your item).
- [ ] **Markdown renders (V15).** Feedback prose shows **bold** styling, **not**
  literal `**asterisks**` anywhere.
- [ ] **Three cards (V16).** A **FEED-UP · GOAL** / **FEED-BACK · GAP** /
  **FEED-FORWARD · NEXT** triplet.
- [ ] **Feed-up label hygiene (R5).** The goal card reads
  *"Punctuation · underlined-span item…"* — **no** raw **"mc"** token.
- [ ] **All-choice rationales (V17).** Every choice A–D shows its own rationale
  line (not just the correct + your pick).
- [ ] **Self-explanation + gauge (V18).** A *"Saying it back makes it stick"*
  textarea, with **"This clicked ✓ / Still fuzzy"** chips. Typing is **optional**
  — you can advance without it.

---

## 6. Coached solve confirms in place (FR-15 / R4)

Click **Next question**. On the new item, submit a **wrong** letter to enter the
loop, then click **"Let me try again"** and pick the **correct** letter and
submit (retry until you hit it).

- [ ] **In-place confirmation (FR-15).** The feedback screen does **NOT** auto-open.
  Instead the coach panel shows *"Yes — that's it. You worked through the trap…"*
  plus an inline **"Worked through it with the coach"** label.
- [ ] **Correct-choice mark (R4).** The correct choice turns **green** with a
  **✓** on the right.
- [ ] **Learner-initiated breakdown (FR-15).** A **"See the breakdown →"** button
  is offered; the full feedback screen appears only after you click it.

---

## 7. Coach page grounding (V22/V23)

Click the **Coach** icon in the left rail (or the **4 Coach** tab in the prototype).

- [ ] **Grounded opener (V22).** A proactive coach greeting referencing the
  session — e.g. *"Ready when you are. Want to unpack the Q1 · Punctuation item,
  or work a fresh one?"* — **not** an empty conversation area.
- [ ] **Miss-cluster id hygiene (R2c).** If a miss count shows, it reads
  *"cluster on **Punctuation**"* (the skill name) — never the item label
  "Commas" and never `s-punc`.
- [ ] **Context sidebar (V23).** Left of the chat: **"THE COACH KNOWS YOUR LAST
  ITEM"** (current item + diagnosed misconception, or an honest "no current item
  pinned yet") and **"ONE COACH, THREE MODES"** list.

---

## 8. Summary via End session (T14 / R6 / V25 / V26)

Go back to the quiz, then click **End session**.

- [ ] **Routes to summary (T14).** You land on **`/learn/summary?session=…`**
  (NOT the dashboard). If nothing was resolved, dashboard is correct instead.
- [ ] **Tiles.** **"SOLVED FIRST-TRY"** (e.g. `0/2`), **MASTERY CHANGE**, **TIME**.
- [ ] **Outcome heading honesty (R6).** The counts sit under **"HOW ITEMS
  RESOLVED THIS SESSION"** — it must **NOT** say *"Each skill ran until you
  cleared it"* (we don't render a per-skill breakdown).
- [ ] **Three outcome lines.** ✓ Solved on first try · ↺ Worked through with the
  coach · → Walked through (not counted as solved), with a legend.
- [ ] **Misconception recap (V26 / R7) — DATA-DEPENDENT.** Currently the dev bank
  has `misconception` on only 47/987 items, so the recap card is usually
  **honestly absent** — that is expected, not a bug. To see it render, you need
  an item whose `misconception` field is populated (the "author misconception
  fields" task covers bank coverage). The *logic* is unit-proven; this line is
  the one place the manual pass can legitimately show nothing.

---

## 9. Regression: flag OFF (FR-14)

Restart the server **without** the flag (`pnpm dev`, no
`NEXT_PUBLIC_FF_COMMIT_FIRST_COACH`), reload `/learn/quiz`.

- [ ] Old behavior returns: **"Get a hint"** pre-submit, instant feedback view on
  any submit, no retry loop. Nothing from §1–§8 above should appear.

---

## Result

| § | Area | Pass? | Notes |
|---|---|---|---|
| 1 | Idle / purpose card / id hygiene | | |
| 2 | Wrong → transcript + ack + rail | | |
| 3 | Escalation | | |
| 4 | Exhaustion CTA + footer | | |
| 5 | Walked-through feedback | | |
| 6 | Coached-solve confirm (FR-15) | | |
| 7 | Coach page grounding | | |
| 8 | Summary via End session | | |
| 9 | Flag-OFF regression | | |

**Automated backstop already green:** vitest 652/652 (affected areas),
Playwright 16/16 (v3 conformance + journeys). This manual pass covers the
*presentation-form* checks the automated suite can't assert.
