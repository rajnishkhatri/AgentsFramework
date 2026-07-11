---
title: 'D4 — Skills nav via comingSoon · Implementation trace'
type: impl
sprint: D4
epic: D
status: Closed — Declined 2026-07-11 (T-GATE → defer to Epic E)
owner: Rajnish Khatri
derives_from: docs/plan/preact-parity-D4-skills-nav.tasks.md
---

# D4 — Implementation trace

Branch: `feat/preact-parity-d4-skills-nav` (from `origin/main`, isolated from D3).
**Sprint closed via T-DEFER** — no production code.

## T-DES-D4 — Nav-order + surface-consistency (locked 2026-07-11)

### 1. Placement in `NAV_MEMBERSHIP.desktop` / `.ipad`

**Decision:** insert `"skill"` between `"coach"` and `"progress"`:

```ts
desktop: ["dashboard", "quiz", "coach", "skill", "progress"],
ipad:    ["dashboard", "quiz", "coach", "skill", "progress"],
```

**Prototype citation.** `PreAct/UI-Design/design-spec.md` §8 Navigation Map (line 268):

> sidebar (desktop/iPad) — Dashboard / Practice→Quiz / Skills→Skill / Progress / Coach

That order places Skills after Practice and before Progress, with Coach last.
The live shell already diverges: membership is
`["dashboard", "quiz", "coach", "progress"]` (Coach before Progress). Reordering
Coach to match the prototype is out of D4 scope (surgical add only). Inserting
`"skill"` between `"coach"` and `"progress"` keeps Coach where it ships today
and lands Skills immediately before the aggregate Progress view — same
semantic slot the plan §2 rationale describes ("drill into one bucket" between
conversational coach and aggregate progress).

**Not chosen:** reordering to
`["dashboard", "quiz", "skill", "progress", "coach"]` to match the prototype
literally — that would also move Coach and expand the blast radius beyond
D-8.

### 2. iPhone consistency call

**Decision:** Skills does **not** appear on iPhone. `NAV_MEMBERSHIP.iphone`
stays `["dashboard", "quiz", "progress"]`.

**Citations:**
- `design-spec.md` line 216 / 268: iPhone bottom tabs are
  Home / Practice / Coach / Progress — **Skills is not a global tab**.
- Product already supersedes with a 3-tab bar (no Coach on iPhone either);
  D4 does not reopen that.

**Follow-up (Epic E, not D4):** if a contextual Skills overflow ("More" /
long-press) appears in a later prototype pass, Epic E owns it together with
the live `/learn/skill` route.

## T-GATE — human posture pick (2026-07-11)

**Chose: Default (defer to Epic E).** Ship path T-1..T-11 skipped.

## T-DEFER — closure evidence

- `docs/adr/decisions.md` — D-8 deferral line prepended (newest-first).
- `docs/plan/preact-parity-sprint-board-D.md` — D4 status → **Declined**.
- `docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md` — §D-8 → deferred to Epic E.
- No `frontend/` code changes.
- Verification: `grep 'D-8' docs/adr/decisions.md` returns the deferral line.

## Manual validation

Step-by-step checklist (docs-only deferral path):
[`frontend/scripts/validate_d4_skills_nav_defer.md`](../../frontend/scripts/validate_d4_skills_nav_defer.md).
Ship-path UI runbook (`validate_d4_skills_nav_ui.md`) was **not** authored — T-VAL-D4* skipped.

**Walk completed 2026-07-11 — Parts 0–8 all pass.** Evidence paste:

```
feat/preact-parity-d4-skills-nav
15:- D-8 (2026-07-11): deferred to Epic E per D4 alternate declined. ...
57:| **D4 (opt.)** | ... | ⬛ **Declined** 2026-07-11 — deferred to Epic E |
NAV_MEMBERSHIP desktop/ipad = ["dashboard","quiz","coach","progress"] (no skill)
OK: no skill route
git diff --stat -- frontend/ → empty
```
