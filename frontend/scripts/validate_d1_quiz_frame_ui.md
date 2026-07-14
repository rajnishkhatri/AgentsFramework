# D1 Manual UI Walkthrough — Quiz session-frame chrome (Q-7 / Q-8 / Q-9)

**Sprint:** D1 · **PR:** [#149](https://github.com/rajnishkhatri/AgentsFramework/pull/149) · **Branch:** `feat/preact-parity-d1-quiz-frame`

| Artifact | Path |
|---|---|
| Spec (EARS) | [`docs/plan/preact-parity-D1-quiz-frame.spec.md`](../../docs/plan/preact-parity-D1-quiz-frame.spec.md) |
| Plan / tasks | [`docs/plan/preact-parity-D1-quiz-frame.plan.md`](../../docs/plan/preact-parity-D1-quiz-frame.plan.md) |
| Playwright FRs | [`docs/plan/preact-parity-D1-quiz-frame-playwright.spec.md`](../../docs/plan/preact-parity-D1-quiz-frame-playwright.spec.md) |
| Decision | [`docs/adr/decisions.md`](../../docs/adr/decisions.md) (2026-07-10 — extend `QuizItemVM`) |
| Board | [`docs/plan/preact-parity-sprint-board-D.md`](../../docs/plan/preact-parity-sprint-board-D.md) §Sprint D1 |
| L4 suite | [`e2e/learn/quiz-frame.spec.ts`](../e2e/learn/quiz-frame.spec.ts) |

This runbook is the **manual** half of Block 5 / T5.1. Tick every `[ ]` as you
confirm it in **your** browser. Quiz itself is a pure on-device engine
(InMemoryEngineDb + Maya seed); middleware is required so Coach / chat routes
do not spam `ECONNREFUSED` and so you can smoke the live BFF.

> **Do not validate on stale `main` UI.** D1 lives on the PR branch. After
> checkout, **restart** `pnpm dev` so the frame chrome is actually loaded.

---

## What you should expect to SEE (acceptance bar)

| # | Affordance | Expect on `/learn/quiz` |
|---|---|---|
| Q-7 | Skill chip | Colored dot + skill name (e.g. **Punctuation**) above the item |
| Q-8 | End session | Enabled **End session** button; click → **`/learn`** (dashboard), **not** Summary |
| Q-9 | Timer | Default: **Show timer** only (no `m:ss` clock). Reveal → ticking clock; Hide collapses; next item starts collapsed again |
| Regress | Finish | **Finish & see summary** still → **`/learn/summary`** (distinct from End) |

### Selectors (DevTools / Accessibility tree)

| UI | `data-testid` |
|---|---|
| Frame row | `quiz-frame` |
| Skill chip | `quiz-skill-chip` · accent glyph `bucket-dot` |
| End session | `quiz-end-session` |
| Timer reveal | `quiz-timer-reveal` (label **Show timer**) |
| Timer clock | `quiz-timer` (text like `0:05`) |
| Progress sentinel | `quiz-progress` (`Question N of 30`) |
| Choices / submit | `choice-A` … `choice-D` · `quiz-submit` |
| Feedback | `feedback-banner` |
| Next / Finish | `quiz-next` · `quiz-finish` |

### Dev seed (why the chip names look like this)

Learner **Maya**; skills from
[`lib/adapters/engine/_dev_seed.ts`](../lib/adapters/engine/_dev_seed.ts):

| Skill name | `accent_var` |
|---|---|
| Punctuation | `--color-bucket-punctuation` |
| Grammar & Usage | `--color-bucket-grammar` |
| Sentence Structure | `--color-bucket-sentence` |
| Rhetorical Skills | `--color-bucket-rhetoric` |
| Organization | `--color-bucket-organization` |
| Style | `--color-bucket-style` |

First item is usually a **Punctuation** bank item when opened cold from
`/learn/quiz` (no focus param). Focused opens (`/learn/quiz?focus=…`) may show a
different skill — chip text must still be non-empty and match that skill.

---

## Task → FR → manual step map

Use this while ticking boxes so every plan task has a visible UI check.

| Plan task | FR | Manual step |
|---|---|---|
| T1.4 / T1.7 / T1.9 (chip render + page wire) | FR-Q7-2, FR-Q7-4 | Part 1 · Steps 1–2, Part 2 |
| T1.2 (translator join — visible via chip text) | FR-Q7-1/2/3 | Part 1 · Step 1 (+ optional focus) |
| T2.4 / T2.6 (End control + close+route) | FR-Q8-3/4/5 | Part 1 · Step 1, Part 3 |
| T2.2 (`end_session` ≠ `finish`) | FR-Q8-6 | Part 3 vs Part 4 |
| T3.4 / T3.6 / T3.7 (timer UI + key reset) | FR-Q9-2/3/5/7/8 | Part 1 · Step 1, Part 2 |
| T3.2 (elapsed format) | FR-Q9-4 | Part 2 · Steps 2–3, 5 |
| T5.1 live walk | all above | Parts 1–5 |
| T5.2 / T5.3 docs | decisions + board | Part 6 |

L1-only edges (null skill join, reducer no-ops, `NaN` clamp) are covered by
Vitest — optional §A, not required for the manual walk.

---

## Part 0 — Start latest middleware + D1 frontend

### 0.1 Checkout the D1 branch

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
git fetch origin
git checkout feat/preact-parity-d1-quiz-frame
git pull --ff-only
```

- [ ] **0.1** `git rev-parse --abbrev-ref HEAD` → `feat/preact-parity-d1-quiz-frame`

### 0.2 Middleware (latest local)

From the **repo root** (loads your local env):

```bash
source .venv/bin/activate
python -m middleware
```

Default bind is **:8000**; if busy the process may print a higher port (this
workspace has previously served **:8123**). Note the printed port.

```bash
# try the port you saw in the middleware terminal:
curl -s http://127.0.0.1:8000/healthz
# or:
curl -s http://127.0.0.1:8123/healthz
# expect: {"status":"ok","profile":"dev",...}
```

If middleware is not on `:8000`, point the Next BFF at it and **restart** the
frontend:

```bash
export MIDDLEWARE_URL=http://localhost:8123   # use your real port
```

- [ ] **0.2** `/healthz` returns `"status":"ok"` on the port you will use

### 0.3 Frontend (auth bypass, D1 code)

Stop any old Next process on `:3000`, then from `frontend/`:

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
E2E_BYPASS_AUTH=1 pnpm install   # only if deps drifted
E2E_BYPASS_AUTH=1 pnpm dev
# If middleware is not on :8000:
# MIDDLEWARE_URL=http://localhost:8123 E2E_BYPASS_AUTH=1 pnpm dev
```

- [ ] **0.3** **http://localhost:3000/learn** loads Maya’s dashboard (not WorkOS login)
- [ ] **0.4** **http://localhost:3000/learn/quiz** shows `Question 1 of 30` (or N of 30)

Hard-refresh once (`Cmd+Shift+R`) so you are not on a stale HMR shell from
another branch.

Ignore chat-route `ECONNREFUSED` in the Next log only if middleware is down —
for this walk middleware should be up (Part 5).

---

## Part 1 — Cold open: frame chrome present (T5.1a)

Open: **http://localhost:3000/learn/quiz**

Do **not** select a choice yet.

- [ ] **1.1** Progress reads **Question 1 of 30** (`quiz-progress`).
- [ ] **1.2** Frame row (`quiz-frame`) sits **above** the passage / stem.
- [ ] **1.3 Q-7** Skill chip (`quiz-skill-chip`) is visible with a **non-empty**
  name (typically **Punctuation**) and a filled accent dot (`bucket-dot`).
- [ ] **1.4 Q-8** Button **End session** (`quiz-end-session`) is visible and
  **enabled** (not greyed out).
- [ ] **1.5 Q-9** **Show timer** (`quiz-timer-reveal`) is visible.
- [ ] **1.6 Q-9** There is **no** `quiz-timer` clock text in the DOM yet
  (collapsed by default — FR-Q9-2).
- [ ] **1.7** Existing chrome still present: four choices, **Get a hint**,
  **Reveal answer**, **Submit answer**.

**Optional DevTools (accent color):**

```js
getComputedStyle(
  document.querySelector('[data-testid="quiz-skill-chip"] [data-testid="bucket-dot"]')
).backgroundColor
// expect a real rgb(...) — not "" / transparent / rgba(0,0,0,0)
```

- [ ] **1.8** Dot `backgroundColor` is a resolved color (FR-Q7-2 / FR-P7-3).

---

## Part 2 — Timer: reveal, tick, hide, reset on next (T5.1b–c / Q-9)

Stay on the first item.

### 2A — Reveal + tick (FR-Q9-3 / FR-Q9-4 / FR-Q9-8)

- [ ] **2.1** Click **Show timer**.
- [ ] **2.2** Clock (`quiz-timer`) appears; text matches `m:ss` (e.g. `0:00` / `0:01`).
- [ ] **2.3** Wait ~2 seconds without clicking — reading **increases** (e.g. `0:00` → `0:02`).
- [ ] **2.4** A **Hide** control is present (`aria-label="Hide timer"`).

### 2B — Collapse (FR-Q9-5)

- [ ] **2.5** Click **Hide**.
- [ ] **2.6** Clock gone; **Show timer** is back (collapsed again).

### 2C — Persist chip/End through Feedback; timer resets on Next (FR-Q7-4, FR-Q8-3, FR-Q9-7)

1. Click **Show timer** again (leave it revealed).
2. Select **A** → **Submit answer**.
3. Wait for Feedback (`feedback-banner`).

- [ ] **2.7** On Feedback: skill chip still visible with the **same** name as before submit.
- [ ] **2.8** On Feedback: **End session** still visible and enabled.
- [ ] **2.9** Click **Next question** (`quiz-next`).

On the **new** item:

- [ ] **2.10** Timer is **collapsed** again (**Show timer** present, no `quiz-timer`).
- [ ] **2.11** Skill chip still present (may change name if the next item is a
  different skill — that is OK; empty chip is a fail).
- [ ] **2.12** Optional elapsed continuity: reveal timer, note `t0`; answer +
  Next; reveal again; after ~2s the new reading is **strictly greater** than `t0`
  (session clock does not restart — FR-Q9-4 / FR-P9-5).

---

## Part 3 — End session → dashboard (T5.1d / Q-8)

End and Finish are **mutually exclusive exits**. Do this in a **fresh** session
(do not Finish first).

1. Open **http://localhost:3000/learn/quiz** (full navigation / hard refresh).
2. Confirm frame chrome (Part 1), optionally answer 0–1 items.
3. Click **End session**.

- [ ] **3.1** URL becomes **`/learn`** (dashboard) — not `/learn/quiz`, not
  `/learn/summary`.
- [ ] **3.2** Dashboard greeting / mastery / trust rail render (Maya home).
- [ ] **3.3** No stuck “Loading…” / blank error page.

**Optional — End from Feedback:**

1. Re-open `/learn/quiz` → answer A → Submit → Feedback.
2. Click **End session** on the Feedback frame.

- [ ] **3.4** Still lands on `/learn` (FR-Q8-3 + FR-Q8-5 from reviewing).

---

## Part 4 — Finish regression (FR-Q8-6 / FR-P8-4)

Fresh session again — prove the other exit still works.

1. Open **http://localhost:3000/learn/quiz**.
2. Select a choice → **Submit answer** → Feedback.
3. Click **Finish & see summary** (`quiz-finish`) — do **not** click End.

- [ ] **4.1** URL becomes **`/learn/summary`**.
- [ ] **4.2** Summary shows a score / session payoff (not the Home dashboard).
- [ ] **4.3** Mental check: End → `/learn`, Finish → `/learn/summary` (two
  distinct reducer exits).

---

## Part 5 — Coach via latest middleware (smoke)

Quiz does not need middleware; this proves your BFF is aimed at the **live**
process from Part 0.2.

Open: **http://localhost:3000/learn/coach**

- [ ] **5.1** Coach chrome loads (not a blank 500 / WorkOS wall).
- [ ] **5.2** Send a short message (e.g. `Why is the comma wrong here?`).
- [ ] **5.3** A streamed reply arrives (proves BFF → middleware on `MIDDLEWARE_URL`).
- [ ] **5.4** If it fails: match `MIDDLEWARE_URL` to the port `/healthz` answered
  on, restart `pnpm dev`, retry.

---

## Part 6 — Docs / decision spot-check (~1 minute)

- [ ] **6.1** `docs/adr/decisions.md` — newest D1 line: **extend QuizItemVM**
  (not a new `QuizFrameVM` / no numbered ADR).
- [ ] **6.2** `docs/plan/preact-parity-sprint-board-D.md` — Sprint D1 marked
  **Implemented** with an implementation-evidence section.
- [ ] **6.3** Sidebar still has **no Skills** nav row (D-8 deferred — not in D1).

---

## Part 7 — Console / hygiene (T5.1e)

During Parts 1–4, open DevTools → Console.

- [ ] **7.1** No red errors that block answering, End, Finish, or timer reveal.
- [ ] **7.2** Chat `ECONNREFUSED` only appears if middleware was down (should not
  during Part 5).

---

## §A — Optional automated proof (before or after the manual walk)

With the same bypass-auth server from Part 0.3:

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend

# L1 — translator / timer / reducer / view / hook
pnpm exec vitest run \
  lib/translators/quiz_item_vm.test.ts \
  lib/translators/quiz_frame_timer.test.ts \
  components/quiz/quiz_screen_reducer.test.ts \
  components/quiz/QuizView.test.tsx \
  components/quiz/use_quiz.test.ts

# L4 — full D1 browser suite (video under test-results/)
CI=1 BASE_URL=http://localhost:3000 E2E_BYPASS_AUTH=1 \
  pnpm exec playwright test --project=learn-e2e \
  e2e/learn/quiz-frame.spec.ts --reporter=list
```

**Expected L4:** 12 passed across `Q-7 skill chip` / `Q-8 End session` /
`Q-9 collapsible timer`.

Headed watch (optional):

```bash
CI=1 BASE_URL=http://localhost:3000 \
  pnpm exec playwright test --project=learn-e2e \
  e2e/learn/quiz-frame.spec.ts --headed
```

- [ ] **A.1** Vitest D1 suites green
- [ ] **A.2** `quiz-frame.spec.ts` 12 passed

---

## Pass / fail summary

| Check | FR | Manual |
|---|---|---|
| Chip + accent on first item | FR-Q7-2 | Part 1 |
| Chip persists answering → reviewing | FR-Q7-4 | Part 2 · 2.7 |
| End visible answering + reviewing | FR-Q8-3 | Part 1 · 1.4, Part 2 · 2.8 |
| End → `/learn` | FR-Q8-4/5 | Part 3 |
| Finish → `/learn/summary` | FR-Q8-6 | Part 4 |
| Timer collapsed by default | FR-Q9-2 | Part 1 · 1.5–1.6 |
| Reveal → `m:ss` + ticks | FR-Q9-3/4 | Part 2 · 2.1–2.3 |
| Hide collapses | FR-Q9-5 | Part 2 · 2.5–2.6 |
| Next resets reveal | FR-Q9-7 | Part 2 · 2.10 |
| Accessible Show/Hide labels | FR-Q9-8 | Part 2 · 2.1 / 2.4 |
| Coach via live middleware | — | Part 5 |
| Decisions + board | T5.2 / T5.3 | Part 6 |

**D1 shipped Q-7 + Q-8 + Q-9.** It did **not** ship D2 (Skills taxonomy nav) or
D3 (Q-1b). If any box fails: note the step number, exact URL, and a screenshot;
do not “fix” by routing End to Summary or by rendering a live clock by default —
those reopen rejected framings from D0/D1.
