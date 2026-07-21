# EARS Specification — English Coach, Gen2 Slice (v2 final)

**Source of truth:** `English Coach - Gen2 Slice v2 -desktop-.html` (approved prototype) + `gen2-slice.fixture.json` (data contract). This spec translates the finalized prototype into EARS requirements for the implementation agent. Requirement IDs are stable — reference them in commits and tests.

EARS patterns used: Ubiquitous ("The system shall…"), Event-driven ("WHEN…"), State-driven ("WHILE…"), Unwanted-behavior ("IF…THEN…"), Optional ("WHERE…").

---

## 1. Data contract

- **DAT-1** The system shall load coaching content exclusively from the Gen2 slice: 15 reviewed items, each with `why_correct_md`, `rule_md`, per-choice `misconception` + `per_choice_rationale`, and `_hint_ladders` keyed `"<item_id>:<letter>"` for each wrong letter.
- **DAT-2** The system shall treat `gen2-slice.fixture.json` as immutable input; no runtime mutation, no re-authoring of stems, choices, rationales, or ladder rungs.
- **DAT-3** Each wrong-choice ladder shall contain exactly 3 rungs ordered pump → hint → prompt. The system shall NOT synthesize or append a 4th (assertion) rung.
- **DAT-4** The correct letter of an item shall have no ladder; the system shall never look one up for it.
- **DAT-5** WHERE an item-level (pre-pick) ladder is absent from Gen2 (always, in this slice), the system shall use one synthesized, misconception-neutral opener per item, visibly marked as placeholder (see MOM-2).

## 2. Session sequencing (outer loop)

- **SEQ-1** The system shall run sessions from `SESSION_ORDER` (15 item ids, blocked by skill), presented in order, one item at a time.
- **SEQ-2** WHEN an item is loaded, the system shall display a "why this item" line derived from its skill + difficulty + position ("Opening in <skill> at difficulty <d> — the first of 15 reviewed items." for position 0; skill-transition or continuation copy otherwise). Copy shall never claim interleaving while the order is blocked.
- **SEQ-3** WHEN the learner completes the final item, the system shall transition to the session summary.
- **SEQ-4** The system shall record per item: id, skill, first-try success (boolean), miss tag (misconception of first wrong pick, if any).

## 3. Moment routing (inner loop) — the four moments

One coach panel; the active moment re-renders it. Moments: **no-pick, wrong-pick, correct, free-ask**.

- **MOM-1** WHILE no choice has been submitted for the current item, the system shall be in the no-pick moment: coach panel shows the opener only; nudge control reads "Ask for a nudge first".
- **MOM-2** WHEN the learner requests a nudge in the no-pick moment, the system shall show the synthesized opener with a visible "placeholder — item-level ladder not yet authored (Gen2)" badge, and counter "1 of 1". The opener shall remind (activate what the learner already knows) and shall NOT teach new rules or facts. IF the learner requests further no-pick nudges THEN the system shall not escalate (no ladder exists) and shall keep the placeholder visible.
- **MOM-3** WHEN the learner submits a wrong letter L, the system shall enter the wrong-pick moment for L: acknowledge (shared-ground first: what the learner already does correctly → the specific trap this item sets → hand off to the question), then reveal ladder `"<id>:L"` rung 1 (pump).
- **MOM-4** WHEN the learner requests another nudge in wrong-pick, the system shall reveal the next rung (hint, then prompt), with an honest counter "n of 3". IF all 3 rungs are used THEN the control shall disable with copy stating no more nudges exist and the coach never tells; the system shall NOT reveal or paraphrase the answer.
- **MOM-5** WHEN the learner switches wrong letter L1 → L2, the system shall abandon L1's ladder and start L2's ladder at rung 1, stating the switch in the trace (TRACE-3).
- **MOM-6** WHEN the learner submits the correct letter, the system shall enter the correct moment: verdict first (confirmation), then `why_correct_md`, then `rule_md` — answer-first ordering; no ladder fires, no counter shown; footnote "Solved — no more nudges needed."
- **MOM-7** WHEN the learner sends a free-text question, the system shall enter the free-ask moment and respond via the deterministic fallback stub (no live LLM). The fallback shall lead with the honest limitation, then one reusable move; it shall never contain the answer letter or key phrase.
- **MOM-8** The no-pick moment shall never render a choice-keyed ladder, and the wrong-pick moment shall never render the item-level placeholder.

## 4. Leakage guard

- **LEAK-1** The system shall check every coach-emitted body (rungs, openers, fallback, acknowledgments) against the item's correct letter and key text; IF a body would name the correct letter or restate the key THEN the system shall not emit it (regenerate or substitute the neutral fallback).
- **LEAK-2** The leakage check result shall be visible in the reasoning trace as a pass/fail line, phrased plainly ("✓ checked — doesn't name or restate the answer").

## 5. Coach voice & presentation rules (SCQA — silent, no terminology in UI)

- **VOICE-1** Wrong-pick acknowledgments shall order content: shared ground → specific complication → question. No verdict-only openers, no rule lecture before the pump.
- **VOICE-2** Correct-moment feedback shall order content: answer/verdict → explanation → rule (drill-down last).
- **VOICE-3** All learner-facing copy shall use human-scale language; engine vocabulary (ladder, choice-keyed, moment, wrong-pick, LIB, assertion rung, ICAP) shall not appear in learner-facing surfaces. Stakeholder annotations (trace, placeholder badge) may name Gen2.
- **VOICE-4** Every screen/panel heading shall be an action title (a conclusion with a verb), not a topic label, and shall be provable by the content beneath it. Headings containing "and" indicate two points — split or trim.
- **VOICE-5** Displayed statistics shall be sourced from session state or fixture data; no decorative or fabricated numbers. Counters shall be honest: "n of 3" (wrong-pick), "1 of 1" or none (no-pick).

## 6. Reasoning trace (stakeholder annotation)

- **TRACE-1** The system shall keep a per-turn reasoning trace, hidden by default, toggled by a control labeled "Under the hood" / "Hide the trace", headed "Every rung is deliberate and leak-checked · prototype annotation".
- **TRACE-2** Wrong-pick trace lines shall show: moment + chosen letter → that choice's own 3-rung ladder; selected move + rung n of 3 with a plain-language rationale; misconception label + `per_choice_rationale[L]`; leakage check (LEAK-2).
- **TRACE-3** Trace lines shall cover: correct moment (source: "Gen2 authored why-correct explanation"), no-pick (source: "Not authored — Gen2 has no item-level ladders yet; synthesized placeholder"), ladder exhaustion, wrong-letter switch, and free-ask fallback (canned reply carries no answer).
- **TRACE-4** Trace copy shall be plain-language; internal keys (`LIB["<id>:<letter>"]`), file names, and framework jargon shall not appear.

## 7. Item panel controls

- **CTRL-1** WHILE unsolved with no submission, the primary action shall be Submit (enabled once a choice is selected); secondary "Ask for a nudge first".
- **CTRL-2** WHILE in wrong-pick with rungs remaining, the nudge control shall show the next-rung affordance with footnote "Nudge n of 3 used — these questions follow your pick of <L>."
- **CTRL-3** WHEN solved, the item panel's primary action shall advance: "Next question →" (or "Finish session →" on the last item). The coach panel shall separately offer "See the breakdown →" (consolidation). These two actions shall never duplicate each other.
- **CTRL-4** WHEN the learner advances, the system shall record the item result (SEQ-4) before loading the next item or summary.

## 8. Feedback (consolidation) view

- **FBK-1** The feedback view shall show: result label ("Solved on first try" / "Worked through it with the coach"), the why-correct block from `why_correct_md`, the rule block from `rule_md` ("One rule decided this item"), and a self-explanation input ("Saying it back makes it stick").
- **FBK-2** Self-explanation shall be optional and never gate progression.

## 9. Session summary

- **SUM-1** The summary shall show first-try score "k/15", 15 as "Gen2 reviewed items" (count, not minutes), and mastery delta for the session focus skill.
- **SUM-2** The played-sequence display shall group consecutive same-skill items into run-length chips: skill dot + label once, then one mark per item in the run (✓ first-try, ↺ coached), chronological. Heading: "Each skill ran until you cleared it" (or equivalent honest action title — never an interleaving claim for blocked order).
- **SUM-3** The dominant-misconception card shall derive from recorded miss tags (most frequent), naming the misconception label + hint text; IF no misses THEN it shall state no recurring error was found.
- **SUM-4** The recommended-next card shall be mastery-gated copy derived from the dominant misconception (or mixed set when none), headed "Your next drill is already queued".

## 10. Packaging & platform

- **PKG-1** The deliverable shall be one self-contained desktop HTML file: engine + data inlined, no network requests, opens offline by double-click.
- **PKG-2** The system shall not modify the served banks (`_test_item_bank.ts` / `_hint_bank.ts`) or any AgentsFramework repo runtime.
- **PKG-3** Desktop only (min-width 1280 layout); no mobile/iPad variant.
- **PKG-4** No live LLM calls anywhere; free-ask uses the stub (MOM-7).

## 11. Acceptance walkthrough (AC-M1…M6 — the four-moment acceptance criteria)

1. Load → dashboard → start session → item 1 shows no-pick state (MOM-1).
2. Ask nudge before picking → placeholder opener + badge + "1 of 1" (MOM-2, AC-M2).
3. Pick the tempting distractor → shared-ground acknowledgment + pump question; counter "1 of 3"; trace shows misconception + rationale + leak check (MOM-3, TRACE-2, AC-M1/M4/M5).
4. Two more nudges → hint, prompt; "3 of 3" then honest exhaustion; never the answer (MOM-4, AC-M3).
5. Switch to another wrong letter → new ladder at rung 1 (MOM-5).
6. Pick correct → verdict-first feedback; advance + breakdown as separate actions (MOM-6, CTRL-3, AC-M6).
7. Finish 15 → summary with run-length chips, honest counts, misconception thread (SUM-1…4).

---
*Trace anchor: prototype approved 2026-07-18. Any implementation deviation from a REQ id above requires an explicit decision note.*
