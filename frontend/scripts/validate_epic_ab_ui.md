# Manual UI walkthrough — Epic A (PR #140) + Epic B (PR #141)

**Audience:** you (the user), running the app on your machine, in a browser, following steps 1–15
sequentially. Each step has a **do** action and one or more **check** observations. Tick each row
after you observe it; annotate any red-flag with a screenshot.

**Pre-req:** local dev backend running against `main` (or a checkout of `main`); browser at
[http://localhost:3000](http://localhost:3000); dev tools open so you can inspect DOM/CSS.

```bash
git checkout main
git pull
cd frontend
pnpm install
E2E_BYPASS_AUTH=1 pnpm dev
```

If sign-in intercepts, either sign in with your WorkOS user OR set `E2E_BYPASS_AUTH=1` in the dev
env (see `frontend/AGENTS.md`).

Companion: [../../docs/plan/epic-a-b-post-merge-review.md](../../docs/plan/epic-a-b-post-merge-review.md).

---

## Legend

- ✅ PASS — behavior matches spec.
- ❌ FAIL — behavior contradicts spec.
- ⚠️ FLAG — unexpected but not clearly a defect (log for follow-up).
- 🚧 KNOWN-GAP — see honesty note H# in the review doc.

---

## Step 1 — Guard test is present and green

**Do:** in the repo root, run:
```bash
pytest tests/architecture/test_parity_docs_no_refuted_framing.py -v
```

**Check:**
- [ ] Command exits 0.
- [ ] Test file exists at `tests/architecture/test_parity_docs_no_refuted_framing.py`.
- [ ] Try temporarily inserting the string "FR-D5/FR-D6 contradiction" (unmarked) into
      `docs/plan/preact-parity-sprint-board-A.md` — re-run test — it MUST fail. Restore.

Covers: **A0-1, A0-7**. Honesty note **H7**.

---

## Step 2 — decisions.md + ADR-0025 present

**Do:**
```bash
head -60 docs/adr/decisions.md
ls docs/adr/0025-coach-surface-vm.md
```

**Check:**
- [ ] Newest decisions.md entries reference: FR-D5/D6 compatibility (A0), A1 Reveal alias, D5a mode
      display, C-4 honesty rule.
- [ ] `0025-coach-surface-vm.md` exists (status: Accepted).

Covers: **A0-3, A1-FR6, B0-1, B0-2, B1-FR11**.

---

## Step 3 — Quiz screen: Reveal is gated, honest ghost control

**Do:** navigate to [http://localhost:3000/learn/quiz](http://localhost:3000/learn/quiz). Wait for a
question to load. Open DOM inspector on the two buttons: "Get a hint" and "Reveal answer".

**Check (BEFORE clicking any choice):**
- [ ] "Get a hint" has classes containing `border-dashed` and `border-accent` (or `text-accent`).
- [ ] "Reveal answer" has classes containing `text-muted` — visually lighter than Submit.
- [ ] "Reveal answer" `data-enabled` attribute = `"false"`.
- [ ] "Reveal answer" `disabled` attribute is present (button is not clickable).
- [ ] Click "Reveal answer" — nothing happens. URL stays `/learn/quiz`; no Feedback appears.

Covers: **A1-FR1, A1-FR4**.

---

## Step 4 — Quiz answering DOM never leaks the answer

**Do:** with the question loaded but no choice yet selected, open the browser page-source view (or
copy the `<main>` innerText).

**Check:**
- [ ] No text like "Why A is correct" / "Why B is correct" / "CORRECT ANSWER" anywhere on screen.
- [ ] `data-testid="quiz-reveal"` button has NO `data-answer` or similar reveal attribute.

Covers: **A1-FR2**. This is the trust invariant that keeps the letter off the Quiz surface even if
Reveal is later re-shaped.

---

## Step 5 — Selecting a choice enables Reveal (same gate as Submit)

**Do:** click choice A (or any letter).

**Check:**
- [ ] Both buttons flip to `data-enabled="true"`; neither is disabled.
- [ ] They share the same gate: try un-selecting is not offered; both remain enabled.

Covers: **A1-FR1 (positive), A1-FR3 (setup)**.

---

## Step 6 — Reveal → Feedback (the same path as Submit)

**Do:** click "Reveal answer" (NOT Submit).

**Check:**
- [ ] Feedback banner appears (`data-testid="feedback-banner"`).
- [ ] The banner text is one of: "Exactly right." OR "Not quite — and that's useful."
- [ ] The Quiz Reveal + Submit buttons are GONE from the DOM (Quiz phase replaced by review).
- [ ] "Why X is correct: …" line is visible (Feedback teaches the letter).
- [ ] URL is still `/learn/quiz` (Feedback is a sub-state of the quiz page).

Covers: **A1-FR3**.

---

## Step 7 — Feedback recap block + Ask-the-coach control

**Do:** stay on Feedback from Step 6. Find the recap `<p>` right below the banner. Find the
"Ask the coach" button below the rationale sections.

**Check:**
- [ ] `data-testid="feedback-recap"` exists and has `data-has-underline` in {`true`, `false`}.
      - If `true`: an underlined span within it is styled green (`text-success`, `underline`).
      - If `false`: recap is plain text (no invented highlight). 🚧 this is legit — see H4.
- [ ] `data-testid="feedback-ask-coach"` button is visible with text "Ask the coach" on desktop.
      (On iPad — skip; the panel handles it.)
- [ ] "Next question →" and "Finish & see summary" both visible below.

Covers: **B-FR7 (recap), B-FR5 (button visible)**. Honesty **H4**.

---

## Step 8 — Cold `/learn/coach`: honest-absent chrome

**Do:** in a new tab, go to [http://localhost:3000/learn/coach](http://localhost:3000/learn/coach)
directly (NOT via Ask-the-coach — this simulates cold entry).

**Check:**
- [ ] Header shows `← Back` and `Wrap up session →` (both `data-testid="coach-back"` and
      `coach-wrap-up`).
- [ ] Rail (or strip / stacked, depending on viewport) shows "Your Coach" and "Adaptive · always on".
- [ ] NO `data-testid="coach-current-item"` element present in DOM. (search DOM)
- [ ] NO `data-testid="coach-history"` element present in DOM.
- [ ] Three mode labels visible: "In-drill Socratic", "Post-answer deep-dive", "Misconception summary".
- [ ] Each mode is a `<span>` (NOT a `<button>`); inspecting confirms.
- [ ] Exactly one mode has `data-active="true"` — should be Socratic (pre_submit).
- [ ] Try clicking the mode labels — nothing happens (they're display-only).

Covers: **B-FR2 (header), B1-FR4 (rail), B1-FR3 (no pin), B1-FR1 (no misses), B1-FR2 (non-interactive
modes), B1-FR7 (three labels, one active), B-FR4 (cold honest-absent), B-FR14**. Honesty **H3, H5**.

---

## Step 9 — Desktop `/learn/coach`: two-column layout

**Do:** ensure your browser is at desktop width (≥1024px, e.g. maximize a Chrome window on a
1440px screen).

**Check:**
- [ ] `data-testid="coach-workspace-body"` contains BOTH `coach-context-column` and
      `coach-chat-column`.
- [ ] In dev-tools, `getBoundingClientRect()` on the two columns: **rail's right edge ≤ chat's left
      edge** (they are side-by-side, not stacked).
- [ ] `coach-context-column` has class `w-64` → 256px wide.
- [ ] The chat column contains chips ABOVE the log region.

Covers: **B-FR3, B-FR9 (chips beside composer)**. Honesty **H6, H8** (cosmetic-only rail-width
difference vs prototype's ~280px).

---

## Step 10 — Cold coach: chip click → ask fires without fabricated history

**Do:** on cold `/learn/coach` (Step 8 state), open DevTools → Network tab. Click one of the three
chips (e.g. "Explain the rule simply"). Inspect the outgoing POST to `/api/coach/run/stream`.

**Check:**
- [ ] A POST to `/api/coach/run/stream` fired.
- [ ] Response streams a reply into the coach log region (`role="log"`).
- [ ] Request body: EITHER no `coach_context` field, OR `coach_context` present but with NO
      `misses_aggregate` object (or `misses_aggregate == null`). ⚠️ if you see a
      `misses_aggregate.window` field with anything like "of last 5", flag it: this is a HONESTY
      violation.
- [ ] Coach reply arrives; typing indicator `[data-testid='coach-typing']` disappears.

Covers: **B1-FR8 (chip→ask), B-FR9 (no fake history), B-FR13 (mocked path OK)**.

---

## Step 11 — Feedback → Ask-the-coach → pin + `coach_context` on wire

**Do:** in a fresh tab: `/learn/quiz` → submit an answer → Feedback → click "Ask the coach".

**Check:**
- [ ] URL becomes `/learn/coach`.
- [ ] `data-testid="coach-current-item"` NOW visible with text starting `Current item: Q1 · …`.
- [ ] If the pinned skill has any prior misses in the fixtures →
      `data-testid="coach-history"` visible with `Sees your history: N misses on <skill>`.
      🚧 if no misses in fixtures, history line is absent (this is CORRECT per H3).
- [ ] Open DevTools → Network. Click a chip. Inspect the POST body.
- [ ] `body.input.coach_context.question_id` = the pinned question ID.
- [ ] `body.input.coach_context.skill_id` = the pinned skill.
- [ ] The BFF's returned mode may differ from client-sent mode — this is expected (ADR-0012;
      sanitizer overwrites).
- [ ] The active mode label in the rail flips from "In-drill Socratic" → "Post-answer deep-dive"
      (the store pin uses `post_feedback`).

Covers: **B-FR5, B-FR6, B-FR10, B1-FR5, B-FR11, B1-FR7 (mode flip), B-FR12 (opener when honest
opener applies)**. Honesty **H1, H3, H5**.

**If any of the wire-body checks fail, this is H1 — file a follow-up per §5.**

---

## Step 12 — Modes are display-only (D5a)

**Do:** in the same coach view (with or without pin), inspect each of the three mode `<span>`s.

**Check:**
- [ ] Attempt to change the mode by clicking / keyboard: NOTHING happens.
- [ ] `data-active="true"` is set on exactly ONE mode; that one visually reads "active"
      (accent border/bg).
- [ ] `aria-current="true"` on the active one (for screen readers).

Covers: **B1-FR2, B1-FR7, B-FR14**.

---

## Step 13 — Coach header actions actually navigate

**Do:** on `/learn/coach`, click "← Back".

**Check:**
- [ ] Browser goes back one page in history (if you came from Quiz, back to Quiz). If cold-opened
      (no history), it navigates to `/learn/quiz` as a fallback.

**Do:** click "Wrap up session →".

**Check:**
- [ ] URL becomes `/learn/summary` (query-string may be empty on cold, or `?session=…` if
      a live quiz session id is known).

Covers: **B-FR2**.

---

## Step 14 — Feedback Next / Finish still work (no regression)

**Do:** run through 2 quiz items via Submit + Next, then Finish on the 3rd.

**Check:**
- [ ] Each "Next question →" loads a new question.
- [ ] "Finish & see summary" navigates to `/learn/summary`.
- [ ] Summary page displays a real score, mastery delta, time (may show 0 min for a fast session —
      known capture artifact per Epic A A2 board, not a defect).

Covers: **B-FR8** (bridge doesn't regress loop) plus A2 board caveat.

---

## Step 15 — iPad viewport parity spot-check

**Do:** open Chrome DevTools → Device toolbar → select "iPad" (or 768×1024). Reload
`/learn/coach`.

**Check:**
- [ ] `data-testid="coach-chrome"` has `data-layout="strip"` (or `stacked`), NEVER `rail`.
- [ ] No 256px left column; rail collapses to a header strip.

**Do:** in the same iPad viewport, go to `/learn/quiz`.

**Check:**
- [ ] The page renders as a SPLIT: quiz item on the left, `CoachPanel` on the right (or panel
      below on iPhone).
- [ ] The panel contains its own `data-testid="coach-chrome"` (shared component).
- [ ] Type in the panel composer → the reply appears in the panel log.
- [ ] Ask-the-coach button is NOT shown on iPad Feedback (spec FR-8: iPad has live panel already).

Covers: **B-FR1, B1-FR9, B-FR8 (iPad non-regression), FE-FR-J3 one-thread invariant**.

---

## Sign-off block

After every step ticked (or every red-flag logged in the review doc as a follow-up):

- [ ] Automated: `pnpm exec playwright test e2e/learn/validate_epic_ab.spec.ts` green.
- [ ] All ✅ / 🚧 rows in this checklist ticked; ❌ rows filed as issues.
- [ ] Honesty notes H1–H8 in the review doc read; H1/H2 either accepted or filed as follow-ups.
- [ ] `pytest tests/architecture/ -q` still green on `main`.

Reviewer: ______________________________ · Date: _______ · PR #140, #141 reviewed.
