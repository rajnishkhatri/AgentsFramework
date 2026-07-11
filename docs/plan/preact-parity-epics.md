---
title: 'PreAct English Coach — Parity Release Program: Epics'
type: program
date: 2026-07-09
status: Draft
derives_from: docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
governs:
  - docs/plan/preact-parity-sprint-board-*.md   # one board per epic (authored when the epic is picked up)
method: SDD lifecycle (.claude/skills/sdd-lifecycle) — one full pass per sprint
---

# PreAct English Coach — Parity Release Program: **Epics**

**Purpose.** Close the prototype↔app parity gap catalogued in the
[canonical parity report](preact-ui-prototype-parity-VISUAL-gap-report.md) as a **staged
release program**, not one big push. This document is the **epic decomposition** — the top
of the pipeline. It groups the report's 12-item backlog into coherent **release units**,
each of which ships on its own.

```
Parity report  →  EPICS (this doc)  →  Sprint board  →  Sprints
  the WHAT gap       release units       ordered plan     one full SDD-lifecycle pass each
                     (ranked below)      (per-epic file)  (own .spec.md · own tests · own gate · mergeable)
```

## Program rules (how this runs)

1. **One epic in flight at a time.** We do not open Epic *N+1*'s sprint board until Epic
   *N* is **released** (all its sprints merged to `main`, gates green). The user gatekeeps
   the transition between epics.
2. **Ranked, trust-bugs first.** Release order follows the parity report's own
   *impact-per-effort* ranking, with the two 🟥 latent trust defects shipped first as a
   fast, low-risk opener. (See **Release order** below.)
3. **A sprint is the unit of SDD.** Each sprint runs the **complete** lifecycle
   (`sdd-lifecycle`): brainstorm → spec → plan/tasks → *(replan)* → implement →
   **code-review** → `make check` + `pytest tests/architecture/ -q` → converge/sign-off.
   It produces its own `docs/plan/<sprint>.spec.md` (EARS acceptance criteria) and an ADR
   **iff** an `⚠️ Ask first` trigger fires (root `AGENTS.md`).
4. **Every sprint is independently testable + releasable.** A sprint must be mergeable to
   `main` on its own: its acceptance criteria are verifiable in isolation, its tests pass
   without the rest of the epic, and shipping it alone leaves the app in a coherent state.
   If a candidate slice can't meet that bar, it's split further at sprint-board time — not
   folded into a bigger drop.
5. **The report is the source of truth for the WHAT.** Every epic's scope is expressed as a
   set of **finding IDs** from the parity report (e.g. `Q-6`, `S-2b`, `C-2…C-7`). No scope
   exists here that isn't traceable to a report finding. When a sprint is authored, its spec
   restates those findings as EARS FRs.
6. **The constitution stays on.** `AGENTS.md` (8 invariants + ✅/⚠️/🚫 boundaries) enforced
   by `tests/architecture/` is the constitution for **every** sprint — including the
   trivial-looking ones. The two new-route screens (Epics E & F) are **ADR-gated** (new
   routes + engine reads → `⚠️ Ask first`).

> **This doc does not schedule sprints.** It defines *what the epics are* and *in what order
> they release*. The sprint-by-sprint breakdown for an epic is authored in that epic's
> **sprint board** — the next artifact, produced only when the epic is picked up.

---

## Release order (ranked)

Six epics. Ordered by user-visible impact per unit effort, trust bugs first, unbuilt-screen
mega-work last (each of those carries its own ADR).

| # | Epic | Theme | Report findings | Sev band | Rough size | Gate notes |
|---|------|-------|-----------------|----------|-----------|-----------|
| **A** | **Trust-bug hardening** | Two labeled-but-broken controls | `Q-6`, `S-2b` | 🟥×2 | XS–S | pure fix; no ADR |
| **B** | **Coach surface build-out** | Make `/learn/coach` a real coaching workspace | `C-2…C-7`, `F-6`, `F-4` | 🟥/🟧 | L | backend-dependent stream; chrome buildable now. Likely ADR (coach VM/mode surface) |
| **C** | **Coaching-relationship surfaces** | Dashboard rail + Summary misconception payoff | `D-1`, `D-5`, `S-1`, `S-3`, `S-4b`, `S-5`, `S-6` | 🟧/🟨 | M | VM field additions; watch `use_dashboard` / summary VM |
| **D** | **Quiz session frame + taxonomy polish** | End-session, skill chip, timer, ACT labels, Skills nav | `Q-7`, `Q-8`, `Q-9`, `Q-1b`, `D-3b`, `D-8`, `X-4` | 🟨 | M | one product decision (session length 30 vs 10) |
| **E** | **Skill-detail screen** | Whole new `/learn/skill` route (spec §5.6) | `SD-1…SD-6`, `D-4` caveat | 🟧 | XL | **ADR-gated** — new route + `getTutorial` engine read |
| **F** | **Progress screen** | Whole new `/learn/progress` route (spec §5.7) | `P-1…P-5` | 🟧 | XL | **ADR-gated** — new route + `listProgressPoints` + trend chart |

**Why this order.** A ships value *today* and de-risks trust (a labeled control that lies is
worse than a missing one). B is the single largest *within-screen* gap and the flagship
parity increment. C restores the "coaching relationship" the whole loop exists to sell. D is
incremental polish that rounds out the core loop. E and F are the two **unbuilt screens** —
biggest, each its own ADR + engine amendment, so they land last when the surrounding surfaces
are stable.

---

## Epic A — Trust-bug hardening  🟥

> **Board authored** ([preact-parity-sprint-board-A.md](preact-parity-sprint-board-A.md)) — a
> code-seam scout **revised both findings**, folded in below: `Q-6` needs a spec-conflict
> *decision* before any code (not "just wire it"), and `S-2b` is **probably not a defect** (the
> elapsed-time wiring already exists + is unit-tested) → A2 is a **triage**, not a fix.

**Goal.** Eliminate controls that are *present but lie*. One is a **confirmed** dead control
(`Q-6`); the other (`S-2b`) is a **suspected** stat that needs triage before we know if there's a
bug at all. Small, low-risk opener.

**In scope (report findings):**

| ID | Finding | Fix shape (post-scout) |
|----|---------|-----------|
| `Q-6` | **`Reveal answer` is a dead placeholder** — `data-testid` + label, no `onClick`. **Confirmed dead.** | ⚠️ **Decision first:** code documents a **FR-D5 "never reveal" vs FR-D6 "Reveal sanctioned" contradiction**, and the VM omits the answer letter. Resolve which is authoritative → then *build it* (post-submit-gated reveal + a gated VM field) **or** *remove it*. Not a pure wire-up. |
| `S-2b` | **Summary "time" showed `0 min`** in the capture. **Downgraded to triage.** | Scout found elapsed time **already threaded + unit-tested** (`timeTile()` → real minutes; "—" unclosed). The walk opened+closed inside one minute → legit round-to-0. **Triage the observation** with a live multi-minute repro; fix *only if* a real bug surfaces (e.g. stale `use_summary` read). |

**Release criteria.** `Q-6`: Reveal works **only post-submit** or is removed, with a test proving
whichever + the FR-D5/FR-D6 contradiction resolved in `decisions.md`. `S-2b`: the "0 min"
observation is **explained via live repro** — closed as a capture artifact (+ a regression e2e
guard) **or** a real defect specced and fixed. `make check` + arch-tests green for both.

**Independence / releasability.** Fully standalone — touches Quiz + Summary VMs only, no
dependency on any other epic. A1 and A2 are independent of each other and ship as separate PRs.

**Sprint split (now decided — see board):** **A1** Resolve the Reveal control · **A2** Triage
Summary "0 min". Each independently testable + releasable.

**Gates.** No `⚠️ Ask first` trigger expected (no new node/service/dep/abstraction/trust type).
The FR-D5/FR-D6 resolution + the A2 triage outcome are `docs/adr/decisions.md` entries.

---

## Epic B — Coach surface build-out  🟥/🟧  *(flagship within-screen parity)*

> **Board authored** ([preact-parity-sprint-board-B.md](preact-parity-sprint-board-B.md)) —
> Stage-1 CLOSED ([brainstorm](preact-parity-epic-B.brainstorm.md)): **D1+D6** shared chrome ·
> **D5a** display-only 3→2 modes · **D2** Feedback bridge+recap · **D3** slip-capable stream ·
> chips = `onAsk` seeds · ladder **B0 → B1 → B2 → B3**. Scout revised `C-5`/`C-4`/`C-6` framing
> (folded in below).

**Goal.** Turn `/learn/coach` from a title+composer **empty shell** into the prototype's
**coaching workspace**: a context rail, an honest history trust line (real skill-scoped misses
or absent — never placeholder "N of M"), a **derived-mode display** (not a free switcher),
quick-reply chips, and the Feedback→Coach bridge on desktop.

**In scope (report findings):**

| ID | Finding | Fix shape (post-brainstorm) |
|----|---------|-----------|
| `C-2` | Context rail ("Your Coach / Adaptive · always on", status dot) | Shared chrome leaf (standalone + iPad panel) |
| `C-3` | Current-item context ("Current item: Q4 · Commas, non-essential") | Pin when present; honest absent otherwise |
| `C-4` | **"Sees your history: 3 of last 5 comma items missed"** | Real `AttemptRepo.misses()` aggregate **or honestly absent** — never placeholder |
| `C-5` | **COACH MODES** (prototype: 3 labels) | **D5a** — display-only map onto 2 marker-derived modes (`pre_submit` / `post_feedback`); no learner override (ADR-0012) |
| `C-6` | Seeded conversation / reply logic | Stream route **already exists**; B3 = `coach_context` + optional seed — **slip-capable** |
| `C-7` | Quick-reply chips ("Explain the rule simply", …) | Composer-fill / `onAsk` seeds only (no local canned coach) |
| `F-6` | **"Ask the coach"** on desktop Feedback | Consume existing `askCoachContext`; desktop action (today iPad-only) |
| `F-4` | Green-span sentence recap on Feedback | **FR-E1** gap — ships with F-6 in B2 |

**Release criteria.** `/learn/coach` (and iPad panel) render shared chrome for rail + history
line + mode display + chips; "Ask the coach" reaches the coach from desktop Feedback; green-span
recap on Feedback. The *context/seed depth* (`C-6` / B3) may be deferred — chrome + bridge ship
and are testable without it.

**Independence / releasability.** B0 docs, B1 chrome, and B2 Feedback bridge are each mergeable
alone (B1 before B2 preferred for current-item pin). B3 may slip without failing B1/B2.

**Sprint split (now decided — see board):** **B0** mode taxonomy + honesty docs · **B1** shared
coach chrome (`C-2…C-5`, `C-7`) · **B2** Feedback bridge + recap (`F-6`/`F-4`) · **B3** live
context (slip-capable). Each independently testable + releasable.

**Gates.** **Likely an ADR at B1** — coach surface VM (G1). D5a itself is `decisions.md` (no new
derived mode). History line is a **trust signal** → real or absent (AP-6). Confirm ADR at B1
spec time.

---

## Epic C — Coaching-relationship surfaces  🟧/🟨

**Goal.** Restore the two surfaces that make the app feel like a *coach who knows you*: the
Dashboard **right rail** (score-goal / streak / weekly sessions / coach note) + personalized
greeting, and the Summary **misconception payoff** (the emotional core of the loop) with its
misconception-framed title and richer recommended-next.

**In scope (report findings):**

| ID | Finding | Surface |
|----|---------|---------|
| `D-1` | Greeting "Let's get you to 28, Maya." + day/time | Dashboard header |
| `D-5` | **Right rail**: SCORE GOAL 26→28, 9-day streak, 3/3 weekly, coach note | Dashboard |
| `S-1` | Misconception-framed title ("Nice work — you found the pattern.") | Summary |
| `S-3` | **"The misconception I spotted"** accent narrative card | Summary |
| `S-4b` | Recommended-next names a *specific drill* (not bare skill) | Summary |
| `S-5` | Recommended skill name **tappable** (`summary-skill-link`) | Summary |
| `S-6` | **Three** summary actions (drill / full lesson / done) not one | Summary |

**Release criteria.** Dashboard renders the rail with real VM-backed values (streak, weekly,
score-goal, coach-note) + the greeting; Summary renders the misconception narrative + framed
title + a tappable, specific recommended drill + the three actions. Each value is real or
honestly absent (no placeholder numbers).

**Independence / releasability.** Splits cleanly along the screen boundary — Dashboard-rail
and Summary-misconception are independent releasable sprints. Note `S-5` (tappable skill) may
depend on Epic E's `/learn/skill` route for its *destination*; until E ships, it can link to
the drill (as the bucket card does) — an intentional interim.

**Likely sprint split:** `C1` Dashboard rail + greeting (`D-1`,`D-5`), `C2` Summary
misconception + title + actions (`S-1`,`S-3`,`S-4b`,`S-5`,`S-6`).

**Gates.** New VM fields on `use_dashboard` + summary VM — likely no ADR (no new
node/service), but the **misconception text source** is a real decision (engine-derived vs
templated) → `decisions.md` at minimum, ADR if it introduces a new derivation path.

---

## Epic D — Quiz session frame + taxonomy polish  🟨

> **Board authored** ([preact-parity-sprint-board-D.md](preact-parity-sprint-board-D.md)) —
> Stage-1 CLOSED-pending-human-gate ([brainstorm](preact-parity-epic-D.brainstorm.md)):
> five premises refuted (Q-7 view-only, Q-9 "dismissible", Q-1b as code, D-8 as free
> add, X-4 as separate); ladder **D0 → { D1, D2, D3 }** (parallel-independent) with **D4**
> optional. `X-4` merged into `D-3b`. `D-8` **defaulted to defer** to Epic E's board
> (dead-nav trust risk = Q-6 class).

**Goal.** Round out the core loop's *session framing* — the affordances that wrap the quiz —
and align the bucket taxonomy to ACT-standard labels. Individually minor; together they close
the last visible deltas on the two most-used screens.

**In scope (report findings):**

| ID | Finding | Surface |
|----|---------|---------|
| `Q-7` | Skill chip on the session frame ("● Punctuation") — **wire→VM→view** seam: join `Skill.name` / `Skill.accent_var` at the hook + translator boundary onto the Quiz VM (`skillName` / `accentVar`); not a view-only chip render | Quiz |
| `Q-8` | **"✕ End session"** (abandon → Dashboard) | Quiz |
| `Q-9` | **Collapsible / off-by-default** timer (starts collapsed; reveals `elapsed_ms` when expanded). Capture is already correct ([`session_summary_vm.ts:60-65`](../../frontend/lib/translators/session_summary_vm.ts:60) / A2 triage) — Q-9 is the UI affordance, not the plumbing | Quiz |
| `Q-1b` | Session length **30 vs 10** — **decision-first sprint (D3)** recorded via [`decisions.md`](../adr/decisions.md); upgrades to code + ADR-0023 amend iff the decision changes `DEFAULT_TARGET_COUNT` (not a code sprint by default) | Quiz |
| `D-3b` | Bucket **names** → ACT-standard labels + per-bucket color dot | Dashboard |
| `D-8` | **"Skills" nav** — `screen("skill", …, comingSoon: true)` already exists at [`nav_model.ts:75`](../../frontend/components/shell/nav_model.ts:75) but is excluded from `NAV_MEMBERSHIP`; `/learn/skill` **404s today** (Epic E). Adding to membership before E lands = dead nav item (Q-6 class). **Default = defer to Epic E**; alternate = D4 `comingSoon`-gated add | Nav |
| `X-4` | Bucket taxonomy mismatch (app 6 ≠ prototype 6 by name) — **absorbed into D2** (cross-cut duplicate of `D-3b`; not a separate sprint) | Cross-cutting |

**Release criteria.** Quiz shows the skill chip + End-session + a dismissible timer; bucket
labels/dots match the ACT-standard taxonomy; a "Skills" nav entry exists. `Q-1b` resolved as
a *documented product decision* (may be "keep 30" — recorded in `decisions.md`, not
necessarily a code change).

**Independence / releasability.** Session-frame (`Q-7`/`Q-8`/`Q-9`) and taxonomy
(`D-3b`/`D-8`/`X-4`) are two independent sprints. The timer reuses the already-recorded
`elapsed_ms` — pairs conceptually with Epic A's `S-2b` time-plumbing but is separable.

**Likely sprint split:** `D1` Quiz session frame, `D2` taxonomy + Skills nav, plus a
lightweight `D0` decision note for `Q-1b`.

**Gates.** No ADR expected. `D-8`'s "Skills" nav entry should *not* be enabled until Epic E's
route exists — ship it as `comingSoon` or omit until E lands (avoid a second dead nav item —
the very class of bug Epic A fixes).

---

## Epic E — Skill-detail screen  🟧  ⛔ *app unbuilt · ADR-gated*

**Goal.** Build the per-skill mini-lesson screen (spec §5.6) that today **404s** — the first
of the two unbuilt screens. Gives bucket cards and the Summary "See full lesson" action a real
destination.

**In scope (report findings):**

| ID | Finding |
|----|---------|
| `SD-1` | Header: bucket dot + name + "~19% of ACT English" + "Drill this skill" |
| `SD-2` | "The rule, in one line" + worked examples |
| `SD-3` | "Why you missed these" (auto-built from the learner's misses) |
| `SD-4` | Accuracy bar chart (last 6 sessions) |
| `SD-5` | "Due for review" (FSRS due-count per skill) |
| `SD-6` | Entry points wired: bucket card → here; Summary "See full lesson" → here; "Drill this skill" → Quiz |
| `D-4` (caveat) | resolve the `?focus=` "does not pin scheduler" gap if it blocks the drill entry |

**Release criteria.** `/learn/skill` route exists and renders SD-1…SD-5 from a real
`getTutorial` engine read; the three entry points (`SD-6`) route correctly; no 404. Miss-history
and per-skill session history are real or honestly empty.

**Independence / releasability.** Standalone route — ships without touching the core loop.
**Depends on** engine reads that may not exist yet (`getTutorial`, per-skill miss/session
history) → those become explicit sprint prerequisites. Enables Epic C's `S-5` and Epic D's
`D-8` to point at a real screen once landed.

**Likely sprint split:** `E0` engine reads (`getTutorial` + miss/history aggregation),
`E1` route + static lesson (SD-1/SD-2), `E2` personalized panels (SD-3/SD-4/SD-5),
`E3` entry-point wiring (SD-6). `E0` is a backend seam; the rest are Frontend Ring.

**Gates.** **ADR required** — new route is a new surface, and the engine reads are new data
paths (`⚠️ Ask first`: new abstraction / potentially new service read). Copy
`docs/adr/0000-template.md`; record the rejected alternatives (e.g. templated-lesson vs
engine-derived).

---

## Epic F — Progress screen  🟧  ⛔ *app unbuilt · ADR-gated*

**Goal.** Build the long-term analytics screen (spec §5.7) that today **404s** and whose nav
item is a disabled placeholder — the second unbuilt screen and the program's final increment.

**In scope (report findings):**

| ID | Finding |
|----|---------|
| `P-1` | Header "Your progress · 147 items reviewed · 9-day streak" |
| `P-2` | **Range tabs** (30 days / All time) that switch the trend |
| `P-3` | **Projected-score trend** (line chart, goal-28 guide line) |
| `P-4` | **Mastery-by-bucket bars** (all 6, per-bucket color, Due flag) |
| `P-5` | Enable the currently-disabled Progress nav item (make it lead somewhere) |

**Release criteria.** `/learn/progress` route exists and renders P-1…P-4 from a real
`listProgressPoints` engine read (plan D1) with a working range toggle + trend chart; the
Progress nav item is enabled and routes here (closing `P-5`). No 404.

**Independence / releasability.** Standalone route. **Depends on** `listProgressPoints` +
a score-projection series (may not exist) → explicit sprint prerequisites. Enabling the nav
item (`P-5`) must land **with** the route, never before (else it's another dead control).

**Likely sprint split:** `F0` engine reads (`listProgressPoints` + score-projection series),
`F1` route + mastery bars (P-1/P-4), `F2` trend chart + range tabs (P-2/P-3), `F3` enable nav
(P-5, ships last in the epic).

**Gates.** **ADR required** — new route + new engine read + a projection series
(`⚠️ Ask first`). Same template + rejected-alternatives discipline as Epic E.

---

## Traceability — every backlog item is in exactly one epic

Confirms the decomposition is a **partition** of the report's 12-item backlog (no item
dropped, none double-counted). Backlog ranks from parity report §11.

| Backlog # (report §11) | Item | Epic |
|---|---|---|
| 1 | Fix `Reveal answer` dead button | **A** |
| 2 | Fix Summary "0 min" | **A** |
| 3 | Coach screen build-out | **B** |
| 4 | Dashboard right rail + greeting | **C** |
| 5 | Summary misconception write-up + title | **C** |
| 6 | Feedback "Ask the coach" desktop + green-span recap | **B** |
| 7 | Quiz session frame (End-session, skill chip, timer) | **D** |
| 8 | Bucket taxonomy + color dots + Skills nav | **D** |
| 9 | Tappable recommended skill + 3 summary actions | **C** |
| 10 | Session length review (30 vs 10) | **D** |
| 11 | Skill-detail screen (whole route) | **E** |
| 12 | Progress screen (whole route) | **F** |

**Coverage:** 12/12 backlog items assigned; 6 epics; ranked A→F. Epics B and C each absorb one
Feedback/Summary item that pairs with their theme (backlog #6→B, #9→C) rather than sitting in a
thin "polish" bucket — keeping every epic a coherent release unit.

---

## What happens next (not part of this doc)

1. **You gatekeep + pick the first epic** (default per ranking: **Epic A**).
2. I author that epic's **sprint board** — `docs/plan/preact-parity-sprint-board-<epic>.md` —
   breaking it into the independently-releasable sprints sketched above, each with its entry
   in the board and its own forthcoming `.spec.md`.
3. **Sprint 1 of that epic** then enters the SDD lifecycle: `sdd-brainstorm` (if the approach
   is open) → `sdd-spec` (EARS `.spec.md`) → implement → **code-review** → `make check` +
   arch-tests → `sdd-converge`. You gatekeep each stage transition.
4. On release of the epic's last sprint, we return here and open the next epic.
