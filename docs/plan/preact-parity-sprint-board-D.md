---
title: 'Epic D — Quiz session frame + taxonomy polish · Sprint Board'
type: sprint-board
epic: D
date: 2026-07-10
status: Draft — gated on human direction pick from Stage-1 brainstorm §7
derives_from: docs/plan/preact-parity-epics.md
report: docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
governs:
  - docs/plan/preact-parity-epic-D.brainstorm.md   # Stage-1 (this board's premise audit)
  - docs/plan/preact-parity-D0-correct-record.spec.md   # written when D0 enters sdd-spec
  - docs/plan/preact-parity-D1-quiz-frame.spec.md       # written when D1 enters sdd-spec
  - docs/plan/preact-parity-D2-taxonomy.spec.md         # written when D2 enters sdd-spec
  - docs/plan/preact-parity-D3-session-length.spec.md   # written when D3 enters sdd-spec
method: SDD lifecycle — one full pass per sprint (sdd-brainstorm → sdd-spec → implement → code-review → make check + arch-tests → sdd-converge)
---

# Epic D — Quiz session frame + taxonomy polish · **Sprint Board**

**Epic goal** (from [epics doc §Epic D](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)):
round out the core loop's *session framing* — the affordances that wrap the quiz — and align
the bucket taxonomy to ACT-standard labels. Individually minor; together they close the last
visible deltas on the two most-used screens.

**Findings in scope:** `Q-7` (skill chip via wire→VM→view), `Q-8` (End session), `Q-9`
(collapsible / off-by-default timer), `Q-1b` (session length 30 vs 10 — decision-first),
`D-3b` (bucket names + color dots), `D-8` (Skills nav — deferred to Epic E by default),
`X-4` (bucket taxonomy mismatch — merged into D-3b).

> ⚠️ **This board revises the epics-doc read of four findings** based on the Stage-1
> premise audit ([`preact-parity-epic-D.brainstorm.md`](preact-parity-epic-D.brainstorm.md)).
> Changes folded in below and back-propagated by D0:
>
> - **`Q-7` is not "view-only"** — wire `Question` doesn't carry `skill_name` / `accent_var`;
>   the fix is a hook + translator seam, not just a chip render.
> - **`Q-9` "dismissible" is misleading** — no clock renders today; reframe as *collapsible
>   / off-by-default*, not "toggle a rendered clock".
> - **`Q-1b` is a product decision, not a code sprint** — parity report leaves it explicitly
>   open ("is 30 intended for adaptive?"). D3 runs as a decision-first sprint that
>   *may* land code.
> - **`D-8` is NOT a free nav-add** — `screen("skill", .., comingSoon: true)` already exists
>   in `nav_model.ts:75`, but its route (`/learn/skill`) 404s today (Epic E territory).
>   Adding it to `NAV_MEMBERSHIP` before Epic E ships a **dead nav item = same class as
>   `Q-6`**, the trust bug Epic A closed. Board defers D-8 to Epic E's window by default.
> - **`X-4` is `D-3b` — cross-cut duplicate.** Merged into D2, not a separate sprint.

---

## Sprint ladder (release order within the epic)

| Sprint | Title | Findings | Type | Releasable alone? | Blocks |
|--------|-------|----------|------|-------------------|--------|
| **D0** | Correct the record (refuted premises) | `Q-7`, `Q-9`, `Q-1b`, `D-8` framing | Docs-only — no production code | ✅ yes | D1 / D2 / D3 (removes stale framing) |
| **D1** | Quiz session-frame chrome | `Q-7`, `Q-8`, `Q-9` | Hook + translator + view (one sprint) | ✅ yes | — |
| **D2** | Taxonomy + bucket dots | `D-3b` (+ `X-4` merged) | Content + view | ✅ yes | — |
| **D3** | Session-length decision | `Q-1b` | Decision-first (docs-only, may upgrade to code) | ✅ yes | — |
| **D4 (opt.)** | Skills nav via `comingSoon` | `D-8` | Nav config + optional stub route | ✅ yes, if adopted | — |

**Independence rule (program §4):** each sprint may merge to `main` alone. Between D1, D2,
D3 there is **no sequential dependency** — they touch different surfaces. D0 unblocks by
correcting framing. D4 is optional and only if the human accepts the Stage-1 §7-Q1
alternate posture (default = defer to Epic E).

```
  D0 ──► D1 (frame chrome)  ── ships alone
     ├─► D2 (taxonomy)       ── ships alone
     ├─► D3 (Q-1b decision)  ── ships alone (docs-only, may upgrade)
     └─► D4 (Skills nav, if adopted) ── ships alone
```

---

## Sprint D0 — Correct the record (audit-refuted premises)  🟦 *(docs-only)*

**Origin:** the `sdd-brainstorm` Stage-1 premise audit (2026-07-10) for Epic D found four
premises in the epics doc / parity report to be **refuted or misleading**. Per the
brainstorm hardening rule, refuted load-bearing premises force a re-pose — captured here
as tracked work, not silently continued. D0 lands the corrections before D1/D2/D3 fire
their own `sdd-spec`.

**Premise-status table (what the audit found):**

| # | Premise (as epics-doc / report states it) | Status | Evidence (verified `file:line`) |
|---|---|---|---|
| P3 | `Q-7` is a view-only chip render | **REFUTED** | Wire `Question` has no `skill_name`/`accent_var` ([engine_entities.ts:61-64](../../frontend/lib/wire/engine_entities.ts:61)); those live on `Skill` ([:34-44](../../frontend/lib/wire/engine_entities.ts:34)). Fix is hook + translator. |
| P8 | `Q-9` "dismissible timer" = *learner turns off a rendered clock* | **REFUTED** | No clock renders today — grep on `components/quiz/` for "timer"/"Clock"/"elapsed" = 0 UI hits. Reframe: *collapsible / off-by-default*. |
| P10 | `Q-1b` is a code sprint ("change 30 to 10") | **REFUTED** | Parity report §Q-1b line 140 leaves the decision **explicitly open** ("is 30 intended for adaptive?"). This is a product decision, not a bug. Epics doc says "may be 'keep 30' — recorded in decisions.md, not necessarily a code change." |
| P14 | `D-8` is a safe one-liner (add "skill" to `NAV_MEMBERSHIP`) | **REFUTED** | `screen("skill")` at [nav_model.ts:75](../../frontend/components/shell/nav_model.ts:75) points at `/learn/skill` which **404s today** (Epic E route). Adding to membership = **dead nav item = Q-6-class trust bug** Epic A just closed. Default posture: defer to Epic E. |
| P15 | `X-4` is a separate finding from `D-3b` | **REFUTED** | Parity report §X-4 explicitly says "see D-3b". Same 6-name list, cross-cut framing. Merge into D2. |

**Sprint tasks (docs-only — no `.tsx` / reducer / VM / seed change):**

1. **Record the resolutions in `decisions.md`.** Append newest-first entries:
   - **P3 → Q-7 seam.** Q-7 is a hook + translator + view seam (not view-only); cite
     `engine_entities.ts:34-64`. Ensures D1's spec doesn't try to fake a chip from
     `skillId` alone.
   - **P8 → Q-9 framing.** Q-9's "dismissible" = *collapsible, off-by-default*; underlying
     `elapsed_ms` capture is correct (per Sprint A2 triage). Q-9 UI = **new** clock render
     that starts collapsed.
   - **P10 → Q-1b format.** Q-1b is a product decision recorded via `decisions.md`
     (D3), not a code sprint by default. If it resolves "change to 10", D3 upgrades to
     code + ADR-0023 amend.
   - **P14 → D-8 gate.** D-8 is blocked on Epic E's `/learn/skill` route existing; default
     posture = defer to Epic E's board. Alternate posture (D4) = `comingSoon`
     visible-but-not-clickable-to-404 — human decision at Stage-1 gate.
   - **P15 → X-4 merge.** X-4 is the same finding as D-3b under a cross-cut framing;
     both ship in D2 as one sprint.

2. **Back-propagate to [`preact-parity-epics.md §Epic D`](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-):**
   - Q-7 row: strike "skill chip" language that implies view-only; replace with
     "wire→VM→view seam adding `skillName`/`accentVar` on Quiz VM".
   - Q-9 row: strike "dismissible timer"; replace with "collapsible, off-by-default timer
     rendering (`elapsed_ms` already captured)".
   - Q-1b row: strike "product decision (may be code change)"; replace with
     "decision-first sprint (D3) recording via `decisions.md`; upgrades to code + ADR-0023
     amend iff decision changes `DEFAULT_TARGET_COUNT`".
   - D-8 row: strike "Sidebar missing a 'Skills' entry"; add "`screen('skill')` already
     catalogued as `comingSoon`; blocked on Epic E's route; default posture = defer to
     Epic E's board; alternate = `comingSoon`-gated add".
   - X-4 row: mark as "cross-cut duplicate of D-3b; ships in D2".

3. **Back-propagate to [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) §11 / §0** where the
   above framings appear:
   - Q-9 "dismissible" → "collapsible / off-by-default" (with a short note that
     `elapsed_ms` capture is already correct, cite [`session_summary_vm.ts:60-65`](../../frontend/lib/translators/session_summary_vm.ts:60)).
   - D-8 add a caveat: "gated on Epic E route; do not enable until E lands, or ship as
     `comingSoon`".

**Definition of Done (D0):** the four refuted premises are corrected everywhere they
appeared (epics doc + VISUAL report + this board's opening banner + `decisions.md`); D1,
D2, D3 enter their own `sdd-spec` over the *corrected* framing. **No production code, no
test change** → `make check` green trivially. Explicitly log that D0 **corrected the
record**, it did not implement anything (that is D1/D2/D3) — so "green" is not mistaken
for "features shipped."

**Gates:** No `⚠️ Ask first` trigger (docs-only). This is the **G7/comprehension** payload
the brainstorm surfaced: intent debt (why the framings were wrong) captured before code.
No ADR (`decisions.md` is the right weight — no structural change).

**Releasable alone:** ✅ — pure docs PR; unblocks D1/D2/D3 by removing their stale
framings.

---

## Sprint D1 — Quiz session-frame chrome  🟧 *(one sprint, three sub-features)*

**Report findings:** `Q-7` skill chip · `Q-8` End session · `Q-9` collapsible timer.

**Direction:** **D1 (Stage-1 recommended lead)** — ship all three as one sprint. They
share the Quiz header/frame surface + the same VM plumbing seam. Split into three
commits **inside** the sprint if reviewer prefers, but the spec is one.

**Visual / seam anchors (pre-D1):**

| Seam | Today | Target |
|------|-------|--------|
| Wire | [`Question`](../../frontend/lib/wire/engine_entities.ts:61) has `skill_id` only | unchanged — hook joins via `skillTaxonomy.list` |
| Skill lookup | [`Skill.name`](../../frontend/lib/wire/engine_entities.ts:34) + `Skill.accent_var` exist | joined at hook boundary |
| Hook | [`use_quiz.ts`](../../frontend/components/quiz/use_quiz.ts) reads `skillTaxonomy.list` already | derive `{name, accentVar}` for `Question.skill_id` |
| VM | [`quiz_item_vm.ts:24-32`](../../frontend/lib/translators/quiz_item_vm.ts:24) — `QuizItemVM` has `skillId` only | add `skillName: string \| null` + `accentVar: string \| null` (or new `QuizFrameVM` — spec decides) |
| View | [`QuizView.tsx`](../../frontend/components/quiz/QuizView.tsx) — no chip / no end / no timer | + skill chip in header · + `data-testid="quiz-end-session"` button · + collapsible timer (starts collapsed) |
| Reducer | [`quiz_screen_reducer.ts`](../../frontend/components/quiz/quiz_screen_reducer.ts) — `elapsedMsFrom` for per-item timing | new dispatch: `endSession` (reads current tally, calls `sessionRepo.close(id, tally)`, routes to `/learn`) |
| Session close | [`drizzle_session_repo.ts:113-128`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:113) — `close(id, score)` idempotent | reused verbatim |
| Route | Dashboard exists at `/learn` ([`app/(coach)/learn/page.tsx`](../../frontend/app/(coach)/learn/page.tsx)) | End-session routes here |

**In scope:**

- **Q-7:** skill chip in the Quiz header — "● {Skill.name}" using the skill's
  `accent_var` for the dot color. Honest absent if the join returns no skill (defensive,
  should not happen with valid data).
- **Q-8:** `data-testid="quiz-end-session"` control that closes the session in its
  current tally state and routes to `/learn`. Fires `sessionRepo.close()` — no new port
  method. Non-actionable while the session is already closed (defensive).
- **Q-9:** collapsible timer that is **off by default**. When collapsed: no clock
  rendered, just a small reveal affordance (icon or `data-testid="quiz-timer-reveal"`).
  When expanded: renders `elapsed_ms` since `session.started_at` as `m:ss`. Session
  timing already captured — no engine change.
- Extract a small `QuizFrame` (or add slots to `QuizView`) — decided at `sdd-spec`.

**Out of scope (other sprints or later work):**

- Renaming buckets (D2).
- Session length change (D3).
- Adding `"skill"` to `NAV_MEMBERSHIP` (D4 / Epic E).
- A **per-question** live timer (not requested; `Q-9` is session-level).
- Any change to `elapsed_ms` recording (already correct per A2 triage).

**Likely seams (spec will pin):**

| Layer | Pattern to follow |
|-------|-------------------|
| Hook | [`use_quiz.ts`](../../frontend/components/quiz/use_quiz.ts) — engine reads in hook; skill join at boundary; same pattern as `use_summary` skill-join |
| Translator | pure T1 VM extension (`skillName`/`accentVar`) — G1 gate at `sdd-spec` if we introduce `QuizFrameVM` |
| View | presentational leaf (F-R1); reveal affordance for timer follows existing `data-*` disciplines |
| Reducer | `endSession` dispatch mirrors `finishSession` (same shape, different route) |
| Tests | L1 RTL/jsdom for chip / end-session / timer expand-collapse; L2 for session-close reducer path; E2E walk for end-session → dashboard |

**Definition of Done:** Quiz header renders skill chip with accent dot (Q-7); End-session
control closes the session in-tally + routes to `/learn` (Q-8); timer is collapsible,
starts collapsed, renders `elapsed_ms` when revealed (Q-9); ADR (iff `QuizFrameVM` is a
new abstraction — decide at spec) + `make check` + arch-tests green; mergeable
independently of D2/D3.

**Gates:** **Possibly an ADR** (G1 new-abstraction gate) — if `QuizFrameVM` is
introduced. Same pattern as ADR-0025 (coach surface VM). Frontend Ring F-R1 / T1 /
adapter boundary. `decisions.md` entry recording the `QuizFrameVM`-vs-extend-item-VM
choice regardless.

**Releasable alone:** ✅ — no dep on D2/D3/D4; ships even if the others slip.

---

## Sprint D2 — Taxonomy + bucket dots  ✅ *(Implemented — content + view)*

**Report findings:** `D-3b` bucket names → ACT-standard + per-bucket color dot ·
`X-4` bucket taxonomy mismatch **(merged — same finding cross-cut).**

**Direction:** **D2 (Stage-1 recommended lead)** — content edit to the dev-seed +
presentation update surfacing the existing `accent_var` as a dot glyph. No new tokens,
no new abstractions.

**Visual / seam anchors (pre-D2):**

| Seam | Today | Target |
|------|-------|--------|
| Skill labels (6 rows) | [`_dev_seed.ts:54-105`](../../frontend/lib/adapters/engine/_dev_seed.ts:54) — "Punctuation", "Grammar & Usage", "Sentence Structure", "Rhetorical Skills", "Organization", "Style" | Rename to prototype's ACT-standard labels (open `PreAct/UI-Design/design-spec.md` at `sdd-spec` time; cite verbatim) |
| Color mechanism | `accent_var: "--color-bucket-<key>"` on each skill ([e.g. :57](../../frontend/lib/adapters/engine/_dev_seed.ts:57)) | reused — no new tokens |
| Consumer (dashboard) | [`BucketCard.tsx:33`](../../frontend/components/dashboard/BucketCard.tsx:33) — uses `accent_var` as border/bar `--accent` | + `<span data-testid="bucket-dot" style={...}>` in header |
| Consumer (Quiz chip from D1) | new in D1 | reuse `accent_var` as dot |
| Other consumers | audit at spec time (Summary "See lesson", Coach history line, Progress) | rename-safe grep pass |

**In scope:**

- Rename the 6 bucket labels to the ACT-standard names — **first read
  `PreAct/UI-Design/design-spec.md` and cite the 6 labels verbatim in the spec**
  (Stage-1 P11 caveat — unverifiable target list until source-of-truth is opened).
- Surface `accent_var` as a discrete dot glyph on Dashboard bucket headers (D-3b's
  "color dot" ask). Reuse variable — no new color tokens.
- Grep audit for old label string usages; update any test that pins the old strings.

**Out of scope (other sprints or later work):**

- Any Q-7 chip work (D1 owns the chip render; D2 provides the dot styling).
- `X-4` as an independent sprint (merged here).
- Changes to skill keys / IDs (rename touches display name only; keys stay).

**Likely seams (spec will pin):**

| Layer | Pattern to follow |
|-------|-------------------|
| Content | dev-seed edit — same shape as `emit_test_item_bank.py` content authoring track from Sprint C2 Block 6 |
| Presentation | `<span data-testid="bucket-dot">` + existing `--accent` var — no CSS token additions |
| Tests | L1 RTL asserting the 6 new labels; regression grep for the old labels; E2E walk asserting a dot renders per bucket |

**Definition of Done:** the 6 bucket labels in `_dev_seed.ts` match the prototype's
ACT-standard names (cited verbatim from `PreAct/UI-Design/design-spec.md` in the spec);
Dashboard bucket headers render a discrete dot glyph tinted by the existing `accent_var`;
every consumer of bucket labels has been grep-audited and updated; `decisions.md` entry
records the 6 canonical labels + source citation; `make check` + arch-tests green;
mergeable independently of D1/D3.

**Gates:** No ADR (content + view, no new abstraction). `decisions.md` entry for
the label list is the right weight.

**Releasable alone:** ✅ — no dep on D1/D3/D4.

### § Implementation evidence (Stage 6 — 2026-07-11)

**Shape call:** rename display `name` only on 3 seed rows (`Usage` / `Rhetoric` /
`Conciseness`); insert leading 11×11 `rounded` (4px) dot gated on `vm.accentVar`
(prototype exact — overrides plan default 8px circle). No new CSS tokens, no VM
change, no ADR (`decisions.md` line).

**L1 (Vitest):** `_dev_seed.test.ts` (FR-3/6) · `preact_learn_corpus.test.ts`
(FR-4) · `BucketCard.test.tsx` (FR-2/5) · arch `test_bucket_labels_no_old_strings`
(FR-1) · `test_bucket_tokens_unchanged` (FR-7) — red-first then green. Trace:
[`preact-parity-D2-taxonomy.impl.md`](preact-parity-D2-taxonomy.impl.md).

**L4 (Playwright):** `dashboard-bucket-taxonomy.spec.ts` +
`validate_d2_taxonomy.spec.ts` (learn-e2e). Manual runbook:
[`validate_d2_taxonomy_ui.md`](../../frontend/scripts/validate_d2_taxonomy_ui.md).

**PR log:** D2 closes D-3b + absorbs X-4. Dot size/shape locked to prototype
(`English Coach - Prototype.dc.html:71`).

---

## Sprint D3 — Session-length decision (Q-1b)  ✅ Implemented *(decision-first, docs-only)*

**Report finding:** `Q-1b` — app default `target_count = 30`, prototype = 10. Parity
report explicitly left this open ("is 30 intended for adaptive?").

**Status:** **Implemented** — 2026-07-11. Outcome: **keep 30** (docs-only). Spec:
[preact-parity-D3-session-length.spec.md](preact-parity-D3-session-length.spec.md) ·
Plan: [preact-parity-D3-session-length.plan.md](preact-parity-D3-session-length.plan.md) ·
Tasks: [preact-parity-D3-session-length.tasks.md](preact-parity-D3-session-length.tasks.md) ·
Impl: [preact-parity-D3-session-length.impl.md](preact-parity-D3-session-length.impl.md) ·
Decision: [`decisions.md` Q-1b line](../adr/decisions.md).

**Direction:** **decision-first** — resolve as a product answer recorded in
`decisions.md`. If "keep 30" → sprint closes docs-only. If "change to 10" → sprint
upgrades to a code change (one const + ADR-0023 amend).

### § Implementation evidence (Stage 6 — 2026-07-11)

- **T-D1 answer (verbatim):** `keep 30` — ADR-0023 adaptive mastery signal; design-spec `:143` "10" is narrative-only; FR-11 covers thin-skill shortfall.
- **Rejected:** move to 10 (prototype fidelity + thin-bank full drills without S3-pre).
- **Code path:** not taken. `DEFAULT_TARGET_COUNT` remains 30; ADR-0023 not amended.
- **Evidence:** [`decisions.md`](../adr/decisions.md) Q-1b line; parity report §Q-1b → Resolved.

**Visual / seam anchors:**

| Seam | Today | Target if "change to 10" |
|------|-------|--------------------------|
| Default | [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26) — `const DEFAULT_TARGET_COUNT = 30` | `10` |
| ADR | [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md) — accepted with `30` | Amend with new count + rejected alternative + rationale |
| Tests | grep at decision time for hard-coded `30` | update any |
| Wire | [`QuizSession.target_count`](../../frontend/lib/wire/engine_entities.ts:213) — already nullable + int-positive | unchanged |

**Sprint task (a spike, gated on outcome):**

1. **Author `decisions.md` entry framing the question.** Two candidates:
   (a) keep 30 (rationale: adaptive-loop mastery signal; matches what S3 shipped);
   (b) change to 10 (rationale: matches prototype; shorter feedback loop for the
   Phase-1 learner).
2. **Product answer.** Human picks.
3. **Branch on the finding:**
   - **"Keep 30"** → close D3 with a `decisions.md` entry ("Q-1b resolved: keep 30;
     prototype's 10 was a demo-length choice, not a product spec"); no code, no test,
     `make check` green trivially. **This closes the sprint.**
   - **"Change to 10"** → author `preact-parity-D3-session-length.spec.md` with an EARS FR
     ("WHEN a new session opens, THEN `target_count` = 10"); one-const change; ADR-0023
     amend with rejected alternative (keeping 30); test seen red first (existing session
     length tests will fail on `30` literal); L1 + E2E green.

**Definition of Done (decision):** the `Q-1b` question is **resolved with rationale
recorded** in `decisions.md`; if code was needed, ADR-0023 is amended and the change
is TDD'd. `make check` green.

**Gates:** No `⚠️ Ask first` for the docs-only outcome. If the decision changes
`DEFAULT_TARGET_COUNT`, **amend** ADR-0023 (structural change to a shipped decision) —
that's the ADR ratchet discipline, not a new ADR. Explicitly log that the sprint
resolved the question, not "fixed a bug" — the parity report itself was open.

**Releasable alone:** ✅ — either a docs-only change or a small isolated code + ADR
change.

---

## Sprint D4 — Skills nav via `comingSoon`  🟨 *(OPTIONAL — human picks at Stage-1 §7-Q1)*

**Report finding:** `D-8` — Sidebar missing a Skills nav entry.

**Direction:** **D4 (Stage-1 alternate)** — ship `D-8` behind a **`comingSoon` visual
state**, reusing the pattern `nav_model.ts` already uses for `progress`. Only fire this
sprint if the human declines the default posture ("defer D-8 to Epic E").

**Default posture:** ⚠️ **defer D-8 to Epic E's board.** Rationale: adding a nav entry
whose target route 404s is the exact class of bug Epic A closed (`Q-6`). Epic E naturally
lands the target route + the nav entry together, cleaner and cheaper. This sprint only
exists as an alternate if the human explicitly picks it.

**Visual / seam anchors (only relevant if adopted):**

| Seam | Today | Target |
|------|-------|--------|
| Nav catalog | [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) — `screen("skill", ..., comingSoon: true)` **already exists** | unchanged |
| Membership | [`nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103) — desktop/ipad = `["dashboard","quiz","coach","progress"]`; iphone = `["dashboard","quiz","progress"]` | add `"skill"` to both |
| Rendering | `AppNav.tsx` — must render `comingSoon: true` items with `data-coming-soon` + non-clickable state (confirm at spec) | reused pattern (already handled for `progress`) |
| Optional stub route | `/learn/skill` 404s today | optional: `frontend/app/(coach)/learn/skill/page.tsx` — 10 lines "Coming soon" + link back to Dashboard |
| Test | [`nav_model.test.ts`](../../frontend/components/shell/nav_model.test.ts) | extend with new membership assertion |

**In scope (if adopted):**

- Add `"skill"` to `NAV_MEMBERSHIP` for the surfaces the prototype shows it on.
- Confirm `AppNav.tsx` renders `comingSoon: true` items visibly-but-not-clickable (or
  clickable-to-stub if we add the stub route).
- Optional: 10-line stub route to avoid the 404.

**Out of scope:**

- Actually building `/learn/skill` (that is Epic E).
- Any change to the `screen()` catalog entry itself.

**Definition of Done (if adopted):** Skills entry visible in the sidebar with a clear
"Coming soon" state; either not clickable or routes to a "Coming soon" stub; no 404
reachable from the nav; `nav_model.test.ts` extended; `make check` + arch-tests green.

**Gates:** No new ADR expected (reuses existing `comingSoon` pattern). If `AppNav.tsx`
doesn't already handle `comingSoon`, that's a larger change — spec at `sdd-spec` time and
may warrant an ADR. `decisions.md` entry for the "gated ship vs defer" choice regardless.

**Releasable alone:** ✅ — no dep on D1/D2/D3.

---

## Epic-D exit criteria (what "released" means)

- [ ] **D0 shipped:** the four refuted premises (P3/P8/P10/P14) are corrected everywhere
      they appeared (epics doc + VISUAL report + this board + `decisions.md`); D1/D2/D3
      framings are the corrected ones. Docs-only.
- [ ] **D1 shipped:** Quiz header renders skill chip (Q-7) via VM extension; End-session
      control closes-and-routes (Q-8); collapsible timer starts collapsed and reveals
      `elapsed_ms` (Q-9); ADR (iff `QuizFrameVM` introduced) accepted; L1 + E2E green.
- [ ] **D2 shipped:** 6 bucket labels renamed to ACT-standard (verbatim from
      `PreAct/UI-Design/design-spec.md`); Dashboard renders bucket dots via `accent_var`;
      all consumers grep-audited; `decisions.md` records the canonical 6 labels.
- [x] **D3 resolved:** `Q-1b` closed with a `decisions.md` rationale; if the decision
      changed `DEFAULT_TARGET_COUNT`, ADR-0023 amended + code TDD'd; either way `make
      check` green. **Outcome 2026-07-11: keep 30 (docs-only).**
- [ ] **D4 (optional):** either explicitly deferred to Epic E (`decisions.md` note) or
      shipped as `comingSoon` — no dead nav item, either way.
- [ ] Parity report §11 / §0 updated to reflect the corrected status of Q-7 / Q-8 / Q-9 /
      Q-1b / D-3b / X-4 / D-8. `X-4` marked as absorbed into D2.
- [ ] **Gate to Epic E:** with D1+D2+D3 (+ D4 if adopted) on `main`, return to the
      [epics doc](preact-parity-epics.md) and the user opens Epic E's board. One epic in
      flight at a time.

---

## Notes carried back to the parity report / epics

Stage-1 (2026-07-10) corrections to fold into the VISUAL report §11/§0 and epics doc
§Epic D — D0 owns the mechanical propagation. Summary of the changes:

1. **Q-7** — "skill chip render" → "wire→VM→view seam adding `skillName`/`accentVar` on
   Quiz VM"; view-only framing was wrong (P3).
2. **Q-9** — "dismissible timer" → "collapsible / off-by-default timer"; the underlying
   `elapsed_ms` capture is already correct per Sprint A2 triage (P8).
3. **Q-1b** — "product decision (may be code)" → "decision-first sprint (D3) recording
   via `decisions.md`; upgrades to code + ADR-0023 amend iff decision changes 30" (P10).
4. **D-3b** absorbs **X-4** — one sprint (D2), not two (P15).
5. **D-8** — "sidebar missing Skills" → "screen('skill') already catalogued as
   `comingSoon` but excluded from `NAV_MEMBERSHIP`; blocked on Epic E's route existing;
   default = defer to Epic E; alternate = `comingSoon`-gated add (D4)" (P14).

---

## What's next (not part of this board)

1. **Human gate on Stage-1 §7 questions** ([brainstorm §7](preact-parity-epic-D.brainstorm.md#7--open-questions-for-the-human)):
   Q1 (D-8 in this epic or defer?), Q2 (D3 posture), Q3 (D1 as one sprint or three?).
2. Once the gate closes, **D0 enters `sdd-spec`** (docs-only) and ships first.
3. In parallel or after D0: **D1, D2, D3 each enter their own `sdd-spec`** and ship
   independently. **D4 only fires if the human picked it** at Stage-1 §7-Q1.
4. On Epic-D release (all adopted sprints on `main`), return to the epics doc and the
   user opens Epic E's board.
