# Design-agent prompt — English Coach, Gen2 Slice v3 ("commit-first")

**Paste everything below the line into the design agent, attaching the two baseline
artifacts it references.** Keep this file as the record of what was asked.

- Baseline prototype: `English Coach - Gen2 Slice v2 -desktop-.html` (approved 2026-07-18)
- Data contract: `gen2-slice.fixture.json` (unchanged — do not touch)
- Baseline spec: `03-ears-spec-gen2-coach.md` (requirement IDs referenced below)

---

## Prompt

You previously built **English Coach — Gen2 Slice v2 (desktop)**, a single-file
offline prototype driven by `gen2-slice.fixture.json`. Iterate it into **v3
("commit-first")**. This is a targeted behavioral revision, not a redesign: keep the
visual system, layout, session flow, summary, reasoning trace, and all copy voice
rules exactly as in v2 unless a delta below says otherwise.

### The one-sentence change

Remove all pre-pick help (the "Ask for a nudge first" opener) so coaching begins
only after the learner commits to a choice, and replace the ladder's dead-end
exhaustion state with a priced escape that routes to the breakdown without the
chat ever revealing the answer.

### Why (context you should honor, not display)

The pre-pick opener was always a synthesized placeholder — Gen2 has no item-level
ladders, and the ladder's strength is misconception-keying, which requires a
committed wrong choice. Removing it makes the first attempt an honest, unhinted
retrieval attempt. The priced escape fixes the v2 dead-end ("re-read and pick
again" with nowhere to go) without granting a free in-chat reveal: the walkthrough
costs the learner their solve credit, and the answer still only ever appears in
the breakdown view, never in the coach conversation.

### Requirement deltas (against `03-ears-spec-gen2-coach.md`)

**REMOVED — delete these behaviors entirely:**

- **DAT-5** (synthesized opener) — gone. No opener is synthesized for any item.
- **MOM-2** (no-pick nudge, placeholder badge, "1 of 1" counter) — gone. There is
  no nudge affordance of any kind before a submission.

**AMENDED:**

- **MOM-1 (no-pick moment → idle moment).** WHILE no choice has been submitted,
  the coach panel shall show a quiet idle state: coach identity + one line of
  copy in the spirit of "Commit to a choice — coaching starts from what you
  pick." Free-ask (MOM-7 stub) remains available in this state. No ladder, no
  counter, no hint affordance.
- **MOM-4 (exhaustion).** WHEN all 3 rungs are used, the nudge control shall
  disable as in v2, but the moment shall now offer exactly two actions:
  1. **"Let me try again"** (primary) — unchanged v2 behavior; and
  2. **"Walk me through it"** (secondary) — the priced escape, new ESC-1…4 below.
  The exhaustion copy shall still state plainly that the coach has no more
  nudges and never tells the answer.
- **CTRL-1.** WHILE unsolved with no submission: primary action Submit (enabled
  once a choice is selected). There is **no** secondary nudge control. Delete
  "Ask for a nudge first" from every surface.
- **CTRL-2.** Unchanged for rungs 1–3, but the footnote wording must no longer
  imply a pre-pick nudge existed (no "first" framing).
- **FBK-1 (result labels).** The feedback view's result label gains a third
  state: "Solved on first try" / "Worked through it with the coach" /
  **"Walked through together"** (or equivalent honest, non-judgmental phrasing —
  never shaming). The walked-through state uses the same `why_correct_md` +
  `rule_md` blocks; additionally surface `why_tempted_md` for the learner's
  last wrong letter.
- **SEQ-4 (recording).** Per-item record gains a third outcome:
  `first-try | coached | walked-through`, plus the miss tag as before.
- **SUM-2 (summary chips).** Run-length chips gain a third mark for
  walked-through items, visually distinct from ✓ (first-try) and ↺ (coached).
  Legend must name all three honestly.
- **SUM-1 (score).** First-try score stays k/15; walked-through items never
  count toward it.
- **Acceptance walkthrough (§11)** — replaced below.

**NEW — ESC (priced escape):**

- **ESC-1** WHEN the learner activates "Walk me through it" at exhaustion, the
  system shall route directly to the feedback/breakdown view for the current
  item in the walked-through state (FBK-1 above) and record the outcome
  (SEQ-4). The coach chat shall NOT emit the answer as part of this transition —
  the reveal happens only inside the breakdown view.
- **ESC-2** The escape shall be visibly priced before activation: one line of
  copy stating the trade in plain language (e.g. "The breakdown shows the
  answer — this one won't count as solved."). No confirmation dialog; the
  labeled cost is the friction.
- **ESC-3** The escape shall exist ONLY in the exhausted state. It shall never
  appear at rungs 0–2, never pre-submission, and the free "Reveal answer"
  affordance shall not exist anywhere in v3.
- **ESC-4** The reasoning trace (TRACE family) shall log the escape with source
  copy in the spirit of: "Learner chose the walkthrough after 3 rungs — recorded
  as walked-through, no first-try credit. The breakdown reveals the answer; the
  conversation still never did." Leak checks (LEAK-1/2) continue to apply to
  every chat-emitted body; the breakdown view is exempt by design, as in v2.

**UNCHANGED — everything else, explicitly including:** DAT-1…4 (data contract;
3-rung ladders, no 4th rung, no ladder for the correct letter), SEQ-1…3, MOM-3
(shared-ground acknowledgment → pump), MOM-5 (letter-switch restarts ladder),
MOM-6 (correct moment, verdict-first), MOM-7 (free-ask stub, now also the idle
moment's only input), MOM-8 (moment isolation), LEAK-1/2, VOICE-1…5, TRACE-1…4
(minus any opener-related lines, which no longer exist), CTRL-3/4, FBK-2,
SUM-3/4, PKG-1…4.

### Acceptance walkthrough (replaces §11)

1. Load → dashboard → start session → item 1 shows the idle moment: no hint
   affordance anywhere, Submit disabled until a choice is selected (MOM-1,
   CTRL-1).
2. Free-ask in the idle moment → stub reply, leak-guarded, no answer (MOM-7).
3. Pick the tempting distractor → shared-ground acknowledgment + pump; counter
   "1 of 3"; trace shows misconception + rationale + leak check (MOM-3).
4. Two more nudges → hint, prompt; "3 of 3" → exhausted state shows BOTH
   "Let me try again" and the priced "Walk me through it" with its cost line
   (MOM-4, ESC-2).
5. Take the escape → breakdown in walked-through state: why-correct + rule +
   why-tempted for the last wrong letter; chat transcript contains no reveal
   (ESC-1, FBK-1).
6. On a later item, switch wrong letters → new ladder at rung 1 (MOM-5); solve
   it → "Worked through it with the coach" (MOM-6).
7. Solve one first-try → "Solved on first try"; finish 15 → summary chips show
   three distinct marks with an honest legend; first-try score excludes the
   walked-through item (SUM-1/2).

### Deliverable

One self-contained desktop HTML file, offline, no network calls, driven only by
the inlined `gen2-slice.fixture.json` data: **"English Coach - Gen2 Slice v3
-desktop-.html"**. Do not modify the fixture. Everything the new states need
(`_hint_ladders`, `why_correct_md`, `rule_md`, `why_tempted_md`,
`per_choice_rationale`) already exists in it.
