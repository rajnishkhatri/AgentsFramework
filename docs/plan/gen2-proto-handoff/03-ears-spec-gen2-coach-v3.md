# EARS Specification — English Coach, Gen2 Slice **v3 "commit-first"** (final)

**Source of truth:** `English Coach - Gen2 Slice v3 -desktop-.html` (approved prototype) + `gen2-slice.fixture.json` (immutable data contract). This spec is **self-contained** — implement v3 end to end from this document; do not consult the v2 spec except via the delta log (§13). Requirement IDs are stable; reference them in commits and tests. IDs retired from v2 are listed as RETIRED and must not be re-implemented.

EARS templates used: Ubiquitous ("The system SHALL…"), Event-driven ("WHEN … the system SHALL…"), State-driven ("WHILE … the system SHALL…"), Optional ("WHERE … the system SHALL…"), Unwanted ("IF … THEN the system SHALL…").

**The v3 thesis (context, not UI copy):** coaching begins only after the learner commits to a choice — there is no pre-pick help of any kind — and ladder exhaustion ends in a *priced escape* to the breakdown, never a dead end and never an in-chat reveal.

---

## 0. Definitions & state model

- **Moment** — the coach panel's active mode. v3 moments: **idle** (no submission yet), **wrong-pick**, **correct**, **free-ask**. (v2's "no-pick nudge" moment does not exist.)
- **Ladder** — the fixture's `_hint_ladders["<letter>"]` for one wrong letter of one item: exactly 3 rungs, pump → hint → prompt.
- **Outcome** (per item, SEQ-4): `first-try` | `coached` | `walked-through`.
- Minimum per-item state: `selected`, `submittedLetter`, `attempts[]`, `rung` (−1 = no ladder open), `exhausted` (bool), `walkedThrough` (bool), `solved` (bool). `rung`, `exhausted`, `walkedThrough` reset on item load; `rung` survives "Let me try again" within the same item (used-nudge honesty).

## 1. Data contract

- **DAT-1** The system SHALL load coaching content exclusively from the Gen2 slice: 15 reviewed items, each with `why_correct_md`, `why_tempted_md`, `rule_md`, per-choice `misconception` + `per_choice_rationale`, and `_hint_ladders` keyed by wrong letter.
- **DAT-2** The system SHALL treat `gen2-slice.fixture.json` as immutable input; no runtime mutation, no re-authoring of stems, choices, rationales, or ladder rungs. (Markdown emphasis markers may be stripped for display.)
- **DAT-3** Each wrong-choice ladder SHALL contain exactly 3 rungs ordered pump → hint → prompt. The system SHALL NOT synthesize or append a 4th (assertion) rung.
- **DAT-4** The correct letter of an item SHALL have no ladder; the system SHALL never look one up for it.
- **DAT-5** — RETIRED (v2 synthesized item-level opener). The system SHALL NOT synthesize an opener, item-level ladder, or any pre-submission coaching content for any item.

## 2. Session sequencing (outer loop)

- **SEQ-1** The system SHALL run sessions from `SESSION_ORDER` (15 item ids, blocked by skill), presented in order, one item at a time.
- **SEQ-2** WHEN an item is loaded, the system SHALL display a "why this item" line derived from its skill + difficulty + position; copy SHALL never claim interleaving while the order is blocked.
- **SEQ-3** WHEN the learner completes the final item, the system SHALL transition to the session summary.
- **SEQ-4** *(amended)* The system SHALL record per item: id, skill, **outcome** (`first-try` | `coached` | `walked-through`), and miss tag (misconception of the first wrong pick, if any). `first-try` ⇔ the first submitted letter was correct; `walked-through` ⇔ the learner exited via ESC-1; otherwise `coached`.

## 3. Moment routing (inner loop)

One coach panel; the active moment re-renders it.

- **MOM-1** *(amended: no-pick → idle)* WHILE no choice has been submitted for the current item, the system SHALL show the quiet idle state: coach identity plus one line of copy in the spirit of "Commit to a choice — coaching starts from what you pick." (prototype: "Commit to a choice — coaching starts from what you pick. Ask me anything below; I never reveal the answer."). The free-ask input (MOM-7) SHALL remain available. The idle state SHALL contain **no ladder rail, no counter, and no nudge/hint affordance of any kind**.
- **MOM-2** — RETIRED (no-pick nudge, placeholder badge, "1 of 1" counter). There SHALL be no nudge affordance of any kind before a submission, on any surface.
- **MOM-3** WHEN the learner submits a wrong letter L, the system SHALL enter the wrong-pick moment for L: acknowledge (shared-ground first: what the learner already does correctly → the specific trap this item sets → hand off to the question), then reveal ladder `L` rung 1 (pump).
- **MOM-4** *(amended)* WHEN the learner requests another nudge in wrong-pick, the system SHALL reveal the next rung (hint, then prompt) with an honest counter "n of 3". IF all 3 rungs are used, THEN the nudge control SHALL disable and the moment SHALL offer **exactly two actions**: **"Let me try again"** (primary; clears the pick, keeps the rung count) and **"Walk me through it"** (secondary; the priced escape, ESC-1…4). The exhaustion copy SHALL state plainly that the coach has no more nudges and never tells the answer (prototype: "That's all three nudges — I don't have more, and I never tell the answer. Re-read the sentence with the last prompt in mind and try again — or have the breakdown walk you through it.").
- **MOM-5** WHEN the learner switches wrong letter L1 → L2, the system SHALL abandon L1's ladder and start L2's ladder at rung 1, stating the switch in the trace (TRACE-3).
- **MOM-6** WHEN the learner submits the correct letter, the system SHALL enter the correct moment: verdict first, then `why_correct_md`; no ladder fires, no counter shown; footnote "Solved — no more nudges needed."
- **MOM-7** WHEN the learner sends a free-text question (in any unsolved moment, **including idle**, where it is the only input), the system SHALL respond via the deterministic fallback stub (no live LLM): lead with the honest limitation, then one reusable move; never the answer letter or key phrase.
- **MOM-8** Moment isolation: the idle moment SHALL never render a choice-keyed ladder or rung content, and the wrong-pick moment SHALL never render idle copy.
- **MOM-9** *(new, prototype behavior)* WHILE `rung < 0` (idle, or a first-try solve), the system SHALL hide the pump/hint/prompt ladder rail entirely; WHEN the first rung of a ladder fires, the rail SHALL appear and persist for the remainder of the item (including across "Let me try again").

## 4. Priced escape (ESC — new in v3)

- **ESC-1** WHEN the learner activates "Walk me through it" at exhaustion, the system SHALL route directly to the feedback/breakdown view for the current item in the walked-through state (FBK-1) and record the outcome (SEQ-4). The coach chat SHALL NOT emit the answer as part of this transition; any handoff turn is leak-checked (prototype handoff: "Deal — the breakdown takes it from here. It shows the answer and the why; this conversation still hasn't."). The reveal happens only inside the breakdown view.
- **ESC-2** The escape SHALL be visibly priced before activation: one line of plain-language copy adjacent to the control stating the trade (prototype: "The breakdown shows the answer — this one won't count as solved."). No confirmation dialog — the labeled cost is the friction.
- **ESC-3** The escape SHALL exist ONLY in the exhausted state. IF the state is rungs 0–2 or pre-submission, THEN the system SHALL NOT render the escape; a free "Reveal answer" affordance SHALL NOT exist anywhere.
- **ESC-4** The reasoning trace SHALL log the escape with source copy in the spirit of: "Learner chose the walkthrough after 3 rungs — recorded as walked-through, no first-try credit. The breakdown reveals the answer; the conversation still never did." LEAK-1/2 apply to every chat-emitted body including the handoff; the breakdown view is exempt by design.

## 5. Leakage guard

- **LEAK-1** The system SHALL check every coach-emitted body (rungs, acknowledgments, exhaustion copy, escape handoff, free-ask fallback) against the item's correct letter and key text; IF a body would name the correct letter or restate the key, THEN the system SHALL not emit it (substitute the neutral fallback).
- **LEAK-2** The leakage check result SHALL be visible in the reasoning trace as a plain pass/fail line ("✓ checked — doesn't name or restate the answer").

## 6. Coach voice & presentation

- **VOICE-1** Wrong-pick acknowledgments SHALL order content: shared ground → specific complication → question. No verdict-only openers, no rule lecture before the pump.
- **VOICE-2** Correct-moment feedback SHALL order content: answer/verdict → explanation → rule (drill-down last).
- **VOICE-3** Learner-facing copy SHALL use human-scale language; engine vocabulary (ladder, choice-keyed, moment, wrong-pick, assertion rung) SHALL not appear in learner-facing surfaces. Stakeholder annotations (trace) may name Gen2.
- **VOICE-4** Every screen/panel heading SHALL be an action title provable by the content beneath it; headings containing "and" indicate two points — split or trim.
- **VOICE-5** Displayed statistics SHALL be sourced from session state or fixture data; counters SHALL be honest ("n of 3", wrong-pick only). Outcome labels SHALL be honest and non-judgmental — never shaming (see FBK-1, SUM-2).

## 7. Reasoning trace (stakeholder annotation)

- **TRACE-1** WHERE the reasoning trace is enabled (toggle "Under the hood" / "Hide the trace", hidden by default), the system SHALL show per-turn trace lines headed "Every rung is deliberate and leak-checked · prototype annotation".
- **TRACE-2** Wrong-pick trace lines SHALL show: moment + chosen letter → that choice's own 3-rung ladder; selected move + rung n of 3 with plain-language rationale; misconception label + `per_choice_rationale[L]`; leakage check (LEAK-2).
- **TRACE-3** Trace lines SHALL cover: correct moment (source: Gen2 authored why-correct), ladder exhaustion (including the priced-escape offer), wrong-letter switch ("Switched L1 → L2 — restarting that choice's ladder at rung 1"), free-ask fallback, and the escape itself (ESC-4). No opener-related lines exist in v3.
- **TRACE-4** Trace copy SHALL be plain-language; internal keys, file names, and framework jargon SHALL not appear.

## 8. Item panel controls

- **CTRL-1** *(amended)* WHILE unsolved with no submission, the primary action SHALL be Submit, enabled once a choice is selected (disabled before). There SHALL be **no secondary nudge control**; "Ask for a nudge first" SHALL not appear on any surface. Idle helper copy SHALL not promise pre-pick help (prototype item-panel hint: "Pick a choice and submit — no hints until you commit."; coach-panel footnote: "Coaching starts after you submit — it works from what your pick reveals.").
- **CTRL-2** *(amended wording only)* WHILE in wrong-pick with rungs remaining, the nudge control SHALL show the next-rung affordance ("Show me more →", then "I'm still stuck →" at rung 3) with footnote "Nudge n of 3 used — these questions follow your pick of \<L\>." The footnote SHALL NOT imply any pre-pick nudge existed (no "first" framing).
- **CTRL-3** WHEN solved, the item panel's primary action SHALL advance ("Next question →" / "Finish session →" on the last item); the coach panel SHALL separately offer "See the breakdown →". These two actions SHALL never duplicate each other.
- **CTRL-4** WHEN the learner advances, the system SHALL record the item result (SEQ-4) before loading the next item or summary. (The walked-through outcome is fixed at ESC-1 activation; advancing from the breakdown commits the record.)

## 9. Feedback (consolidation) view

- **FBK-1** *(amended)* The feedback view's result label SHALL have three states: **"Solved on first try"** / **"Worked through it with the coach"** / **"Walked through together"** (honest, non-judgmental phrasing). All states SHALL show the why-correct block (`why_correct_md`) and the rule block (`rule_md`, "One rule decided this item"). The walked-through state SHALL additionally surface `why_tempted_md` for the learner's **last wrong letter** (prototype: the Feed-back/gap card carries `why_tempted_md` + names the last pick; the banner states the answer appears here, not in the chat, and that the item won't count as solved). The walked-through state SHALL be visually distinct (prototype: warning-toned banner, "→" glyph) but not punitive.
- **FBK-2** Self-explanation SHALL be optional and never gate progression.

## 10. Session summary

- **SUM-1** *(amended)* The summary SHALL show the first-try score "k/15" counting ONLY `first-try` outcomes — `walked-through` items SHALL never count toward it — plus 15 as "Gen2 reviewed items" and the mastery delta for the session focus skill.
- **SUM-2** *(amended)* The played-sequence display SHALL group consecutive same-skill items into run-length chips with one mark per item: **✓** (`first-try`), **↺** (`coached`), and a third visually distinct mark **→** (`walked-through`, warning tone). A legend SHALL name all three honestly (prototype: "✓ solved first try · ↺ worked through with the coach · → walked through together — not counted as solved").
- **SUM-3** The dominant-misconception card SHALL derive from recorded miss tags (most frequent), naming the misconception label + hint text; IF no misses, THEN it SHALL state no recurring error was found.
- **SUM-4** The recommended-next card SHALL be mastery-gated copy derived from the dominant misconception (or mixed set when none), headed "Your next drill is already queued".

## 11. Packaging & platform

- **PKG-1** The deliverable SHALL be one self-contained desktop HTML file: engine + fixture data inlined, no network requests, opens offline by double-click.
- **PKG-2** The system SHALL not modify the served banks (`_test_item_bank.ts` / `_hint_bank.ts`) or any AgentsFramework repo runtime.
- **PKG-3** Desktop only (min-width 1280 layout); no mobile/iPad variant.
- **PKG-4** No live LLM calls anywhere; free-ask uses the stub (MOM-7).

## 12. Acceptance walkthrough (replaces v2 §11)

1. Load → dashboard → start session → item 1 shows the **idle moment**: no hint affordance anywhere, no ladder rail, Submit disabled until a choice is selected (MOM-1, MOM-9, CTRL-1).
2. Free-ask in the idle moment → stub reply, leak-guarded, no answer (MOM-7).
3. Pick the tempting distractor → shared-ground acknowledgment + pump; ladder rail appears; counter "1 of 3"; trace shows misconception + rationale + leak check (MOM-3, MOM-9, TRACE-2).
4. Two more nudges → hint, prompt; "3 of 3" → exhausted state shows BOTH "Let me try again" and the priced "Walk me through it" with its cost line (MOM-4, ESC-2).
5. Take the escape → breakdown in walked-through state: why-correct + rule + why-tempted for the last wrong letter; chat transcript contains no reveal (ESC-1, FBK-1).
6. On a later item, switch wrong letters → new ladder at rung 1 (MOM-5); solve it → "Worked through it with the coach" (MOM-6).
7. Solve one first-try → "Solved on first try"; finish 15 → summary chips show three distinct marks with an honest legend; first-try score excludes the walked-through item (SUM-1/2).

## 13. Delta log vs v2 (traceability only)

- REMOVED: DAT-5 (synthesized opener), MOM-2 (no-pick nudge + placeholder badge + "1 of 1").
- AMENDED: MOM-1 (no-pick → idle), MOM-4 (exhaustion → two actions incl. priced escape), CTRL-1 (no secondary nudge control), CTRL-2 (no "first" framing), FBK-1 (third result state + why-tempted), SEQ-4 (third outcome), SUM-1 (walked-through never scores), SUM-2 (third mark + legend), §11→§12 walkthrough.
- NEW: ESC-1…4 (priced escape), MOM-9 (ladder-rail visibility).
- UNCHANGED: DAT-1…4, SEQ-1…3, MOM-3/5/6/7/8, LEAK-1/2, VOICE-1…5, TRACE-1…4 (minus opener lines), CTRL-3/4, FBK-2, SUM-3/4, PKG-1…4.

---
*Trace anchor: v3 prototype approved 2026-07-19. Any implementation deviation from a REQ id above requires an explicit decision note.*
