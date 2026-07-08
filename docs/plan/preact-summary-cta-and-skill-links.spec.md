# Spec — PreAct Summary CTA contrast + tappable skill/bucket names (Sprint S1+S2)

**Status:** Implemented — 2026-07-08 (human-gated; T1–T7 landed red/green; all gates green +
CTA screenshots captured, §10). Follow-up: TodayFocusBanner twin-defect (task_4fd6b91b).
**Owner:** Rajnish Khatri
**Related:** [preact-ui-prototype-parity-gap-matrix.md](preact-ui-prototype-parity-gap-matrix.md)
(gaps **S-4**, **S-5**, **D-4**); SDD Stage 1 brainstorm `[[preact-ui-gap-brainstorm]]`.
Frontend Ring rules: `frontend/AGENTS.md` (F-R1, U6, FD4).

---

## 1. Goal

Two small, independently-testable UI fixes on the shipped `/learn` surface, closing
three prototype-parity gaps with **no engine change and no ADR**:

- **S1 (gap S-4):** the Session-Summary "Practice this next" CTA is currently white text
  on a pale per-bucket fill → effectively invisible. Make it legible (WCAG-AA).
- **S2 (gaps S-5, D-4):** the recommended-skill label on Summary and the six Dashboard
  bucket cards are inert text/articles. The prototype opens **Skill detail** on a
  bucket/skill click. Make the skill name + bucket cards navigable.

Audience: the single Phase-1 learner ("Maya"); dev/local scope (bank-in-UI already
verified there — production on-device DB is out of scope, per the brainstorm decision).

## 2. Context

The gap matrix (built from the prototype's own Playwright specs as oracle) found these
three as the smallest, zero-risk, "ship-and-validate-early" wins. Evidence:

- **S-4 (MEASURED, Stage-4 corrected):** `SummaryView.tsx:76` — the CTA uses
  `bg-[var(--accent)] text-on-accent`, but its parent `<section>` rebinds `--accent` to a
  **per-bucket** color (`accentVar`, `SummaryView.tsx:52`). Ground truth from the running
  app (`preview_inspect`): with an *Organization* recommendation the CTA renders
  `bg rgb(98,119,65)` (bucket olive `--color-bucket-organization`) + white text
  (`--color-on-accent: #ffffff`) = **≈3.6:1, FAILS WCAG-AA (4.5:1)**; the pale mauve buckets
  (Grammar/Conciseness `#926086`) are ≈4.9:1 (borderline). Root cause: the button inherits
  the **per-bucket accent** as its fill; mid/pale bucket tones + white text miss AA. Fix:
  fill with the **brand** accent (`--color-accent` = `#93513d` → white ≈ 6.5:1 ✓), which is
  bucket-independent. NOTE: `TodayFocusBanner.tsx:43` uses the *identical* pattern (also sets
  `--accent` to a bucket color) and shares this **latent** defect — out of scope for S1
  (Summary only), tracked for a follow-up so the same fix lands there.
- **S-5:** `SummaryView.tsx:64` — `skillName` is a static `<p>`; only the separate CTA is a
  `<Link>`. `RecommendedNextVM` already carries `skillId` (`session_summary_vm.ts:69`).
- **D-4:** `BucketCard.tsx` JSDoc claims "the card is a link to Skill detail (FR-C4)" but the
  JSX renders a plain `<article>` with no link/handler. `BucketCardVM` carries `skillId`
  (`bucket_card_vm.ts:40`).

**Prototype oracle (all 3 device specs):** a bucket-card click opens **Skill detail**
(`btn(/Rhetoric/).click()` → "The rule, in one line" / "Why you missed these"), and
"Drill this skill" then launches the quiz. Skill detail is `comingSoon` in the app
(`nav_model.ts:75`, deferred to S9), so this spec ships an **interim** navigation target
and re-points to Skill detail when S9 lands.

## 3. Functional requirements (EARS)

Failure/robustness paths first.

- **FR-1 (S1, failure path).** IF the recommended-next CTA renders on any bucket accent
  (including the palest, Conciseness/Grammar), THEN THE SYSTEM SHALL keep the CTA's
  text-vs-background contrast ratio ≥ 4.5:1 (WCAG-AA normal text).
- **FR-2 (S2, failure path).** IF the interim navigation target is the `comingSoon` Skill
  screen, THEN THE SYSTEM SHALL route the skill/bucket link to the **quiz** (not to a
  disabled/blank Skill route), so no control leads to a dead end.
- **FR-3 (S1).** THE SYSTEM SHALL render the "Practice this next" CTA with the **brand**
  accent fill (`--color-accent`), independent of the card's per-bucket `--accent`.
- **FR-4 (S2, Summary).** WHEN the learner activates the recommended-skill name on the
  Summary, THE SYSTEM SHALL navigate to the quiz focused on that skill
  (`/learn/quiz?focus=<skillId>`).
- **FR-5 (S2, Dashboard).** WHEN the learner activates a Dashboard bucket card, THE SYSTEM
  SHALL navigate to the quiz focused on that bucket's skill (`/learn/quiz?focus=<skillId>`).
- **FR-6 (S2, focus honored).** WHEN the quiz page loads with a `focus` search param naming
  a known skill, THE SYSTEM SHALL open the session as a **drill** on that skill
  (`openSession({ mode: "drill", focus })`); absent/unknown → adaptive (unchanged).
- **FR-7 (S2, a11y).** THE SYSTEM SHALL expose the skill name and each bucket card as a
  single semantic link/`<button>` (not a `<div onClick>`), keyboard-activorable, with an
  accessible name that includes the skill name (Rule U "interactive elements are
  `<button>`/`<a href>`").
- **FR-8 (S1, non-regression).** THE SYSTEM SHALL leave the CTA label ("Practice this
  next"), its route, and the three stat tiles unchanged.

## 4. Data model / contracts

**No new or changed wire shapes, schemas, or engine types.** `RecommendedNextVM.skillId`
and `BucketCardVM.skillId` already exist and are the only data consumed. `OpenSessionArgs.focus`
already exists (`use_quiz.ts:51`). This is a pure component + one page-wiring change; the
engine, Drizzle schema, and `wire/` are untouched → **no ADR trigger**.

## 5. Invariants & security boundaries

Frontend Ring invariants (`frontend/AGENTS.md`):

- **F-R1 (no domain logic in components):** the "which skill" decision already lives in the
  translators/`use_summary`/`use_dashboard`; components only render `skillId` into an
  `href`. The quiz page reading `?focus=` and forwarding it to `openSession` is thin glue,
  not domain logic (mirrors its existing `openSession({mode:"adaptive"})` call). **Holds.**
- **U6 / §13 (a11y, `cn()`, `<a>`/`<button>` only):** links use `next/link` `<Link>` (already
  imported in both files); classes via `cn()`. **Holds.**
- **FD4 (accessibility / WCAG-AA):** FR-1 is the AA contrast fix; FR-7 the semantic-link fix.
- No SDK import, no `trace_id`, no secrets, no sandboxing, no trust type, no live-LLM.
  Backend Architecture Invariants #1–#8 are **not touched** (frontend-only, no engine seam).

## 6. Edge cases

- **Palest bucket accent** (Conciseness `--color-bucket-concise`, Grammar): the exact case
  that fails today — FR-1 must hold for *every* bucket, tested against the worst one.
- **Dark theme:** the CTA + links must stay AA in `[data-theme="dark"]` too (bucket accents
  re-resolve; brand accent `--color-accent` also has a dark value).
- **`focus` param names an unknown/nonexistent skill:** FR-6 falls back to adaptive, never
  errors (guard in the quiz page).
- **`focus` present but the drill has no reviewed item for that skill:** the existing
  `openQuizItem`/`nextReviewed` path already surfaces "no reviewed question" — unchanged;
  not newly introduced by this spec.
- **Cold-start Dashboard** (no `todayFocus`): bucket cards still render and must still be
  navigable (FR-5 independent of the focus banner).

## 7. Non-functional requirements

- **Determinism:** fully deterministic; no LLM, no network. All tests run in `make check` /
  the frontend unit + e2e suites (no live path).
- **Reversibility:** trivially revertable (component-local + one page edit); no migration,
  no data change.
- **Latency/cost:** negligible; no new fetch. `?focus=` is read from the URL, not a request.

## 8. Test plan

Failure-path tests first. Frontend pyramid (`frontend/AGENTS.md` §20): Vitest+RTL (unit),
Playwright+axe (e2e). "L1" = deterministic unit; "e2e" = Playwright.

| FR | Test | Layer | In gate? |
|----|------|-------|----------|
| FR-1 | `e2e/learn/summary-cta.spec.ts` — axe/contrast on CTA over the palest bucket accent (+ dark) | e2e (axe) | yes (e2e) |
| FR-2 | `SummaryView.test.tsx` / `BucketCard.test.tsx` — link `href` targets `/learn/quiz…`, never the `comingSoon` skill route | L1 | yes |
| FR-3 | `SummaryView.test.tsx` — CTA class uses brand-accent fill, not the card `--accent` | L1 | yes |
| FR-4 | `SummaryView.test.tsx` — skill name is a link to `/learn/quiz?focus=<skillId>` | L1 | yes |
| FR-5 | `BucketCard.test.tsx` — card is a link to `/learn/quiz?focus=<skillId>` | L1 | yes |
| FR-6 | `quiz_page`/`use_quiz` test — `focus` param → `openSession({mode:"drill",focus})`; absent → adaptive | L1 | yes |
| FR-7 | `SummaryView.test.tsx` + `BucketCard.test.tsx` — accessible-name assertion; `a11y.spec.ts` axe sweep stays clean | L1 + e2e | yes |
| FR-8 | `SummaryView.test.tsx` — label/route/stat-tiles snapshot unchanged | L1 | yes |

## 9. Definition of Done

- [x] All FRs implemented; each has a passing test *seen to fail first* (red/green).
- [x] `make check` green + frontend unit (`pnpm test`) + `e2e/learn` (learn-e2e project) green.
- [x] Invariants in §5 unbroken (`tests/architecture/` + frontend layering test green).
- [x] No ADR needed (no ⚠️ trigger — confirmed §4). One `docs/adr/decisions.md` line for the
      interim-target choice (skill link → quiz-focus until S9 Skill detail lands).
- [x] Actual command output pasted (not summarized) for the verification claims — §10 below.
- [x] Screenshot: the CTA legible over the reported failing bucket, light+dark — §10 below.

## 10. Implementation evidence (2026-07-08)

**Files changed** (matches the plan's touchpoints; +149/−12):
- `frontend/components/summary/SummaryView.tsx` — CTA fill `bg-[var(--accent)]`→`bg-accent`
  (FR-1/3); skill name `<p>`→`<Link href=/learn/quiz?focus=<id>>` (FR-4).
- `frontend/components/dashboard/BucketCard.tsx` — card `<article>`→`<Link>` focus target (FR-5);
  stale JSDoc corrected.
- `frontend/app/(coach)/learn/quiz/page.tsx` — reads `?focus=`, resolves + forwards to
  `openSession` (FR-6).
- `frontend/components/quiz/resolve_focus_mode.ts` (NEW) + `use_quiz.ts` (`listSkillIds`) — the
  pure FR-6 decision + read-only taxonomy accessor.
- Tests: `resolve_focus_mode.test.ts` (NEW), `SummaryView.test.tsx` (+FR-3/4/8),
  `DashboardView.test.tsx` (+FR-5/2/7), `e2e/learn/summary-cta.spec.ts` (NEW, FR-1 axe + FR-4/5).

**Red→green trail:** FR-3 seen red (`expected '…bg-[var(--accent)]…' to contain 'bg-accent'`)
before the CTA swap; FR-4/FR-5 seen red (`Cannot read properties of null` — no link yet) before
the `<Link>` wraps; FR-6 seen red (module `resolve_focus_mode` unresolved) before the helper.

**Unit (`vitest run`, arch excluded):** `135 passed (135 files) · 1422 tests`.
- `SummaryView.test.tsx` — 8 passed · `DashboardView.test.tsx` — 9 passed ·
  `resolve_focus_mode.test.ts` — 5 passed · `components/quiz/` — 58 passed.

**Frontend architecture (`pnpm run test:arch`, ts-morph F-R1..F-R9 + port conformance):**
`170 passed (5 files)` — layering invariants (§5) unbroken.

**Backend architecture (`.venv/bin/python -m pytest tests/architecture/ -q`):**
`180 passed, 4 skipped` (identical to the pre-implement baseline — no regression).

**e2e (`playwright test --project=learn-e2e`, real dev bank path):** `34 passed (1.4m)` — the
full learn suite incl. a11y sweeps (light+dark), full-session, bank-integration, and the 4 new
`summary-cta` tests. FR-1 proven by axe `color-contrast` scoped to the recommended card, light
AND dark; FR-4/FR-5 by clicking the skill name / a bucket card → `/learn/quiz?focus=…` renders a
bank item.

**Screenshot (the reported failing case, `[data-testid=summary-recommended]`):** captured over the
**Organization** bucket — the exact tone measured worst pre-fix (~3.6:1 olive). Light: white on
brand terracotta `#93513d` (~6.5:1). Dark: dark text on `#e5967c`. Both legible; the CTA fill is
now bucket-independent while the card keeps its neutral border/tint. (Artifacts:
`summary-cta-light.png` / `summary-cta-dark.png`, produced by the `CTA_SHOT_DIR` hook in the spec.)
