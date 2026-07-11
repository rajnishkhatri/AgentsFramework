---
title: 'Sprint D1 — Quiz session-frame chrome · Plan + Tasks'
type: plan
status: Draft — 2026-07-10
date: 2026-07-10
owner: Rajnish Khatri
epic: D
implements: docs/plan/preact-parity-D1-quiz-frame.spec.md
related:
  - docs/plan/preact-parity-D1-quiz-frame.spec.md
  - docs/plan/preact-parity-sprint-board-D.md
  - docs/plan/preact-parity-epic-D.brainstorm.md
  - docs/plan/preact-quiz-progress-surface.plan.md   # precedent — S4 translator + component
  - docs/plan/preact-quiz-done-state.plan.md         # precedent — S5 reducer flag + banner
  - docs/plan/preact-parity-A1-reveal.plan.md        # precedent — reducer dispatch + close+route
  - docs/adr/decisions.md                            # target for the "extend vs new VM" line
---

# Sprint D1 — Plan + Tasks

Implements [preact-parity-D1-quiz-frame.spec.md](preact-parity-D1-quiz-frame.spec.md).
Frontend Ring only; no `⚠️ Ask first` trigger under the default posture (extend
`QuizItemVM`) → **no ADR**; a `docs/adr/decisions.md` line records the shape
call. Flip to `QuizFrameVM` fires G1 → ADR-0026 authored in the same PR (see
§1.1 below).

---

## 1. Architecture / approach

D1 is three sub-features sharing one seam:

- **Q-7 (skill chip)** — a **hook + translator + view** join. `use_quiz`
  already reads `skillTaxonomy.list` (via `listQuizSkillIds` at
  [`use_quiz.ts:105`](../../frontend/components/quiz/use_quiz.ts:105))
  and the page consumes it for focus-param resolution
  ([`quiz/page.tsx:90`](../../frontend/app/(coach)/learn/quiz/page.tsx:90)).
  D1 extends the hook to return the full `Skill[]`
  (not just `id[]`), the page keeps that list in state, and the translator
  extension joins the current `Question.skill_id` against it to fill
  `QuizItemVM.skillName` + `QuizItemVM.accentVar`.
- **Q-8 (End session)** — a new reducer action (`end_session`), a new page
  callback (`onEndSession`), a new `<button data-testid="quiz-end-session">`
  in the frame region. The callback runs the *existing* `closeSession`
  orchestration (idempotent) with the running tally, then routes to
  `/learn`. Nothing new below the port.
- **Q-9 (collapsible timer)** — a new pure elapsed helper next to
  `elapsedMsFrom` (`formatElapsedFromStartedAt(startedAtIso, nowMs)`
  → `"m:ss"`), a new tiny presentational leaf `QuizTimer` (reveal /
  collapsed / expanded states + 1s tick) rendered in the frame region.
  No engine touch — the reducer is not extended for the timer.

**Grouping rationale.** All three additions land in the same `QuizView` header
region and share one test file. Three internally-independent commits inside
one PR (per §11 of the sprint board) so a partial revert stays cheap.

### 1.1 The `QuizItemVM`-vs-`QuizFrameVM` call — locked

**Decision: extend `QuizItemVM`** with two nullable fields (`skillName`,
`accentVar`). Rationale:

- Q-7's data is *per-item* (each item has one skill); the natural home is the
  item VM.
- Q-8's tally and Q-9's `session.started_at` are read directly off React state
  (`state.score`, `session.started_at`) — no VM needed for them.
- Two nullable fields is not a new abstraction; the existing `QuizItemVM`
  already carries multiple item-scoped fields (`stem`, `choices`,
  `contextHtml`). Adding two more scores same on the G1 test as adding one.
- If a *later* sprint pushes the item VM past 8+ fields, that sprint can
  refactor to `QuizFrameVM` under its own G1 ADR. Doing it here would be
  speculative.

`decisions.md` line captures this call (T5.2 below). **No ADR.**

### 1.2 Timer tick — locked to `setInterval(1000)`

`m:ss` display needs 1s resolution. `requestAnimationFrame` at 60Hz would
over-tick and burn battery. `useEffect` with `setInterval(1000)` + cleanup on
unmount / phase change. Reducer is clock-free (FR-X1 respected).

### 1.3 Reducer terminal state — locked to converge on `done` (no tag)

The reducer's existing `done` phase already models "session over". End session
and Finish differ only in **which page callback fires**, not in the reducer
state. The page callback owns the route target:
- `onFinish` → `closeSession` → route to `/learn/summary` (existing).
- `onEndSession` → `closeSession` → route to `/learn` (new).

`FR-Q8-6` is satisfied by the **two distinct callbacks + two distinct
`data-testid`s** (`quiz-finish`, `quiz-end-session`), not by a reducer tag.
The reducer gets a new action `end_session` (mirrors `finish` in shape) so an
L1 test can assert the two transitions do not collapse. This is the
lightest posture that satisfies FR-Q8-6 without over-modelling.

### 1.4 iPad split — preserved without re-flow

Chip / End / timer render inside the *item column* of the split
([`quiz/page.tsx:317-321`](../../frontend/app/(coach)/learn/quiz/page.tsx:317)),
above the phase content. The `useSurface` gate is not touched. FR-X4.

### 1.5 Why no new port

- Q-7: reuses `SkillTaxonomy.list` (existing).
- Q-8: reuses `SessionRepo.close` (existing, idempotent, already used by
  `onFinish`).
- Q-9: reads `session.started_at` off React state (no port at all).

No new abstraction below the hook. Symptom of a wrong plan: an entry for
"new port" here. There is none.

## 2. Files touched

| File | Edit | Owning FR(s) |
|------|------|-----------|
| [`frontend/lib/translators/quiz_item_vm.ts`](../../frontend/lib/translators/quiz_item_vm.ts) | Extend `QuizItemVM` with `skillName: string \| null` + `accentVar: string \| null`; extend `toQuizItemVM(question, skillsById?)` signature | FR-Q7-1, FR-Q7-3 |
| [`frontend/lib/translators/quiz_item_vm.test.ts`](../../frontend/lib/translators/quiz_item_vm.test.ts) | Add cases: match → name/accent populated; no-match → both `null`; empty skills map → both `null` | FR-Q7-1 |
| **NEW** `frontend/lib/translators/quiz_frame_timer.ts` | Pure helper `formatElapsedFromStartedAt(startedAtIso: string \| null, nowMs: number): string` | FR-Q9-4 |
| **NEW** `frontend/lib/translators/quiz_frame_timer.test.ts` | Table tests: 0:00 / 0:59 / 1:00 / 10:00 / future-clock → 0:00 / null → 0:00 / unparseable → 0:00 | FR-Q9-4 |
| [`frontend/components/quiz/QuizView.tsx`](../../frontend/components/quiz/QuizView.tsx) | Render a new frame region above the item body: skill chip (Q-7), End-session button (Q-8), timer reveal/expanded (Q-9). Add props: `endSessionEnabled`, `onEndSession`, `startedAtIso` | FR-Q7-2, FR-Q7-4, FR-Q8-1, FR-Q8-3, FR-Q9-2..7 |
| [`frontend/components/quiz/QuizView.test.tsx`](../../frontend/components/quiz/QuizView.test.tsx) | Add SSR + jsdom cases per FR table (§spec §8) | FR-Q7-*, FR-Q8-1/3, FR-Q9-* |
| **NEW** `frontend/components/quiz/QuizTimer.tsx` (or inline in QuizView — see §3 T3.1) | Presentational leaf with reveal/expanded states + 1s tick effect | FR-Q9-2/3/5/7/8 |
| [`frontend/components/quiz/quiz_screen_reducer.ts`](../../frontend/components/quiz/quiz_screen_reducer.ts) | Add action `{ type: "end_session" }`; transitions from `answering`/`reviewing` → `done` carrying tally (mirrors `finish`); no-op from `done`/`loading` | FR-Q8-2, FR-Q8-6 |
| [`frontend/components/quiz/quiz_screen_reducer.test.ts`](../../frontend/components/quiz/quiz_screen_reducer.test.ts) | Add: `end_session` from answering → done; from reviewing → done; from done → no-op; `finish` still routes semantically same (assertion on state, page test asserts route) | FR-Q8-2, FR-Q8-6 |
| [`frontend/components/quiz/use_quiz.ts`](../../frontend/components/quiz/use_quiz.ts) | Add `listSkills(subject) → Skill[]` next to `listSkillIds`; keep the id-list method for `resolveFocusMode` (no regression) | FR-Q7-3 |
| [`frontend/app/(coach)/learn/quiz/page.tsx`](../../frontend/app/(coach)/learn/quiz/page.tsx) | (a) Extend Effect 1 to also stash `Skill[]` → `skillsById` state; (b) pass `skillsById` into `toQuizItemVM`; (c) add `onEndSession` callback that awaits `closeSession` then `router.push(screen("dashboard").route)`; (d) pass `session?.started_at ?? null` + `session != null` + `onEndSession` into `<QuizView>` | FR-Q7-2/4, FR-Q8-4/5, FR-Q9-1/4/7 |
| [`docs/adr/decisions.md`](../adr/decisions.md) | Append newest-first entry: D1 shape choice = extend `QuizItemVM`, reject `QuizFrameVM` — rationale + rejected alt | plan §1.1 |
| [`docs/plan/preact-parity-sprint-board-D.md`](preact-parity-sprint-board-D.md) | (post-implementation) flip §Sprint D1 status marker to "Implemented" + evidence-section link | DoD §9 |

**Explicitly NOT touched:**

- Any `trust/`, `services/`, `components/` (Python), `orchestration/`, or
  `governance/` file — this is Frontend-Ring only.
- Any `wire/` field on the Python side; `__python_schema_baseline__.json`
  stays green (no engine change).
- Any e2e test hard-pinning bucket labels (that's D2 territory).
- `nav_model.ts` `NAV_MEMBERSHIP` (D-8 is deferred to Epic E per D0).
- `drizzle_session_repo.ts` (`close` is reused as-is; no schema change).
- `elapsedMsFrom` / D0 elapsed-timing path (FR-Q9-6 respect).

## 3. Task list

Task markers:
- `[red]` — write the test FIRST; must be seen to fail before impl.
- `[green]` — the implementation that flips the red test.
- `[verify]` — a check that runs after (arch test, grep, live browser walk).
- `[P]` — can run in parallel with siblings inside the same block.

Every FR from [spec §3](preact-parity-D1-quiz-frame.spec.md#3-functional-requirements-ears)
maps to at least one `[red]` + `[green]` pair or a `[verify]` — see §4 crosswalk.

### Block 0 — Baseline (green before red)

- **T0.1** Run baseline `make check` — confirm the tree is green *before* D1
  starts. Paste output. If red: stop and fix independently.
- **T0.2** From `frontend/`: `pnpm exec tsc --noEmit -p tsconfig.json` → 0
  errors. Paste output.
- **T0.3** From repo root: `.venv/bin/python -m pytest tests/architecture/ -q`
  → all pass. Paste output.

### Block 1 — Q-7 skill chip (translator + hook)

- **T1.1 [red]** In `quiz_item_vm.test.ts` add:
  (a) match case: `toQuizItemVM(q, skillsById)` returns `skillName === skill.name` and
      `accentVar === skill.accent_var`;
  (b) no-match: skillId not in map → `skillName === null`, `accentVar === null` (FR-Q7-1);
  (c) omitted `skillsById` (backward compat): both `null`.
  Run — must be RED (types/values mismatch). Paste failure.
- **T1.2 [green]** In `quiz_item_vm.ts`:
  (a) extend `QuizItemVM` with `skillName: string | null` + `accentVar: string | null`;
  (b) extend `toQuizItemVM(question, skillsById?: ReadonlyMap<string, { name: string; accent_var: string }>)`
      to look up + populate. If `skillsById` is omitted OR the id is missing, both fields are `null`.
  Re-run T1.1 → green. Paste.
- **T1.3 [red]** In `QuizView.test.tsx` add SSR case: a VM with `skillName` +
  `accentVar` set renders `quiz-skill-chip` containing the skill name with a
  dot styled by `accent_var` (FR-Q7-2). A VM with `skillName: null` renders
  NO `quiz-skill-chip` node (FR-Q7-1). Run — RED. Paste.
- **T1.4 [green]** In `QuizView.tsx`:
  (a) add a `frame` region above the item body (a small `<div>` wrapping chip / End / timer);
  (b) inside it render `{vm.skillName ? <span data-testid="quiz-skill-chip">…</span> : null}`.
  Re-run T1.3 → green. Paste.
- **T1.5 [red] [P]** In `use_quiz.test.ts` (or the co-located hook test file) add: `listQuizSkills(subject) → Skill[]` returns the seeded skills verbatim; still passes for empty. Run — RED. Paste.
- **T1.6 [green] [P]** In `use_quiz.ts` add:
  ```ts
  export async function listQuizSkills(
    ports: EnginePortBag,
    subject: string,
  ): Promise<Skill[]> {
    return ports.skillTaxonomy.list(subject);
  }
  ```
  and export it from the hook's returned bag. Keep `listSkillIds` (used by `resolveFocusMode`) unchanged.
  Re-run T1.5 → green. Paste.
- **T1.7 [green]** In `quiz/page.tsx`:
  (a) add `const [skillsById, setSkillsById] = React.useState<ReadonlyMap<string, Skill>>(new Map())`;
  (b) in Effect 1, after `listSkillIds` resolves, ALSO call `listQuizSkills` (parallel with the existing focus-param path — chained via `Promise.all`) and set `skillsById`. Ensure cancellation guard survives;
  (c) pass `skillsById` into `toQuizItemVM(state.item.question, skillsById)`.
- **T1.8 [red]** Add L1 test: chip persists across phase change from `answering` → `reviewing` for the same item (FR-Q7-4). Run — RED if not present. Paste.
- **T1.9 [green]** Confirm the `content` render path in both branches (`answering`, `reviewing`) is wrapped by the same `frame` region so the chip renders in both. Re-run → green. Paste.

### Block 2 — Q-8 End session (reducer + view + page)

- **T2.1 [red] [P]** In `quiz_screen_reducer.test.ts` add:
  (a) `end_session` from `answering` → `done` (score carries);
  (b) from `reviewing` → `done` (score carries);
  (c) from `loading` → no-op (stays `loading`);
  (d) from `done` → no-op (FR-Q8-2/6);
  (e) `finish` still routes semantically to `done` from `reviewing` (regression).
  Run — RED. Paste.
- **T2.2 [green] [P]** In `quiz_screen_reducer.ts`:
  (a) add `{ type: "end_session" }` to `QuizScreenAction`;
  (b) reducer case: from `answering` or `reviewing` → return `{ phase: "done", score: state.score }`; else return `state` unchanged.
  Re-run T2.1 → green. Paste.
- **T2.3 [red] [P]** In `QuizView.test.tsx` add:
  (a) `endSessionEnabled: true` → renders `quiz-end-session` button, clickable, fires the provided callback (FR-Q8-3, FR-Q8-4);
  (b) `endSessionEnabled: false` → button disabled or absent, click does not fire callback (FR-Q8-1);
  (c) button label is a plain-text learner-readable string.
  Run — RED. Paste.
- **T2.4 [green] [P]** In `QuizView.tsx`:
  (a) accept props `endSessionEnabled: boolean` + `onEndSession: () => void`;
  (b) inside `frame` region render `<button data-testid="quiz-end-session" onClick={onEndSession} disabled={!endSessionEnabled}>End session</button>` (or the label chosen).
  Re-run T2.3 → green. Paste.
- **T2.5 [red]** Add a page-level test in `quiz_page.test.tsx` (or the closest existing page-test file): mounting the page with a seeded engine + a session with tally `{correct:1,total:3}`, clicking `quiz-end-session` calls `closeSession({ sessionId, scoreCorrect:1, scoreTotal:3 })` and pushes to `/learn` (FR-Q8-4/5). Run — RED (no callback wired yet). Paste.
- **T2.6 [green]** In `quiz/page.tsx`:
  (a) add `onEndSession` callback mirroring `onFinish` at [`page.tsx:162`](../../frontend/app/(coach)/learn/quiz/page.tsx:162):
  ```ts
  const onEndSession = React.useCallback(() => {
    if (session == null) return;
    dispatch({ type: "end_session" });
    const { correct, total } = state.score;
    closeSession({ sessionId: session.id, scoreCorrect: correct, scoreTotal: total })
      .then(() => {
        router.push(screen("dashboard").route);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to end the session");
      });
  }, [session, state.score, closeSession, router]);
  ```
  (b) pass `endSessionEnabled={session != null && (state.phase === "answering" || state.phase === "reviewing")}` + `onEndSession={onEndSession}` into `<QuizView>`.
  Re-run T2.5 → green. Paste.

### Block 3 — Q-9 collapsible timer

- **T3.1 [red] [P]** Create `frontend/lib/translators/quiz_frame_timer.test.ts`
  with a table:

  | `startedAtIso` | `nowMs` | expected |
  |---|---|---|
  | `"2026-07-10T10:00:00.000Z"` (parses to `t0`) | `t0` | `"0:00"` |
  | same | `t0 + 59_000` | `"0:59"` |
  | same | `t0 + 60_000` | `"1:00"` |
  | same | `t0 + 600_000` | `"10:00"` |
  | same | `t0 - 5_000` (future clock) | `"0:00"` (clamp; FR-Q9-4) |
  | `null` | `t0` | `"0:00"` |
  | `"not-a-date"` | `t0` | `"0:00"` |

  Run — RED (module doesn't exist). Paste.
- **T3.2 [green] [P]** Create `quiz_frame_timer.ts`:
  ```ts
  export function formatElapsedFromStartedAt(
    startedAtIso: string | null,
    nowMs: number,
  ): string {
    if (startedAtIso == null) return "0:00";
    const parsed = Date.parse(startedAtIso);
    if (!Number.isFinite(parsed)) return "0:00";
    const elapsedMs = Math.max(0, nowMs - parsed);
    const totalSec = Math.floor(elapsedMs / 1000);
    const mm = Math.floor(totalSec / 60);
    const ss = String(totalSec % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  }
  ```
  Re-run T3.1 → green. Paste.
- **T3.3 [red] [P]** In `QuizView.test.tsx` add jsdom cases (interaction, not SSR):
  (a) `startedAtIso: null` → no `quiz-timer-reveal` in DOM (FR-Q9-1);
  (b) `startedAtIso` set → `quiz-timer-reveal` present, no `quiz-timer` in DOM (FR-Q9-2);
  (c) click `quiz-timer-reveal` → `quiz-timer` appears (FR-Q9-3);
  (d) click again (or its collapse affordance) → `quiz-timer` removed (FR-Q9-5);
  (e) `item_loaded` (component re-mounted with new key OR the `key` prop advances) → reveal returns to collapsed (FR-Q9-7).
  Run — RED. Paste.
- **T3.4 [green] [P]** In `QuizView.tsx` add a small inline `QuizTimer`
  sub-component (or a dedicated `QuizTimer.tsx` under `components/quiz/` if
  the JSX exceeds ~30 lines — plan §3.5 decides):
  ```ts
  function QuizTimer({ startedAtIso }: { startedAtIso: string }) {
    const [revealed, setRevealed] = React.useState(false);
    const [now, setNow] = React.useState(() => Date.now());
    React.useEffect(() => {
      if (!revealed) return;
      const id = setInterval(() => setNow(Date.now()), 1000);
      return () => clearInterval(id);
    }, [revealed]);
    if (!revealed) {
      return (
        <button
          type="button"
          data-testid="quiz-timer-reveal"
          onClick={() => setRevealed(true)}
          aria-label="Show timer"
        >
          Show timer
        </button>
      );
    }
    return (
      <div className="flex items-center gap-2">
        <span data-testid="quiz-timer" role="timer" aria-live="off">
          {formatElapsedFromStartedAt(startedAtIso, now)}
        </span>
        <button
          type="button"
          onClick={() => setRevealed(false)}
          aria-label="Hide timer"
        >
          Hide
        </button>
      </div>
    );
  }
  ```
  Render `{startedAtIso ? <QuizTimer startedAtIso={startedAtIso} /> : null}` inside the `frame` region. Note: `aria-live="off"` intentional — a screen reader should not chatter every second; the reveal itself is the accessible affordance (FR-Q9-8).
  Re-run T3.3 → green. Paste.
- **T3.5** Plan sub-decision — inline vs `QuizTimer.tsx`: if the inline JSX
  from T3.4 stays under ~30 lines and the `formatElapsedFromStartedAt` call
  is the only meaningful logic, **inline in `QuizView.tsx`**. If it grows
  past ~30 lines or the tests want to import `QuizTimer` directly, promote
  to `frontend/components/quiz/QuizTimer.tsx`. Either posture satisfies the
  spec; the promotion is a mechanical file split. Not gated.
- **T3.6 [green]** In `quiz/page.tsx`, key the `QuizView` (or the `frame` /
  `QuizTimer`) by `item.question.id` so a new item resets the reveal state
  (FR-Q9-7). Alternate: pass `key={item.question.id}` through a wrapping
  fragment/div. Confirm with T3.3(e).
- **T3.7 [green]** Pass `startedAtIso={session?.started_at ?? null}` into
  `<QuizView>`.

### Block 4 — Structural + regression

- **T4.1 [verify]** From `frontend/`:
  `pnpm exec vitest run components/quiz/ lib/translators/` → expect the S3 /
  S3.1 / S4 / S5 suites still green with the new suites added. Paste.
- **T4.2 [verify]** From `frontend/`:
  `pnpm exec vitest run tests/architecture/` → `test_frontend_layering.test.ts`
  green (F-R1: translator + timer helper pure; components hold no
  domain logic). Paste.
- **T4.3 [verify]** `pnpm exec tsc --noEmit -p tsconfig.json` → 0 errors. Paste.
- **T4.4 [verify]** Root: `.venv/bin/python -m pytest tests/architecture/ -q`
  → all pass. Paste.
- **T4.5 [verify]** Root: `make check` → green. Paste.
- **T4.6 [verify]** Grep audit (FR-X3):
  ```bash
  grep -rnE 'data-testid="quiz-(context|hint-toggle|submit|reveal|next|finish|progress)"' frontend/
  ```
  Every listed testid must still resolve to an element that renders. New
  testids `quiz-skill-chip`, `quiz-end-session`, `quiz-timer-reveal`,
  `quiz-timer` must appear at their new call-sites.

### Block 5 — Live browser walk + evidence

- **T5.1 [verify]** Start dev preview (`preview_start`), navigate to
  `/learn/quiz`, walk:
  (a) On load: **skill chip** shows the current item's skill name with a
      dot; **End session** button visible; **timer** collapsed (only
      "Show timer" reveal visible; no clock text in DOM). Paste an
      accessibility snapshot + a screenshot.
  (b) Click **Show timer** → clock renders `0:00` → within ~2s ticks to `0:02`.
      Paste a snapshot showing the clock reading.
  (c) Answer A → Submit → the chip and End session persist through Feedback
      (FR-Q7-4, FR-Q8-3); click Next; on the new item the timer is again
      collapsed (FR-Q9-7).
  (d) Click **End session** → land on `/learn` (dashboard). Paste the URL.
  (e) Zero console errors across the walk (`preview_console_logs`).

- **T5.2 [green]** Append newest-first line to `docs/adr/decisions.md`:
  ```
  ## 2026-07-10 — Sprint D1: extend QuizItemVM instead of introducing QuizFrameVM

  D1 (Quiz session-frame chrome, Q-7/Q-8/Q-9) extends `QuizItemVM` with two
  nullable fields (`skillName`, `accentVar`) rather than introducing a new
  `QuizFrameVM` translator + view slot.

  Why: two nullable fields is not a new abstraction; the frame's only
  cross-cutting derived data (Q-7's skill join) is per-item, so its home is the
  item VM. Q-8 (tally) and Q-9 (started_at) are read directly from React state
  (page-owned), so they need no VM. No G1 gate; `decisions.md` is the correct
  weight (per root AGENTS.md).

  Rejected alternative: a separate `QuizFrameVM` mirroring ADR-0025's coach
  surface VM — deferred until the item VM crosses ~8 fields (would need its
  own G1 ADR at that point).
  ```
- **T5.3 [green]** Flip the sprint board §Sprint D1 status marker to
  **Implemented** and add a "§ Implementation evidence" section mirroring
  S4's shape (§10 of `preact-quiz-progress-surface.spec.md`) with:
  (a) T0.1 baseline output, (b) each block's red-then-green output, (c)
  T4.x gate output, (d) T5.1 live-walk snapshots/screenshots.
- **T5.4 [green]** PR-body log: "**D1 shipped Q-7 + Q-8 + Q-9 for Epic D.**
  Inherited D0's corrected framings (P3, P8). Did NOT ship D2 (taxonomy) or
  D3 (Q-1b decision). No ADR (default posture — extend `QuizItemVM`;
  `decisions.md` line appended)."

---

## 4. FR → task crosswalk

Every FR from [`spec §3`](preact-parity-D1-quiz-frame.spec.md#3-functional-requirements-ears)
maps to at least one red + green (or verify) task. No FR is "tested by
inspection alone".

| FR | Red | Green | Verify |
|----|-----|-------|--------|
| FR-Q7-1 | T1.1(b/c), T1.3 (null path) | T1.2, T1.4 | T4.2 (arch), T5.1(a) |
| FR-Q7-2 | T1.3 | T1.4 | T5.1(a) |
| FR-Q7-3 | (structural) | T1.2 (pure translator) | T4.2 |
| FR-Q7-4 | T1.8 | T1.9 | T5.1(c) |
| FR-Q8-1 | T2.3(b), T2.5 (session null branch) | T2.4, T2.6 | T5.1(a) |
| FR-Q8-2 | T2.1(c/d) | T2.2 | T4.1 |
| FR-Q8-3 | T2.3(a) | T2.4 | T5.1(a) |
| FR-Q8-4 | T2.5 | T2.6 | T5.1(d) |
| FR-Q8-5 | T2.5 | T2.6 | T5.1(d) |
| FR-Q8-6 | T2.1(a/b/e) | T2.2 | T4.1 (existing finish tests stay green) |
| FR-Q9-1 | T3.3(a) | T3.4, T3.7 | T5.1 |
| FR-Q9-2 | T3.3(b) | T3.4 | T5.1(a) |
| FR-Q9-3 | T3.3(c) | T3.4 | T5.1(b) |
| FR-Q9-4 | T3.1 (7-row table incl. edge cases) | T3.2 | T5.1(b) |
| FR-Q9-5 | T3.3(d) | T3.4 | (walk) |
| FR-Q9-6 | (structural) | (no reducer edit here) | T4.1 (reducer tests unchanged around `presentedAt`/`elapsedMsFrom`) |
| FR-Q9-7 | T3.3(e) | T3.6 | T5.1(c) |
| FR-Q9-8 | T3.3 (button + label assertion) | T3.4 | (a11y snapshot in T5.1) |
| FR-X1 | (structural) | T1.2, T3.2 (pure) | T4.2 |
| FR-X2 | (structural) | (no new port) | T4.6 (grep) |
| FR-X3 | — | — | T4.1, T4.6 |
| FR-X4 | — | — | T5.1 (walk on desktop; iPad-split spec if run) |

---

## 5. Parallelization envelope

Blocks fire sequentially — each has an artifact the next reads/verifies.
Inside each block:

- **Block 0:** T0.1..T0.3 independent — run in parallel.
- **Block 1:** T1.1↔T1.2 and T1.5↔T1.6 are two independent red/green pairs,
  parallel-safe. T1.3/T1.4 (view) depends on T1.2 (VM shape). T1.7 (page
  wiring) depends on T1.6 (hook) + T1.4 (view). T1.8/T1.9 (persistence
  test) depends on T1.7. So: `{T1.1,T1.5}` → `{T1.2,T1.6}` → T1.3 → T1.4 →
  T1.7 → T1.8 → T1.9.
- **Block 2:** T2.1↔T2.2 (reducer) and T2.3↔T2.4 (view) are independent
  red/green pairs — parallel-safe (marked `[P]`). T2.5↔T2.6 (page wiring)
  runs last, depending on both.
- **Block 3:** T3.1↔T3.2 (helper) and T3.3↔T3.4 (view+jsdom) are
  parallel-safe. T3.5 is a plan sub-decision (no code). T3.6 depends on
  T3.4. T3.7 (page prop wiring) depends on T3.4.
- **Block 4:** all `[verify]` — parallel-safe.
- **Block 5:** sequential (walk → decisions.md → board flip → PR body).

Cross-block gates: Block 1's chip and Block 2's End session both edit
`QuizView.tsx` — merge/rebase between them if run truly in parallel; safer
posture is Block 1 → Block 2 → Block 3 in sequence with `[P]` inside each
block. That's the recommended order for a single-author run.

---

## 6. Definition of Done (D1)

Mirrors [spec §9](preact-parity-D1-quiz-frame.spec.md#9-definition-of-done).
All paste-into-PR items are in the block-level tasks above; the DoD is where
they land as a checklist for the reviewer:

- [ ] T0.1–T0.3 baseline outputs pasted.
- [ ] Each block's red-then-green pair has both outputs pasted (RED first,
      then GREEN — the "watched red" evidence the root `AGENTS.md` requires).
- [ ] T4.1–T4.5 gate outputs pasted.
- [ ] T4.6 grep audit output pasted (new testids present, existing testids
      still resolve).
- [ ] T5.1 live-walk snapshots + screenshots pasted; zero console errors.
- [ ] T5.2 `decisions.md` newest-first line committed in the same PR.
- [ ] T5.3 sprint board §Sprint D1 status flipped to **Implemented** with
      §Implementation-evidence section added.
- [ ] T5.4 PR body log line present.
- [ ] **No ADR authored** under the default posture; if the plan review
      flipped the shape to `QuizFrameVM`, ADR-0026 authored in the same PR
      (following ADR-0025's shape).
