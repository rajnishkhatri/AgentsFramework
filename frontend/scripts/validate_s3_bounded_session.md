# S3 Manual Validation Runbook — Bounded No-Repeat Quiz Session

**Spec:** [`docs/plan/preact-quiz-target-count.spec.md`](../../docs/plan/preact-quiz-target-count.spec.md) · **ADR:** [`docs/adr/0023-quiz-bounded-session-target-count.md`](../../docs/adr/0023-quiz-bounded-session-target-count.md)

This is the step-by-step, human-followable companion to
[`validate_s3_bounded_session.ts`](validate_s3_bounded_session.ts). Follow it top to
bottom; tick each `[ ]` box as you confirm it.

**What S3 shipped** (two groups):
- **(a) `target_count` field** — a nullable session-length field on `QuizSession`
  (`null` = endless; omitted = per-mode default **30**).
- **(b) within-session no-repeat** — a session never serves the same question twice;
  when the weakest skill is used up it falls through to the next; when everything
  servable is exhausted it ends (throws) rather than repeating.

**Scope honesty (read once):** `target_count` is *stored* but **not rendered** until
S4 (no "12 of 30" progress bar yet), and there is **no visible "done" screen** until
S5. So group **(a)** is only checkable via the automated harness (Part 1); the
**no-repeat** behavior of group **(b)** is what you can actually *see* in the browser
(Part 2).

---

## Part 0 — One-time setup

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
```

- [ ] **0.1** Dependencies installed (`node_modules/` present). If not: `pnpm install`.
- [ ] **0.2** `tsx` is available at `./node_modules/.bin/tsx` (it is — used below).

> ⚠️ **Always run from `frontend/` with the local binary** (`./node_modules/.bin/...`).
> Running vitest/tsx from the repo root or via `npx` pulls in stale worktree copies
> and a cache that's missing `jsdom`.

---

## Part 1 — Automated checks (run the harness)

This drives the **real engine seams** — the same adapter classes the browser wires
(`InMemoryEngineDb` + the Drizzle repos + `TestItemQuestionRepo` + `FsrsScheduler` +
the `use_quiz` served-ids derivation) — against the **actual dev corpus** (Maya + the
171-item governed bank). Deterministic; no browser, no network.

```bash
./node_modules/.bin/tsx scripts/validate_s3_bounded_session.ts
```

- [ ] **1.1** Command exits **0**.
- [ ] **1.2** Last line reads **`Result: 22 passed, 0 failed`** (no `Failures:` line).

If it prints `1 failed` (or more), the named check is the acceptance criterion that
regressed — read the `✗ FR-… — …` line; the `— expected X, got Y` detail tells you
what broke. Exit code is `1` on any failure.

### What each check proves (so you can spot a wrong pass)

**Group (a) — `target_count` field (FR-1..8)**

- [ ] **FR-1** `QuizSession` **rejects** `target_count` = `0` / `-1` / `2.5` / `NaN`.
- [ ] **FR-2/4** accepts a **positive int** *and* an **explicit `null`** (endless).
- [ ] **FR-5** `open()` with no target resolves the **default 30** (both `adaptive`
  and `drill`).
- [ ] **FR-6** an **explicit `12`** wins over the default.
- [ ] **FR-2** an explicit **`null` = endless** (distinct from omitted → default).
- [ ] **FR-7** `close()` stores the score tally but leaves `target_count` **unchanged**.
- [ ] **FR-8** `target_count` **round-trips** through the DB seam (`open` → `get`).

**Group (b) — within-session no-repeat (FR-9..13)**

- [ ] **FR-13** `servedQuestionIds(sessionId)` returns *this* session's answered ids
  (any correctness) and does **not** leak another session's ids.
- [ ] **FR-9** a **30-item walk never re-serves** a question.
- [ ] **FR-9 (control)** *without* served-ids the **same** item re-serves every call —
  proves the exclusion is what prevents repeats (a real negative control, not a tautology).
- [ ] **FR-10** exhaust the weakest skill (`s-punc`) → the next pick is a **different
  skill**, and that fell-through item is itself **unserved**.
- [ ] **FR-11** walking to exhaustion ends by **throwing** (`EngineNotFoundError`),
  never by repeating.
- [ ] **FR-12** excluding the only reviewed item returns **`null`**, never surfaces an
  **unreviewed** one (the reviewed-gate holds under exclusion).
- [ ] **FR-13 (purity)** a `next()` that uses served-ids performs **zero**
  `skill_state` writes (read-only).

**Group (c) — round-robin skill rotation (S3.1, FR-1/3 — ADR-0024)**

- [ ] **FR-3** a **24-item real-bank walk** never serves the same skill twice in a
  row and spreads across **≥3 skills** — the fix for "after finishing a skill the
  next is always sentence-completion."
- [ ] **FR-1** with an **empty served set** the first pick is still weakest-first
  (`s-punc`) — rotation is opt-in, backward-compatible.

**Scope boundary**

- [ ] **FR-14** exhaustion is a *serving* signal (a thrown not-found), **not** a
  rendered done-state (that's S5).

> To print only the UI walkthrough (skip the automated block):
> `./node_modules/.bin/tsx scripts/validate_s3_bounded_session.ts --ui-only`

---

## Part 2 — UI walkthrough (validate no-repeat in the browser)

Group (b)'s no-repeat serving is observable on-screen. Group (a) is **not** (deferred
to S4) — Part 1 is the authority there.

### Part 2 setup

- [ ] **2.1** Start the dev preview (or confirm it's running) at
  **http://localhost:3000/learn/quiz**. The dev preview seeds **Maya** + the
  **171-item bank**; the quiz is **bank-backed**.

### 2A — No-repeat within a session (FR-9)

- [ ] **2A.1** Open **`/learn/quiz`**. A **punctuation** item loads first (Maya's
  weakest skill `s-punc` is served first).
- [ ] **2A.2** Answer it: pick any choice → **"Submit answer"** → the Feedback panel
  appears → **"Next"**.
- [ ] **2A.3** Repeat for **~10–15 items**, and **track the question stems** (jot the
  first few words of each, or just watch closely).
- [ ] **2A.4** ✅ **EXPECT:** you **never** see the same stem/question twice in the
  session. The item changes on every "Next". *(This is FR-9.)*

> A fast way to confirm distinctness without hand-copying: after several items, open
> DevTools → Console and check that the stems you've seen are all different. There's
> no repeat.

### 2B — Round-robin skill rotation (S3.1, FR-3 — ADR-0024)

- [ ] **2B.1** Answer several items and **watch the skill/topic of each**. The session
  **rotates across skills** (punctuation → organization → grammar → …) — it does
  **not** keep serving the same skill (in particular, it is **no longer always
  sentence-completion** after you finish one).
- [ ] **2B.2** ✅ **EXPECT:** consecutive items are from **different** skills, and over
  ~8 items you see the skills **cycle** (verified live on `424d8cc`: all six —
  `s-punc → s-org → s-gram → s-sent → s-rhet → s-style` — then wrapping back to
  `s-punc`, with **no skill twice in a row**). *(This is the "always sentence-
  completion" fix, FR-3.)*

> For the S3.1-specific walkthrough with the full seed table and the deterministic
> `data-skill` check, see [`validate_s3_1_rotation_ui.md`](validate_s3_1_rotation_ui.md).

### 2C — Exhaustion ends the session (FR-11) — optional, long

- [ ] **2C.1** *(Only if you want to see FR-11.)* Keep answering until you've exhausted
  every servable reviewed item.
- [ ] **2C.2** ✅ **EXPECT:** the next load surfaces an **error** ("no unserved reviewed
  question") rather than repeating an item. *(This is FR-11 — the raw serving signal.
  S5 will render this as a clean "you're done" screen.)*

### 2D — Focus-mode deep link (opens a drill session)

- [ ] **2D.1** Open **`/learn/quiz?focus=s-gram`** → the session opens in **drill
  mode** (the mode is stored on the session).
- [ ] **2D.2** ✅ **EXPECT:** the no-repeat guarantee still holds — walk several items
  and confirm none repeat.

> ⚠️ **Honest scope note:** `?focus=` opens a drill-**mode** session, but the
> scheduler's `next()` has **never** taken a skill filter, so it still schedules
> across the **whole** taxonomy — the drill **does not pin the quiz to one skill**,
> and rotation applies. This is a pre-existing gap (not an S3.1 regression); see
> Part 3 of [`validate_s3_1_rotation_ui.md`](validate_s3_1_rotation_ui.md).

### 2E — No console errors

- [ ] **2E.1** With DevTools → Console open through the whole walkthrough, ✅ **EXPECT:
  zero errors** (until the deliberate FR-11 exhaustion signal in 2C, if you went there).

---

## What is NOT yet visible (deferred — do not treat as a bug)

- [ ] The **`target_count` (30) is stored but not rendered** — there is **no progress
  bar / "12 of 30" counter** yet. That is **S4** (FR-14). Verify the field only via
  Part 1.
- [ ] There is **no visible "session finished" done-state / retake button** — that is
  **S5**. Exhaustion currently shows the raw not-found error (see 2C).

---

## Sign-off

- [ ] **Part 1** — `22 passed, 0 failed`.
- [ ] **Part 2A** — no repeats across ~10–15 items.
- [ ] **Part 2B** — skill fall-through observed, still no repeat.
- [ ] **Part 2D** — focus-mode drill honors no-repeat.
- [ ] **Part 2E** — no console errors during the walkthrough.

If all boxes are ticked, S3's bounded no-repeat behavior is validated end-to-end (real
seams + live UI), with the `target_count` field confirmed headlessly and the
S4/S5-deferred surfaces explicitly out of scope.
