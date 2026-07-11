---
title: 'PreAct Parity — Epic C: Coaching-relationship surfaces (BRAINSTORM · SDD Stage 1)'
type: brainstorm
date: 2026-07-10
status: Draft
stage: SDD Stage 1 (sdd-brainstorm)
derives_from:
  - docs/plan/preact-parity-epics.md            # Epic C row
  - docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md  # findings D-1, D-5, S-1, S-3, S-4b, S-5, S-6
spec_source_of_truth:
  - Eng-coach-ui-design/PreACT-English-Coach-Spec.md   # §5.1 Dashboard, §5.5 Summary, §7 sample-data supplement
awaits: Stage-1 direction gate (human picks lead + sprint split)
---

# Epic C — Coaching-relationship surfaces · **BRAINSTORM**

**Framing (from epics doc §Epic C).** Restore the two surfaces that make the
app feel like a *coach who knows you*:

- **Dashboard**: right rail (score goal, streak, weekly sessions, coach note)
  + personalized greeting.
- **Summary**: misconception payoff (framed title + accent narrative card) +
  richer recommended-next (tappable skill link + three actions).

Findings: **D-1**, **D-5**, **S-1**, **S-3**, **S-4b**, **S-5**, **S-6**.

Sub-agent may deliver a scout revision after this doc; the human gate below
locks the lead direction before spec.

---

## 0. Premise audit — before ideating (mandatory)

The Stage-1 runbook makes this step blocking. Every load-bearing premise in
Epic C's framing checked against the working tree today.

| # | Premise (as stated in epics.md §Epic C) | Verdict | Evidence |
|---|-----------------------------------------|---------|----------|
| P1 | `S-5` — "tappable skill link" is currently missing | **REFUTED — already shipped** | [SummaryView.tsx:69-75](../../frontend/components/summary/SummaryView.tsx:69) renders `summary-skill-link` as a `<Link href="?focus=…">` under the recommended-next card. |
| P2 | `S-4b` — recommended-next names a bare skill, not a specific drill | **VERIFIED** | Same view line 74 uses `summary.recommended.skillName` from [session_summary_vm.ts](../../frontend/lib/translators/session_summary_vm.ts). No "6-item drill: …" phrasing anywhere in the VM. |
| P3 | `S-6` — only 1 action ("Practice this next"); no "See full lesson" / "Done for today" | **VERIFIED** | Only one CTA in [SummaryView.tsx:77-88](../../frontend/components/summary/SummaryView.tsx:77). |
| P4 | `S-1` — Summary title is "Session summary / Here's how this session went." | **VERIFIED** | [SummaryView.tsx:45-47](../../frontend/components/summary/SummaryView.tsx:45). |
| P5 | `S-3` — no misconception narrative card | **VERIFIED** | No `misconception` field on `SessionSummaryVM`; [session_summary_vm.ts:12](../../frontend/lib/translators/session_summary_vm.ts:12) notes "The misconception write-up itself (FR-G3) is generated content shown in the coach card; it is passed through by the hook, not synthesized here." **Dangling contract** — VM never carries it, hook never passes it. |
| P6 | `D-1` — Dashboard has no greeting / date | **VERIFIED** | [DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx) renders `TodayFocusBanner` → `Skill mastery` → secondary actions. No `<header>` with a greeting. |
| P7 | `D-5` — Dashboard has no right rail (score-goal / streak / weekly / coach-note) | **VERIFIED** | Same file; no rail region. `DashboardVM` has three fields: `buckets`, `todayFocus`, `reviewMissesCount` ([use_dashboard.ts:32-39](../../frontend/components/dashboard/use_dashboard.ts:32)). None of streak/weekly/goal/note. |
| P8 | Streak, weekly-sessions, coach-note are **derivable from existing engine reads** | **REFUTED — engine gap** | `SessionRepo` exposes `open`/`close`/`get` **only** ([session_repo.ts](../../frontend/lib/ports/engine/session_repo.ts:44-56)). No `listByLearner` / `listRecent`. Streak-of-consecutive-days + "3/3 sessions this week" **cannot be computed from the current ports** without either a new read method or a new repo. |
| P9 | Score-goal ("26 → 28") is derivable from `SkillState.mastery` | **UNVERIFIABLE without product decision** | `SkillState.mastery` exists per skill (0..1, [engine_entities.ts:255](../../frontend/lib/wire/engine_entities.ts:255)). A single learner-level scalar with a **goal** does not — no `projected_score`, no `goal_score` field on any learner-level entity. `projected_score` exists only on the (unused) `Attempt.projected_score` row ([engine_entities.ts:286](../../frontend/lib/wire/engine_entities.ts:286)) — that is per-attempt after-effect, not a persistent learner score. Spec §7 wants the flavor "26 → 28"; the engine has no learner projection to derive from. Needs a product decision (see D3). |
| P10 | Misconception text has a real source in the engine or corpus | **REFUTED — source not identified** | The word `misconception` in code appears only as (a) a **coach-mode display label** ([coach_surface_vm.ts:74](../../frontend/lib/translators/coach_surface_vm.ts:74)) and (b) an aspirational comment in the summary VM. The spec §7 example ("learner lets *conciseness* override *punctuation*") is prose, not a `hints.j2` rung field or a `Question`/`Attempt` column. **There is no engine channel that carries it today.** |
| P11 | Coach-note text has a real source | **REFUTED — same shape as P10** | No `coach_note` / `note` on any port; nowhere in `frontend/lib/wire/`. If the rail shows one, we would have to synthesize it (banned by C-4 honesty rule from Epic B) or add a source. |
| P12 | `S-5` "tappable skill" destination is `/learn/skill` (which is `comingSoon`) | **PARTIAL** | Currently links to `?focus=<skillId>` (drill-start) — [SummaryView.tsx:40](../../frontend/components/summary/SummaryView.tsx:40) — because `screen("skill").comingSoon = true` ([nav_model.ts:75](../../frontend/components/shell/nav_model.ts:75)). The comment in `SummaryView` calls this out. Interim is honest; permanent destination waits on Epic E. |

### Corrected framing (re-posed for the human)

Epic C, as written, is **not one homogeneous "restore trust" job**. The audit
splits it cleanly into three **class-different tracks**:

- **C-α ("pure wire-up") — S-4b, S-6, and the S-1 framed-title copy change.**
  Everything the VM/View needs is either already in the summary VM or a pure
  copy/branching decision. Zero engine seams; smallest ADR footprint.
  *S-5 is already shipped* — remove it from the epic and note it (Epic B/D
  polish, whichever ships first, can re-verify).

- **C-β ("engine gap — trust signals") — D-5 rail + D-1 greeting.**
  Needs **new engine reads**: at minimum, a way to list a learner's recent
  sessions (streak + weekly), plus a product decision on the score-goal source
  and the coach-note source. Under Epic B's C-4 rule ("real or absent, never
  placeholder"), a rail with fake numbers is worse than no rail.

- **C-γ ("engine gap — misconception source") — S-3 narrative card + S-1
  framed title body.** Has no source-of-truth today. Choosing where the text
  comes from is an ⚠️-Ask-first decision (new derivation path or new field on
  Question/Attempt); the ADR is nontrivial. Small-looking, big consequences.

Each track has a **different** ADR footprint, a **different** risk profile,
and a **different** dependency on Epics B, D, E. Bundling them as "Epic C"
guarantees one of the three drags the other two.

---

## 1. Nested `AGENTS.md` sweep (what the ADR/invariant floor looks like)

- **Root [AGENTS.md](../../AGENTS.md).** Invariants 1–8; ⚠️ Ask-first list
  covers *new abstraction*, *new horizontal service*, and any deviation from
  an invariant → **any new engine port method needs an ADR** (Ask-first #6:
  new service; §G1 new-abstraction gate).
- **[frontend/AGENTS.md](../../frontend/AGENTS.md).** F-R1 (no domain logic in
  components), F-R2 (SDK only in adapters), F-R8 (no SDK type past adapter),
  F-R9 (BFF holds no cloud creds). Rail state must resolve through the
  Frontend Ring **engine ports**, not through a new BFF or middleware path.
- **`frontend/lib/AGENTS.md`** (implied by the style guide's [§4/§5](../style-guides/STYLE_GUIDE_FRONTEND.md)):
  P1 (one interface per port module), P2 (vendor-neutral names), P3
  (behavioral contract in JSDoc), P7 (conformance test with the new adapter).
- **`docs/adr/GATES.md`** (root AGENTS.md ADR.1). Any new derived channel
  (misconception, coach-note) is a G1 gate — must document rejected
  alternatives. C-γ **cannot** land without an ADR.
- **`components/summary/`, `components/dashboard/`** — presentational, both
  already `"use client"` and both consume a translator VM. Additive VM fields
  are the safe extension pattern.

---

## 2. D0 — is there a live, blocking defect that outranks new capability?

**Yes.** From the Epic A+B post-merge review, three defects are shipped on
`main` today:

- **FLAG-4** (Back → Q1 on quiz) and **FLAG-5** (Wrap-up strips `?session=`
  → "No session to summarize.") both **touch Summary directly**.
- **FLAG-6** (Mastery tile signed delta easy to misread as absolute).

Trust-relationship epic that ships new Summary chrome **on top of** a broken
Summary landing path (FLAG-5) is a regression multiplier: the misconception
card lands, but half the time the learner never sees it because they arrive
at the empty-`?session=` error page.

**D0 recommendation.** Fold FLAG-5 (wire the `?session=` param through
Wrap-up) into Epic C's opening PR — *before* the trust chrome. It is
one-line in `learn/coach/page.tsx onWrapUp` + a one-line E2E flip. Cheaper as
a leading fix than as a follow-up sprint. FLAG-4 and FLAG-6 stay outside
Epic C (own follow-ups).

---

## 3. Six directions (three high-probability + three exploratory)

Each direction says: **what it delivers**, **what it costs**, **the
Architecture Invariant it stresses**, and **what breaks if we pick it**.
Where a direction needs data that must accumulate first, it is tagged
`needs-probe`.

### D1 · **"Ship what's cheap; defer what needs a source"** *(high-probability, follows the Epic A+B pattern)*

**Scope.** C-α only.
- **S-4b:** Add `drillTitle` to `RecommendedNextVM`
  (e.g. "6-item drill: {skillName}") — deterministic from the `target_count`
  (already on `QuizSession`) + skill name. Pure translator change.
- **S-6:** Add the three actions to `SummaryView`. "Start recommended drill"
  = the current CTA renamed. "See full lesson" = link to
  `screen("skill").route` **only if not `comingSoon`**; else render disabled
  (same pattern nav uses today, FR-B5). "Done for today" = link to
  `screen("dashboard").route`.
- **S-1 (framed title copy):** flip the header to
  "Nice work — you found the pattern." *only when session score ≥ threshold*
  (deterministic: correct/total ≥ 0.6, spec §5.5). Below threshold → today's
  neutral copy. No misconception body — deferred to D5/D6.
- **D0 fold-in:** wire `?session=` through Wrap-up (FLAG-5).

Follows the pattern of: [Epic A1's Reveal wire-up](preact-parity-sprint-board-A.md) — pure VM/View
extension, no new ports.

- **Cost.** XS. One translator file, one view file, one page-nav wire fix.
  No engine seams. `make check` + arch + 2–3 new e2e specs.
- **ADR?** No (G1 doesn't fire — no new abstraction). `decisions.md` entry
  for the threshold + the "See full lesson while comingSoon" rendering rule.
- **Invariant stressed.** F-R1 (view stays presentational) — trivial. FR-B5
  (no dead controls) — actively upheld: disabled render when `comingSoon`.
- **What breaks if picked.** Rail (D-5) and greeting (D-1) still absent —
  visible parity gap remains. Misconception (S-3) still absent — the
  "emotional core" of the loop stays out.

### D2 · **"Rail with real numbers or none — build the missing engine read"** *(high-probability, extends existing ports)*

**Scope.** C-β only: D-1 greeting + D-5 rail, honestly.

- **New engine read:** `SessionRepo.listByLearner(subject, learnerId, {sinceISO}): Promise<QuizSession[]>` — closed sessions newest-first. Backed
  by a Drizzle query on `quiz_session` (rows exist; only the port surface is
  missing). Adds one row to the port conformance test.
- **Derivations (all pure translators):**
  - **Streak** = count-consecutive-days with ≥1 *closed* session ending in a
    "today" bucket (injected clock). Absent any closed sessions → "start a
    streak" (honest empty state, no fake number).
  - **Weekly sessions** = count of closed sessions in [Mon-of-this-week ..
    now]. Same clock injection.
  - **Score-goal**: **defer** the "26 → 28" phrasing (needs a projected-score
    channel; see D3). Render the goal tile as a **coach-note-style empty
    state** in this direction until the projection lands ("Set a score goal
    with your coach") **or** hide the goal region entirely — decision at spec
    time.
- **Greeting (D-1):** date/time from the injected clock (F-R7 free — this
  isn't `trace_id` territory). Learner name — `LEARNER_ID = "maya"` is the
  Phase-1 single-learner surface (see `use_dashboard.ts:23`); the greeting
  is "Good afternoon, Maya" with the raw id title-cased. When multi-learner
  lands, this becomes a real display-name lookup.
- **Coach-note (D-5 last tile):** **omit** in this direction; reintroduce
  in D5/D6 when the source is chosen.

Follows the pattern of: `use_dashboard.ts`'s existing three concurrent reads
+ pure-translator VMs.

- **Cost.** S. One new port method, one adapter method, one conformance-test
  row, three translators (`streak`, `weeklySessions`, `greeting`), rail view
  region, rail e2e.
- **ADR?** **Yes — G1 fires** (new engine read). Rejected alternatives to
  document: (a) synthesize streak on the client from an in-memory session
  cache; (b) put it on a separate `LearnerStatsRepo` port; (c) leave the
  rail out until Epic F (Progress) ships. Ratchet rule: cite the failure
  that justifies the new port (Epic C's C-4 honesty rule = no placeholder).
- **Invariant stressed.** #7 (services must not import from components) —
  passes; the new port sits under `lib/ports/engine/`. F-R3 (one interface
  per module) — passes; we're adding a method to an existing port, not a
  new port.
- **What breaks if picked.** Score-goal tile is temporarily absent or
  bland; misconception (S-3) still absent. Rail feels 60% built rather than
  100% built — but every visible number is real.

### D3 · **"Learner-level derived signals — introduce `LearnerStats` port"** *(exploratory: horizontal service)*

**Scope.** C-β + a durable data plane for future signals (projection,
streak, mastery-by-bucket for Epic F's D-5-adjacent Progress screen).

- **New horizontal port:** `LearnerStatsRepo` — one file:
  - `streak(subject, learnerId, nowISO)`
  - `weeklySessions(subject, learnerId, nowISO)`
  - `projectedScore(subject, learnerId)` — deterministic function of
    `SkillState.mastery` across all six buckets (weighted by bucket share of
    ACT English, already known in `Skill`). Returns `{ projected, goal? }`.
- **Score-goal:** derived, not stored. Goal defaults to `projected + 2`
  (spec §7 shows "26 → 28"). Overridable later by a learner-preference
  entity (deferred).
- **Coach-note:** placeholder — still absent in this direction; a
  companion ADR can decide (D6).
- Everything else in D2 stays; the rail translator moves to consume this
  new port.

Follows the pattern of: `focus_pick.ts` — a deterministic pure derivation
promoted to a named port when a second consumer arrives (Epic F). Applies
the constitution's abstraction-introduction principle: **don't** create
`LearnerStatsRepo` until the second consumer is real.

- **Cost.** M. New port + adapter + conformance test + arch-test entry +
  ADR. Meaningfully bigger than D2.
- **ADR?** **Yes — G1 + Ask-first #6** (new horizontal service). Rejected
  alternatives: (a) add methods to `SessionRepo` (D2) — rejected here on
  cohesion grounds (session lifecycle ≠ learner stats); (b) put the
  projection in the translator layer — rejected on testability (projection
  is future-facing behavior worth a port).
- **Invariant stressed.** #1 (dependency direction) + #4 (services
  framework-agnostic) — both preserved. But abstraction-introduction (§G1)
  wants **two consumers** before we build the port; today only Dashboard
  needs it. Epic F is the second, but Epic F is ADR-gated and unshipped.
- **What breaks if picked.** Sprint is bigger than the visible parity gain
  suggests; risks pulling forward Epic F's design decisions before Epic F's
  human gate. **This is the "class over instance" fix** for the coming
  Epic F work if we want to pay the tax now.

### D4 · **"Misconception is a Question-level field, filled by content"** *(high-probability, extends existing corpus contract)*

**Scope.** C-γ: land S-3 (misconception narrative) via the content pipeline.

- **New field on `Question`:** `misconception?: string` — a one-line rule
  phrasing captured by the item author (e.g. "learner lets *conciseness*
  override *punctuation*"). Nullable. Backed by the item-bank schema.
- **Summary derivation:** for a completed session, the misconception card
  reads the misconception phrase from **the most-recently-missed item on
  the session's focus skill** (or is honestly absent when the learner
  missed nothing). Pure translator — no new port.
- **Framed title body (S-1):** "Nice work — you found the pattern" only
  when the learner *self-corrected* the misconception (spec §7). Signal =
  same skill-scoped miss present in the first half of the session and
  absent in the second half. Deterministic; matches the spec's "worked
  through Q7 and got Q9/Q10 right".

Follows the pattern of: how `hints.j2` rungs are content-authored per item.
Reuses the item-bank cascade (`docs/plan/coach-item-bank-live-adr0021`).

- **Cost.** M. Item-bank schema change (nullable field is safe), content
  authoring pass on the existing corpus, translator + view + e2e.
- **ADR?** **Yes — G1 fires** (new derivation path *and* new corpus
  contract). Rejected alternatives: (a) LLM-synthesize misconception from
  misses (rejected: C-4 honesty rule + this synthesis is exactly what the
  Coach card should say later, not what the Summary claims after 5 items);
  (b) attach misconception to `Skill` (rejected: misconception is
  *item-specific*, per prototype's "conciseness overrode punctuation" —
  skill-level would blur it back to the skill name); (c) attach to
  `Attempt` at grade time (rejected: post-hoc, no author signal).
- **Invariant stressed.** #2 (trust kernel unchanged — misconception is
  not a signed field). AGENTS.md ⚠️ Ask-first (new abstraction).
- **What breaks if picked.** The corpus needs a content pass to *carry*
  values before the card lights up on real items. Until that pass ships,
  the card is "absent" for most items (honest-absent, aligned with C-4).
  `gated-on-data: <missing-misconception-count>` — the initial `needs-probe`
  is "how many bank items have a plausible misconception phrase" (measure
  before spec is red).

### D5 · **"Misconception is a runtime signal from the Coach"** *(exploratory: reuse under-used signal)*

**Scope.** C-γ, but derived, not authored. Uses the **under-used signal
lens**: the Coach already runs and (per Epic B) has a `coach_context` with
`misses_aggregate`. Its response is text the learner just read. Reuse it.

- **New store:** `coach_thread_store` already tracks per-thread turns
  (Epic B). Add a **structured "misconception marker"** the Coach emits
  when appropriate (a new AG-UI-style event or a simple `<misconception>…
  </misconception>` inline tag the frontend parses out). Summary reads
  the *last* marker from the session's coach thread.
- **Absent case (no coach turn ever happened this session)** → the card
  is honestly absent, same as D4.
- Framed-title rule = same as D4.

Follows the pattern of: `coach_context` piggybacking on the composer's
open input dict (ADR-0012); this piggybacks on the response side.

- **Cost.** M–L. Coach-side prompt change + response parser + a probe on
  how often the Coach actually emits one on real sessions (`needs-probe`
  before we can promise this is worth shipping).
- **ADR?** **Yes** — a new derived channel at the Coach boundary. Bigger
  ADR than D4 (touches prompts + response protocol + a new persistence
  contract for the marker).
- **Invariant stressed.** #6 (orchestration nodes stay thin) — the marker
  has to be an existing-node emission, not a new node. Coach prompt
  authoring is R-5 territory (`prompts/` is the boundary — good).
- **What breaks if picked.** Adoption gap — the card only lights up for
  learners who used the Coach, which is a smaller subset than "everyone".
  For a "trust-relationship" epic this may actually be **desirable** (only
  claim to have "spotted a misconception" when the Coach actually did).
  `needs-probe` on real coverage before committing.

### D6 · **"Bundle-and-ADR — solve C-α, C-β, C-γ together with one big ADR + one sprint"** *(exploratory: class-level release)*

**Scope.** Everything: rail, greeting, misconception, framed title,
recommended-next drill title, three actions, S-5 (already shipped,
re-verified).

- One ADR that names all three tracks, the misconception source (D4 by
  default, D5 rejected with reason), the streak/weekly derivation (D2's
  extend-`SessionRepo`), and the score-goal source (D3's
  `projectedScore`, gated on a probe that shows the value stays realistic
  across 6 buckets).
- Sprint is one PR: rail + greeting + summary payoff + wire FLAG-5.

Follows the pattern of: **rejected** by the epics doc's own rule 4 ("every
sprint independently releasable") — so this is an exploratory foil, not a
recommendation. Included per the "class-over-instance" lens the runbook
requires — sometimes bundling is the correct answer, and we should say
why it isn't here.

- **Cost.** L. Any single failure blocks the whole PR.
- **ADR?** One big ADR. Higher blast radius on rejection.
- **Invariant stressed.** Rule 4 of the epic program (independent
  releasability) — **violated**. That is why this direction is dominated
  by D1+D2+D4 as three sequential sprints.
- **What breaks if picked.** Epic C stops shipping incrementally, which
  is the whole point of the epic decomposition. Reject unless spec time
  discovers a coupling that forces bundling.

---

## 4. Dependency structure

```
                      C-α  ── D1 ─────────────────────►  ships anywhere
                                                        (mergeable alone)
                                    ┌──── D2 (extend SessionRepo)
      C-β  ── needs new engine read ┤
                                    └──── D3 (new LearnerStatsRepo)
                                          (ADR gate — larger)

                                    ┌──── D4 (Question.misconception field)
      C-γ  ── needs a source ───────┤
                                    └──── D5 (Coach marker) — needs-probe

              D6 (bundled) — dominated by D1+D2+D4 unless coupling forces it
```

- **Do-regardless (all directions):** D0 FLAG-5 fix goes with the first PR
  that touches Summary. Zero-cost, closes a real trust regression.
- **Pick-the-priority:** the sequence D1 → D2 → D4 covers all seven
  findings with **three independently releasable** sprints and **two ADRs**
  (D2, D4). D3 is a future consolidation, not an Epic C sprint.
- **Deferred behind X:** score-goal "26 → 28" and coach-note copy both
  stay out of D2 unless a source is decided in the ADR.

**Cost axes.** Engineering time on D1 is XS (hours). D2 is S (a day of
port + arch-test + e2e). D4 is M but its **calendar-time** load-bearing
cost is the corpus pass — code lands quickly; wide coverage waits on
content. **Say it out loud so the picker knows.**

---

## 5. Leading direction + hypotheses

**Lead: D1 → D2 → D4, in that order, three sprints, two ADRs.**

The lead is a *composition* because the audit shows Epic C is not one job.
Picking D1 as the opener respects the epics doc's ranking (impact per
effort) and de-risks the trust bar (S-6, S-4b, FLAG-5 wire-up) before the
port work.

### Load-bearing hypotheses (each with a repo-evidence check)

| # | Hypothesis | Validation | Verdict |
|---|-----------|------------|---------|
| H1 | Adding `drillTitle` to `RecommendedNextVM` is pure — no schema change | [session_summary_vm.ts:22-38](../../frontend/lib/translators/session_summary_vm.ts:22) + `QuizSession.target_count` on wire ([engine_entities.ts:213](../../frontend/lib/wire/engine_entities.ts:213)) already carries the count. Pure translator addition. | ✅ verified |
| H2 | The Summary "3 actions" pattern has a working precedent to copy | [DashboardView.tsx:42-64](../../frontend/components/dashboard/DashboardView.tsx:42) already renders three CTAs in a secondary-actions row — style + a11y already worked out. | ✅ verified |
| H3 | FLAG-5 fix is one line in `learn/coach/page.tsx` `onWrapUp` | [coach/page.tsx:101-104](../../frontend/app/(coach)/learn/coach/page.tsx:101). Change `router.push(screen("summary").route)` to append `?session=${activeSessionId}` iff known. `activeSessionId` currently absent from the coach page — need to thread it through the coach_thread_store (Epic B's persistence layer) OR pass the current quiz session id via a URL param when the Feedback→coach bridge fires. **Not a one-liner** — revise cost to XS-S. | ⚠️ REVISED |
| H4 | `SessionRepo` can grow a `listByLearner` method inside its existing port without breaking the P1 rule | [session_repo.ts:44-56](../../frontend/lib/ports/engine/session_repo.ts:44). Same interface, one more method. Conformance test needs a new row. | ✅ verified |
| H5 | Streak can be derived from closed sessions alone (no clock skew across sessions) | Every `QuizSession` carries `ended_at: z.string().nullable()` ([engine_entities.ts:206](../../frontend/lib/wire/engine_entities.ts:206)). Bucketing by ISO local-date + counting consecutive → deterministic given an injected clock. | ✅ verified |
| H6 | The prototype's "3/3 sessions this week" means **≥1 completed session per day, capped 3** OR **3 sessions any distribution** | Spec §5.1 says "3/3 weekly sessions (7-dot week strip)" — 7 dots imply per-day. Spec §7 says "3/3 sessions this week". **Ambiguous.** Spec time needs to pick. | ❌ **needs-probe** — spec-clarify item |
| H7 | Misconception carrying via `Question.misconception` doesn't collide with the item-bank cascade | [coach-item-bank-live-adr0021.md](../../frontend/lib/wire/engine_entities.ts:101) shows generated items already carry `generated_by`; adding a nullable string is additive. | ✅ verified |
| H8 | Framed-title "self-corrected" signal is derivable from the session's attempts on the focus skill | `AttemptRepo` lists misses newest-first ([attempt_repo.ts:39-40](../../frontend/lib/ports/engine/attempt_repo.ts:39)); ordering + timestamps yield the "first-half miss / second-half hit" pattern. Deterministic. | ✅ verified |
| H9 | Coach-note has *no* honest source today; not deriving one, not synthesizing one | Grep for `coach_note` / `note` in `lib/` returns zero. Spec §7 has a sample string; no producer. | ✅ verified — **omit until a source is decided** |

**Works because.** The three tracks map to three distinct engineering
shapes (pure VM, extend-existing-port, add-authored-field). Each has a
precedent already in the repo. None of them needs a new trust type, a new
graph node, or a new BFF/middleware channel.

**Safe because.** (a) The C-4 honesty rule already established in Epic B
gets applied to every new tile (no fake numbers, no synthesized
misconception, no fabricated coach note). (b) Every direction that
introduces a new engine read is ADR-gated — no silent capability drift.
(c) D0 fold-in (FLAG-5) means the very first PR closes a real regression
before adding chrome.

---

## 6. What this brainstorm is *not* deciding

Explicitly out of scope for this Stage-1 gate (per the runbook: **direction
only**, not the spec itself):

- Exact wording of the framed title / three-actions labels.
- Sprint numbering (`C1`, `C2`, `C3` will be authored on the sprint board
  after the human picks a direction).
- Item-bank content-pass scheduling for D4 (a downstream program
  question).
- Whether Skill detail (Epic E) lands before we redirect S-5's tappable
  link to `/learn/skill` — it stays on the `?focus=` interim.
- Cross-cutting Progress screen (Epic F) coupling — D3 stays a **future**
  option, not this epic's decision.

---

## 7. Human gate — pick a track (or tell me the framing is wrong)

Independent tracks (do-regardless / pick-the-priority / deferred-behind-X):

- **A. Do-regardless.** Fold **D0 FLAG-5 fix** into the first Epic C PR
  regardless of which lead you pick — cheap trust win, closes a live
  regression. **Confirm A?** (y/n)

- **B. Pick-the-priority.** Which lead direction advances to `sdd-spec`?
  - **B-1. `D1` (C-α only) — XS.** Ship S-4b + S-6 + S-1 title flip
    now; author board rows `C1: summary-payoff-lite` this week.
    No ADR; `decisions.md` only. **Preferred by the ranking** (impact per
    effort — closest to Epic A shape).
  - **B-2. `D2` (C-β only) — S.** Extend `SessionRepo`, build the rail
    with real streak/weekly, hold the score-goal + coach-note tiles for
    a later decision. One ADR. Lands the visually biggest gap first.
  - **B-3. `D4` (C-γ only) — M.** Misconception field + framed-title
    self-correction signal + content pass. One ADR + a corpus pass
    (calendar cost). Lands the "coach who knows you" *feeling* first.
  - **B-4. Composition (recommended): D1 first, then D2, then D4 —
    three sprints, two ADRs.** Matches the epic-program rule (independent
    releasability) and puts the cheapest-highest-trust move first.

- **C. Deferred-behind-X.** **`D3` (`LearnerStatsRepo` port) — DEFER.**
  Revisit when Epic F opens (second consumer arrives). Do not build
  today. **Confirm defer?** (y/n)

- **D. Reject-as-stated.** If any premise-audit refute (P1 S-5 shipped,
  P8 engine gap, P10 misconception source) changes the epic's shape
  enough that you want to re-scope Epic C on the epics doc first — say
  so; I'll pause and re-pose.

**On advance:** the picked track → `sdd-spec` with the validated
hypotheses (`H1`, `H2`, `H4`, `H5`, `H7`, `H8`, `H9`), the flagged
spec-clarify item (`H6`), the revised cost on `H3`, and the two-ADR
budget the composition carries.
