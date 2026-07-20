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
