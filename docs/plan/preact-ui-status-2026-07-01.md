# PreACT English Coach — Frontend UI Status Report

**Date:** 2026-07-01
**Branch:** `feat/preact-ui-phase0-and-gate-fixes` (uncommitted; committed in a separate thread)
**Plan:** [`~/.claude/plans/serene-percolating-axolotl.md`](../../.claude/plans/serene-percolating-axolotl.md) (Stage 3/4/5 artifact)
**Spec:** [`docs/plan/preact-english-coach-ui.spec.md`](preact-english-coach-ui.spec.md)

---

## Executive summary

The **deterministic learning loop is complete and wired end-to-end** — Dashboard → Quiz →
Feedback → Summary — plus the **live streaming Coach client**. Everything was built
red-first (TDD, watched-fail-first), is `tsc --noEmit` clean, and is green: the coach-UI
slice is **38 test files / 297 tests passing**. What remains is the Phase-2 **backend**
(coach persona/judges, flags OFF), the responsive/a11y/theme polish (Phase 4), a browser
dev-seed (in progress in a separate session), and the deferred tutorial/progress screens.

---

## ✅ Done

| Phase | Deliverable | Notes |
|---|---|---|
| **0** | 6 bucket accent tokens (light+dark); engine browser accessor (C2 seam); `EngineProvider` / `useEngine()`; 6 VM translators | `composition_engine_browser.ts`, `app/engine-provider.tsx`; 16 translator test files |
| **0.6** | ADR-0011 `LearnerReadRepo` read-only seam — `ReadableEngineDb` projection (write methods unreachable = compiler-enforced read-only), `DrizzleLearnerReadRepo`, wired into both composition roots | Scheduler stays sole `skill_state` writer (FR-A2) |
| **1.1** | Shell + nav model + surface hook + `(coach)/learn` route group; coach anchored at `COACH_BASE="/learn"` (code-review finding #1 fix) | `components/shell/*` (4 test files) |
| **1.2** | Dashboard — real mastery via `LearnerReadRepo`, read-only (no `scheduler.next()`), today's-focus via pure `pickFocusSkillId` | `components/dashboard/*` |
| **1.3 / 1.3′** | Quiz orchestration (`next→get→grade→record→review`) + `skillStateAtStart` snapshot (ADR-0011 §4: captured after `sessionRepo.open`, before first `review()`, immutable `ReadonlyMap`) | `components/quiz/use_quiz.ts` |
| **1.4** | Quiz view components **+ `/learn/quiz` RSC route + Quiz→Summary live snapshot handoff** — pure `quiz_screen_reducer` phase machine + `quiz_session_store` singleton; Finish → `/learn/summary?session=<id>` with live delta | `quiz_screen_reducer` (8 tests), `quiz_session_store` (5 tests) |
| **1.5** | Feedback (Quiz sub-state, OD-5) — celebrate/soft banner, both rationales, per-choice styling, color-never-sole-signal (FR-A8) | `components/feedback/*` |
| **1.6** | Summary — stored score (no recompute, FR-G1), signed mastery delta from snapshot vs fresh read (`—` when unknown), recommended-next; `pickFocusSkillId` extracted to shared `lib/translators/focus_pick.ts` | `components/summary/*` |
| **2.1–2.3** | Coach **client** — BFF SSE route (`/api/coach/run/stream`), `use_coach` over `use_agent_run`, `CoachView` (single `role="log"`, typing indicator, **retry-not-spinner FR-F4 proven live**). Coach is a *consumer of the chat runtime*, not an engine port (design §7 divergence #1). | `components/coach/*` |

**Architecture invariants held & verified:** F-R1 (logic in hooks/reducers/translators, not
components), C2/C3 (adapters named only in composition roots; ports via context), T1 (pure
translators), U4 (single streaming region), read-only `ReadableEngineDb`.

### Files added/changed this session (Quiz route + handoff)

- `frontend/components/quiz/quiz_session_store.ts` (+ `.test.ts`) — module-singleton carrier
  for the FR-G1 `skillStateAtStart` snapshot across the Quiz→Summary route change (ADR-0011
  §4). Not a port, not persisted.
- `frontend/components/quiz/quiz_screen_reducer.ts` (+ `.test.ts`) — pure phase machine
  `loading → answering → reviewing → next|finish → done`; keeps transition logic out of the
  component (F-R1). Edge invariants proven first: a no-selection submit (FR-D2a) does not
  advance; `usedHint` is sticky per item.
- `frontend/app/(coach)/learn/quiz/page.tsx` — thin `'use client'` glue: reducer + `useQuiz`
  orchestration; Feedback rendered inline (OD-5); Finish navigates to Summary with the
  session id.
- `frontend/app/(coach)/learn/summary/page.tsx` — now reads `readQuizSessionSnapshot(sessionId)`
  before the empty fallback, so the delta is live within an unbroken session.

---

## 🔩 In progress (separate session)

- **Dev seed for the browser engine bag** — `browserEngineAdapters()` builds an *empty*
  `InMemoryEngineDb`, so the `/learn` surface renders empty (Dashboard) / errors (Quiz
  `openQuizItem` → "scheduled question not found") in a live browser preview. The loop is
  fully proven by node tests against seeded DBs, but is not yet exercisable in-browser. A
  dev-only seed (guarded so tests are unaffected) is being added in a spawned background task.

---

## ⛔ Remaining (TO-BUILD)

### Client-side (small)
- **2.4** Feedback "Ask the coach" chip — routes to Coach with the item in context (FR-E5).

### Phase-2 backend (gated ON, flags OFF — a separate build)
- `subject-coach-english` AgentFacts instance (reuses existing `AgentFacts` type → no
  `trust/models.py` change, no kernel re-sign), persona `.j2`, English-only
  `InputGuardrail.accept_condition`, `reflexion_enabled = False` (ADR-0009).
- The three judges + the `GoalJudge` `build_graph`-injection API change (landed **paired**
  with the judge build).
- **ADR-0008 conditions (mechanical gates):** a tracked κ TPR/TNR floor for `answer_leakage`
  before its flag is trusted in any gate; `answer_leakage` recorded **distinctly, never
  averaged** into a quality score.
- **2.5** Socratic-tone offline eval (L3, no live LLM in CI).

> The capability-gating filter is already landed (`components/capability_gating.py`, wired in
> `react_loop.py::build_graph`, flags default OFF → shadow-first; ADR-0007 accepted). The coach
> flags flip on only after the above lands, shadow-first.

### Phase 4 — Responsive / iPad-split / a11y / theme
- Theme toggle across screens; iPhone **3-tab** footer + focus-mode ✕ (UI-spec §8.1 supersedes
  FR-B1's 4-tab text); iPad split with persistent live coach panel (`CoachPanel` +
  `coach_thread_store` shared thread, FR-J3/J4); a11y sweep (axe per surface, ≥44px touch
  targets, WCAG-AA); desktop ≤1180 / quiz ≤760 width constraints.
- Playwright `e2e/coach/` (mocked SSE; the prototype suite is the behavioral oracle). Verify
  the split/responsive surfaces in real WKWebView, not just Chromium (ADR-0001 standing gate).

### ADR-0010 conditions (gate the *next* increment — on-device SQLite / Progress)
- Dual-dialect parity test `schema.spec::same_drizzle_schema_compiles_pg_and_sqlite` → add to
  `make check`.
- `DATABASE_URL`-gated `pgEngineDb` integration test filed in the engine spec §8.

### Deferred (second ADR-0006 amendment)
- Screens 6 & 7 — Skill-detail/Tutorial (FR-H) + Progress/Analytics (FR-I), gated on surfacing
  `getTutorial` + `listProgressPoints` (**not** on `LearnerReadRepo`). Dashboard/Summary links
  to them ship **disabled/"coming soon"** — never dead controls (FR-B5).

---

## Test evidence (this session)

- **Coach-UI slice** (`app`, `components/{quiz,summary,feedback,coach,dashboard,shell}`,
  `lib/translators`): **38 files / 297 tests passed**, zero worker errors.
- **Architecture suite:** 136/136 (run with `--testTimeout=60000`).
- **`tsc --noEmit`:** exit 0.
- **Full frontend run:** 235 passed / exit 0 — the 89 "errors" were a single vitest
  **worker-pool crash under combined load** (`Worker exited unexpectedly`), not test failures;
  confirmed by the clean isolated re-runs above. Recorded as a known flake class.

---

## Known limitation (by design)

- **Session-resume (ADR-0011 §4):** on reload/deep-link, the in-memory `skillStateAtStart`
  snapshot is lost → the Summary mastery-delta tile renders "—". Acceptable for Phase-1
  single-learner short sessions; the decision trigger for a persisted snapshot is real
  session-resume UX.

---

## Key architectural decisions in force

- **Coach is NOT an engine port** — it rides the chat `AgentRuntimeClient` (`use_coach` wraps
  `use_agent_run`); engine bounded context = 7 ports → 8 with `LearnerReadRepo`, never the
  coach (`docs/adr/decisions.md`).
- **`skill_state` reads are in scope now** via the narrow ADR-0011 `LearnerReadRepo`; only
  tutorial/progress reads are deferred (D1).
- **Native shells** are already covered by ADR-0001 (Tauri + Capacitor, live `server.url`
  model); no Turbo monorepo (single package — revisit at a second shared-package consumer).
