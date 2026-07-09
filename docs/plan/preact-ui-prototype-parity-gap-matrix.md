# PreAct English Coach — Prototype ↔ App Parity Gap Matrix

> ⚠️ **SUPERSEDED (2026-07-09).** This Stage-1 matrix predates the S3/S4/S5 merges (PR #136–#139),
> so its `🔴 missing` rows for the progress bar, bounded session, done-state, clickable bucket card,
> and CTA contrast are **stale — those all shipped.** The current, canonical, screenshot-verified
> 7-screen audit (with spec + E2E coverage checklist) is
> **[preact-ui-prototype-parity-VISUAL-gap-report.md](preact-ui-prototype-parity-VISUAL-gap-report.md)**.
> Keep this file for historical/provenance value only; use the visual report going forward.

**Stage:** SDD Stage 1 (brainstorm) evidence artifact · **Date:** 2026-07-08
**Method:** Hybrid — prototype Playwright specs (`eng-coach-ui-design/tests/e2e/*.spec.js`) as
the behavior oracle, mapped to shipped code (`frontend/app/(coach)/learn/` + `frontend/components/*`),
with rendered screenshots settling visual gaps.

**Legend — App status:**
`✅ present` · `🟡 partial` (exists, diverges) · `🔴 missing` · `🐞 defect` (present but broken) ·
`⛔ unbuilt` (intentionally `comingSoon`) · `➕ app-only` (app has it, prototype doesn't).

**Oracle artifacts:** `English Coach - Prototype.html` (desktop) + `.iphone`/`.ipad` specs.
**Spec of record:** `eng-coach-ui-design/PreACT-English-Coach-Spec.md`.

---

## Screen 1 — Dashboard / Home

| # | Prototype affordance (oracle) | App status | Evidence | Sprint |
|---|---|---|---|---|
| D-1 | Greeting "Let's get you to 28, Maya." | 🔴 missing | no greeting in `DashboardView.tsx` / `use_dashboard.ts` VM | S6 (dashboard rail) |
| D-2 | Today's focus banner (weakest+due, CTA "Start adaptive session") | ✅ present | `TodayFocusBanner.tsx` (CTA → `/learn/quiz`) | — |
| D-3 | Skill-mastery grid: 6 bucket cards (%, share, bar, Due) | ✅ present | `DashboardView.tsx:33`, `BucketCard.tsx` | — |
| D-4 | **Bucket card click → Skill detail** | 🐞 defect | `BucketCard.tsx` JSDoc claims "card is a link to Skill detail (FR-C4)" but JSX renders a plain `<article>` — **no Link/href/onClick**. Inert. | **S2 (clickable skill)** |
| D-5 | Right rail: score goal 26→28, 9-day streak, 3/3 weekly, coach note | 🔴 missing | none in VM/components | S6 |
| D-6 | "Drill a skill" → Quiz/Skill; "Review my misses (N)" → Feedback | 🟡 partial | both are `<Link href="/learn/quiz">` (`DashboardView.tsx:43,49`) — count is real, but both go to plain quiz, not distinct destinations | S6 |
| D-7 | — | ➕ app-only | "Take a timed test" → `/learn/test` (Test Mode); prototype has NO timed-test concept | (keep; document) |

## Screen 2 — Quiz / Drill  *(core of the reported pain)*

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| Q-1 | Context sentence + underlined span | ✅ present | `QuizView.tsx` `contextHtml` (reviewed engine content) | — |
| Q-2 | Stem "Which choice is correct?", 4 choices (A=NO CHANGE) | ✅ present | `QuizView.tsx` choices map | — |
| Q-3 | Submit gated until a choice selected | ✅ present | `canSubmit()` drives `disabled` (`QuizView.tsx`) | — |
| Q-4 | Hint toggle, labeled "not the answer", ≠ Reveal | ✅ present | `quiz-hint-toggle` + `quiz-reveal` (`QuizView.tsx`) | — |
| Q-5 | **Slim top bar: "Question N / M" + progress bar** | 🔴 missing | `QuizView.tsx` renders NO top bar / counter / progress | **S4 (progress bar)** |
| Q-6 | **Bounded session (10 items) — a first & last question** | 🔴 missing | `openQuizItem` always calls `scheduler.next()` (`use_quiz.ts:91`); `FsrsScheduler.next` always returns most-due (`fsrs_scheduler.ts:73`); `QuizSession` has no length field (`engine_entities.ts:199`). **Loop is infinite BY DESIGN.** | **S3 (session-length field)** |
| Q-7 | **Done-state: "you finished all N" + retake** | 🔴 missing | reducer `finish→done` only on manual Finish (`quiz_screen_reducer.ts:182`); no terminal-on-target | **S5 (done + retake)** |
| Q-8 | Dismissible timer (14:32 ⊘↔⏱) | 🔴 missing | app records internal `elapsed_ms` (D0 timing) but renders NO visible/dismissible clock | S7 (timer) |
| Q-9 | End session → Dashboard | 🟡 partial | app has "Finish & see summary" → Summary; no "End session → Dashboard" abandon path | S5 |

## Screen 3 — Post-answer Feedback

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| F-1 | Adaptive banner (A→"Exactly right." / B→"Not quite") | ✅ present | `FeedbackView.tsx` `BANNER_TEXT` | — |
| F-2 | Per-choice CORRECT / YOUR CHOICE / other (icon+label, not color-only) | ✅ present | `ReviewedChoiceRow` (`FeedbackView.tsx`) FR-A8 | — |
| F-3 | "Why A is correct" + "Why [pick] tempted you" + rule | ✅ present | `FeedbackView.tsx` rationale block | — |
| F-4 | Sentence recap (correct span in green) | 🟡 partial | feedback shows choices+rationale; recap-with-green-span not separately rendered | S7 (polish) |
| F-5 | Actions: Ask the coach → Coach · Next question → Summary | 🟡 partial | app: "Next question" (loops) + "Finish & see summary" (`quiz/page.tsx:207`); "Ask the coach" only on iPad split | S5/S7 |
| F-6 | Top progress bar | 🔴 missing | same root as Q-5 | S4 |

## Screen 4 — AI Coach Chat

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| C-1 | Header (avatar + "Your Coach" + Wrap-up) | ✅ present | `CoachView.tsx` / `CoachPanel.tsx` | — |
| C-2 | Context rail: current item + "sees your history: 3 of last 5…" + 3 modes | 🟡 partial | coach thread + derived mode exist; the explicit "sees your history N of M" line needs confirmation | S8 (coach parity) |
| C-3 | Conversation stream + typing indicator (3 dots) + auto-scroll | ✅ present | `CoachView.tsx` (coach_thread_store) | — |
| C-4 | Composer: quick-reply chips + input + send | 🟡 partial | composer present; keyword-routed canned chips need confirmation vs oracle | S8 |
| C-5 | iPad: coach as persistent RIGHT panel of split Quiz, shared thread | ✅ present | `CoachPanel` in `quiz/page.tsx:231` (iPad surface), shared `coach_thread_store` | — |

## Screen 5 — Session Summary

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| S-1 | Title "Nice work — you found the pattern." | 🟡 partial | app title = "Session summary" / "Here's how this session went." — misconception-framed *title* not used | S7 (copy) |
| S-2 | 3 stats (7/10, +8% mastery, 12 min) | ✅ present | `SummaryView.tsx` StatTile ×3 (score/mastery/time) | — |
| S-3 | **Coach misconception write-up (accent card)** | 🔴 missing | app shows recommended-next card, NOT a misconception narrative | S7 |
| S-4 | Recommended-next card + CTA | 🐞 defect | card present BUT "Practice this next" CTA is **white text on accent@8% → invisible** (`SummaryView.tsx:76`, screenshot-confirmed) | **S1 (CTA contrast)** |
| S-5 | Recommended skill name tappable (→ Skill/drill) | 🐞 defect | "Grammar & Usage" is static `<p>` (`SummaryView.tsx:64`), not a link | **S2 (clickable skill)** |
| S-6 | Actions: Start recommended drill / See full lesson / Done for today | 🟡 partial | app: one "Practice this next" Link; no "See full lesson" / "Done for today" | S7 |

## Screen 6 — Skill Detail / Tutorial

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| SD-1 | "The rule, in one line" + ✓ examples + "Why you missed these" | ⛔ unbuilt | `nav_model.ts:75` `skill` = `comingSoon:true`; no `/learn/skill` route | S9 (Skill epic) |
| SD-2 | Accuracy bar chart (last 6 sessions) + "Due for review" | ⛔ unbuilt | needs engine amendment (getTutorial) | S9 |
| SD-3 | "Drill this skill" → Quiz | ⛔ unbuilt | — | S9 |

## Screen 7 — Progress / Analytics

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| P-1 | Projected-score trend (line chart, goal guide) | ⛔ unbuilt | `nav_model.ts:76` `progress` = `comingSoon:true`; no `/learn/progress` route; nav item greyed (screenshot) | S9 (Progress epic) |
| P-2 | Mastery-by-bucket bars | ⛔ unbuilt | needs engine amendment (listProgressPoints, plan D1) | S9 |
| P-3 | Range tabs (30 days / All time) switch trend | ⛔ unbuilt | — | S9 |

## Cross-cutting

| # | Prototype affordance | App status | Evidence | Sprint |
|---|---|---|---|---|
| X-1 | Theme toggle light↔dark (whole UI re-themes) | ✅ present | shipped (see `[[preact-learn-a11y-phase4]]`) | — |
| X-2 | Sidebar (desktop/iPad): Home/Practice/Coach/Progress | 🟡 partial | present but Progress greyed (`comingSoon`) | S9 |
| X-3 | iPhone bottom tabs: Home/Practice/Progress | 🟡 partial | present; Progress tab → unbuilt | S9 |
| X-4 | Header flow-step pills (jump-nav) | 🔴 missing | app has no header flow-step pills (prototype-only navigation aid) | (skip — prototype scaffolding) |

---

## Re-ranked sprint ladder (against the FULL gap list)

Each sprint is independently testable + production-ready. `⚠️` = ADR/Ask-first trigger.

| Sprint | Scope | Gaps closed | Engine? | Test gate |
|---|---|---|---|---|
| **S1** ⭐ | Fix invisible "Practice this next" CTA (solid accent fill) | S-4 | no | axe contrast on `/learn/summary` + visual |
| **S2** | Make skill/bucket names tappable (Summary label + Dashboard BucketCard). **Target = Skill detail per oracle** — but Skill is `comingSoon`, so interim target = focused drill `/learn/quiz?focus=<skill>` until S9 | D-4, S-5 | no | RTL: name is a link w/ href; Playwright click→lands |
| **S3** ⚠️ | Add nullable `target_count` to `QuizSession` (schema pg+sqlite + wire + `SessionRepo.open`); **per-mode default** (adaptive N, drill M). Backward-compatible (null = endless) | Q-6 (capability) | **yes — ADR** | migration applies clean; repo tests w/ + w/o target |
| **S4** | Quiz top bar: "Question N / M" + progress bar + End-session | Q-5, F-6 | no (reads S3) | RTL counter/bar; Playwright walk N items |
| **S5** | Done-state (`complete` reducer phase at target) + Retake + End-session→Dashboard | Q-7, Q-9, F-5 | no (reads S3) | reducer node test: Nth submit → `complete`; no over-fetch |
| **S6** | Dashboard rail: greeting, score-goal 26→28, streak, weekly, coach note; distinct destinations for D-6 | D-1, D-5, D-6 | maybe (streak data) | RTL rail; VM tests |
| **S7** | Summary/Feedback copy + misconception write-up + recap green span + missing actions | S-1, S-3, S-6, F-4, F-5 | maybe (misconception text) | RTL copy; snapshot |
| **S8** | Coach context-rail parity ("sees your history N/M") + chip routing audit | C-2, C-4 | no | Playwright chip→reply |
| **S9** ⚠️ | Skill-detail + Progress screens (the `comingSoon` plane) | SD-*, P-*, X-2/3 | **yes — engine amendment (getTutorial/listProgressPoints, plan D1)** | new-route e2e; chart render |
| — | Timer UI (Q-8) | Q-8 | no | (optional; low priority) |

**Sequencing:** S1, S2 ship immediately (zero-risk, no ADR — the "validate earlier" wins). S3→S4→S5 = the bounded-session mini-epic (spine). S6–S8 = incremental parity. **S9 is the final, largest sprint** (own ADR + engine amendment) — included per decision, ships last.

**Two oracle-derived decisions now settled:**
- **Sprint-1 link target:** the prototype opens **Skill detail** on bucket-card / skill-name click (all 3 specs: `btn(/Rhetoric/).click()` → "Why you missed these"). Since Skill detail is unbuilt (S9), S2 ships an **interim** focused-drill target and re-points to Skill detail when S9 lands.
- **Session length:** **per-mode** (confirmed) — adaptive vs drill get different N.
