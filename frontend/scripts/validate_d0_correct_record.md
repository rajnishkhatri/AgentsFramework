# D0 — Correct the record (Epic D): validation guide

How to validate Sprint **D0** after [PR #148](https://github.com/rajnishkhatri/AgentsFramework/pull/148)
merged. D0 is **docs-only**: it erased five refuted framings and recorded the
intent debt. It did **not** implement Q-7 / Q-8 / Q-9 / Q-1b / D-3b / D-8 UI.

| Artifact | Path |
|---|---|
| Spec | [`docs/plan/preact-parity-D0-correct-record.spec.md`](../../docs/plan/preact-parity-D0-correct-record.spec.md) |
| Plan | [`docs/plan/preact-parity-D0-correct-record.plan.md`](../../docs/plan/preact-parity-D0-correct-record.plan.md) |
| Board | [`docs/plan/preact-parity-sprint-board-D.md`](../../docs/plan/preact-parity-sprint-board-D.md) |
| Decisions | [`docs/adr/decisions.md`](../../docs/adr/decisions.md) (2026-07-10 Epic D entry) |
| Playwright baseline | ~~`e2e/learn/validate_d0_baseline.spec.ts`~~ — **retired by Epic E1a** (ADR-0028): the spec's premise was "Skills nav still absent"; E1a shipped Skill as a live nav tab, so the guard was deleted. Quiz-continuity coverage lives in `e2e/learn/quiz-frame.spec.ts`; the live Skill surface in `e2e/learn/skill-lesson.spec.ts`. |

**What you are proving:**

| Check | Kind | Pass looks like |
|---|---|---|
| FR-2..FR-5 | Docs greps | Epics + VISUAL rows carry corrected framings |
| FR-6 | Docs read | `decisions.md` newest Epic D entry + Rejected tail |
| FR-7 | Docs grep | Board has no *live* stale claims |
| DoD | Playwright | Core Quiz works; D1 frame chrome present *(Skills-nav-absent check retired by E1a — see baseline row)* |
| Manual UI | Browser + live middleware | Same baseline + Coach still reachable via real middleware |

---

## §0 — One-time setup

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent

# Frontend (auth bypass for /learn)
cd frontend
pnpm install
E2E_BYPASS_AUTH=1 NEXT_PUBLIC_PREACT_E2E_HOOKS=1 pnpm dev
# → http://localhost:3000

# Latest middleware (separate terminal, repo root)
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
source .venv/bin/activate
python -m middleware
# Prefer :8000. If the process prints "listening on 8001", point the BFF at it:
#   export MIDDLEWARE_URL=http://localhost:8001
# and restart `pnpm dev` so the Next.js BFF picks it up.
```

Health checks:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/learn     # expect 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/healthz  # expect 200
```

- [ ] **0.1** Frontend up on `:3000` with `E2E_BYPASS_AUTH=1`
- [ ] **0.2** Middleware `/healthz` → 200 (latest checkout on `main`)
- [ ] **0.3** `MIDDLEWARE_URL` matches the port middleware actually bound

---

## §A — Automated proof (run this first)

### A.1 Docs greps (FR-2..FR-7) — the real D0 DoD

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent

# FR-2 Q-7 → VM / translator / hook
grep -n "Q-7" docs/plan/preact-parity-epics.md
# expect §Epic D row: wire→VM→view / translator / hook

# FR-3 Q-9 → collapsible (not live "dismissible")
grep -n "Q-9" docs/plan/preact-parity-epics.md \
  docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
# expect: "collapsible"; quoted "dismissible" only inside a correction note is OK

# FR-4 Q-1b → decision-first D3 / decisions.md
grep -n "Q-1b" docs/plan/preact-parity-epics.md
# expect: D3 + decisions.md; not "code sprint by default"

# FR-5 D-8 + X-4
grep -n "D-8\|X-4" docs/plan/preact-parity-epics.md \
  docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
# expect: D-8 mentions Epic E / gated; X-4 mentions absorbed / D-3b / D2

# FR-6 decisions.md
head -40 docs/adr/decisions.md
# expect: Epic D Stage-1 … P3 P8 P10 P14 P15 + Rejected alternatives

# FR-7 board — live stale claims should be gone
grep -niE "skill chip|dismissible|change 30 to 10|X-4 (as )?independent" \
  docs/plan/preact-parity-sprint-board-D.md
# expect: only premise-table / quoted-refutation context (no findings-in-scope "dismissible")
```

- [ ] **A.1** All six greps match the expectations above

### A.2 Playwright D0 baseline — RETIRED (superseded by Epic E1a)

> `validate_d0_baseline.spec.ts` asserted "Skills nav still absent". Epic E1a
> (ADR-0028) shipped Skill as a live nav tab, invalidating that premise, so the
> spec was deleted. The coverage it carried now lives in:
>
> - **Quiz chrome + Submit→Feedback regression** → `pnpm test:e2e:learn e2e/learn/quiz-frame.spec.ts`
> - **The live `/learn/skill` surface** → `pnpm test:e2e:learn e2e/learn/skill-lesson.spec.ts`
>
> This D0 record is preserved as history; the absence-guard it described no longer holds.

### A.3 Learn-suite regression (optional but recommended)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
E2E_BYPASS_AUTH=1 BASE_URL=http://localhost:3000 \
  pnpm test:e2e:learn --reporter=list
```

D0 touches no `frontend/` runtime — functional learn specs should stay green as a
no-op regression gate. Known pre-existing (unrelated to D0): `e2e/learn/a11y.spec.ts`
may fail on `aria-progressbar-name` for the Quiz progress bar — track separately;
do not treat as a D0 regression.

- [ ] **A.2** D0 baseline 1 passed
- [ ] **A.3** learn-e2e green (or note any pre-existing failures unrelated to D0)

---

## §B — Manual UI walk (localhost + live middleware, ~5 minutes)

Do this in **your** browser against the bypass-auth frontend from §0 and the
**live** middleware (`python -m middleware`). This is a **baseline** walk: you
are confirming D0 did not ship D1/D4 chrome, and that the existing loop still
works with the latest middleware for Coach.

### Step 1 — Dashboard + nav (D-8 deferred)

Open: **http://localhost:3000/learn**

- [ ] Today-focus / mastery cards render.
- [ ] Sidebar shows **Home · Practice · Coach · Progress** (Progress may be greyed / coming soon).
- [ ] There is **no "Skills"** nav row (D-8 default = defer to Epic E).
- [ ] Optional DevTools: no `[data-screen="skill"]` in `nav[aria-label="Primary"]`.

### Step 2 — Quiz answering (Q-7 / Q-8 / Q-9 still absent)

Open: **http://localhost:3000/learn/quiz**

- [ ] You see progress ("Question N of …"), passage, stem, four choices, Get a hint, Reveal answer, Submit answer.
- [ ] You do **not** see a skill chip like "● Punctuation" in the header (Q-7 → D1).
- [ ] You do **not** see an **End session** / ✕ abandon control (Q-8 → D1).
- [ ] You do **not** see a visible mm:ss timer or clock toggle (Q-9 → D1; `elapsed_ms` is capture-only today).

### Step 3 — Core loop still works

- [ ] Select a choice → **Submit answer** → Feedback banner appears.
- [ ] Continue or finish until Summary (or stop after Feedback if short on time).
- [ ] No console errors that block the loop.

### Step 4 — Coach via latest middleware (smoke)

Open: **http://localhost:3000/learn/coach**

- [ ] Coach chrome loads (not a blank 500).
- [ ] Send a short message (e.g. "Why is the comma wrong here?").
- [ ] A streamed reply arrives (proves BFF → live middleware on `MIDDLEWARE_URL`).
- [ ] If the reply fails: check middleware terminal for `/healthz` and that
      `MIDDLEWARE_URL` matches the bound port (8000 vs 8001).

### Step 5 — Docs spot-check (~1 minute)

- [ ] `docs/plan/preact-parity-epics.md` §Epic D — Q-7 mentions VM/translator/hook; Q-9 says collapsible; D-8 cites Epic E; X-4 absorbed into D2.
- [ ] `docs/adr/decisions.md` top — **Epic D — Stage-1 premise audit corrections (Sprint D0)** with P3/P8/P10/P14/P15 + Rejected tail.

---

## §C — Pass / fail summary

| Check | Automated | Manual |
|---|---|---|
| FR-2..FR-5 corrected rows | §A.1 greps | §B Step 5 |
| FR-6 decisions.md | §A.1 | §B Step 5 |
| FR-7 board clean | §A.1 | — |
| No Skills nav (D-8 deferred) | §A.2 | §B Step 1 |
| No skill chip / end / timer | §A.2 | §B Step 2 |
| Submit → Feedback still works | §A.2 | §B Step 3 |
| Coach via live middleware | — | §B Step 4 |

**D0 corrected the record — it did NOT ship Q-7 / Q-8 / Q-9 / Q-1b / D-3b / D-8.**
"Green" means the docs match the audit and the UI baseline is unchanged.
D1/D2/D3 are the sprints that will add UI; re-run this guide after those land
and expect the absence checks in §B Step 2 to flip to presence checks.
