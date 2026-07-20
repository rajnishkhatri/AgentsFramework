# Visual gap register — v3 prototype vs app (paired-state Playwright audit)

**Date:** 2026-07-20 · **Stage:** SDD-5 replan evidence (post T13–T18)
**Method:** A Playwright script drove BOTH surfaces through matched journey states
(idle → wrong-submit/ack+rung1 → rung2 → exhaustion → walked-through feedback →
coached-solve → coach page → summary → dashboard) and captured a full-page
screenshot pair per state at 1440×900. Each pair was then audited
region-by-region. Literal pixel-diffing was rejected (design prototype vs app =
100% pixel noise); this is a paired-state structural audit.

- **Prototype:** `docs/plan/gen2-proto-handoff/English Coach - Gen2 Slice v3 -desktop-.html` (file://)
- **App:** `localhost:3000/learn/quiz` (`commit_first_coach` ON, bypass auth)
- **Capture script (re-runnable):** [`visual-audit/capture.cjs`](gen2-proto-handoff/visual-audit/capture.cjs) — `node capture.cjs` with dev server on :3000
- **Screenshots:** [`visual-audit/pairs/`](gen2-proto-handoff/visual-audit/pairs/) — 20 PNGs named `<state>-{proto|app}.png` + `capture-log.json` (regenerate any time via the script)
- **Spec references:** `03-ears-spec-gen2-coach-v3.md` (v3 EARS) · `commit-first-coach.spec.md` (app spec)

## What already matches (verified, no action)

- MOM-1 idle coach copy — exact text match.
- Exhaustion copy, escape cost line, "Let me try again"/"Walk me through it" labels — exact.
- ESC flow: escape → walked-through banner variant + "Walked through together" label.
- FBK-1 three result labels; honest "n of 3" counter; letter-keyed nudge footnote.
- **T14 verified live:** End session with resolved items → `/learn/summary?session=…`.
- Feedback stem span turns green on reveal (close to prototype treatment).

## Gap register

Severity: **H** = breaks the coach voice/pedagogy · **M** = content/affordance miss · **L** = polish.
Evidence = state pair number from the capture set.

### A. Coached loop (quiz)

| ID | Sev | Evidence | Gap |
|---|---|---|---|
| V1 | H | 02–04 | Coached exchange is a static "COACHING" block, not a conversation: missing pick echo ("I chose B."), acknowledgment as its own coach turn, each rung as its own turn, "I'm still stuck." user echoes between rungs. |
| V2 | H | 02 | Ack composition (coached_ack_vm) lacks the verdict→diagnosis→hand-off shape ("Not quite — and it's a telling miss. … So —"). App concatenates fixed shared-ground + raw misconception + a generic "Re-read the sentence…" hand-off that *competes with* rung-1's pump instead of leading into it. |
| V3 | H | 02–04 | MOM-9 ladder rail (PUMP → HINT → PROMPT with fill-progress) absent; per-rung stage badges + "no answer 🛡" shield absent. Learner never sees least-help-first structure. |
| V4 | M | 02–04 | During the coached loop the quiz card still shows a full-width enabled "Submit answer" (prototype hides submit while in the loop); at exhaustion the decision buttons sit below the panel fold at 1440×900 (require scroll — pair 04). |
| V5 | M | 02 | "Let me try again" only appears at exhaustion; prototype offers it from rung 1 alongside "Show me more →". |
| V6 | M | 03 | Escalation control drift: prototype keeps the button "Show me more →" and echoes "I'm still stuck." as a *user message*; app relabels the button "I'm still stuck →" at rung cap−1. |
| V7 | M | 04 | Exhaustion CTA hierarchy inverted: prototype makes "Let me try again" primary (filled) and the priced escape secondary (outline); app fills the escape and outlines try-again — visually nudging toward the answer-revealing path. |
| V8 | L | 02 | Committed wrong pick: prototype shows filled red letter badge + ✗ marker on the choice; app shows only a generic selected tint. |
| V9 | L | 01–04 | Coach header identity: prototype "Coach — never gives the answer / Least help first…" + "Under the hood"; app "Your Coach / Adaptive · always on / Current item: Q1 · s-punc / Sees your history: 0 misses on s-punc" — leaks internal skill ids (`s-punc`, VOICE-3) and mode chips overflow-clip. |
| V10 | L | 02 | Extra generic CONVERSATION bubble ("You're in the coaching loop for that pick…") that the prototype doesn't have — retire once V1/V2 land. |

### B. Idle / pre-commit

| ID | Sev | Evidence | Gap |
|---|---|---|---|
| V11 | M | 01 | SEQ-2 rendered as bare metadata ("Question 1 of 30 · Punctuation · difficulty 1") vs labeled purpose card ("THIS ITEM WAS PICKED ON PURPOSE — Opening in Grammar & Usage at difficulty 2 — the first of 15 reviewed items."). All prototype claims are sourceable (VOICE-5-safe). |
| V12 | L | 01 | Composer footer microcopy missing ("Coaching starts after you submit — it works from what your pick reveals."). |
| V13 | L | 01 | Session-frame polish family: no in-card skill·difficulty chip or visible timer; submit full-width and colored pre-pick (prototype: right-aligned, visually gated). |

### C. Feedback screen

| ID | Sev | Evidence | Gap |
|---|---|---|---|
| V14 | H | 05/06 | Walked-through banner never delivers the answer. Prototype: "The answer appears here, not in the chat: it's A. Your last pick was B — the cards below unpack both." This is where the no-reveal contract pays off; app shows only the cost line. |
| V15 | H | 05, 10 | **Rendering bug:** markdown literals visible in feedback prose — "Commas separate \*\*every item\*\* in a simple series." `*_md` fields rendered as plain text. |
| V16 | M | 05/06 | FEED-UP·GOAL / FEED-BACK·GAP / FEED-FORWARD·NEXT card triplet absent; app has flat "Why X is correct / Why Y tempted you" prose. |
| V17 | M | 05/06 | Per-choice rationales shown for all four choices in prototype (data exists: `per_choice_rationale`); app annotates only correct + picked. |
| V18 | M | 05/06 | Self-explanation lacks the "Gauge understanding before moving on: This clicked ✓ / Still fuzzy" chips; prompt/placeholder copy differs. |
| V19 | M | 05/06 | "One rule decided this item": app one-sentence rule vs prototype's numbered 5-step decision procedure. |
| V20 | L | 10 | Coached-solve moment: prototype confirms in place ("Yes — that's it…" chat turn + inline "Worked through it with the coach" + optional "See the breakdown →"); app jumps straight to the full feedback screen. Flow-shape decision, not a bug. |

### D. Coach page

| ID | Sev | Evidence | Gap |
|---|---|---|---|
| V22 | M | 07 | No proactive grounded opener (prototype: "Ready when you are. Want to unpack the parallelism item, or work a fresh one? Your misses cluster on…"); conversation area is an empty dead zone. |
| V23 | M | 07 | No context sidebar: "THE COACH KNOWS YOUR LAST ITEM" (current item + diagnosed misconception cards) and "ONE COACH, THREE MODES" list absent; fresh page shows no current-item grounding at all. |
| V24 | L | 07 | "Wrap up session →" is a plain link vs filled CTA; chip label drift ("Show my comma pattern" vs "Show my miss pattern" — app's may be intentionally skill-specific). |

### E. Summary

| ID | Sev | Evidence | Gap |
|---|---|---|---|
| V25 | M | 08 | Outcome counts are one plain text line; prototype gives per-skill outcome rows with ✓/↺/→ glyphs + legend ("EACH SKILL RAN UNTIL YOU CLEARED IT"). |
| V26 | M | 08 | Misconception recap card ("The misconception I spotted · … Once the coach flagged it, you carried the fix…") absent. App spec §10 excluded SUM-2 *chips*; the recap narrative is the larger miss — revisit the exclusion. |
| V27 | L | 08 | Next-drill card: generic "30-item drill: Usage" vs targeted 6-item misconception drill + spacing copy ("resurface tomorrow, then in 3 days"); no headline tone ("Nice work — you found the pattern."); tile label "SCORE" vs "solved first-try". |

### F. Config / out of slice

| ID | Sev | Gap |
|---|---|---|
| V28 | cfg | Session target 30 items vs prototype's bounded 15 — confirm intended target_count for the coached experience. |
| V29 | n/a | Dashboard is a different (already-shipped) surface; only note: "Start adaptive session" CTA parity already exists. Out of commit-first scope. |

## Root-cause reading

Three roots explain ~80% of the register:

1. **Presentation model** — the app renders coaching as *labeled boxes*; the prototype's medium IS a chat transcript (V1, V2, V6, V10, V20, V22).
2. **Data surfaced ≠ data available** — per-choice rationales, misconception, procedure steps, purpose copy all exist in the fixture/VMs but aren't composed into the UI (V11, V16, V17, V19, V23, V26).
3. **Un-designed states** — markdown rendering (V15), CTA hierarchy (V7), below-fold exhaustion (V4) are plain defects, not design choices.

## Proposed Phase 3 (pending human approval — append-only to tasks.md)

- **T19 (H):** Conversational coached-loop transcript in CoachedLoopSection — pick echo, ack turn, per-rung turns with stage badges + no-answer shield, stuck echoes. Retires the generic disclaimer bubble (V1, V6, V10).
- **T20 (H):** Ack composer v2 — verdict + misconception diagnosis + "So —" hand-off; drop the competing re-read hand-off (V2).
- **T21 (H):** MOM-9 ladder rail PUMP/HINT/PROMPT with fill state (V3).
- **T22 (H):** Feedback fixes — banner delivers answer + last pick (V14); render `*_md` markdown (V15).
- **T23 (M):** Feedback composition — feed-up/back/forward cards, all-choice rationales, gauge chips, procedure block (V16–V19).
- **T24 (M):** Coached-loop controls — try-again from rung 1, keep "Show me more →" label, primary/secondary CTA flip at exhaustion, hide submit during loop, keep exhaustion actions in view (V4, V5, V7).
- **T25 (M):** SEQ-2 purpose card (V11) + idle polish batch (V8, V12, V13).
- **T26 (M):** Coach page grounding — opener + context sidebar (V22, V23) + V24 polish.
- **T27 (M):** Summary — per-skill outcome rows + misconception recap (V25, V26; V26 needs a spec-exclusion revisit) + V27 polish.
- **T28:** Form-level e2e assertions (pick-echo, stage badges, banner names answer, no raw `**`) **plus** Phase-3 hard gate: re-run this capture script against localhost after implementation and region-audit the fresh `*-app.png` pairs before declaring convergence.

Routing per sdd-replan: V20 (coached-solve flow shape), V26 (SUM-2 exclusion), V28 (target_count) are **spec-level questions**; everything else is priorities-only → sdd-implement after approval.

## Phase-3 residual pass (2026-07-20, post T19–T28)

Fresh paired capture after Phase 3 confirmed V1–V8, V11–V17, V22–V24, FR-15
landed. Residual audit found 7 gaps (R1–R7); 6 fixed red/green this pass:

| ID | Maps to | Status | Fix |
|---|---|---|---|
| R1 | V4 | FIXED | transcript auto-scrolls newest turn + actions into view; exhaustion footer opaque (was `bg-surface/95`+blur bleed) |
| R2a | V9 | FIXED | history line falls back to "this skill", never raw `s-*` id (`coach_surface_vm`) |
| R2b | V9 | FIXED | pin label = `Q{n} · {skill display name}`, unresolved → `Q{n}` (`quiz_coach_pin` + 3 page call sites) |
| R2c | V9 | FIXED | opener miss-cluster scope names the skill label, never the item label / raw id (`honest_coach_opener`) |
| R4 | V20 | FIXED | coached-solve confirm marks the correct choice green + ✓ (`QuizView`) |
| R5 | V16 | FIXED | feed-up humanizes `item_type` ("underlined-span item", no raw "mc") |
| R6 | V25 | FIXED | summary heading → "How items resolved this session" (VOICE-5: global counts must not claim a per-skill breakdown) |
| R7 | V26 | OPEN | misconception recap conditional is FR-12 recommended-skill-scoped (pinned by test); session-narrative recap = spec decision, routed to human |

Remaining polish (L, not blocking): mode-chip overflow clip in panel header;
per-skill outcome rows (V25 full form); prototype-style banner headline weight;
sliver of transcript text visible below the sticky footer boundary.

Stale-test fix: `quiz-commit-first.spec.ts` journey (b) updated to the FR-15
contract (in-place confirm → "See the breakdown →" → feedback), was asserting
the pre-FR-15 auto-feedback flow.

Gate evidence: vitest 651/651 (affected areas); e2e 16/16 (v3 conformance +
journeys); tsc clean except 3 pre-existing `use_expandable_list` errors;
fresh capture 0 FAILED, End session → `/learn/summary?session=…` live.

**R7 update (2026-07-20, later same day):** session-wide fallback approved and
implemented (`use_summary.deriveMisconception`; pinning test rewritten to the
new contract, red→green 652/652). Live rendering blocked by DATA, not code:
`_test_item_bank.ts` has `misconception: null` on 940/987 items — recap stays
honestly absent (AP-6) until bank coverage lands (spawned task). Capture script
end-session step now waits for the summary URL instead of a fixed delay
(eliminates the mid-transition screenshot artifact).

---

## Manual-pass observations (M-series, 2026-07-20)

Captured by the human running `commit-first-coach.manual-validation.md` on
localhost (HEAD `07692b9`, flag ON). These are **observations, not accepted
fixes** — each needs an analysis pass to decide if a change is warranted. Logged
here so they're durable; NOT yet scheduled into a task board.

| ID | Where | Observation | Disposition |
|---|---|---|---|
| M1 | Coach mode chips — `modeDisplays()` `coach_surface_vm.ts:68-86`, rendered `CoachChrome.tsx:119-146` (`data-testid="coach-modes"`). Actual labels: **"In-drill Socratic"** / **"Post-answer deep-dive"** / **"Misconception summary"** (`misconception` chip is always display-only, never active). | Labels were intentional earlier, but against the coach's real estate they "don't add much value." Candidate for removal/simplification. | **Analyze** — do the modes earn their space, or is a single coach voice clearer? The 3rd chip is already inert. Decide before cutting. |
| M2 | Quick-action chips — `COACH_CHIP_SEEDS` `coach_surface_vm.ts:18-22` ("Explain the rule simply" / "Give me a similar item" / **"Show my comma pattern"** — note: no "me"); rendered `CoachChrome.tsx:26-59`; click → `ask` → `sendCoachAsk` `use_coach.ts:100-176` → `runtime.streamRun` → POST `/api/coach/run/stream` (`route.ts:83`). Same path for free-text composer submit. | Buttons ARE clickable, but the coach is **not wired to a live LLM** in this build → the stream errors, mapped by `coach_message_vm.ts:41-58` to *"The coach could not respond."* + retry. Same failure typing free text and submitting. | **Analyze** — affordance implies a capability the build can't deliver (AP-6 / VOICE-1). Options: (a) gate the live-coach affordances behind the same condition as the LLM wiring; (b) stub; (c) leave but gate. Pick deliberately — not a silent-degrade. |
| M3 | Composer controls — shared `Composer.tsx`: "+" attach button `:150-160` (**no `onClick` — display-only parity affordance, confirmed**), model-picker `DropdownMenu` `:165-209`. Coach uses this composer via `CoachPanel.tsx:313-320`. | Not needed for the learner-facing coach; no attach or model-selection use case here. Candidate for removal *on the coach surface*. | **Analyze** — `Composer` is **shared** (also the main chat composer). Removal must be a coach-scoped prop (e.g. `showAttach`/`showModelPicker=false`), NOT a delete of the shared control. The "+" is already inert, so removing it is pure de-clutter with no behavior loss. |

> M2 is the load-bearing one: a clickable coach that only errors is worse than
> an honestly-unavailable coach (VOICE-1 / AP-6 — don't imply a capability the
> build doesn't have). Whatever we do, the affordance and the backing capability
> must agree.

**Decision (2026-07-20, human):** RECORD ONLY — no M-series fixes this branch.
M2 disposition: **leave as-is** — the missing live LLM is treated as a
deploy/config concern (wire the coach upstream), not a UI change; the error+retry
path stays. M1/M3 remain candidates for a later pass, not scheduled. These stay
as durable observations; revisit when the coach gets a live backend.

### M-series, second manual pass (2026-07-20) — ladder styling vs prototype

Human comparing app ↔ prototype at the wrong-submit → escalation states. Grounded
against the committed capture pairs `03-rung2-{app,proto}.png` and
`04-exhaustion-{app,proto}.png`.

| ID | Where | Observation | Grounding | Disposition |
|---|---|---|---|---|
| M4 | Ladder rail + loop controls in the coach panel (`QuizView` / `CoachedLoopSection`) | App styles the PUMP→HINT→PROMPT rail and the "Let me try again" / "Show me more →" controls as **rounded-red-outlined pills**; prototype uses a **flat 3-segment underline bar** (plain "PUMP HINT PROMPT" labels) and quiet/plain buttons. The red frames eat vertical space. Match prototype: flatten the rail to the underline style, quiet the button chrome. | **CONFIRMED** by pairs: proto rail = flat segmented underline (`03-rung2-proto.png`); app = outlined pills (`03-rung2-app.png`). Pure presentation. | **Analyze** — cosmetic convergence toward prototype; VOICE-neutral. Low risk. |
| M5 | "Nudge N of 3 used" counter | Claim: app doesn't show the "nudge N of 3 used" line that the prototype shows. | **NOT REPRODUCED** — app DOES render *"Nudge 2 of 3 used — these questions follow your pick of A."* at rung 2 (`03-rung2-app.png`), matching the prototype. No gap at the captured state. Possible the human hit a scroll position where it was below the fold. | **No action** — parity already holds; re-check live if it recurs. |
| M6 | Priced-escape cost line *"The breakdown shows the answer — this one won't count as solved."* | Claim: app shows this line but the prototype does **not**. | **CONTRADICTED** — the prototype **also** shows this exact line, at the very bottom of the exhaustion panel in muted gray (`04-exhaustion-proto.png`, last line). The app shows it too (`04-exhaustion-app.png`). Both have it; the prototype's is just quiet/easy to miss. | **No removal** — the line is a deliberate priced-escape signal present in BOTH surfaces (FR-7). Surfaced the discrepancy rather than acting on it. If anything, the *app's* placement is more prominent than the prototype's muted one — that's a styling nuance, folded into M4. |

> M4 is the only actionable item in this pass. M5/M6 are reconciled as
> non-gaps against the capture evidence — recording them so the "why we didn't
> touch it" is durable, not lost.

### M7 — coach-panel "scroll within scroll" (2026-07-20)

Human flagged the coach panel showing a scroll region nested in a scroll region,
with a cramped visible band (red-boxed the "PROMPT · NO ANSWER" rail). Proposed
fix: stop piecemeal patching — adopt the prototype's coach layout wholesale.

**Live DOM diagnosis** (measured against the running app, `coach-panel-inline`,
399×672 panel, idle state — numbers are `scrollWidth` vs `clientWidth`):

| Region | testid | Scrolls? | Evidence |
|---|---|---|---|
| Panel root | `coach-panel-inline` | no | 399/399, `overflow: visible` |
| Zone A (header) | `coach-zone-a` | no | h=188px fixed |
| Mode chips | `coach-modes` | **H-scroll** | `scrollW 489 > clientW 323`, `overflow-x-auto` — 3rd chip clipped mid-word |
| Zone B (transcript) | `coach-zone-b` | V only (correct) | `overflow-y-auto`, but squeezed to **h=226px** |
| Ladder rail | `coach-rail` / `quiz-ladder-rail` | **no** | `overflow: visible`; plain `grid grid-cols-3` — NOT a nested strip |
| Quick-action chips | `coach-chips` | **H-scroll** | `scrollW 540 > clientW 367`, `overflow-x-auto` |
| Zone C (footer) | `coach-zone-c` | no | h=256px fixed |

**Root cause (corrected from the initial read):** the rail the human boxed is
NOT its own scroll container. The real defects are:
1. **Two horizontal-scroll chip strips** (`coach-modes` + `coach-chips`) that clip
   their last item — these are the literal "scroll within scroll" the eye catches.
2. **Zone A (188px) + Zone C (256px) = 444px of the 672px panel are fixed
   chrome**, crushing the actual conversation (Zone B) into a 226px window. The
   transcript then scrolls inside that sliver, compounding the cramped feel.

The prototype avoids both: its mode rail is a flat inline segment bar (no
horizontal scroll), it has no always-on quick-action strip competing for width,
and its header/footer are lighter — so the transcript gets the vertical real
estate. **Adopting the prototype layout = the right structural fix, not a patch.**

**Scope of a layout rework** (from the structural scout):
`CoachPanel.tsx` (zone stack), `CoachChrome.tsx` (Zone A + both chip strips),
`CoachedLoopSection.tsx` (rail + transcript bubbles), `CoachedConfirmSection.tsx`,
`CoachView.tsx` (transcript), `CoachDrawer.tsx` (mobile host), `Composer.tsx`
(Zone C). Mounted twice by `app/(coach)/learn/quiz/page.tsx` (desktop inline +
mobile drawer). No existing React component mirrors the prototype layout — the
prototype is only the standalone HTML artifact. This is a real SDD change
(FR/ADR touch), NOT a residual tweak — route through spec/replan, not a quick edit.

**Resolved (2026-07-20) → SPEC LANDED.** Human chose P2. Written:
[ADR-0037](../adr/0037-coach-column-single-scroll-prototype.md) (supersedes
ADR-0036 on FR-11/FR-12 + Zone contract only) + spec amendment §11 in
[`preact-wide-layout-coach-panel.spec.md`](preact-wide-layout-coach-panel.spec.md)
adding FR-21…FR-26 (single-scroll body; pin only composer; no H-scroll;
flex-remainder transcript; drop inert "Misconception summary" chip).

**IMPLEMENTED (2026-07-20) — Phase 4 T29–T33 green.** Single-scroll coach column
shipped: mode chips flattened (2 live modes, no clip); quick-action chips wrap +
moved into the scroll body; pinned bar = composer-only; **M1 + M3 folded in**
(inert "Misconception summary" chip dropped = M1; coach composer `showToolbar=
false` removes the "+" attach + model picker = M3). FR-24 amended from an
unreachable "≥50% at idle" floor to the honest flex-remainder contract (Zone B is
the single `flex-1 overflow-y-auto` region; header+composer `shrink-0`). Live
verified: `hScrollOffenders:[]`, `windowScrollTop:0`, `hasAttach/hasModelPicker:
false`. vitest 412/412; tsc clean (bar 3 pre-existing `use_expandable_list`
errors). Board detail: `commit-first-coach.tasks.md` Phase 4.

### M8 — residual: unpin the coach header too (2026-07-20)

**CONFIRMED actionable (human, post-M7 screenshot).** After M7 shipped, the coach
identity header — "Your Coach" / "Adaptive · always on" / "Current item: …" /
"Sees your history: …" + the two mode chips (`In-drill Socratic` /
`Post-answer deep-dive`) — was still rendered as the **fixed Zone A** (`shrink-0`
header outside the scroll region). At idle it measured ~187px, which — with the
pinned composer — is what forced FR-24 down to a ~40% flex-remainder and left the
transcript with the small "scroll within scroll" visible area the screenshot
still showed.

**Fix:** unpin Zone A → move `CoachChrome` (title/status/current-item/history +
mode chips) to the **top of the scroll body** (Zone B), so it scrolls away with
the transcript. Zone A collapses to nothing; the **only** pinned region is the
composer (Zone C). This is a tightening of the FR-24 flex-remainder contract, not
a reversal: with the header no longer fixed, Zone B now takes essentially all
height above the composer and wins the ≥50% the original FR-24 wanted — reachable
now precisely *because* the header is not fixed. Routed to spec (§11 refinement +
FR-24 tightened + new FR-27); dismiss control stays reachable (rides with the
chrome at the top of the scroll body). Implemented Phase 4 follow-up (T34).

**IMPLEMENTED + live-verified (2026-07-20).** `CoachChrome` + dismiss moved to the
top of `coach-zone-b`; `coach-zone-a` removed (no fixed header). Live DOM on the
399px inline panel (`http://localhost:3000/learn/quiz`, 672px tall):
`zoneA_exists:false`, `chromeInBody:true`, `dismissInBody:true`, **Zone B = 460px
= 68%** of the panel at idle (was ~40% with the fixed header — the M7/M8 defect),
`hScrollOffenders:[]`, `windowScrollTop:0`. Red/green: FR-27 test seen to fail
first, then green; the FR-24/25 test was retargeted (G8) — it required a
`shrink-0` fixed Zone A, which no longer exists. vitest 413/413; tsc clean (bar
the 3 pre-existing `use_expandable_list` errors).

### M9 — exhaustion actions pin over the scrolling transcript (2026-07-20)

**CONFIRMED actionable (human, two screenshots).** In the wrong-pick loop's
**exhausted** state, the actions block — the "That's all three nudges…" message,
the "Let me try again" / "Walk me through it" buttons, and the cost line — is
initially scrollable but, **as the conversation grows, becomes pinned above the
text-entry**. Its opaque background then paints *over* the transcript: the
"PROMPT · NO ANSWER" bubble scrolls up and disappears **behind** the pinned block
(observed clipping mid-word). This contradicts the M7/M8 single-scroll intent
(only the text-entry composer is pinned; everything else scrolls).

**Root cause:** `CoachedLoopSection.tsx:236` applies
`sticky bottom-0 z-10 bg-surface pb-1 pt-2` to the actions block **when
`coachedLoop.exhausted`**. That was an intentional pre-single-scroll choice (V4/R1
— "keep exhaustion CTAs in view"; fully opaque so transcript text wouldn't bleed
through). Post-M7/M8 it is the defect: a sticky, opaque footer inside the one
scroll body is exactly the overlap the human is seeing.

**Fix (human-confirmed):** remove the `sticky bottom-0 z-10 bg-surface` treatment
so the exhaustion actions sit in normal document flow and scroll with the
transcript — nothing paints behind anything; only the composer stays pinned. The
`scrollIntoView`-on-new-rung effect is **kept** (it brings the newest turn into
view; it does not pin). G8: the R1 test "exhaustion action footer is opaque (no
translucent bleed-through)" asserted the sticky footer's opaque background — its
premise is now the bug, so it is retargeted (not deleted) to assert the block is
**not** sticky. Implemented Phase 4 follow-up (T35).
