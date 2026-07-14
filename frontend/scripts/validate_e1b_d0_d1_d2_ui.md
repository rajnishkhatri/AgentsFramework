# E1b Manual UI Walkthrough — D0 + D1 + D2 (PR #156)

**Epic:** E1b · **PR:** [#156](https://github.com/rajnishkhatri/AgentsFramework/pull/156) · **Branch:** `feat/preact-parity-epic-E`

| Artifact | Path |
|---|---|
| D0 spec | [`docs/plan/preact-parity-E1b-D0-mastery-write-path.spec.md`](../../docs/plan/preact-parity-E1b-D0-mastery-write-path.spec.md) |
| D1 spec | [`docs/plan/preact-parity-E1b-D1-accuracy-read.spec.md`](../../docs/plan/preact-parity-E1b-D1-accuracy-read.spec.md) |
| D2 spec | [`docs/plan/preact-parity-E1b-D2-coach-seed.spec.md`](../../docs/plan/preact-parity-E1b-D2-coach-seed.spec.md) |
| ADR-0029 | [`docs/adr/0029-mastery-from-stability.md`](../../docs/adr/0029-mastery-from-stability.md) |
| ADR-0030 | [`docs/adr/0030-lesson-coach-seed-contract.md`](../../docs/adr/0030-lesson-coach-seed-contract.md) |
| L4 validation | [`e2e/learn/validate_e1b_d0_d1_d2.spec.ts`](../e2e/learn/validate_e1b_d0_d1_d2.spec.ts) |

This runbook is the **manual** half of E1b UI validation. Tick every `[ ]` as you
confirm it. Prefer a hard refresh (`Cmd+Shift+R`) between parts that say so — the
in-memory engine bag resets on full reload.

> `/learn` is a **pure on-device engine** (InMemoryEngineDb + Garvit seed + lesson seed).
> Middleware is optional for D0/D1; D2 coach chrome does not need a live coach stream.

---

## What you should expect to SEE (acceptance bar)

| # | Deliverable | Expect |
|---|---------|--------|
| D0 | Dashboard mastery | After several **wrong** Punctuation grades, bucket mastery stays **low** (not ~100%) |
| D1 | `accuracyStat` | Returning `s-punc` shows **64%** + **6 bars** + footnote naming mastery **28%** as a different number |
| D1 | Self-omit | With no on-skill attempts, **no** `accuracyStat` block (never a padded zero chart) |
| D2 | Open coach | From returning lesson → `/learn/coach` **without** `Current item`; mode **In-drill Socratic** |
| D2 | Stale pin | After a quiz Ask-coach item pin, lesson Open coach **clears** Current item |

### Seed (why the numbers look like this)

| Piece | Source | What it gives you |
|-------|--------|-------------------|
| Learner **Garvit** | [`_dev_seed.ts`](../lib/adapters/engine/_dev_seed.ts) | `s-punc` mastery **28%**, due; ≥6 closed sessions with punc accuracy |
| Accuracy tallies | same | Aggregate **9/14 → 64%**; newest-first bars **100 · 50 · 75 · 0 · 100 · 50** |
| Lesson | [`_lesson_seed.ts`](../lib/adapters/engine/_lesson_seed.ts) | Full teaching fields for **`s-punc`** |

---

## Part 0 — Boot the UI

From `frontend/`:

```bash
cd frontend
E2E_BYPASS_AUTH=1 pnpm dev
```

- [ ] **0.1** Open **http://localhost:3000/learn** — Home loads for Garvit (not WorkOS login).
- [ ] **0.2** Hard-refresh once so you are not on a stale HMR shell.

### Automated proof (run this first)

```bash
cd frontend
E2E_BYPASS_AUTH=1 pnpm test:e2e:e1b
```

---

## Part 1 — D0 mastery write-path (ADR-0029)

Goal: wrong answers must **not** pin mastery near 100% (the pre-fix F1 bug).

1. Hard-refresh **http://localhost:3000/learn**.
2. Note Punctuation mastery on `[data-testid="bucket-s-punc"]` (seeded ~28%).
3. Open **http://localhost:3000/learn/quiz?focus=s-punc**.
4. Submit **three wrong** answers in a row (pick a wrong choice → Submit → Next → repeat).
5. Click **End session** (not Finish) → land on `/learn` **without** a full browser reload if possible.
6. Read Punctuation mastery again.

- [ ] **1.1** Mastery is **well below 50%** (typically much lower after collapses).
- [ ] **1.2** Mastery is **not** ~100% / full bar (that was the D0 bug).

---

## Part 2 — D1 accuracyStat (dev seed)

Open **http://localhost:3000/learn/skill?skillId=s-punc&context=returning** (full navigation).

- [ ] **2.1** `[data-testid="skill-detail"]` visible; rail includes `[data-testid="block-accuracyStat"]`.
- [ ] **2.2** `[data-testid="accuracy-value"]` reads **64%**.
- [ ] **2.3** Exactly **6** bars under `[data-testid="accuracy-bars"]`
  (`accuracy-bar-0` … `accuracy-bar-5`).
- [ ] **2.4** Footnote `[data-testid="accuracy-mastery-footnote"]` reads:
  **Not your mastery estimate (28%) — accuracy is a different number**
- [ ] **2.5** The Accuracy label is **not** showing the mastery scalar as a substitute.

### Self-omit (optional / Playwright covers)

With the e2e corpus override (no attempt history), returning `s-punc` still shows
`coachEntry` but **no** `block-accuracyStat`.

---

## Part 3 — D2 lesson coach seed (ADR-0030)

Stay on (or reopen) **http://localhost:3000/learn/skill?skillId=s-punc&context=returning**.

- [ ] **3.1** `[data-testid="coach-entry-seam"]` (**Open coach**) is visible on the rail.
- [ ] **3.2** Click it → URL `/learn/coach`.
- [ ] **3.3** ✅ **ABSENT:** `[data-testid="coach-current-item"]` / “Current item:”.
- [ ] **3.4** Mode chrome shows **In-drill Socratic** (`pre_submit`).
- [ ] **3.5** ✅ **ABSENT:** any “correct answer” reveal copy.

### Stale-pin overwrite (manual soft-nav)

1. From the returning lesson, click a **Drill →** link in the due checklist (soft-nav).
2. Answer **wrong** → **Ask the coach** → confirm **Current item** appears.
3. Coach **← Back** → quiz, then browser **Back** to the lesson (do **not** hard-refresh).
4. Click **Open coach** again.

- [ ] **3.6** Current item is **gone**; mode stays In-drill Socratic (lesson pin won).

---

## Selectors cheat-sheet

| UI | `data-testid` |
|---|---|
| Bucket mastery | `bucket-s-punc` · `[role=progressbar]` `aria-valuenow` |
| Accuracy block | `block-accuracyStat` · `accuracy-value` · `accuracy-bars` · `accuracy-bar-N` |
| Mastery footnote | `accuracy-mastery-footnote` |
| Open coach | `coach-entry-seam` |
| Coach item chrome | `coach-current-item` (must be absent for lesson pin) |
| Quiz ask coach | `feedback-ask-coach` |

---

## Task → FR → step map

| Dir | FR | Manual / automated |
|---|---|---|
| D0 | FR-1 / FR-2 | Part 1 · `validate_e1b_d0_d1_d2` D0 describe |
| D1 | FR-3 / FR-4 / FR-6 | Part 2 · D1 value+bars describe |
| D1 | FR-1 self-omit | Playwright D1 second test |
| D2 | FR-3 / FR-5 / FR-7 | Part 3 · D2 first test |
| D2 | FR-1 stale overwrite | Part 3.6 · D2 second test |
