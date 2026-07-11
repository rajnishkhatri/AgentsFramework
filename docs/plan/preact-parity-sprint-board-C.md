---
title: 'Epic C — Coaching-relationship surfaces · Sprint Board'
type: sprint-board
epic: C
date: 2026-07-10
status: Draft
derives_from: docs/plan/preact-parity-epics.md
report: docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
prerequisite: docs/plan/epic-ab-continuity-fixes.spec.md   # provides ActiveQuizPointer that C2's FLAG-5 fix reads
governs:
  - docs/plan/preact-parity-epic-C.brainstorm.md   # Stage-1 CLOSED 2026-07-10
  - docs/plan/preact-parity-C1-dashboard-rail.spec.md   # to author at C1 sdd-spec
  - docs/plan/preact-parity-C2-summary-payoff.spec.md    # to author at C2 sdd-spec (after C1)
method: SDD lifecycle — one full pass per sprint (spec → plan/tasks → implement → review → converge)
---

# Epic C — Coaching-relationship surfaces · **Sprint Board**

**Epic goal** (from [epics doc](preact-parity-epics.md#epic-c--coaching-relationship-surfaces-)):
restore the two surfaces that make the app feel like a *coach who knows you* — Dashboard
right rail + greeting, and Summary misconception payoff. Trust-relationship increment.

**Findings in scope:** `D-1`, `D-5`, `S-1`, `S-3`, `S-4b`, `S-6`. (**`S-5` was in scope in the
epics doc; Stage-1 premise audit refuted it — already shipped**. See §"Notes carried back".)

> **Stage-1 CLOSED** ([brainstorm](preact-parity-epic-C.brainstorm.md)) — binding:
> **composition D2 → D4**, two sprints, two ADRs. **D1 (pure wire-up) DROPPED as a standalone
> sprint** — its three cheap items (S-4b `drillTitle`, S-6 three actions, S-1 framed title)
> absorb into C2 where they naturally belong (C2 already reworks the Summary landing surface).
> **D0 (FLAG-5 `?session=`)** absorbs into C2, wired via the `readActiveQuiz()` hook that the
> in-flight [epic-ab-continuity-fixes](epic-ab-continuity-fixes.spec.md) sprint plants on
> `quiz_session_store`. **D3** (`LearnerStatsRepo` port) DEFERRED to Epic F. **D5** (Coach
> runtime misconception marker) REJECTED in favor of D4 (Question-authored). **D6** (bundled)
> REJECTED — violates program §4 (independent releasability).
>
> Stage-1 framing (binding for this epic):
>
> - **`S-5` already shipped** ([SummaryView.tsx:69-75](../../frontend/components/summary/SummaryView.tsx:69)). Do
>   not re-implement. Verified in-passing by C2's e2e (Summary landing renders `summary-skill-link`).
> - **C-4 honesty rule (from Epic B) governs C1 and C2.** Every new tile / card is a real
>   number from a real read (or authored content), or **honestly absent** — never a
>   placeholder. AP-6 applies.
> - **Rail (D-5) `SessionRepo` gap is real.** `SessionRepo` today exposes only
>   `open`/`close`/`get` ([session_repo.ts:44-56](../../frontend/lib/ports/engine/session_repo.ts:44)).
>   C1 adds a `listByLearner`-shaped read; ADR required (⚠️ Ask-first #6, G1).
> - **Score-goal ("26 → 28") and coach-note deferred out of C1.** No engine source today
>   → do not ship a placeholder tile. Revisit in Epic F alongside `projectedScore`.
> - **Misconception is Question-authored (D4), not Coach-derived (D5).** Aligned with C-4:
>   we only claim to have "spotted the misconception" for items whose author captured one.
>   Absent otherwise. ADR required at C2 spec time.
> - **FLAG-5 is a soft-dependency on continuity-fixes.** If continuity-fixes lands first,
>   C2 flips the FLAG-5 regression guard green. If C2 lands first, C2's Summary chrome
>   ships without the Wrap-up wire and a follow-up commit adds it once continuity-fixes is
>   on `main`. Neither path blocks the other.

---

## Prerequisite — [epic-ab-continuity-fixes](epic-ab-continuity-fixes.spec.md) *(in flight, Approved 2026-07-10)*

Not an Epic C sprint. Called out here because it plants the exact substrate C2 needs for
FLAG-5, and the manual-validation-report defects it fixes (FLAG-1 / FLAG-4 / FLAG-6) were
explicitly left outside Epic C by Stage 1.

| What it delivers | Where C2 reads it |
|------------------|-------------------|
| `ActiveQuizPointer` on `quiz_session_store` — `{ sessionId, questionId, position, phase? }` — set while Quiz is live, cleared on Finish, retained across Coach nav | C2's Wrap-up handler on `/learn/coach` calls `readActiveQuiz()?.sessionId` and appends `?session=${id}` to the Summary route when known; falls back to today's behavior when absent (honest recovery) |
| FLAG-1 miss-refresh (deps += `pin?.questionId`), FLAG-4 Back resumes item, FLAG-6 tile relabel "Mastery change", Reveal enabled-color polish | Independent of Epic C — do not re-implement or re-spec |

**Continuity-fixes spec directly references this board's C2:** [epic-ab-continuity-fixes.spec.md:164-166](epic-ab-continuity-fixes.spec.md:164) says
"the active pointer's `sessionId` is the natural source for Wrap-up `?session=` once C0 lands
— prefer reading `readActiveQuiz()` over putting quiz session id on `coach_thread_store`."
This board honors that: C2 owns the FLAG-5 wire, and it reads `readActiveQuiz()`.

---

## Sprint ladder (release order within the epic)

| Sprint | Title | Findings | Type | Releasable alone? | Blocks |
|--------|-------|----------|------|-------------------|--------|
| **C1** | Dashboard rail + greeting (real numbers or absent) | `D-1`, `D-5` (streak + weekly · goal/note deferred) | **D2** — new engine read (ADR) | ✅ yes | — |
| **C2** | Summary payoff — misconception + framed title + three actions + drill-title + FLAG-5 | `S-3`, `S-1`, `S-4b`, `S-6` + **FLAG-5** | **D4** — new corpus contract (ADR); FLAG-5 = one-line wire via `readActiveQuiz()` | ✅ yes | — |

**Independence rule (program §4):** each sprint may merge to `main` alone.

- **C1** touches Dashboard VM + view + a new method on the existing `SessionRepo` port. No
  dependency on continuity-fixes or C2. Rail can ship with only streak+weekly tiles rendered
  honestly (goal + coach-note tiles are explicitly out of scope until Epic F).
- **C2** touches Summary VM + view + `Question` wire shape + item-bank corpus + coach
  `onWrapUp`. No hard dependency on C1. **Soft-dependency on continuity-fixes** for the
  FLAG-5 wire only: if continuity-fixes is not on `main` at C2 merge time, C2 ships without
  the FLAG-5 fix and a follow-up commit adds it later. Content pass is calendar-load-bearing
  — code lands fast, wide misconception coverage waits on corpus authoring.

```
       continuity-fixes (FLAG-1/4/6 + ActiveQuizPointer)   ── in flight ──►
             (soft-dependency for C2's FLAG-5 wire only)

       C1 (dashboard rail + greeting)                      ── ships anywhere ──►
       C2 (summary payoff + FLAG-5)                        ── ships anywhere ──►

Either C1 or C2 may ship first; the compose-order preference is C1 → C2 because
C1's honest-absent pattern (deferred tiles) sets up C2's honest-absent posture
(no misconception card when the item has no authored one).
```

---

## Sprint C1 — Dashboard rail + greeting  🟧 *(S, one ADR)*

**Report findings:** `D-1` greeting ("Let's get you to 28, Maya." + day/time) · `D-5` right
rail (score-goal · streak · weekly sessions · coach note).

**Origin:** Stage-1 audit **refuted** P8 — `SessionRepo` cannot derive streak/weekly today.
Direction **D2** — extend the *existing* `SessionRepo` port with a `listByLearner`-shaped
read, then derive streak + weekly in pure translators. Score-goal + coach-note **stay out**
of this sprint (no honest source; C-4 rule).

**Visual / seam anchors:**

| Seam | Today | Target |
|------|-------|--------|
| Port | [session_repo.ts:44-56](../../frontend/lib/ports/engine/session_repo.ts:44) `open`/`close`/`get` only | + `listByLearner(subject, learnerId, {sinceISO}): Promise<QuizSession[]>` returning closed sessions newest-first. **Same interface, one new method** (P1 preserved). |
| Adapter | [drizzle_session_repo.ts](../../frontend/lib/adapters/engine/repos/drizzle_session_repo.ts) implements the current three | + `listByLearner` Drizzle query on `quiz_session` (rows already exist; only surface missing). |
| Conformance | `engine_repos.test.ts` parametrizes port assertions | + one row per adapter for `listByLearner` (newest-first, `sinceISO` filter, closed-only). |
| Dashboard VM | [use_dashboard.ts:32-39](../../frontend/components/dashboard/use_dashboard.ts:32) `DashboardVM = {buckets, todayFocus, reviewMissesCount}` | + `greeting: GreetingVM`, `rail: RailVM` (both pure T1). |
| Dashboard view | [DashboardView.tsx](../../frontend/components/dashboard/DashboardView.tsx) — no header, no rail | + `<header>` with greeting; + `<aside aria-label="Trust rail">` with rendered tiles. Layout matches the spec's iPad "row" variant on narrow; desktop 2-column with the mastery grid. |
| Greeting derivation | new pure translator `greeting_vm.ts` from `nowISO` + `LEARNER_ID` (Phase-1 single-learner surface, [use_dashboard.ts:23](../../frontend/components/dashboard/use_dashboard.ts:23)) | "Good afternoon, Maya" — raw id title-cased; multi-learner display-name lookup deferred. |
| Streak derivation | new pure translator `streak_vm.ts` from `QuizSession[]` + `nowISO` | Count consecutive local-date buckets with ≥1 *closed* session (`ended_at != null`). Absent any → "Start a streak" (honest empty state, no fake number). |
| Weekly derivation | new pure translator `weekly_sessions_vm.ts` from `QuizSession[]` + `nowISO` | Count closed sessions in [Mon-of-this-week .. now]. Cap-and-target rule (3/3 vs 3/7 vs 7-dot strip) **is a spec-clarify item** (see §H6 below). |
| Score-goal tile | **DEFERRED** — no engine source | Do not render. `decisions.md` entry: "score-goal defers to Epic F when `projectedScore` lands." |
| Coach-note tile | **DEFERRED** — no engine source | Do not render. Same `decisions.md` entry as score-goal. |

**In scope:**

- New `SessionRepo.listByLearner` method + adapter + conformance test row.
- New pure translators: `greeting_vm.ts`, `streak_vm.ts`, `weekly_sessions_vm.ts`.
- `DashboardVM` grows `greeting` + `rail`; `useDashboard` fires a fourth read concurrently.
- View renders header greeting + rail; layout adapts to iPad-row / desktop-rail per prototype.
- Honest-absent path for cold starts (no closed sessions → "Start a streak" copy, no fake `0`).
- E2E: cold start (empty rail state), returning-learner (streak N, weekly M), midnight-boundary
  determinism (injected clock).

**Out of scope:**

- Score-goal tile / "26 → 28" copy (no source; C-4 honesty).
- Coach-note tile (no source; C-4 honesty).
- Multi-learner display-name lookup (deferred to whenever multi-learner lands).
- `LearnerStatsRepo` as a new horizontal port (D3 — deferred to Epic F).
- Progress screen (Epic F).
- Any Summary work (C2).

**Likely seams (spec will pin):**

| Layer | Pattern to follow |
|-------|-------------------|
| Port | one-interface-per-file preserved (P1) — new method on existing port |
| Adapter | Drizzle mirror in `drizzle_session_repo.ts`; conformance test entry |
| Translator | pure T1s (T1 rule) — injected clock; no `Date.now()` inside |
| Hook | `use_dashboard` grows a 4th concurrent read; unchanged shape otherwise |
| View | presentational (F-R1); iPad-row / desktop-rail responsive |
| Tests | L1 RTL/jsdom for view; unit for translators; conformance for adapter; Playwright for cold + returning-learner + injected-clock determinism |

**Definition of Done (C1):**

- [ ] `SessionRepo.listByLearner` method landed on port + Drizzle adapter + conformance test.
- [ ] Three pure translators (`greeting`, `streak`, `weeklySessions`) with unit tests covering
      cold / returning / midnight-boundary cases.
- [ ] Dashboard renders greeting + rail with only streak + weekly tiles; score-goal /
      coach-note absent (documented `decisions.md` entry).
- [ ] Cold-start renders honest empty states ("Start a streak") — never a fake `0`-day streak.
- [ ] E2E covering cold, returning, injected-clock determinism.
- [ ] `make check` + `pytest tests/architecture/ -q` green.
- [ ] **ADR** written and Accepted (see Gates).

**Gates:**

- **ADR required — G1 (new engine read) fires.** Rejected alternatives to document:
  (a) synthesize streak on the client from an in-memory session cache;
  (b) create a new `LearnerStatsRepo` port (D3) — deferred by abstraction-introduction rule
      until Epic F is the second consumer;
  (c) leave the rail out until Epic F ships the projection.
- Invariants stressed: **#7** (services must not import from components) — passes; new
  method sits under `lib/ports/engine/`. **F-R3 / P1** (one interface per module) —
  passes; adding a method to an existing port is not a new interface.
- `⚠️ Ask-first` items: **new port method** = Ask-first #6 (new horizontal service? — no,
  extending existing) + G1 (new abstraction? — new *derivation*, yes).

**Releasable alone:** ✅ — Rail ships with two honest tiles instead of four. Deferred tiles
are documented, not silently missing. No dependency on continuity-fixes or C2.

**Spec:** `preact-parity-C1-dashboard-rail.spec.md` *(to author at sdd-spec)*.
**ADR:** `docs/adr/00XX-session-repo-list-by-learner.md` *(to write at spec time)*.

---

## Sprint C2 — Summary payoff (misconception + framed title + three actions + FLAG-5)  🟧 *(M, one ADR)*

**Report findings:** `S-3` misconception narrative card · `S-1` framed title (both the title
copy on a score-ratio threshold AND the body copy on a self-correction signal) · `S-4b`
recommended-next names a specific drill · `S-6` three actions (drill / full lesson / done).
**Plus** the manual-validation-report **FLAG-5** wire fix (Wrap-up appends `?session=`).

**Origin:** Stage-1 audit **refuted** P10 — misconception has no engine source today.
Direction **D4** — carry misconception as a new nullable `Question.misconception` field,
filled by content authoring. Absent → honest-absent card. Framed-title body only fires when
a deterministic self-correction signal is detected on the session's focus skill. The D1
leftovers (S-4b drill title, S-6 three actions, S-1 title-on-threshold) fold in because C2
already reworks the Summary landing surface — adding view props is free relative to the
misconception ADR. FLAG-5 folds in because the continuity-fixes sprint plants
`readActiveQuiz()` on `quiz_session_store` — Wrap-up becomes a one-line change once that
substrate lands.

**Visual / seam anchors:**

| Seam | Today | Target |
|------|-------|--------|
| Wire — `Question` | [engine_entities.ts:101](../../frontend/lib/wire/engine_entities.ts:101) `Question` has no `misconception` | + `misconception: z.string().nullable()`. Nullable → additive, no back-compat break. |
| Item-bank schema | [schema.pg.ts](../../frontend/lib/adapters/engine/db/schema.pg.ts) | + column `misconception TEXT NULL`. Migration = additive nullable. |
| Content pass | Existing bank items authored without misconception | Wide corpus pass = **calendar-load-bearing**; code can ship with 0 items filled, card is honest-absent for all sessions until content lands (`gated-on-data`). |
| Summary VM | [session_summary_vm.ts:12](../../frontend/lib/translators/session_summary_vm.ts:12) note says "misconception passed by the hook, not synthesized here" | Add `misconception: string \| null` and `drillTitle: string` to `SessionSummaryVM`/`RecommendedNextVM`. Drill title is deterministic from `session.target_count` + `skillName` (e.g. "6-item drill: {skillName}"). |
| Hook | [use_summary.ts](../../frontend/components/summary/use_summary.ts) | Add a read: session's focus skill → most-recent miss → `question.misconception`. Absent → `null`. Pure derivation; no new port. |
| Framed title (S-1) | [SummaryView.tsx:45-47](../../frontend/components/summary/SummaryView.tsx:45) "Session summary / Here's how this session went." | *Title*: flip to "Nice work — you found the pattern." when score-ratio ≥ threshold (S-1 title). *Body*: additional copy referencing the misconception ONLY when self-correction signal fires (S-1 body). Both branches deterministic; `decisions.md` entry for the threshold. |
| Actions row (S-6) | [SummaryView.tsx:77-88](../../frontend/components/summary/SummaryView.tsx:77) one CTA "Practice this next" | Three actions: (1) primary → "Start recommended drill" (renamed); (2) "See full lesson" (Link to `screen("skill").route`, rendered disabled while `comingSoon` — mirrors nav-model FR-B5); (3) "Done for today" (Link to `screen("dashboard").route`). Pattern precedent = [DashboardView.tsx:42-64](../../frontend/components/dashboard/DashboardView.tsx:42). |
| S-5 verification | [SummaryView.tsx:69-75](../../frontend/components/summary/SummaryView.tsx:69) `summary-skill-link` already shipped | E2E assertion to keep the Stage-1 refuted-premise refuted. |
| View — misconception card | absent | + `<section aria-label="Misconception">…</section>` accent card when `misconception != null`. Absent → nothing rendered (no placeholder). |
| Wrap-up (**FLAG-5**) | [coach/page.tsx:101-104](../../frontend/app/(coach)/learn/coach/page.tsx:101) `onWrapUp` = `router.push(screen("summary").route)` with a "B2 would append session id" comment | `const id = readActiveQuiz()?.sessionId; router.push(id ? \`${route}?session=${id}\` : route);` — falls back to today's behavior when unknown (honest recovery). Soft-gated on continuity-fixes being on `main` (see below). |
| E2E FLAG-5 guard | [validate_epic_ab.spec.ts](../../frontend/e2e/learn/validate_epic_ab.spec.ts) FLAG-5 test wrapped in `test.fail()` | Remove `test.fail()` when the wire is present; guard flips green. If C2 ships without the wire (continuity-fixes slipped), leave `test.fail()` in place and note it in the sprint sign-off. |

**In scope:**

- `Question.misconception` field + item-bank schema migration.
- `SessionSummaryVM.misconception` + hook derivation.
- `RecommendedNextVM.drillTitle` + view renders it.
- Misconception accent card (honest-absent when `null`).
- Framed-title *title* copy conditional on score-ratio threshold.
- Framed-title *body* copy gated on self-correction signal.
- Three-actions row with disabled render on `comingSoon` (FR-B5).
- **FLAG-5 wire** in coach `onWrapUp` reading `readActiveQuiz()?.sessionId` (soft-gated).
- Initial content pass for a **seed corpus subset** (documented count; not full coverage).
- E2E: item with authored misconception → card + body; item without → card + body absent;
  three actions render + disabled Lesson when `comingSoon`; drill-title copy;
  `summary-skill-link` still present; Wrap-up lands on Summary with `?session=` when set;
  self-correction signal true/false branches.

**Out of scope:**

- Coach-derived misconception (D5 — rejected in Stage 1).
- Skill-level misconception (rejected in Stage 1 — misconception is item-specific).
- Full corpus coverage — calendar-load-bearing; documented as follow-up program.
- Coach-note tile on Dashboard (still no source — same rejection as C1).
- Any Dashboard change (C1).
- FLAG-1 / FLAG-4 / FLAG-6 (continuity-fixes).
- Opener copy fix / A0 docs guard (their own tracks).

**Likely seams (spec will pin):**

| Layer | Pattern to follow |
|-------|-------------------|
| Wire | additive nullable field (Zod `.nullable()`); schema-drift baseline update |
| DB | Drizzle migration `ADD COLUMN misconception TEXT NULL` |
| Content | precedent = how `hints.j2` rungs were authored per item (item-bank cascade in ADR-0021) |
| Translator | pure T1 additions to `SessionSummaryVM`; injected values from the hook |
| View | accent card matches the prototype's "✦ The misconception I spotted" — tokens U8; three-actions row mirrors dashboard secondary-actions pattern |
| Wrap-up wire | one line reading `readActiveQuiz()` from `quiz_session_store` (continuity-fixes P1) |
| Tests | L1 RTL/jsdom for view branching; unit for hook derivation + threshold + self-correction; integration for the read chain; Playwright for content-present/absent, FLAG-5 landing, three-actions, drill title |

**Definition of Done (C2):**

- [ ] `Question.misconception` on wire + Drizzle schema + migration.
- [ ] `SessionSummaryVM.misconception` + `RecommendedNextVM.drillTitle` + hook derivation.
- [ ] Misconception accent card renders when `misconception != null`; absent otherwise.
- [ ] Framed title (title) flips at documented threshold; below = today's neutral copy.
- [ ] Framed title (body) fires only when self-correction signal detected; unit tests both branches.
- [ ] Three actions on Summary; "See full lesson" rendered *disabled* while `comingSoon`.
- [ ] `summary-skill-link` still present (S-5 refuted-premise regression guard).
- [ ] **FLAG-5 wire** in place iff continuity-fixes is on `main`; otherwise ship without it
      and leave the guard as `test.fail()` with a sign-off note (follow-up commit lands the
      wire once continuity-fixes merges).
- [ ] Seed content pass: minimum N items with authored misconception (N set at spec time
      based on `needs-probe` count of bank items in scope).
- [ ] E2E: content-present branch, content-absent branch, three actions, disabled Lesson,
      `summary-skill-link`, FLAG-5 landing (when wire present), self-correction branches.
- [ ] `make check` + `pytest tests/architecture/ -q` green.
- [ ] **ADR** written and Accepted (see Gates).
- [ ] `decisions.md` entry for the framed-title threshold + the "disabled Lesson while
      comingSoon" rendering rule.

**Gates:**

- **ADR required — G1 fires (new derivation path AND new corpus contract).** Rejected
  alternatives to document:
  (a) LLM-synthesize misconception from misses at Summary time — rejected: C-4 honesty rule
      + this synthesis is what the Coach card should say later, not what Summary claims after 5 items;
  (b) attach misconception to `Skill` — rejected: skill-level blurs it back to the skill name;
      prototype's "conciseness overrode punctuation" is item-specific;
  (c) attach to `Attempt` at grade time — rejected: post-hoc, no author signal;
  (d) D5 (Coach runtime marker) — rejected in Stage 1: adoption gap; only fires when learner
      used the Coach, which is a subset of "everyone"; keep as future variant if D4 falters.
- Invariants stressed: **#2** (trust kernel unchanged — misconception is not signed);
  **F-R7** free (no `trace_id` concern); item-bank cascade (ADR-0021) is the precedent;
  **FR-B5** actively upheld via disabled-Lesson render.
- `⚠️ Ask-first` items: **new field on wire + DB migration** (Ask-first: trust-kernel change?
  no — it's a domain field; new abstraction? yes — new derivation path; new dependency? no).

**Releasable alone:** ✅ — code lands cleanly with 0 misconception values filled (honest-
absent for all sessions). Content pass is a follow-up program, not a merge blocker. FLAG-5
wire is soft-gated: no wire = no regression from today's broken state; wire present = one
`test.fail()` flips green.

**Spec:** `preact-parity-C2-summary-payoff.spec.md` *(to author at sdd-spec)*.
**ADR:** `docs/adr/00XX-question-misconception-field.md` *(to write at spec time)*.

---

## Cross-sprint spec-clarify items (open before spec time)

Carried forward from the brainstorm hypothesis table. These are questions the human answers
at `sdd-spec` time for the relevant sprint — not board-level decisions.

| ID | Item | Owning sprint | Recommended answer (to confirm at spec time) |
|----|------|---------------|----------------------------------------------|
| **H6** | Weekly sessions rule ambiguity: "3/3 weekly sessions" vs "7-dot week strip" — is the target 3 per week (any distribution) or 1 per day capped at 7? | **C1** | 3-per-week (any distribution); render as `N/3`. 7-dot per-day strip is a **visual** variant deferred with the score-goal tile. `decisions.md` entry. |
| **misconception coverage N** | How many seed items get authored misconception in C2 to make the card meaningful? | **C2** | `needs-probe` at spec time: measure how many bank items have a plausible one-line misconception; N ≥ that count. If probe returns 0, C2 ships code-only (honest-absent for every session) and the content pass becomes its own follow-up. |
| **framed-title threshold** | What score ratio flips the neutral title to "Nice work — you found the pattern."? | **C2** | Recommended: `correct/total ≥ 0.6` (spec §5.5 example is 7/10 = 0.7). `decisions.md` entry. |
| **self-correction signal** | What deterministic pattern on `AttemptRepo.misses` counts as "self-corrected the misconception"? | **C2** | Recommended: same skill-scoped miss present in first half of the session AND absent in second half (with ≥1 correct on the same skill after the miss). Pure derivation from `AttemptRepo`; no new port. |
| **FLAG-5 soft-gate posture** | If continuity-fixes has not merged by C2 merge time, ship C2 without the FLAG-5 wire? | **C2** | Yes — ship the chrome; leave `test.fail()` in place; follow-up commit lands the wire when `readActiveQuiz()` is on `main`. Do not block C2 merge on continuity-fixes. |

---

## Epic-C exit criteria (what "released" means)

- [ ] **C1 shipped:** Dashboard renders greeting + rail with honest streak + weekly tiles;
      score-goal + coach-note deferred with `decisions.md` note; `SessionRepo.listByLearner`
      lives on port + adapter + conformance test; ADR Accepted.
- [ ] **C2 shipped:** `Question.misconception` on wire + DB; Summary renders misconception
      card when present, absent otherwise; framed title (title + body) branches on threshold
      + self-correction; three actions row with disabled Lesson while `comingSoon`; drill
      title; seed content pass documented (N ≥ probe count or ADR-explained 0); FLAG-5 wire
      in place (or follow-up committed after continuity-fixes lands); ADR Accepted.
- [ ] Parity report (`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`) rows for
      `D-1`, `D-5` (streak+weekly), `S-1`, `S-3`, `S-4b`, `S-6` marked 🟩 or 🟨 with real
      references. `S-5` row marked 🟩 with "verified in-passing by C2".
- [ ] Manual-validation-report row for **FLAG-5** marked resolved (owned by C2, delivered
      via `readActiveQuiz()` from continuity-fixes).
- [ ] **Gate to Epic D:** after C1 + C2 on `main` (or explicit human waiver for a
      slipped sprint). One epic in flight (program §1).

---

## Traceability — all seven originally-scoped Epic C findings + FLAG-5 accounted for

Confirms every Epic C finding lands in exactly one sprint (or has been reassigned with reason).

| Finding | Sprint | Note |
|---------|--------|------|
| **D-1** greeting | C1 | header + `greeting_vm` translator |
| **D-5** rail: streak | C1 | derived from `SessionRepo.listByLearner` + `streak_vm` |
| **D-5** rail: weekly | C1 | derived from `SessionRepo.listByLearner` + `weekly_sessions_vm` |
| **D-5** rail: score-goal | **deferred** | no engine source; revisit Epic F alongside `projectedScore` |
| **D-5** rail: coach-note | **deferred** | no engine source; revisit Epic F |
| **S-1** framed title (title) | C2 | score-ratio threshold |
| **S-1** framed title (body) | C2 | self-correction signal from `AttemptRepo` |
| **S-3** misconception narrative | C2 | new `Question.misconception` field, D4 |
| **S-4b** drill title | C2 | `RecommendedNextVM.drillTitle` derived from `target_count` |
| **S-5** tappable skill link | **reassigned — already shipped** | Stage-1 refuted premise; C2 e2e re-verifies |
| **S-6** three actions | C2 | actions row with disabled Lesson while `comingSoon` |
| **FLAG-5** Wrap-up `?session=` | C2 | one-line wire reading `readActiveQuiz()?.sessionId` (soft-gated) |

Coverage: 5 findings → C1, 5 findings → C2, 1 reassigned (S-5 shipped), 2 deferred (score-goal
+ coach-note under D-5), 1 borrowed regression (FLAG-5). Two sprints. Two ADRs.

---

## Notes carried back to the parity report / epics

Stage-1 (2026-07-10) corrections to fold into the VISUAL report and epics Epic C section:

1. **`S-5`** — Stage-1 premise audit refuted: tappable skill link **already shipped**
   ([SummaryView.tsx:69-75](../../frontend/components/summary/SummaryView.tsx:69)). Remove from
   Epic C scope; verified in-passing by C2's e2e. The `?focus=<skillId>` interim destination
   is honest (avoids the `comingSoon` `/learn/skill` dead route — FR-B5).
2. **`D-5`** — the four tiles are not equivalent: streak + weekly are derivable from a real
   engine read (C1 ADR); score-goal + coach-note **have no honest source today** and stay
   deferred (revisit in Epic F alongside `projectedScore`). Report row splits accordingly.
3. **`S-3` / `S-1` body** — misconception source is Question-authored (D4), not
   Coach-derived (D5). C2 ADR records the rejection with reason (D5 adoption gap +
   C-4 honesty on when we may claim to have "spotted" one).
4. **FLAG-5 rehomes from "Epic C sprint C0" (as stated in continuity-fixes spec) to
   **Epic C sprint C2** — the D1 pure-wire-up sprint was dropped after Stage-1 review
   (dominated by C2's Summary chrome rework). Continuity-fixes still delivers the
   `readActiveQuiz()` substrate C2 reads.
5. **FLAG-1 / FLAG-4 / FLAG-6** — owned by [epic-ab-continuity-fixes](epic-ab-continuity-fixes.spec.md), not
   Epic C. Stage-1 brainstorm explicitly left these outside C.
6. **D1 (pure wire-up sprint) dropped from Epic C** — S-4b `drillTitle`, S-6 three actions,
   S-1 framed title *title* copy all fold into C2 because C2 already reworks the Summary
   landing surface. Adding view props alongside the misconception ADR is free relative to
   the ADR; carrying them in a separate sprint was overhead without value.
7. **D3 (`LearnerStatsRepo` port)** — deferred to Epic F when the second consumer (Progress
   screen) arrives. Abstraction-introduction rule (root AGENTS.md G1) — do not build until
   the second consumer is real.

---

## What happens next (per Stage 3/4 of the SDD lifecycle)

1. **Human gates the board** (this doc). Advance / re-scope / reject.
2. On advance: I author **C1's `.spec.md` + `.plan.md`** (EARS acceptance criteria +
   file-level task list) at `sdd-spec`. C1's ADR is authored at spec time.
3. C1 runs the SDD lifecycle to `main` (implement → code-review → converge). Human
   gatekeeps each stage transition.
4. On C1 merged: repeat for **C2**. C2's ADR is authored at spec time. C2's FLAG-5 wire
   posture depends on continuity-fixes merge status at that point (see §"Prerequisite").
