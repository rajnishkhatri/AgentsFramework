# Epic F — Implementation Handoff

> **You are the implementing agent.** This is a self-contained handoff for building the PreAct parity
> program's **final** epic: the Progress screen at `/learn/progress`. All decisions are made and gated;
> your job is **sdd-implement** (red→green through the task list). Do not re-open the design or scope —
> the human closed every gate on 2026-07-13. If something here contradicts the code you find, trust the
> code and flag it; these docs were written 2026-07-13 against the branch tip below.

---

## 0. TL;DR — what you're building

`/learn/progress` today 404s. Build it as **one honest, bundled surface**: a header (streak + total
items reviewed), a range toggle (30 days / All time), an **accuracy-trend line** drawn from the
learner's own closed-session history, and 6 mastery-by-bucket bars. The prototype also shows a
**projected ACT score** ("26 · goal 28") — that has **no honest data source** and is **deferred to a
future epic (D4)**. You must **NOT** render any projected score, goal, or "on track" text. That
self-omission (FR-3) is the load-bearing invariant of this epic.

**Pure composition. No new wire type, no new port, no new adapter, no engine write, no migration, no new
dependency, no ADR.** One new translator + one new hook + one new view + one new SVG chart + one new
page + one nav-flip, plus their tests.

## 1. Read these first (the SDD artifact chain, in order)

All under `docs/plan/`, all committed on the branch base (§3):

1. **`preact-parity-epic-F.brainstorm.md`** — Stage 1. The premise audit (why the epics-doc was stale)
   + the 6 candidate directions + the gate decision. *Read for context; the decision is already applied.*
2. **`preact-parity-epic-F.spec.md`** — Stage 2. **14 EARS functional requirements (FR-1…FR-14).**
   *This is your contract.* Failure/empty paths first. FR-3 (no projected score) is non-negotiable.
3. **`preact-parity-epic-F.plan.md`** — Stage 3+4. Architecture, the **design tasks (§6.5, DT-1…DT-7,
   with the 3 design forks DECIDED)**, and the **atomic task decomposition (§7, T0…T6)**. *This is your
   build order.*

**Local-only caveat:** the ultimate design source-of-truth `PreAct/UI-Design/design-spec.md` §5.7 is
**untracked** (local to the author's machine) — it may be absent in your checkout. The relevant §5.7
text is quoted inside the spec §2 and plan §6.5, and the prototype PNG **is** tracked at
`docs/plan/assets/preact-parity-2026-07-09/proto/07-progress.png` (view it). Do not block on the
untracked design-spec.

## 2. The decisions — do not re-open (all gated by the human 2026-07-13)

| Gate | Decision | Where enforced |
|------|----------|----------------|
| Direction | **Bundled** (one epic, not split) × **D3** (honest series now); **D4** (real projected-score model) **deferred** | whole epic |
| Trend series | **Per-session accuracy** over time (not cumulative items) | FR-7 |
| Score slot | **Self-omit entirely** (no "coming soon" placeholder) | FR-3 |
| Q-D1 card layout | **Full-width line**, caption "Accuracy trend", **no left column** | plan §6.5, T4 |
| Q-D2 chart idiom | **New hand-built SVG polyline** + per-point markers (NOT reuse `AccuracyBars`) | plan §6.5, T2 |
| Q-D3 mastery bars | **New horizontal bar-rows** (dot+name+track/fill+%+DUE), NOT the Dashboard `BucketCard` grid | plan §6.5, T4 |

**Honesty rule (project-wide AP-6 / "don't forge the stamp"):** no fabricated projected score. The
`ProgressRepo`/`ProgressPoint.projected_score` seam exists but has no honest write path — leave
`ports.progressRepo` **unconsumed** (it's the dormant D4 seam). Precedent: Epic E gated Tutorial content
the same way; ADR-0021 made bank items earn `reviewed`.

## 3. Branch base — IMPORTANT (do not branch from main)

- **Branch `feat/preact-parity-epic-F` from the current Epic-E tip: `bed27ce`**
  (`Merge pull request #157 from rajnishkhatri/feat/preact-parity-epic-E`).
- **Why not main:** Epic F re-composes E1b's accuracy read (`6fcb9e9`) + ADR-0029 (mastery-from-stability),
  which are **8 commits ahead of main and NOT yet merged**. Branch from main and the mastery signal +
  accuracy plumbing this epic depends on will be **absent**. (If/when Epic E merges to main, branching
  from the updated main is equivalent.)
- Repo interpreter caveat: use the repo `.venv/bin/python` only; if you work in a git worktree, symlink
  the root `.venv` into it or pyright throws phantom errors.

## 4. The 3 planning docs are UNTRACKED — commit them first

`brainstorm.md`, `spec.md`, `plan.md` (and this HANDOFF.md) are currently `??` untracked in the working
tree. **Before you start, commit all four to the new branch** so your work has its spec/plan under
version control (and so a fresh checkout has them). Suggested first commit on the new branch:
`docs(epic-F): SDD brainstorm + spec + plan + handoff for /learn/progress`.

## 5. What already exists (verified tracked on `bed27ce`) — reuse, don't rebuild

| Building block | Path | Use |
|----------------|------|-----|
| Closed-session read (the ONE honest data source) | `SessionRepo.listByLearner(subject, learnerId, {sinceISO?})` — `frontend/lib/ports/engine/session_repo.ts:41,80`; in `EnginePortBag` at `composition_engine.ts:72` | trend x-axis (`ended_at`), accuracy series (`score_correct/score_total`), items total (`Σ score_total`), range filter (`sinceISO`) |
| `QuizSession` shape | `frontend/lib/wire/engine_entities.ts:203-219` — carries `ended_at`, `score_correct`, `score_total` | the trend's raw rows |
| Streak translator | `toStreakVM(closedSessions, nowISO)` — `frontend/lib/translators/streak_vm.ts:37` | header streak (FR-11) |
| Bucket translator | `toBucketCardVM(skill, skillState, nowISO)` — `frontend/lib/translators/bucket_card_vm.ts:29`; composed at `frontend/components/dashboard/use_dashboard.ts:143-164` (`skillRepo` + `learnerRead.listSkillState` → `stateBySkill` Map → `map`) | 6 mastery bars data (FR-12), ADR-0029 corrected mastery |
| Honest-null pattern to MIRROR | `frontend/lib/translators/skill_detail_vm.ts:383` (`if (inputs.accuracy == null) return null;`) | the FR-3 self-omit discipline |
| a11y-label template (NOT the chart) | `frontend/components/learn/AccuracyBars.tsx` — div bars, `role="group"` + per-bar `role="img" aria-label` | mirror its per-element-label a11y for the new SVG chart's fallback |
| Route/hook seam to MIRROR | `frontend/app/(coach)/learn/skill/page.tsx` (`'use client'`, `LEARNER_ID="Garvit"`, `DEFAULT_SUBJECT`) → `frontend/components/learn/use_skill_detail.ts` (`useEngine()` → `load*` → translator) → `SkillDetailView.tsx` | exact pattern for `progress/page.tsx` → `use_progress_screen.ts` → `ProgressView.tsx` |
| DORMANT — leave unconsumed | `ports.progressRepo` (`frontend/lib/ports/engine/progress_repo.ts`) | the D4 seam; do NOT wire it |

**6 bucket accent tokens** (design-spec §, for the bar-rows): `--b-rhetoric #d87758 · --b-usage #c0863a ·
--b-punct #4f9d8b · --b-org #7a9450 · --b-struct #5b7fa6 · --b-concise #a06a93` (+ dark variants;
re-resolve via `data-theme`). Footer rule: **"color never the only signal"** (WCAG-AA) — DUE is a text
badge, % is a number, the line has markers.

## 6. Files you will create / edit (from plan §1)

```
CREATE app/(coach)/learn/progress/page.tsx            'use client' → useProgressScreen → <ProgressView/>
CREATE components/learn/use_progress_screen.ts         useEngine() → loadProgressScreen(ports,…) → ProgressScreenVM
CREATE components/learn/ProgressView.tsx               header + RangeTabs + TrendChart + horizontal bucket bar-rows + empty state
CREATE components/learn/TrendChart.tsx                 hand-built SVG polyline + markers + a11y fallback (INLINE, one consumer — G1)
CREATE lib/translators/progress_screen_vm.ts           PURE T1: (closedSessions, buckets, range, nowISO) → ProgressScreenVM
CREATE *.test.ts / *.test.tsx co-located per file      red→green
CREATE e2e/learn/validate_epic_f_progress.spec.ts      smoke: nav→render, tab toggle, axe, iPhone no-dead-control
EDIT   components/shell/nav_model.ts:76                 comingSoon: true → false   (the flip)
EDIT   components/shell/AppNav.test.tsx:27              rewrite: Progress is now a live <a href> (was disabled non-link)
EDIT   components/shell/nav_model.test.ts:82            add /learn/progress to the wired-routes snapshot
EDIT   docs/adr/decisions.md                            2–4 line entry (NO ADR file — no ⚠️ trigger fires)
```

## 7. Build order (plan §7 — follow exactly, red→green each)

- **T0** Branch off `bed27ce` (§3). Capture baseline: full frontend `pnpm vitest run` +
  `test_frontend_layering.ts` + `make check` all green. Record counts (nav-flip landmine evidence).
- **T1** Translator `progress_screen_vm.ts` + test. **Write the 9 failure/empty-first tests, watch them
  fail, then implement.** Reductions: trend points = `{atISO: ended_at, accuracyPct: round(100*correct/total)}`
  (drop `score_total===0` rows), oldest→newest; `itemsReviewed = Σ score_total`; streak via `toStreakVM`;
  buckets passthrough. **No `projectedScore` key on any type** (FR-3).
- **T2** `[P]` `TrendChart.tsx` (SVG polyline + markers + a11y fallback) + test.
- **T3** `[P]` `use_progress_screen.ts` (loader computes `sinceISO` for 30d, omits for all-time) + test.
- **T4** `ProgressView.tsx` (header + range tabs + trend card + horizontal bar-rows + empty state) + test.
- **T5** `progress/page.tsx` + **flip `nav_model.ts:76` IN THE SAME TASK** (never a separate commit —
  FR-5 dead-control ban) + **reconcile the 2 inverted nav tests** (T5.3 below).
- **T6** e2e smoke + **FULL** vitest (not per-suite) + layering + `make check` green. **FR-3 double-check:**
  grep built VM + DOM for `projected|goal|on track|score` → none; confirm `progressRepo` still unconsumed.
  Add the `decisions.md` line.

## 8. The landmine — the nav flip inverts 2 existing tests (E1a lesson)

The instant you flip `nav_model.ts:76`, these two **currently-passing** tests fail. Fix them **in T5**:

1. **`components/shell/AppNav.test.tsx:27`** — `"iPhone: coming-soon Progress renders as a disabled
   non-link"` asserts Progress has `aria-disabled="true"`, is not an `<a>`, no `href`. **Rewrite** it to
   assert Progress is now a live `<a href="/learn/progress">` (mirror the E1a `skill` conversion at
   `nav_model.test.ts:111` `"skill screen is live (not comingSoon)"`).
2. **`components/shell/nav_model.test.ts:82`** — the wired-routes snapshot
   (`SCREENS.filter(s => !s.comingSoon).map(s => s.route)`) **gains** `/learn/progress`. Update the
   expected list. (The generic invariant at `:57-67` "disabled ⇔ comingSoon" stays valid unchanged.)

**Run the FULL vitest, not per-suite** — "green per-suite ≠ green branch." These are the ONLY tests you
may weaken/flip; each is justified by the intended behavior change (Progress is now live). No other
assertion is touched (G8 test-mass-rewrite gate).

## 9. Definition of Done (merge gate)

- [ ] All FR-1…FR-14 implemented; each test **seen red first**, then green.
- [ ] `progress_screen_vm.ts` pure T1 (no SDK/React/I-O); `TrendChart` built inline (G1, one consumer).
- [ ] Nav flip landed WITH the page; the 2 inverted tests reconciled; no other test weakened.
- [ ] **FR-3 double-verified:** translator `no-score-key` test + e2e DOM grep both clean;
      `ports.progressRepo` has zero product consumers.
- [ ] **FULL** frontend vitest + `test_frontend_layering.ts` + `make check` green — **paste the actual
      output, do not summarize** (project rule: evidence, not assertions).
- [ ] e2e smoke green + `@axe` clean; iPhone surface hides the range tabs by layout (no dead control).
- [ ] `docs/adr/decisions.md` line added (no ADR file); brainstorm ↔ spec ↔ plan ↔ this handoff cross-linked.

## 10. Constitution reminders (frontend ring)

- **F-R1** no domain logic in components — the accuracy/items/range math lives in the translator; the
  page/hook/view are thin.
- **F-R2 / T1** no SDK in translators — `progress_screen_vm.ts` imports `wire/` + sibling VMs only.
- **G1** the SVG `TrendChart` is inline (one consumer). Promote to a shared primitive only if a 2nd
  consumer lands — do NOT pre-abstract.
- **No ADR** this epic (no new dep/port/graph-node/trust-type). D4 — the `insertProgress` write seam + the
  ACT score model + the psychometric correctness question — is the ADR-bearing FUTURE epic. Don't touch it.
