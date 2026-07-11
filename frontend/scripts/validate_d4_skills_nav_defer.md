# D4 Manual Validation — Skills nav via `comingSoon` (**deferral path**)

**Sprint:** D4 · **Branch:** `feat/preact-parity-d4-skills-nav` · **Outcome:** Declined (T-GATE → defer)

| Artifact | Path |
|---|---|
| Spec (EARS, alternate) | [`docs/plan/preact-parity-D4-skills-nav.spec.md`](../../docs/plan/preact-parity-D4-skills-nav.spec.md) |
| Plan / tasks | [`docs/plan/preact-parity-D4-skills-nav.tasks.md`](../../docs/plan/preact-parity-D4-skills-nav.tasks.md) |
| Impl trace | [`docs/plan/preact-parity-D4-skills-nav.impl.md`](../../docs/plan/preact-parity-D4-skills-nav.impl.md) |
| Decision | [`docs/adr/decisions.md`](../../docs/adr/decisions.md) — `D-8 (2026-07-11)` |
| Board | [`docs/plan/preact-parity-sprint-board-D.md`](../../docs/plan/preact-parity-sprint-board-D.md) §Sprint D4 |
| Parity | [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](../../docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md) §D-8 |

This runbook validates the **tasks that actually ran** in this session:

| Task | Ran? | What to prove |
|---|---|---|
| **T-DES-D4** | yes | Design lock + citations in `impl.md` |
| **T-GATE** | yes | Human chose **defer** (recorded in `impl.md`) |
| **T-DEFER** | yes | `decisions.md` + board Declined + parity §D-8; **no code** |
| T-1…T-11 / T-VAL-D4* | **skipped** | Ship path + UI walk do **not** apply |

> **Not a browser UI walk.** Deferral is docs-only. You should *not* see a Skills
> nav item. If you do, the wrong branch / stale WIP is checked out.

---

## What you should expect (acceptance bar)

| # | Check | Expect |
|---|---|---|
| 1 | Branch | `feat/preact-parity-d4-skills-nav` |
| 2 | `decisions.md` | Newest line starts with `D-8 (2026-07-11): deferred to Epic E per D4 alternate declined` |
| 3 | Sprint board D4 | Header says **Declined**; ladder table row says Declined; exit criterion `[x]` |
| 4 | Parity §D-8 | Status / notes say deferred to Epic E (not "partial" / "defer or ship") |
| 5 | `impl.md` | T-DES-D4 + T-GATE (defer) + T-DEFER evidence present |
| 6 | `NAV_MEMBERSHIP` | Still `desktop/ipad = ["dashboard","quiz","coach","progress"]` — **no `"skill"`** |
| 7 | Route | `frontend/app/(coach)/learn/skill/` does **not** exist |
| 8 | Frontend diff | No production `.ts`/`.tsx` changes from this sprint |

---

## Task → step map

| Plan task | Manual step |
|---|---|
| T-DES-D4 | Part 2 |
| T-GATE | Part 3 |
| T-DEFER (`decisions.md`) | Part 4 |
| T-DEFER (board) | Part 5 |
| T-DEFER (parity) | Part 6 |
| T-DEFER (no code) | Part 7 |
| Negative / Q-6 safety | Part 8 |
| Closure | Part 9 |

---

## Part 0 — Boot (checkout + restore deferral edits)

Parallel D3 work repeatedly switched this checkout and stashed the D4 docs.
**Do this first** or every later grep will fail on the wrong branch.

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent

# 1. Confirm where you are
git branch --show-current
# If not on D4, park other WIP first, then:
git checkout feat/preact-parity-d4-skills-nav

# 2. Find the stash that holds the D-8 deferral line
git stash list | head -15
# Look for a stash created ON feat/preact-parity-d4-skills-nav whose
# `git stash show` touches only:
#   docs/adr/decisions.md
#   docs/plan/preact-parity-sprint-board-D.md
#   docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
# Known good names from this session:
#   "D4-session-dirt before finishing D3 074547"
#   "PARALLEL-WIP before D3 commit isolation 074436"

# 3. Preview, then apply (apply, don't drop — keep a safety copy)
N=0   # replace with the matching stash index
git stash show "stash@{$N}" --stat
git stash show -p "stash@{$N}" | grep -E 'D-8 \(2026-07-11\)|Declined' | head
git stash apply "stash@{$N}"

# 4. Confirm working tree has the three tracked mods + D4 untracked docs
git status --short | grep -E 'decisions|sprint-board|VISUAL|D4-skills'
```

- [ ] On `feat/preact-parity-d4-skills-nav`
- [ ] Stash applied; `docs/adr/decisions.md` is modified
- [ ] Untracked D4 bundle present: `spec.md` / `plan.md` / `tasks.md` / `impl.md`

**Fail if:** still on `feat/preact-parity-d3-session-length`, or `grep 'D-8 (2026-07-11)' docs/adr/decisions.md` is empty after apply.

---

## Part 1 — Scope check (only deferral tasks should have run)

Open [`docs/plan/preact-parity-D4-skills-nav.tasks.md`](../../docs/plan/preact-parity-D4-skills-nav.tasks.md) and confirm the deferral path text:

> If not overridden, only T-DEFER runs.

- [ ] Tasks file still says ship path is alternate-only
- [ ] No new files under `frontend/e2e/learn/nav-skills-coming-soon.spec.ts`
- [ ] No `frontend/tests/architecture/test_no_dead_skill_route.ts`
- [ ] No `frontend/scripts/validate_d4_skills_nav_ui.md` (ship-path UI runbook — not authored)

```bash
test ! -f frontend/e2e/learn/nav-skills-coming-soon.spec.ts && echo OK: no ship e2e
test ! -f frontend/tests/architecture/test_no_dead_skill_route.ts && echo OK: no arch guard
test ! -f frontend/scripts/validate_d4_skills_nav_ui.md && echo OK: no ship UI runbook
```

---

## Part 2 — T-DES-D4 (design lock)

Open [`docs/plan/preact-parity-D4-skills-nav.impl.md`](../../docs/plan/preact-parity-D4-skills-nav.impl.md) §T-DES-D4.

### 2a. Placement decision

- [ ] Records insert `"skill"` between `"coach"` and `"progress"` for desktop + ipad
- [ ] Cites `PreAct/UI-Design/design-spec.md` §8 / line ~268
  (`Dashboard / Practice→Quiz / Skills→Skill / Progress / Coach`)
- [ ] Explains why Coach was **not** reordered (surgical add only)

Spot-check the prototype cite yourself:

```bash
rg -n "Dashboard / Practice|Skills→Skill|bottom tab" PreAct/UI-Design/design-spec.md | head
```

### 2b. iPhone consistency

- [ ] Decision: Skills does **not** appear on iPhone
- [ ] `iphone` membership stays `["dashboard", "quiz", "progress"]`
- [ ] Epic E follow-up noted (contextual overflow out of scope)

---

## Part 3 — T-GATE (human posture)

In the same `impl.md`, §T-GATE:

- [ ] Records **Chose: Default (defer to Epic E)**
- [ ] States ship path T-1..T-11 skipped
- [ ] Matches this session’s chat answer: **defer**

---

## Part 4 — T-DEFER · `decisions.md`

```bash
grep -n 'D-8' docs/adr/decisions.md | head -5
# Expect newest bullet:
# - D-8 (2026-07-11): deferred to Epic E per D4 alternate declined. ...
```

- [ ] Line present near the top (newest-first)
- [ ] Wording includes: `deferred to Epic E per D4 alternate declined`
- [ ] Mentions Q-6 / no live `/learn/skill` / alternate spec path preserved
- [ ] Mentions T-DES-D4 placement lock (coach→skill→progress; iPhone unchanged)

**Fail if:** only the older D0/P14 “default = defer” prose exists and the dated
`D-8 (2026-07-11)` closure line is missing.

---

## Part 5 — T-DEFER · sprint board

Open [`docs/plan/preact-parity-sprint-board-D.md`](../../docs/plan/preact-parity-sprint-board-D.md).

```bash
rg -n 'D4 \(opt\.\)|Sprint D4|\[x\] \*\*D4' docs/plan/preact-parity-sprint-board-D.md
```

- [ ] Ladder table: D4 row → **Declined** 2026-07-11 — deferred to Epic E
- [ ] §Sprint D4 header → **Declined** *(human stuck with default)*
- [ ] **Outcome** paragraph cites `decisions.md` + `impl.md` + preserved alternate spec
- [ ] Epic-D exit criteria: `- [x] **D4 (optional):** explicitly deferred…`

---

## Part 6 — T-DEFER · parity report §D-8

Open [`docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md`](../../docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md).

```bash
rg -n 'D-8' docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md | head -6
```

- [ ] §1 table D-8 status → `🟡 deferred to Epic E` (not bare `partial`)
- [ ] Notes say **Deferred to Epic E per D4 alternate declined (2026-07-11)**
- [ ] §10 findings table D-8 → deferred / route + membership land together
- [ ] Does **not** still say only “defer or ship `comingSoon`” as an open choice

---

## Part 7 — T-DEFER · no production code

```bash
# On the D4 branch, after applying the deferral stash:
git status --short
git diff --stat -- frontend/
git diff -- frontend/components/shell/nav_model.ts   # expect empty
```

- [ ] `git diff --stat -- frontend/` is empty for this sprint’s intent
  (ignore unrelated untracked D2 tests / scripts from other threads)
- [ ] Tracked mods are only the three docs files from Parts 4–6
- [ ] Untracked D4 docs (`spec`/`plan`/`tasks`/`impl` + this runbook) are OK

---

## Part 8 — Negative / Q-6 safety (prove Skills was NOT shipped)

These prove the deferral actually held — taxonomy stays legible only as a
*future* Epic E item, not a dead nav click.

### 8a. Membership unchanged

```bash
rg -n -A6 'NAV_MEMBERSHIP' frontend/components/shell/nav_model.ts
```

- [ ] `desktop:` = `["dashboard", "quiz", "coach", "progress"]`
- [ ] `ipad:` = same
- [ ] `iphone:` = `["dashboard", "quiz", "progress"]`
- [ ] `"skill"` does **not** appear in any of the three arrays

### 8b. Catalog still comingSoon (unchanged FR-6 posture)

```bash
rg -n 'id: "skill"' -A1 frontend/components/shell/nav_model.ts
```

- [ ] `screen("skill")` still `comingSoon: true`, route `/learn/skill`

### 8c. No live route directory

```bash
ls frontend/app/\(coach\)/learn/
test ! -d 'frontend/app/(coach)/learn/skill' && echo OK: no skill route
```

- [ ] Directory listing has no `skill/`
- [ ] `test ! -d …/skill` prints `OK`

### 8d. Optional live smoke (sidebar still 4 items)

Only if `pnpm dev` is already up — **not required** for deferral closure:

1. Open `/learn` at desktop width (≥1280px).
2. Sidebar labels: Home / Practice / Coach / Progress — **no Skill**.
3. Progress remains dimmed / coming-soon.

- [ ] (optional) No Skills row in sidebar
- [ ] (optional) Progress still non-clickable coming-soon

---

## Part 9 — Pass / fail summary

Tick when Parts 0–8 are green:

| Part | Result |
|---|---|
| 0 Boot / restore | [x] pass · [ ] fail — 2026-07-11; applied `stash@{1}` (`D4-session-dirt…074547`) on `feat/preact-parity-d4-skills-nav` |
| 1 Scope (ship tasks absent) | [x] pass · [ ] fail |
| 2 T-DES-D4 | [x] pass · [ ] fail |
| 3 T-GATE defer | [x] pass · [ ] fail |
| 4 `decisions.md` | [x] pass · [ ] fail |
| 5 Sprint board | [x] pass · [ ] fail |
| 6 Parity §D-8 | [x] pass · [ ] fail |
| 7 No frontend code | [x] pass · [ ] fail |
| 8 Q-6 negatives | [x] pass · [ ] fail — membership unchanged; no `skill/` route |

**Sprint closed when all required parts pass.** ✅ Parts 0–8 passed 2026-07-11.
Next durable step: commit the three tracked docs + D4 plan bundle on
`feat/preact-parity-d4-skills-nav` so parallel D3 checkouts stop displacing them.

### One-liner evidence paste (for chat / PR)

```bash
git branch --show-current
grep -n 'D-8 (2026-07-11)' docs/adr/decisions.md
rg -n 'Declined|\[x\] \*\*D4' docs/plan/preact-parity-sprint-board-D.md
rg -n 'deferred to Epic E' docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
rg -n -A6 'NAV_MEMBERSHIP' frontend/components/shell/nav_model.ts
test ! -d 'frontend/app/(coach)/learn/skill' && echo 'OK: no skill route'
git diff --stat -- frontend/
```
