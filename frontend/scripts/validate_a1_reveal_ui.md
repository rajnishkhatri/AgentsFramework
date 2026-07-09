# A1 — Reveal answer (gated submit alias): validation guide

How to validate Sprint A1 on the localhost `/learn` quiz UI — both the
**automated** proof (Playwright) and a **manual** step-by-step walk you can do
yourself. A1 closes trust bug `Q-6`: **"Reveal answer"** was a labelled button
with no `onClick`. After A1 it is an honest, low-emphasis path to Feedback that
matches the prototype — same submit path as **Submit answer**, gated on a
selected choice. The correct answer letter stays off the Quiz screen
(`QuizItemVM` still omits it); Feedback teaches it.

| Artifact | Path |
|---|---|
| Spec | [`docs/plan/preact-parity-A1-reveal.spec.md`](../../docs/plan/preact-parity-A1-reveal.spec.md) |
| Plan / tasks | [`docs/plan/preact-parity-A1-reveal.plan.md`](../../docs/plan/preact-parity-A1-reveal.plan.md) |
| UI FR | [`docs/plan/preact-english-coach-ui.spec.md`](../../docs/plan/preact-english-coach-ui.spec.md) **FR-D6 / FR-D6a** |
| Decision | [`docs/adr/decisions.md`](../../docs/adr/decisions.md) (2026-07-09 A1 entry) |
| Playwright walk | [`e2e/learn/validate_a1_reveal.spec.ts`](../e2e/learn/validate_a1_reveal.spec.ts) |
| L1 units | [`components/quiz/QuizView.test.tsx`](../components/quiz/QuizView.test.tsx) |

**What you are proving (task → FR):**

| Task | FR | What “pass” looks like |
|---|---|---|
| A1-0 | FR-5 | UI spec has **FR-D6a** (docs — grep / open the file) |
| A1-1 + A1-2 | FR-1, FR-3, FR-4 | Reveal disabled until a choice; then Reveal → Feedback |
| — | FR-2 | Quiz answering phase never shows the correct letter in-place |
| A1-3 | FR-6 | `decisions.md` newest entry records D6+D1 |
| A1-4 | DoD | Playwright walk + vitest + `make check` green |

---

## §0 — One-time setup

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
pnpm install
pnpm exec playwright install chromium   # if browsers not installed yet
```

- [ ] **0.1** Dependencies present (`node_modules/`).
- [ ] **0.2** Dev server will run with auth bypass (required for `/learn` without WorkOS).

---

## §A — Automated proof (run this first)

### A.1 Start the local frontend (bypass auth)

In a dedicated terminal:

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
E2E_BYPASS_AUTH=1 pnpm dev
```

Wait until `http://localhost:3000` responds. Leave it running.

### A.2 L1 unit suite (red-first already proven in implement)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
npx vitest run components/quiz/QuizView.test.tsx
```

**Expected:** `12 passed` (includes `QuizView — Reveal answer (UI FR-D6 / FR-D6a)`).

### A.3 Playwright validation walk (all interactive FRs)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend

# Narrated walk — logs each FR checkpoint; attaches screenshots when E2E_SCREENSHOTS=1
E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
  pnpm test:e2e:a1-reveal

# Equivalent explicit command:
# E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
#   ./node_modules/.bin/playwright test --project=learn-e2e \
#   e2e/learn/validate_a1_reveal.spec.ts --reporter=list
```

**Expected console checkpoints:**

```
  ✔ opened /learn/quiz — answering phase visible
  ✔ FR-4: Reveal is a distinct ghost control …
  ✔ FR-1: no selection → Reveal disabled …; click does not open Feedback
  ✔ FR-2: answering DOM has no in-place …
  ✔ hint open: orthogonal — Reveal still gated …
  ✔ selection made → Reveal enabled …
  ✔ FR-3: Reveal → Feedback …; teaching letter on Feedback
  ✔ parity check: Submit on next item also reaches Feedback …
  A1 validation walk PASSED — FR-1/2/3/4 green; Reveal = gated submit alias.
  1 passed
```

### A.4 Watch the run (optional)

The Playwright run uses its **own** browser (not your preview tab).

- **Headed (watch live):**
  ```bash
  BASE_URL=http://localhost:3000 ./node_modules/.bin/playwright test \
    --project=learn-e2e e2e/learn/validate_a1_reveal.spec.ts --headed
  ```
- **Video** (always on for `learn-e2e`):
  ```
  frontend/test-results/validate_a1_reveal-*/video.webm
  ```
- **HTML report** (omit `CI=1`, then):
  ```bash
  ./node_modules/.bin/playwright show-report
  ```

### A.5 Docs tasks (A1-0 / A1-3) — quick grep

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent

# A1-0 / FR-5
rg -n "FR-D6a" docs/plan/preact-english-coach-ui.spec.md
# expect: FR-D6a + "Submit answer" + "non-actionable"

# A1-3 / FR-6
head -20 docs/adr/decisions.md
# expect: 2026-07-09 Sprint A1 … gated submit alias
```

- [ ] **A.2** vitest 12 passed  
- [ ] **A.3** Playwright walk 1 passed  
- [ ] **A.5** FR-D6a + decisions.md entry present  

---

## §B — Manual UI walk (localhost, ~3 minutes)

Do this in **your** browser against the same bypass-auth server from §A.1.

Open: **http://localhost:3000/learn/quiz**

Use DevTools → Elements (or the Accessibility tree) if you want to confirm
`data-testid` / `disabled` / `data-enabled`. Selectors below match the app.

### Step 1 — Land on Quiz (answering)

- [ ] You see the passage / stem and four choices (`choice-A` … `choice-D`).
- [ ] You see **Get a hint**, **Reveal answer**, and **Submit answer**.
- [ ] URL stays on `/learn/quiz`.

### Step 2 — FR-4: Reveal is a ghost, not the hint

- [ ] **Reveal answer** looks low-emphasis (muted text, no dashed accent border).
- [ ] **Get a hint** looks different (dashed accent border / accent text).
- [ ] They are two separate controls in the same action row.

### Step 3 — FR-1: no selection → Reveal lies no more (disabled)

Do **not** pick a choice yet.

- [ ] **Reveal answer** is visually dimmed / not clickable.
- [ ] **Submit answer** is also disabled (same gate).
- [ ] Optional DevTools: `quiz-reveal` has `disabled` and `data-enabled="false"`.
- [ ] Clicking Reveal (if the browser lets you force-click) does **nothing** —
      you stay on Quiz; no Feedback banner.

### Step 4 — FR-2: Quiz does not show the answer letter

Still on the answering screen (before or after opening a hint):

- [ ] You do **not** see copy like “Why B is correct” or a **CORRECT ANSWER** badge
      on the Quiz screen.
- [ ] Opening **Get a hint** shows a Socratic prompt card — still no answer letter
      named as the key.

### Step 5 — Select a choice → Reveal enables

Click any choice (e.g. A).

- [ ] That row looks selected.
- [ ] **Reveal answer** becomes enabled (`data-enabled="true"`).
- [ ] **Submit answer** becomes enabled too.

### Step 6 — FR-3: Reveal → Feedback (do **not** press Submit)

Click **Reveal answer** only.

- [ ] You leave the answering Quiz chrome and see the Feedback banner
      (“Exactly right.” or “Not quite — and that's useful.”).
- [ ] **Reveal answer** is gone (Feedback replaced QuizView).
- [ ] You see teaching copy: **Why \<letter\> is correct:** …
- [ ] Reviewed choices show **CORRECT ANSWER** / **YOUR CHOICE** labels as appropriate.

This is the whole point of A1: Reveal is a **submit alias**, not an in-place
letter dump on the Quiz screen.

### Step 7 — Parity: Submit still works the same way

Press **Next question** (or equivalent `quiz-next`). On the next item:

- [ ] Pick a choice → press **Submit answer** (not Reveal).
- [ ] You again land on Feedback with the same teaching pattern.

### Step 8 — Docs spot-check (optional, ~30s)

- [ ] Open `docs/plan/preact-english-coach-ui.spec.md` §D — **FR-D6a** present.
- [ ] Open `docs/adr/decisions.md` top — A1 “gated submit alias” entry present.

---

## §C — Pass / fail summary

| Check | Automated | Manual |
|---|---|---|
| FR-1 Reveal disabled w/o selection | §A.2 + §A.3 | §B Step 3 |
| FR-2 no in-place letter on Quiz | §A.3 | §B Step 4 |
| FR-3 Reveal → Feedback | §A.3 | §B Step 6 |
| FR-4 ghost ≠ hint | §A.3 | §B Step 2 |
| FR-5 UI FR-D6a | §A.5 | §B Step 8 |
| FR-6 decisions.md | §A.5 | §B Step 8 |

**A1 closed Q-6 via Reveal→submit alias; `QuizItemVM` still non-revealing.**

If any box fails: note the step number, URL, and a screenshot; do not “fix” by
renaming the button or adding an answer letter to the Quiz VM — that reopens
rejected Options 1/3.
