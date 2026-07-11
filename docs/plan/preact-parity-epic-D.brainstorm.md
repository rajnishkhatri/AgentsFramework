---
title: 'PreAct Parity Epic D — Brainstorm (SDD Stage 1)'
type: brainstorm
date: 2026-07-10
status: Draft → gated on human direction pick
stage: SDD Stage 1 (brainstorm) — closes when the human picks a lead per §Directions
derives_from:
  - docs/plan/preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
governs:
  - docs/plan/preact-parity-sprint-board-D.md   # sibling; written alongside this doc
findings_in_scope: [Q-7, Q-8, Q-9, Q-1b, D-3b, D-8, X-4]
---

# PreAct Parity Epic D — **Brainstorm (SDD Stage 1)**

**Purpose.** Expand Epic D — *Quiz session frame + taxonomy polish* — into
grounded directions before any spec, per the SDD lifecycle. This doc is the
**Stage-1 evidence artifact**: audited premises, generated directions,
validated hypotheses, dependency map. The sibling **sprint board**
([`preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md)) is the
release-order artifact derived from the directions the human accepts here.

**Scope (from [epics doc §Epic D](preact-parity-epics.md)):** seven backlog
items grouped by theme:

| Theme | Findings |
|------|----------|
| Session frame chrome | `Q-7` skill chip · `Q-8` End session · `Q-9` dismissible timer |
| Product decision | `Q-1b` session length 30 vs 10 |
| Taxonomy + nav | `D-3b` bucket names → ACT + color dot · `D-8` Skills nav · `X-4` bucket taxonomy mismatch (cross-cut) |

Constitution backdrop: root `AGENTS.md` (8 invariants + ✅/⚠️/🚫). All UI seams
live in the Frontend Ring → nested `AGENTS.md` under `frontend/`. No trust
kernel touched.

---

## 1 · Premise audit (grounded against the working tree)

Every load-bearing claim from the epic map / parity report was checked against
the code before ideation. `verified` / `refuted` / `unverifiable`.

| # | Premise (as epics doc / report states it) | Status | Evidence (`file:line`) |
|---|-------------------------------------------|--------|------------------------|
| P1 | `Q-7` — App renders **no** per-question skill chip today | **verified** | [QuizView.tsx:48](../../frontend/components/quiz/QuizView.tsx:48) has `data-skill={vm.skillId}` but no visible chip; full 145-line file has no skill/bucket surface. |
| P2 | The **VM structurally omits** the skill name / bucket accent | **verified** | [quiz_item_vm.ts:24-32](../../frontend/lib/translators/quiz_item_vm.ts:24) — `QuizItemVM` has `skillId` only; no `skillName`/`accentVar`. |
| P3 | `Q-7` "just render a chip" — one-file change | **REFUTED** | The wire `Question` doesn't carry `skill_name`/`accent_var` ([engine_entities.ts:61-64](../../frontend/lib/wire/engine_entities.ts:61)); those live on the `Skill` entity ([:34-44](../../frontend/lib/wire/engine_entities.ts:34)). Q-7 is a **hook + translator** change (skill lookup during `loadQuestion`), not view-only. |
| P4 | `Q-8` — App has **no** mid-session abandon control | **verified** | Only `quiz-next` + `quiz-finish` render ([quiz/page.tsx:282-297](../../frontend/app/(coach)/learn/quiz/page.tsx:282)); grep for "abandon\|endSession\|quit" in `components/quiz/` + `app/(coach)/learn/quiz/` = 0 hits. |
| P5 | `SessionRepo.close()` already exists and is idempotent-safe | **verified** | [drizzle_session_repo.ts:113-128](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:113) — sets `ended_at` + tally. Called only from `onFinish`. |
| P6 | Dashboard route exists to bail out to | **verified** | [app/(coach)/learn/page.tsx](../../frontend/app/(coach)/learn/page.tsx) at route `/learn` (per [nav_model.ts:65](../../frontend/components/shell/nav_model.ts:65)). |
| P7 | `Q-9` `elapsed_ms` **already recorded** per-attempt + session | **verified** | Per-attempt at [quiz_screen_reducer.ts:40](../../frontend/components/quiz/quiz_screen_reducer.ts:40) → `Attempt.elapsed_ms` [engine_entities.ts:231](../../frontend/lib/wire/engine_entities.ts:231). Session-level `timeTile()` at [session_summary_vm.ts:42,60-65](../../frontend/lib/translators/session_summary_vm.ts:42) (proved by Sprint A2 triage). |
| P8 | `Q-9` "dismissible" = *the learner turns off a rendered clock* | **REFUTED** | No clock is rendered anywhere today (grep in `components/quiz/` = 0 hits). The finding is really **"prototype has a rendered but dismissible clock; app renders no clock"**. The verb is *"add a clock that starts collapsed"* / *"render it optional"*, not "let the learner hide a clock we already show." Reframe accordingly. |
| P9 | `Q-1b` — App default `target_count = 30`, prototype = 10 | **verified** | [drizzle_session_repo.ts:26](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26) — `const DEFAULT_TARGET_COUNT = 30;` shipped in [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md). Parity report §Q-1b line 140 leaves the decision **explicitly OPEN** ("is 30 intended for adaptive?"). |
| P10 | `Q-1b` is a **code change** (make it 10) | **REFUTED** | It is a **product decision**, not code. May resolve as "keep 30 — recorded in `decisions.md`, no code change" per [epics doc §Epic D](preact-parity-epics.md). Do not confuse with a fix sprint. |
| P11 | `D-3b`/`X-4` — App uses different bucket labels than the prototype | **verified (with a caveat)** | The 6 app labels are in [`_dev_seed.ts:54-105`](../../frontend/lib/adapters/engine/_dev_seed.ts:54): `Punctuation`, `Grammar & Usage`, `Sentence Structure`, `Rhetorical Skills`, `Organization`, `Style`. Prototype's exact 6 names were **not** independently opened (`PreAct/UI-Design/design-spec.md` unread) → `unverifiable-by-file` for the target list; source-of-truth is the parity report §D-3b paraphrase ("Rhetoric / Usage / Conciseness"). Any spec that renames buckets MUST first read the prototype and cite verbatim. |
| P12 | `D-3b` — "no per-bucket color dot" today | **PARTIALLY REFUTED** | A per-bucket color mechanism **already exists**: each skill carries `accent_var: "--color-bucket-<key>"` (e.g. [`_dev_seed.ts:57,67,87`](../../frontend/lib/adapters/engine/_dev_seed.ts:57)), consumed as a border/bar accent by [`BucketCard.tsx:33`](../../frontend/components/dashboard/BucketCard.tsx:33). The gap is a **discrete dot glyph** (design language), not a missing token. Reframe: "surface the existing accent as a dot," not "invent color tokens." |
| P13 | `D-8` — Sidebar has **no** Skills nav entry today | **verified** | Full [`nav_model.ts`](../../frontend/components/shell/nav_model.ts) read. A `screen("skill", ..., comingSoon: true)` DOES exist ([`:75`](../../frontend/components/shell/nav_model.ts:75)), but it is **excluded from `NAV_MEMBERSHIP`** ([`:103-107`](../../frontend/components/shell/nav_model.ts:103): desktop/ipad = `["dashboard","quiz","coach","progress"]`; iphone = `["dashboard","quiz","progress"]`). No sidebar/tab-bar renders it. |
| P14 | Adding `"skill"` to `NAV_MEMBERSHIP` is a **safe one-liner** | **REFUTED (this is exactly Epic A's class-of-bug)** | `screen("skill")` at [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) points at route `/learn/skill`, which today **404s** — the whole point of **Epic E** ([epics doc §Epic E](preact-parity-epics.md#epic-e--skill-detail-screen--)). Adding it to `NAV_MEMBERSHIP` before Epic E ships lands a **dead nav item** = the trust-bug class Epic A opened the parity program to close (`Q-6` reveal button). The rule ([epics doc §Epic D Gates](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-)) is explicit: "`D-8`'s 'Skills' nav entry should *not* be enabled until Epic E's route exists — ship it as `comingSoon` or omit until E lands." So D-8 is a **latent** gate, not a free add. |
| P15 | `X-4` is an independent finding | **REFUTED** | The parity report itself cross-refs X-4 → D-3b ([VISUAL-gap-report §X-4](preact-ui-prototype-parity-VISUAL-gap-report.md) — "app 6 buckets ≠ prototype 6 by name (see D-3b)"). X-4 is the same 6-name list framed cross-cuttingly, not a second finding. **Merge into D-3b's sprint**; don't split. |
| P16 | Every sprint is releasable alone | to prove per direction below | — |

**Summary of the audit.** Three findings' framings need re-posing before any
spec fires:

- **`Q-7`** is *not* a view-only chip render — it's a wire→VM→view path that
  today drops `skill_name`/`accent_var` at the translator. Sprint scope must
  include the hook/translator seam, not just `QuizView.tsx`.
- **`Q-9`** is *not* "let the user turn off a rendered clock" — no clock is
  rendered. Reframe as "render a **collapsible, off-by-default** timer that
  can be revealed by the learner; underlying `elapsed_ms` recording is
  already correct."
- **`Q-1b`** is *not* a code sprint — it is a **product decision**
  (`decisions.md` entry, possibly no code). If chosen "make it 10", that's a
  one-const change in `drizzle_session_repo.ts` + ADR-0023 amend.
- **`D-8`** is *not* a free nav-add — it is **gated on Epic E's route
  existing**. Two clean postures: (a) omit from D and wait for E; (b) add
  entry BUT mark it visibly `comingSoon` in the UI and route to a stub page
  that explains "coming soon" — the pattern the app already uses for
  `progress`. The naïve "add to `NAV_MEMBERSHIP`" ships a dead control.
- **`X-4`** and **`D-3b`** are one finding; treat as one sprint.

---

## 2 · Directions (~6, ranked)

Three high-probability directions that follow existing repo patterns, three
exploratory. Each names the file/pattern it follows, its release-alone
posture, its `⚠️ Ask first` triggers, and which Architecture Invariant it
stresses.

### D1 · Session-frame chrome sprint  🟩 *(high-prob)*
> **What:** Ship `Q-7` skill chip + `Q-8` End session + `Q-9` collapsible
> timer as **one sprint** — they share the same surface (the Quiz screen
> header/frame) and the same VM plumbing (a new `QuizFrameVM` slot next to
> the item VM).
>
> **Follows:** the same pattern as [`preact-quiz-progress-surface`](preact-quiz-progress-surface.spec.md) —
> a new VM field (`progress: { current, total }`) landed via translator +
> hook + view, tested L1 + E2E. Frontend Ring F-R1/T1.
>
> **Seams touched:**
> - Wire: no schema change — `Question.skill_id` already carries it; **`Skill`
>   lookup happens in the hook** (existing pattern: [`use_quiz.ts`](../../frontend/components/quiz/use_quiz.ts) already reads `skillTaxonomy.list`).
> - Translator: extend [`quiz_item_vm.ts`](../../frontend/lib/translators/quiz_item_vm.ts) with `skillName: string | null` and
>   `accentVar: string | null` — or a new `QuizFrameVM` beside it (spec
>   decides; ADR only if it's a new abstraction slot).
> - View: new `QuizFrame` presentational leaf (or add slots to `QuizView`) —
>   renders chip + End session button + collapsed-by-default timer with a
>   reveal toggle.
> - Reducer: End session dispatches to `sessionRepo.close(id, currentTally)`
>   + routes to `/learn` (Dashboard).
>
> **Releasable alone:** ✅ — no dep on Q-1b, D-3b, D-8. Each of Q-7/Q-8/Q-9
> could ship as its own commit inside the sprint if desired.
>
> **⚠️ Ask first triggers:** possibly a new frontend VM abstraction
> (`QuizFrameVM`) → ADR at `sdd-spec` time (G1 new-abstraction gate). Same
> pattern as ADR-0025 (coach surface VM).
>
> **Invariant stress:** Frontend Ring only. No layering violation. `use_quiz`
> stays a hook; no engine change.
>
> **What breaks if chosen:** Q-8's "End session then route" needs to update
> the sidebar/tab-bar's active state — same shell we haven't touched since
> S5. Cheap; tested by existing `nav_model.test.ts`.

### D2 · Taxonomy sprint (D-3b + X-4 merged)  🟩 *(high-prob)*
> **What:** Rename the 6 bucket labels to the ACT-standard names the
> prototype uses AND surface the existing `accent_var` as a discrete
> dot-glyph in dashboard headers + the new Q-7 chip.
>
> **Follows:** the `_dev_seed.ts` + `skill_taxonomy` seam already exists —
> this is a **content edit** to the seed + a **presentation update** in
> `BucketCard.tsx` / the new `QuizFrame`. Same shape as the `emit_test_item_bank.py`
> content-authoring track from Sprint C2 Block 6.
>
> **Seams touched:**
> - Content: [`_dev_seed.ts:54-105`](../../frontend/lib/adapters/engine/_dev_seed.ts:54) — the 6 skill rows.
>   **Must first open `PreAct/UI-Design/design-spec.md`** and cite the 6
>   target labels verbatim in the spec (P11 caveat).
> - Presentation: add a `<span data-testid="bucket-dot" style={...}>` to
>   [`BucketCard.tsx`](../../frontend/components/dashboard/BucketCard.tsx) header. Reuse `accent_var` — no new color
>   tokens needed.
> - Any other consumer of bucket labels (Summary "See lesson" copy, Coach
>   history line, Progress screen) — audit at spec time.
>
> **Releasable alone:** ✅ — independent of D1. Ships even if D1 slips.
>
> **⚠️ Ask first triggers:** none. A dev-seed content edit + a `<span>` add
> is not an abstraction. `decisions.md` entry recording which 6 labels
> the ACT standard is (with citation to the prototype).
>
> **Invariant stress:** none. Content + view only.
>
> **What breaks if chosen:** any test that pins bucket labels literally — a
> quick grep at spec time for the old strings ("Rhetorical Skills",
> "Grammar & Usage") will surface them.

### D3 · Session-length decision  🟩 *(high-prob)*
> **What:** Resolve `Q-1b` as a **product decision** recorded in
> `decisions.md`. If "keep 30" → no code. If "change to 10" → one const in
> `drizzle_session_repo.ts` + amend [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md).
>
> **Follows:** the same `decisions.md` pattern used by A0 (FR-D5/FR-D6
> resolution) and B0 (D5a / C-4 honesty). Docs-only most likely.
>
> **Seams touched (worst case):**
> - [`drizzle_session_repo.ts:26`](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts:26) — `DEFAULT_TARGET_COUNT`.
> - [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md) — amend with new count + rejected alternative.
> - Any E2E / L1 that hard-codes `30` (grep at decision time).
>
> **Releasable alone:** ✅ — most likely docs-only PR.
>
> **⚠️ Ask first triggers:** if the decision changes ADR-0023 (structural
> change to a shipped decision), amend the ADR — that's the ADR ratchet
> discipline. Not a new ADR.
>
> **Invariant stress:** none.
>
> **What breaks if chosen "change to 10":** any test that assumes 30 items
> per session — audit at decision time. Cheap.

### D4 · Skills-nav sprint (D-8) — Gated posture  🟨 *(exploratory)*
> **What:** Ship D-8 **behind a `comingSoon` visual state** — add `"skill"`
> to `NAV_MEMBERSHIP` and either (a) render it in the sidebar with a
> `data-coming-soon` badge (same discipline as `progress` today) so it's
> visible but not clickable-to-404, OR (b) route it to a minimal stub page
> at `/learn/skill` that says "Coming soon" (~10 LOC).
>
> **Follows:** the same `comingSoon` pattern [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) already
> uses for `progress`. Look at how the current progress-nav item renders
> (probably grey/disabled) for the shape.
>
> **Seams touched:**
> - [`nav_model.ts:103-107`](../../frontend/components/shell/nav_model.ts:103) — add `"skill"` to `NAV_MEMBERSHIP` per surface.
> - `AppNav.tsx` — confirm coming-soon rendering (may already handle it).
> - Optional stub route: `frontend/app/(coach)/learn/skill/page.tsx` — 10
>   lines saying "Coming soon" + a link back to Dashboard.
> - Test: extend [`nav_model.test.ts`](../../frontend/components/shell/nav_model.test.ts) with the new membership.
>
> **Releasable alone:** ✅ — no dep on D1/D2. But note the **trust-bug
> tension**: showing `comingSoon` is honest; showing a clickable-that-404s
> is dishonest (= `Q-6`, closed by Epic A).
>
> **⚠️ Ask first triggers:** none if we reuse the existing `comingSoon`
> pattern; ADR-0025-style if we introduce a new "gated nav" abstraction.
> Prefer reuse.
>
> **Invariant stress:** Frontend Ring only.
>
> **What breaks if chosen:** the "already in progress the same class of bug"
> concern is exactly Epic A. Ship *only* if we can render the `comingSoon`
> state without regressing trust. **Alternative posture: DEFER to Epic E's
> board** and don't ship a Skills nav at all until E's `/learn/skill`
> exists. This is cheaper and doesn't spend spec/testing budget on a stub.

### D5 · Class-level nav-honesty seam  🟨 *(exploratory)*
> **What:** Instead of adding one nav entry, add a **class-level architecture
> test** that a `NAV_MEMBERSHIP` entry pointing at a route that 404s (or
> whose `screen()` entry has `comingSoon: true`) MUST render with a
> `data-coming-soon` attribute — a mechanical guard against the same bug
> class Epic A closed (dead controls). Then D-8 lands as a positive case
> under the new test.
>
> **Follows:** the same class-over-instance principle as ADR ratchet
> (`tests/architecture/test_adr_ratchet.py`) — mechanical enforcement, not
> convention.
>
> **Seams touched:**
> - New test: `frontend/tests/architecture/test_nav_honesty.test.ts` (or
>   Python if we run it under pytest — see existing arch tests).
> - `nav_model.ts` — no schema change if `comingSoon` already suffices.
> - `AppNav.tsx` — add `data-coming-soon` prop if not present.
>
> **Releasable alone:** ✅ — even without D-8 landing, the test guards future
> adds.
>
> **⚠️ Ask first triggers:** yes — new architecture test = new invariant. ADR
> is warranted (G1: this is a *new discipline* the codebase enforces).
>
> **Invariant stress:** adds an invariant. Positive stress: locks in
> Epic-A-class trust. Cost: an ADR + a new arch test = higher-ceremony than
> D4.
>
> **What breaks if chosen:** more upfront ceremony; slower to ship D-8's
> user-visible bit. Best posture if we think we'll add >1 gated nav
> (Skills + Progress + …).

### D6 · Do-regardless hygiene sprint  🟦 *(docs-only opener)*
> **What:** Author a **D0 docs sprint** (like A0 and B0) that lands:
> - `decisions.md` — the resolved framing for the four refuted premises
>   above (P3, P8, P10, P14).
> - Back-propagate to [`preact-parity-epics.md §Epic D`](preact-parity-epics.md) — correct the "just
>   wire it" language on Q-7/Q-9/Q-1b/D-8 to reflect the audit.
> - Back-propagate to [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md) §11 — Q-9's
>   "dismissible timer" framing is misleading; correct to "collapsible /
>   off-by-default".
>
> **Follows:** identical to A0 / B0.
>
> **Releasable alone:** ✅ — docs-only, ships first, unblocks D1/D2/D3/D4.
>
> **⚠️ Ask first triggers:** none.
>
> **Invariant stress:** none.
>
> **What breaks if chosen:** nothing — this is the "correct the record"
> discipline both prior epics ran. Skipping it means D1/D2 specs inherit the
> stale framing.

---

## 3 · Hypotheses for the leading direction

The audit's dependency map (§4) points at the same lead the ranking suggests:
**D6 (docs opener) → D1 (frame) + D2 (taxonomy) + D3 (decision) as
independent releasable sprints, D4/D5 (skills nav) deferred to Epic E's
window.** Hypotheses under this lead:

- **H1 — Q-7/Q-8/Q-9 are one coherent sprint (D1):** they share the Quiz
  header/frame surface + the same VM plumbing seam. Splitting into three
  sprints doubles ceremony without independence gain.
  **Validates:** [`QuizView.tsx`](../../frontend/components/quiz/QuizView.tsx) is a single ~145-line component; all three
  additions live in the frame region, above the item body. Confirmed by
  fully reading the file in the audit.
- **H2 — Q-7 needs a translator change, not view-only:** wire `Question`
  doesn't carry `skill_name` / `accent_var` — those live on `Skill`.
  **Validates:** [`engine_entities.ts:34-44,61-64`](../../frontend/lib/wire/engine_entities.ts:34) — `Skill.name` +
  `Skill.accent_var` exist; `Question` has `skill_id` only. Hook must join.
- **H3 — Q-9 "dismissible" is really "collapsible off-by-default":** no
  clock renders today.
  **Validates:** grep on `frontend/components/quiz/` for "timer"/"Clock"/"elapsed"
  → 0 UI hits; only the reducer's internal timing logic. Reframe is honest.
- **H4 — D-3b and X-4 are one finding:** parity report cross-refs X-4 → D-3b.
  **Validates:** VISUAL-gap-report §X-4 explicitly says "see D-3b". Merging
  is not scope-loss.
- **H5 — D-3b's color mechanism already exists as `accent_var`:** we surface
  it as a dot, don't invent tokens.
  **Validates:** [`_dev_seed.ts:57,67,87`](../../frontend/lib/adapters/engine/_dev_seed.ts:57) — `accent_var` on every skill;
  [`BucketCard.tsx:33`](../../frontend/components/dashboard/BucketCard.tsx:33) consumes it as `--accent`. New use = same
  variable, new selector.
- **H6 — Q-1b is not a code sprint:** the parity report itself leaves the
  decision open, and the epics doc says "may be 'keep 30' — recorded in
  `decisions.md`, not necessarily a code change."
  **Validates:** [VISUAL-gap-report:140](preact-ui-prototype-parity-VISUAL-gap-report.md) — "is 30 intended for
  adaptive?" (open question, not a bug report). [`epics.md §Epic D`](preact-parity-epics.md) — the
  decisions.md path is called out explicitly.
- **H7 — D-8 deferral is the trust-safe move:** adding a nav entry that
  points at a 404 is exactly the Epic-A class of bug. Two safe postures:
  (a) skip D-8 in this epic; (b) ship via `comingSoon` reusing the
  `progress` pattern. Neither is a *fix* sprint that "unblocks" anything.
  **Validates:** [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) — `screen("skill", .., comingSoon: true)`
  already exists in the catalog; adding it to `NAV_MEMBERSHIP` without a
  target route is the dead-control bug. Under P14 evidence.
- **H8 — Under-used signal (bonus):** `elapsed_ms` is already recorded
  per-attempt and never surfaced anywhere in the UI beyond the Summary tile.
  Q-9's collapsible timer + a future "focus mode" (out of scope) could reuse
  it — the signal is already there; the gap is presentation, not capture.
  **Validates:** per audit — `Attempt.elapsed_ms` populated in the reducer
  path, but no UI consumer exists.

**Rejected hypotheses (before wasting a spec on them):**

- ~~"Q-7 is a one-file view change"~~ — refuted (P3).
- ~~"Q-8 wire existing `endSession()`"~~ — refuted (P4): no such function.
  It's a new dispatch that calls `sessionRepo.close()` in
  the current-tally state + routes.
- ~~"Q-9 add a `<Clock>` component and let user close it"~~ — refuted (P8):
  reframe is *collapsed by default*, not *toggle a rendered clock*.
- ~~"Q-1b change to 10"~~ — refuted (P10): this is a *decision*, not a
  premise. The direction is "record the decision," not "change the const."
- ~~"D-8 add `skill` to `NAV_MEMBERSHIP`"~~ — refuted (P14): dead nav item,
  same class as `Q-6`.
- ~~"X-4 is a separate sprint"~~ — refuted (P15): it's D-3b.

---

## 4 · Dependency map + release order

```
  D6 (docs opener) ──► D1 (frame chrome: Q-7 + Q-8 + Q-9)      ✅ releasable alone
                  │
                  ├──► D2 (taxonomy: D-3b + X-4)               ✅ releasable alone
                  │
                  └──► D3 (Q-1b decision — decisions.md)       ✅ releasable alone

  D-8 (Skills nav)  →  DEFERRED to Epic E's board — dead-nav trust risk
                        (or optional D-8-gated ship inside D, only if we adopt D4's
                         comingSoon posture; human picks)
```

**Sequential dependency:** D6 → { D1, D2, D3 } (D6 unblocks by correcting
the framing D1/D2/D3 rely on). Between D1, D2, D3 — **no sequential
dependency** — they touch different surfaces (Quiz header vs Dashboard/seed
vs docs). Ship in any order, or in parallel PRs.

**Cross-epic dependency (D-8):** blocked on Epic E's `/learn/skill` route
existing, per [epics doc §Epic D Gates](preact-parity-epics.md#epic-d--quiz-session-frame--taxonomy-polish-).
Cleanest is to defer D-8 out of Epic D entirely; second-cleanest is D4's
`comingSoon` posture inside Epic D. Human picks.

**Do-regardless (no-ADR hygiene):**
- Record refuted-premise framings in `decisions.md` (D6).
- Grep audit before every rename (D2) for old string usages.
- Every sprint's `sdd-spec` re-checks the parity report for updates.

**Capability vs operational:** all D sprints are capability
(user-visible parity delta), not operational (perf, cost, telemetry). No
metering / A-B considerations.

**Calendar cost:** D6 = hours. D3 = human decision (calendar-bound: needs a
product answer). D1 = a few sessions of engineering. D2 = one session +
prototype-source read. D-8 (if adopted) = one session + arch-test debate.

---

## 5 · Recommended lead → for the human gate

**Lead direction (pre-gate):** **D6 + D1 + D2 + D3 as four independently-releasable
sprints; D-8 DEFERRED to Epic E's window.** Rationale:
- Matches the Epic A / Epic B pattern (docs opener → typed sprints).
- Each sprint is small, isolated, releasable alone.
- Q-1b (D3) parallelizes on human-decision time; no engineering blocked.
- Deferring D-8 avoids re-opening the trust-bug class Epic A just closed —
  and Epic E naturally lands the target route + the nav entry together.

**Alternate posture if the human wants D-8 in Epic D:** add **D4** (gated
`comingSoon` nav) and skip **D5** (arch-test — heavier ceremony for one
entry). ADR only if AppNav doesn't already handle `comingSoon` visibly; else
`decisions.md`.

**Not recommended:** ~~D5 (class-level nav-honesty arch test)~~ — right idea
but wrong sprint (should ride with Epic E when we have 2 gated navs to
protect: Skills and Progress). Land D5 as an Epic-E sub-sprint instead.

---

## 6 · Directions × invariants (ADR / gate summary)

| Direction | ADR needed? | Which `⚠️ Ask first` trigger? | Invariant stressed |
|-----------|-------------|-------------------------------|--------------------|
| D1 (frame chrome) | **Possibly** (G1: new VM abstraction if we introduce `QuizFrameVM`) — decide at `sdd-spec` | new abstraction | Frontend Ring F-R1/T1 |
| D2 (taxonomy) | No — content + `<span>` add | none | none |
| D3 (Q-1b decision) | **Amend** ADR-0023 if `DEFAULT_TARGET_COUNT` changes | trust-adjacent (session length shipped decision) | none new |
| D4 (Skills nav via `comingSoon`) | No if reusing `nav_model`'s existing flag | none if reused | Frontend Ring |
| D5 (arch test) | **Yes** (G1: new invariant / discipline) | new abstraction | +1 invariant |
| D6 (docs opener) | No | none | none |

---

## 7 · Open questions for the human

Please pick the direction(s):

1. **Include D-8 (Skills nav) in Epic D, or defer to Epic E?**
   - Recommended: **defer to Epic E** (safer, cheaper).
   - Alt: adopt **D4** (gated `comingSoon` inside Epic D).
2. **Q-1b (session length): stage the decision inside D3 now, or run it
   as a background question that closes when the human answers?**
   - Recommended: **run D3 as a docs-only sprint that OPENS the question**
     — if "keep 30", D3 closes as a `decisions.md` line; if "change to 10",
     D3 upgrades to a code sprint (one const + ADR-0023 amend). Either way
     D3 is "in flight" while D1/D2 ship.
3. **D1 posture: one sprint or three?** — recommended **one sprint** with
   three internally-independent commits (chip, end-session, timer). Same
   pattern as A1's D6+D1 single-sprint framing.

Once picked, the sibling sprint board (below) is authored to match; each
sprint then enters its own `sdd-spec` in release order.
