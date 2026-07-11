# D2 Manual UI Walkthrough — Taxonomy + bucket dots (D-3b)

**Sprint:** D2 · **Branch:** `feat/preact-parity-d2-taxonomy` (or current D2 working tree)

| Artifact | Path |
|---|---|
| Spec (EARS) | [`docs/plan/preact-parity-D2-taxonomy.spec.md`](../../docs/plan/preact-parity-D2-taxonomy.spec.md) |
| Plan | [`docs/plan/preact-parity-D2-taxonomy.plan.md`](../../docs/plan/preact-parity-D2-taxonomy.plan.md) |
| Tasks | [`docs/plan/preact-parity-D2-taxonomy.tasks.md`](../../docs/plan/preact-parity-D2-taxonomy.tasks.md) |
| Impl trace | [`docs/plan/preact-parity-D2-taxonomy.impl.md`](../../docs/plan/preact-parity-D2-taxonomy.impl.md) |
| Decision | [`docs/adr/decisions.md`](../../docs/adr/decisions.md) (D2 taxonomy line) |
| Board | [`docs/plan/preact-parity-sprint-board-D.md`](../../docs/plan/preact-parity-sprint-board-D.md) §Sprint D2 |
| L4 smoke | [`e2e/learn/dashboard-bucket-taxonomy.spec.ts`](../e2e/learn/dashboard-bucket-taxonomy.spec.ts) |
| L4 validation | [`e2e/learn/validate_d2_taxonomy.spec.ts`](../e2e/learn/validate_d2_taxonomy.spec.ts) |

This runbook is the **manual** half of T-VAL-D2. Tick every `[ ]` as you
confirm it in **your** browser. Dashboard is a pure on-device engine
(InMemoryEngineDb + Maya seed); middleware is optional for this walk (no Coach).

> **Do not validate on stale `main` UI.** D2 lives on the PR branch. After
> checkout, **restart** `pnpm dev` so the renamed labels + dots are actually
> loaded.

---

## What you should expect to SEE (acceptance bar)

| # | Affordance | Expect on `/learn` |
|---|---|---|
| Labels | 6 bucket cards | Headers read exactly: **Rhetoric · Usage · Punctuation · Organization · Sentence Structure · Conciseness** |
| Dots | Per-card glyph | Each header has `[data-testid^="bucket-dot-"]` (11×11 rounded square, filled with bucket `--accent`) |
| Old labels | Absent | No **Grammar & Usage**, **Rhetorical Skills**, or skill heading **Style** |
| Regress | Quiz chip | Focused quiz skill chip shows the **new** name for `s-gram` / `s-rhet` / `s-style` |

### Selectors (DevTools / Accessibility tree)

| UI | `data-testid` |
|---|---|
| Bucket card | `bucket-s-punc` … `bucket-s-style` |
| Bucket color dot | `bucket-dot-s-punc` … `bucket-dot-s-style` |
| Due badge | `due-<skillId>` |
| Quiz skill chip (D1) | `quiz-skill-chip` · accent glyph `bucket-dot` |

### Dev seed (canonical after D2)

Learner **Maya**; skills from
[`lib/adapters/engine/_dev_seed.ts`](../lib/adapters/engine/_dev_seed.ts):

| Skill name | `accent_var` |
|---|---|
| Punctuation | `--color-bucket-punctuation` |
| Usage | `--color-bucket-usage` |
| Sentence Structure | `--color-bucket-sentence-structure` |
| Rhetoric | `--color-bucket-rhetoric` |
| Organization | `--color-bucket-organization` |
| Conciseness | `--color-bucket-conciseness` |

---

## Task → FR → manual step map

| Plan task | FR | Manual step |
|---|---|---|
| T-6 / T-7 (seed + corpus rename) | FR-3, FR-4 | Part 1 · Steps 1.1–1.2 |
| T-9 (dot glyph) | FR-5 | Part 1 · Steps 1.3–1.5 |
| T-1 (grep audit) | FR-1 | Part 1 · Step 1.6 |
| T-5 FR-2 (null accent) | FR-2 | Part 1 · Step 1.7 (L1 covers; optional DevTools) |
| T-VAL-D2b Playwright | FR-1, FR-3, FR-5 | §A |
| T-13 / T-14 / T-15 docs | — | Part 3 |

---

## Part 0 — Start latest middleware + D2 frontend

### 0.1 Checkout the D2 branch

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
git fetch origin
git checkout feat/preact-parity-d2-taxonomy   # or your D2 working branch
git pull --ff-only
```

- [ ] **0.1** `git rev-parse --abbrev-ref HEAD` shows the D2 branch

### 0.2 Middleware (optional for Dashboard-only)

```bash
source .venv/bin/activate
python -m middleware
curl -s http://127.0.0.1:8000/healthz
```

- [ ] **0.2** (optional) `/healthz` returns `"status":"ok"` if you will open Coach

### 0.3 Frontend (auth bypass, D2 code)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
E2E_BYPASS_AUTH=1 pnpm dev
```

- [ ] **0.3** **http://localhost:3000/learn** loads Maya’s dashboard (not WorkOS login)

Hard-refresh once (`Cmd+Shift+R`) so you are not on a stale HMR shell.

---

## Part 1 — Dashboard cold open (labels + dots)

Open: **http://localhost:3000/learn**

- [ ] **1.1** Exactly **6** bucket cards (`[data-testid^="bucket-s-"]`).
- [ ] **1.2** Headers (exact) include all six: Rhetoric, Usage, Punctuation,
  Organization, Sentence Structure, Conciseness.
- [ ] **1.3** Each card header contains a `[data-testid^="bucket-dot-"]` glyph
  **leading** (left of) the label.
- [ ] **1.4** Dot is decorative: `aria-hidden="true"`.
- [ ] **1.5** Dot fill resolves (DevTools):

```js
[...document.querySelectorAll('[data-testid^="bucket-dot-"]')].map((el) =>
  getComputedStyle(el).backgroundColor,
);
// expect six rgb(...) values — not "" / transparent / rgba(0,0,0,0)
```

- [ ] **1.6** Page text does **not** contain `Grammar & Usage` or
  `Rhetorical Skills`; no heading named exactly `Style`.
- [ ] **1.7** (optional / L1-covered) FR-2 null `accentVar` → no dot — covered by
  `BucketCard.test.tsx::renders_no_dot_when_accent_var_missing`.

---

## Part 2 — Regression walk (quiz chip labels)

Open: **http://localhost:3000/learn/quiz?focus=s-gram**

- [ ] **2.1** Skill chip (`quiz-skill-chip`) reads **Usage** (not Grammar & Usage).

Open: **http://localhost:3000/learn/quiz?focus=s-rhet**

- [ ] **2.2** Chip reads **Rhetoric**.

Open: **http://localhost:3000/learn/quiz?focus=s-style**

- [ ] **2.3** Chip reads **Conciseness**.

If chip still shows old labels — D2 seed did not reload — hard refresh / restart
`pnpm dev`.

---

## Part 3 — Docs spot-check

- [ ] **3.1** `docs/adr/decisions.md` newest line records the 6 canonical labels
  + citation `PreAct/UI-Design/design-spec.md:62-69`.
- [ ] **3.2** Sprint-board D2 flipped to Implemented with Stage-6 evidence.
- [ ] **3.3** Parity report §D-3b marked Resolved; §X-4 marked Absorbed into D2.

---

## Part 4 — Console hygiene

- [ ] **4.1** No red errors in the browser console during Parts 1–2 (ignore
  Coach `ECONNREFUSED` only if middleware is intentionally down).

---

## §A — Automated proof

From `frontend/`:

```bash
# L1 — seed / corpus / BucketCard / arch
pnpm exec vitest run \
  lib/adapters/engine/_dev_seed.test.ts \
  e2e/fixtures/preact_learn_corpus.test.ts \
  components/dashboard/BucketCard.test.tsx \
  tests/architecture/test_bucket_labels_no_old_strings.test.ts \
  tests/architecture/test_bucket_tokens_unchanged.test.ts

# L4 — taxonomy smoke + validation walk
CI=1 BASE_URL=http://localhost:3000 E2E_BYPASS_AUTH=1 \
  pnpm exec playwright test --project=learn-e2e \
  e2e/learn/dashboard-bucket-taxonomy.spec.ts \
  e2e/learn/validate_d2_taxonomy.spec.ts --reporter=list
```

- [ ] **A.1** Vitest D2 suites green
- [ ] **A.2** Playwright D2 specs green

---

## Pass / fail summary

| Check | FR | Manual |
|---|---|---|
| 6 canonical labels on Dashboard | FR-3 | Part 1 · 1.1–1.2 |
| Old strings absent | FR-1 | Part 1 · 1.6 |
| Dot per card, resolved colour | FR-5 | Part 1 · 1.3–1.5 |
| Null accent → no dot | FR-2 | Part 1 · 1.7 / L1 |
| Corpus lock-step | FR-4 | §A L1 |
| Non-name fields untouched | FR-6 | §A L1 |
| Token ids unchanged | FR-7 | §A L1 |
| Quiz chip uses new names | FR-1/3 | Part 2 |
| Docs + board + parity | — | Part 3 |

**D2 ships taxonomy rename + Dashboard bucket dots.** It does **not** ship D3
(Q-1b) or D4 (Skills nav). If any box fails: note the step number, exact URL,
and a screenshot.
