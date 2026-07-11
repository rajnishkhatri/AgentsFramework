---
title: 'Epic A + Epic B — manual UI validation report (PR #140 · #141)'
type: review
date: 2026-07-10
status: Complete
owner: Rajnish Khatri
related:
  - docs/plan/epic-a-b-post-merge-review.md
  - frontend/scripts/validate_epic_ab_ui.md
  - frontend/e2e/learn/validate_epic_ab.spec.ts
reviews:
  - Manual walkthrough Steps 1–15 against main @ 7c2ad26 / d89905c
  - App under test: http://localhost:3003 (E2E_BYPASS_AUTH=1 pnpm dev)
---

# Epic A + Epic B — manual UI validation report

**Verdict:** Epic A **A1** (Reveal alias) and Epic B (coach chrome / pin / cold honesty / iPad
split) **pass in the browser**. Sprint **A0 did not land** on `main`. Session-continuity gaps
(Back, Wrap up, stale miss refresh) are the main follow-up cluster.

Companion review (FR inventory + matrix): [epic-a-b-post-merge-review.md](epic-a-b-post-merge-review.md).
Checklist executed: [validate_epic_ab_ui.md](../../frontend/scripts/validate_epic_ab_ui.md).

---

## Environment

| Item | Value |
|---|---|
| Branch / tip | `main` (merge #140 `7c2ad26`, #141 `d89905c`) |
| Frontend | `E2E_BYPASS_AUTH=1 pnpm dev` → **http://localhost:3003** (port 3000 already in use) |
| Date | 2026-07-10 |
| Method | Manual Steps 1–15 + DevTools Network / DOM; screenshots for Steps 8 / 15 |

---

## Step results

| Step | Title | Verdict | Evidence / notes |
|---|---|---|---|
| 1 | A0 guard test present + green | ❌ **FAIL** | `pytest …/test_parity_docs_no_refuted_framing.py` → **file not found** (exit 4). A0 never merged. |
| 2 | `decisions.md` + ADR-0025 | ⚠️ **PARTIAL** | A1 Reveal, D5a, C-4, ADR-0025 ✅. Dedicated A0 FR-D5/D6 compatibility entry ❌. |
| 3 | Reveal gated + ghost | ✅ PASS | Hint dashed accent; Reveal `text-muted`, disabled before selection. |
| 4 | Answering DOM never leaks answer | ✅ PASS | No “Why X is correct” / CORRECT ANSWER in answering phase. |
| 5 | Selection enables Reveal | ✅ PASS | `data-enabled="true"` after choice. **Polish:** enabled Reveal could use darker text. |
| 6 | Reveal → Feedback | ✅ PASS | Same path as Submit; banner + teaching letter; URL stays `/learn/quiz`. |
| 7 | Feedback recap + Ask the coach | ✅ PASS | Recap + Ask the coach + Next/Finish visible. |
| 8 | Cold `/learn/coach` honest-absent | ✅ PASS | Hard refresh → no current-item / no history. (Sidebar after quiz correctly *keeps* pin — not cold.) |
| 9 | Desktop two-column | ✅ PASS | Rail + chat side-by-side; chips above log. |
| 10 | Cold chip → ask, no fake history | ✅ PASS | POST body: `messages` only; **no** `coach_context` / `misses_aggregate`. Stream deltas OK. |
| 11 | Ask the coach → pin + wire | ✅ PASS* | Pin updates (e.g. Q5 after 5 items). History/opener when misses exist. *See FLAG-1 stale count.* |
| 12 | Modes display-only | ✅ PASS | Mode spans not clickable; chips clickable. |
| 13 | Back + Wrap up navigate | ✅ PASS* | Both navigate. *FLAG-4 / FLAG-5 product gaps.* |
| 14 | Feedback Next / Finish | ✅ PASS* | Next works; Finish → summary **3/5**, time **1 min**. *FLAG-6 mastery tile.* |
| 15 | iPad 768×938 | ✅ PASS | Quiz split + live `CoachPanel`; standalone coach strip (no `w-64` rail); shared thread. |

\* = FR navigation/behavior OK; product follow-ups logged below.

---

## Findings (follow-ups)

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| **A0 gap** | High (docs/trust) | Sprint A0 never landed: no `tests/architecture/test_parity_docs_no_refuted_framing.py`; epics/VISUAL still carry live “FR-D5/FR-D6 contradiction” framing. | Step 1; `ls tests/architecture/` |
| **FLAG-1** | Medium | Miss count `useEffect` on coach page depends only on `pin?.skillId` → after more misses on the same skill, history N can stay stale until remount. | [coach/page.tsx](../../frontend/app/(coach)/learn/coach/page.tsx) effect deps; manual multi-miss walk |
| **FLAG-4** | Medium | ← Back uses `router.back()` but quiz remounts and `openSession` again → learner returns to **Q1**, not the item they left. Spec C2 only required back navigation, not session resume. | Step 13; quiz page mount effect |
| **FLAG-5** | Medium | Wrap up pushes `/learn/summary` **without** `?session=` → “No session to summarize.” Comment says B2 would append session id; never wired. Quiz Finish correctly uses `?session=`. | [coach/page.tsx `onWrapUp`](../../frontend/app/(coach)/learn/coach/page.tsx); summary page requires `session` param |
| **FLAG-6** | Low | Summary “Mastery” tile is **signed delta** on focus/recommended skill; adaptive runs often show `0%` / `+0%` even with a non-zero score — easy to misread as absolute mastery. | Step 14: score 3/5, time 1 min OK, mastery 0% |
| **Polish** | Low | Reveal stays `text-muted` when enabled; opener copy cites `pin.label` (item) for skill-scoped N (“I see 1 miss on Q1 · s-punc”). | Steps 5, 11 |

---

## What shipped cleanly (confirmed live)

- **A1:** Reveal = gated submit alias; ghost styling; no answer leak in answering DOM.
- **B cold honesty:** no fabricated current-item / history / `misses_aggregate` on cold ask.
- **B pin bridge:** Feedback → Ask the coach updates current item; chips POST; stream works.
- **B D5a:** three mode labels, display-only; chips → `onAsk`.
- **B layout:** desktop rail+chat; iPad quiz split + standalone strip.
- **B Finish path:** real score + time on summary when `?session=` present.

---

## Sign-off

| Check | Result |
|---|---|
| Manual Steps 1–15 completed | ✅ (Step 1 fail recorded; rest exercised) |
| Honesty notes H1–H8 from review doc read | ✅; H1 closed by automated suite + Step 10/11 manual Network |
| A0 gap + FLAG-1/4/5/6 accepted as follow-ups | ✅ filed above |
| ADR-0025 + A1/B0 decisions present | ✅ |
| Automated `validate_epic_ab.spec.ts` | Recorded separately in post-merge review (7/7 on 2026-07-10) |

**Reviewer:** Rajnish Khatri · **Date:** 2026-07-10 · **PRs:** #140, #141

**Recommendation:** Treat A1 + Epic B UI as **validated**. Prioritize follow-ups: land A0 guard, wire Wrap-up `?session=`, resume-or-stash quiz session on Back, refresh miss count on pin/question change.
