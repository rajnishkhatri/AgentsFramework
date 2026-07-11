# C1 Manual UI Walkthrough — Dashboard rail + greeting (C1-fix)

**Sprint:** C1 / C1-fix · **Spec:** [`docs/plan/preact-parity-C1-review-fixes.spec.md`](../../docs/plan/preact-parity-C1-review-fixes.spec.md) · **Base:** [`docs/plan/preact-parity-C1-dashboard-rail.spec.md`](../../docs/plan/preact-parity-C1-dashboard-rail.spec.md) · **PR:** [#144](https://github.com/rajnishkhatri/AgentsFramework/pull/144)

This runbook validates the **dashboard Home** surface only — greeting, trust rail
(streak + weekly), container layout, and rail-scoped Retry. Tick each `[ ]` as you
confirm it.

> `/learn` is a **pure on-device engine** (InMemoryEngineDb + Maya seed). Middleware
> is optional for Parts 1–4. Start it anyway so Coach / chat routes do not spam
> `ECONNREFUSED` in the Next log while you walk the dashboard.

---

## What you should expect to SEE (acceptance bar)

| # | Surface | Expect |
|---|---------|--------|
| A | Greeting | `Good <morning\|afternoon\|evening>, Maya` + weekday/date subline |
| B | Trust rail (ok) | Streak tile + weekly `N / 3 sessions` |
| C | Trust rail (fail) | `Trust rail unavailable` + **Retry**; greeting + mastery stay put |
| D | After Retry | Streak/weekly return; greeting text unchanged |
| E | Narrow container | Rail sits **below** skill mastery |
| F | Wide container | Rail sits to the **right** of mastery |
| G | Absent | No score-goal tile, no coach-note tile |

### Dev seed (why the numbers look like this)

Learner **"Maya"** (`learnerId: maya`, display name `Maya`) from
[`lib/adapters/engine/_dev_seed.ts`](../lib/adapters/engine/_dev_seed.ts):

| Skill | Mastery (approx) | Due? |
|-------|------------------|------|
| Punctuation | 28% | yes → today’s focus |
| Organization | 40% | yes |
| Grammar & Usage | 55% | yes |
| Sentence Structure | 61% | — |
| Rhetorical Skills | 74% | — |
| Style | 82% | — |

Cold start (no closed sessions in the in-memory bag): streak = **Start a streak**,
weekly = **0 / 3 sessions**.

---

## Part 0 — Start middleware + UI

### 0.1 Middleware (already healthy if `:8123` answers)

From the **repo root** (loads your local env automatically):

```bash
source .venv/bin/activate
python -m middleware
```

Default is port **8000**; if busy it auto-increments. This workspace currently
serves healthz on **http://127.0.0.1:8123/healthz** →
`{"status":"ok","profile":"dev",...}`.

- [ ] **0.1** `curl -s http://127.0.0.1:8123/healthz` (or `:8000`) returns `"status":"ok"`.

### 0.2 Frontend with C1-fix e2e hooks

Fail-once Retry (Part 3) needs the composition-root decorator. From `frontend/`:

```bash
cd frontend
E2E_BYPASS_AUTH=1 NEXT_PUBLIC_PREACT_E2E_HOOKS=1 pnpm dev
```

- `E2E_BYPASS_AUTH=1` — no WorkOS gate on `/learn`.
- `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` — enables fail-once when the URL has
  `?e2e_rail_fail=1` (FR-2). Without this env, Part 3 is skipped.

> If a Next server is already on `:3000`, either reuse it (confirm hooks work in
> Part 3) or stop it and restart with the env above so `NEXT_PUBLIC_*` is baked in.

- [ ] **0.2** Open **http://localhost:3000/learn** — after a brief
  “Loading your dashboard…”, the Home dashboard appears (not a WorkOS login).

Ignore `ECONNREFUSED` on `/api/threads`, `/api/models`, or `/api/memory` in the
Next log if middleware is down — those are chat routes, not the dashboard.

---

## Part 1 — Happy path (greeting + rail + mastery)

Open **http://localhost:3000/learn** (no query params). Hard-refresh once
(`Cmd+Shift+R`) so you are not on a stale HMR shell.

- [ ] **1.1** Greeting `h1[data-testid="dashboard-greeting"]` reads
  **Good …, Maya** (time-of-day depends on local clock).
- [ ] **1.2** Subline shows today’s weekday + date (e.g. `Friday, July 10`).
- [ ] **1.3** Trust rail (`[data-testid="trust-rail"]`) shows:
  - Streak: **Start a streak** (cold seed)
  - Weekly: **0 / 3 sessions**
- [ ] **1.4** Today’s focus banner names **Punctuation** (weakest due skill).
- [ ] **1.5** Skill mastery shows **six** bucket cards; Punctuation / Grammar /
  Organization show **Due**.
- [ ] **1.6** Secondary actions: **Drill a skill**, **Review my misses (0)**,
  **Take a timed test**.
- [ ] **1.7** ✅ **ABSENT:** score-goal tile, coach-note tile (C1 FR-14).

**DevTools quick check (optional):**

```js
getComputedStyle(document.querySelector('[data-testid="dashboard-root"]')).containerType
// → "inline-size"
document.querySelector('[aria-label="Skill mastery"] .grid')?.className
// → includes "@lg:grid-cols-3" (container query, not viewport lg:)
```

- [ ] **1.8** `container-type` is `inline-size` (FR-1).

---

## Part 2 — Container layout (narrow ↔ wide)

Stay on **http://localhost:3000/learn**. Use DevTools device toolbar **or** paste
in the console:

```js
const root = document.querySelector('[data-testid="dashboard-root"]');
const rail = document.querySelector('[data-testid="trust-rail"]');
const buckets = document.querySelector('[aria-label="Skill mastery"]');

root.style.maxWidth = "380px";
const narrow = { railY: rail.getBoundingClientRect().y, bucketsY: buckets.getBoundingClientRect().y };
root.style.maxWidth = "1280px";
const wide = { railX: rail.getBoundingClientRect().x, bucketsX: buckets.getBoundingClientRect().x };
({ narrow, wide, expectNarrow: narrow.railY > narrow.bucketsY, expectWide: wide.railX > wide.bucketsX })
```

- [ ] **2.1** Narrow (`maxWidth: 380px`): rail **below** mastery
  (`railY > bucketsY`).
- [ ] **2.2** Wide (`maxWidth: 1280px`): rail to the **right** of mastery
  (`railX > bucketsX`).
- [ ] **2.3** Clear the override: `root.style.maxWidth = ""`.

---

## Part 3 — Rail fail-once + rail-scoped Retry (FR-2 / FR-7 / FR-8)

Requires `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` on the Next process.

1. Open **http://localhost:3000/learn?e2e_rail_fail=1** (full navigation, not just
   HMR — the fail-once flag is module-scoped and resets on full reload).
2. Wait for the dashboard (not stuck on Loading).

- [ ] **3.1** Greeting still **Good …, Maya**; mastery grid still visible.
- [ ] **3.2** Rail shows **Trust rail unavailable** + **Retry**
  (`[data-testid="rail-retry"]`). Streak/weekly tiles are **gone**.
- [ ] **3.3** Note the exact greeting string (copy it).
- [ ] **3.4** Click **Retry**.
- [ ] **3.5** ✅ Rail recovers: **Start a streak** + **0 / 3 sessions**.
- [ ] **3.6** ✅ Greeting text is **unchanged** (same string as 3.3) — rail-scoped
  reload only (FR-8).
- [ ] **3.7** ✅ Mastery percentages unchanged (still Maya seed).

**ARIA (optional):** Inspect `[data-testid="trust-rail"]` — it should be the
`<aside>` with `aria-live="polite"` both before and after Retry (FR-7).

If 3.2 never shows unavailable (rail loads healthy immediately), the Next server
was started **without** `NEXT_PUBLIC_PREACT_E2E_HOOKS=1`. Restart Part 0.2 and
retry this part.

---

## Part 4 — Smoke: Practice still reachable

From the recovered Home dashboard:

- [ ] **4.1** Click **Practice** (or **Start adaptive session**). Quiz loads a
  Punctuation (or focus) item — proves the engine bag survived the rail retry.
- [ ] **4.2** Click **Home** — dashboard returns; rail is healthy (no fail-once
  unless you re-open with `?e2e_rail_fail=1` on a **full** reload).

---

## Part 5 — Optional: Coach needs middleware

Only if you want to confirm the stack is wired end-to-end:

- [ ] **5.1** Middleware healthz still ok (Part 0.1).
- [ ] **5.2** Open **http://localhost:3000/learn/coach** — panel loads without a
  hard BFF failure. (Coach content quality is out of C1-fix scope.)

---

## Pass / fail summary

| Part | Pass? | Notes |
|------|-------|-------|
| 0 Boot | | |
| 1 Happy path | | |
| 2 Container layout | | |
| 3 Fail-once + Retry | | |
| 4 Practice smoke | | |
| 5 Coach (optional) | | |

**Automated companions** (not a substitute for this walk):

```bash
cd frontend
pnpm exec playwright test --project=learn-e2e e2e/learn/dashboard_rail.spec.ts
```

---

## Live probe (2026-07-10)

Verified against local `:3000` + middleware `:8123` on branch
`feat/preact-parity-c1-review-fixes` (includes uncommitted `@lg:grid-cols-3` +
shared `nowISO`):

- Happy path: greeting `Good evening, Maya`, streak cold, weekly `0 / 3`, focus
  Punctuation, `container-type: inline-size`.
- `?e2e_rail_fail=1` → unavailable + Retry; after Retry → streak/weekly restored,
  greeting unchanged.
