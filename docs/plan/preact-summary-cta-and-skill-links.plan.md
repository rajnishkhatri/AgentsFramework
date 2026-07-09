# Plan + Tasks — PreAct Summary CTA + tappable skill/bucket names (S1+S2)

**Spec:** [preact-summary-cta-and-skill-links.spec.md](preact-summary-cta-and-skill-links.spec.md) (Clarified)
**Stage:** SDD 2 (plan) + 3 (tasks). No ADR (§4 of spec — no ⚠️ trigger; `decisions.md` entry recorded).

---

## Stage 2 — Plan

### Architecture

Pure Frontend-Ring change, three files of production code + their tests. **No engine,
no `wire/`, no Drizzle, no migration.** Data already flows: translators expose `skillId`
on both VMs; `openSession` already accepts `focus`. The work is (a) one className swap
(S1), (b) wrap two labels in `<Link>` (S2), (c) one thin quiz-page edit to read `?focus=`
(S2, the only behavioral wiring).

Dependency direction stays inward (F-R1): components read a VM `skillId` into an `href`
string; the quiz page (already the glue layer that calls `openSession`) reads the URL and
forwards `focus`. No new domain logic, no adapter/port/translator change.

### File-level touchpoints

| File | Change | FR |
|---|---|---|
| `frontend/components/summary/SummaryView.tsx` | S1: CTA fill `bg-[var(--accent)]`→brand `bg-accent` (+ `text-on-accent` kept); the card keeps its per-bucket `--accent` for border/bg only. S2: wrap `{skillName}` `<p>` in a `<Link href={/learn/quiz?focus=${skillId}}>`. | FR-1,3,4,7,8 |
| `frontend/components/dashboard/BucketCard.tsx` | S2: wrap the `<article>` body in a `<Link href={/learn/quiz?focus=${skillId}}>` (or make the card a link); keep `data-testid`, `role="progressbar"`, Due badge. Correct the stale "card is a link" JSDoc to match reality. | FR-2,5,7 |
| `frontend/app/(coach)/learn/quiz/page.tsx` | S2: read `useSearchParams().get("focus")`; if a known skill → `openSession({subject, learnerId, mode:"drill", focus})`; else adaptive (unchanged). | FR-6 |
| `frontend/components/summary/SummaryView.test.tsx` | Add FR-2/3/4/7/8 cases (renderToStaticMarkup+JSDOM). | — |
| `frontend/components/dashboard/DashboardView.test.tsx` | Add FR-2/5/7 bucket-link cases. | — |
| `frontend/e2e/learn/summary-cta.spec.ts` (NEW) | FR-1 axe/contrast over palest bucket, light+dark; FR-4 click→focused quiz. | — |
| `frontend/app/(coach)/learn/quiz/` test (unit for focus) | FR-6: focus param → drill; absent → adaptive. | — |

### Migration steps

None. No schema, no data, no dependency (`package.json` untouched). Reversible by revert.

### Constitution check (AGENTS.md)

- ⚠️ Ask-first list: none triggered (no new dep, no trust type, no graph node, no new
  service, no new abstraction). Confirmed no ADR.
- Invariants #1–#8 (backend layering): untouched — frontend-only.
- Frontend F-R1/U6/FD4: held (see spec §5).
- Baseline before implement: `make check` + `pytest tests/architecture/ -q` green;
  frontend `pnpm test` + `learn-e2e` green.

---

## Stage 3 — Tasks

Atomic, file-level, red/green. Markers: **[P]** = parallelizable; **→Tn** = depends on Tn.
Each task ends by checking its mapped EARS criteria. Failure-path tasks first.

### T1 — S1 CTA contrast (FR-1, FR-3, FR-8) **[P]**
- Edit `SummaryView.tsx`: CTA `<Link>` fill → brand `bg-accent text-on-accent` (drop the
  card-inherited `bg-[var(--accent)]`). Leave label, route, stat tiles unchanged.
- **Red first:** `SummaryView.test.tsx` — assert CTA className contains the brand-accent
  fill token and NOT `bg-[var(--accent)]` (FR-3); assert label/route/tiles unchanged (FR-8).
- **Verify:** `pnpm test SummaryView` green.

### T2 — S1 contrast e2e/axe (FR-1) **→T1**
- New `e2e/learn/summary-cta.spec.ts`: drive `/learn/summary` (session with a
  Grammar/Conciseness recommendation), run `@axe-core/playwright` scoped to the CTA;
  assert no contrast violation. Repeat with `colorScheme: dark`.
- **Red first:** run against pre-T1 code → contrast failure; after T1 → pass.
- **Verify:** `learn-e2e` green on the new spec, light+dark.

### T3 — S2 quiz page honors `focus` (FR-6) **[P]**
- Edit `quiz/page.tsx`: `const focus = useSearchParams().get("focus")`; validate against
  known skills (via the engine/taxonomy the page can reach or a guard); pass
  `{mode:"drill", focus}` to `openSession` when valid, else current adaptive call.
- **Red first:** unit test — `focus="s-punc"` → `openSession` called with `mode:"drill",
  focus:"s-punc"`; `focus=null`/unknown → `mode:"adaptive"`, no focus (FR-6 + edge).
- **Verify:** `pnpm test` on the quiz-page/use_quiz test green.

### T4 — S2 Summary skill-name link (FR-4, FR-2, FR-7) **→T3** (target route must be honored)
- Edit `SummaryView.tsx`: wrap `{skillName}` in `<Link href={/learn/quiz?focus=${skillId}}>`;
  accessible name = skill name; never link to the `comingSoon` skill route (FR-2).
- **Red first:** `SummaryView.test.tsx` — skill name is an `<a>` with
  `href="/learn/quiz?focus=s-conc"` (FR-4); href is not `/learn/skill` (FR-2); has an
  accessible name (FR-7).
- **Verify:** `pnpm test SummaryView` green.

### T5 — S2 Dashboard bucket-card link (FR-5, FR-2, FR-7) **→T3** **[P with T4]**
- Edit `BucketCard.tsx`: make the card a link to `/learn/quiz?focus=${skillId}`; keep
  `data-testid`, progressbar, Due badge; fix the stale JSDoc.
- **Red first:** `DashboardView.test.tsx` — `bucket-s-punc` is/contains an `<a>` with
  `href="/learn/quiz?focus=s-punc"` (FR-5); not `/learn/skill` (FR-2); accessible name
  includes the bucket name (FR-7).
- **Verify:** `pnpm test DashboardView` green.

### T6 — S2 focused-drill e2e (FR-4, FR-5 live) **→T4, T5, T2**
- Extend `summary-cta.spec.ts` (or add to it): click the Summary skill name → URL is
  `/learn/quiz?focus=…` and a quiz item renders; from `/learn`, click a bucket card →
  same. (Uses the real dev bank path — no seed override, per the bank-integration spec.)
- **Verify:** `learn-e2e` green.

### T7 — Gate + evidence (DoD) **→T1..T6**
- Run `make check`, `pytest tests/architecture/ -q`, `pnpm test`, `learn-e2e`.
- Screenshot the fixed CTA over Grammar & Usage, light + dark (the reported failing case).
- Paste actual output into the spec's DoD; flip spec Status → Implemented.
- **Verify:** all gates green; a11y sweep (`a11y.spec.ts`) still clean.

### Dependency graph
```
T1 ─┬─ T2 ──┐
    │        │
T3 ─┼─ T4 ──┼─ T6 ─── T7
    └─ T5 ──┘
```
T1 and T3 are the two independent roots (S1 vs S2-wiring). T4/T5 need T3 (route honored).
T2 needs T1. T6 needs T2+T4+T5. T7 is the final gate.

### EARS → task coverage (Stage-3 completeness check)
FR-1→T1/T2 · FR-2→T4/T5 · FR-3→T1 · FR-4→T4/T6 · FR-5→T5/T6 · FR-6→T3 · FR-7→T4/T5 ·
FR-8→T1. Every FR maps to ≥1 task with a red-first test. ✅
