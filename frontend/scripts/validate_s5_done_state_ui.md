# S5 — Done-state milestone + retake: validation guide

How to validate the S5 changes on the localhost `/learn` quiz UI — both the
**automated** proof (Playwright) and a **manual** step-by-step walk you can do
yourself. S5 adds a milestone banner ("🎉 You've completed your N-question
session!") when you reach the target, above the item's feedback. At that point the
two actions also flip from their originals to **Keep practising** / **See summary**
(the labels are gated on the target, not shown earlier) — no force-eject.

Spec: [`docs/plan/preact-quiz-done-state.spec.md`](../../docs/plan/preact-quiz-done-state.spec.md) ·
Commit: `9253bf6` · PR: [#138](https://github.com/rajnishkhatri/AgentsFramework/pull/138)

---

## §A — Automated proof (Playwright, run this first)

Two specs cover S5. Both run in the `learn-e2e` project (own headless Chromium,
**video on**), pure T1 (seeded browser engine, no backend/auth/LLM).

**Start the dev server once** (bypass-auth, port 3000) — either:
- the Claude Code preview (`frontend-preview` launch config), or
- `cd frontend && E2E_BYPASS_AUTH=1 pnpm dev` (or the `frontend-dev` config).

Then, from `frontend/`:

```bash
# 1. The narrated validation WALK — one continuous run, logs each FR checkpoint.
#    E2E_SCREENSHOTS=1 also attaches a screenshot at each key state to the report.
E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
  ./node_modules/.bin/playwright test --project=learn-e2e \
  e2e/learn/validate_s5_done_state.spec.ts --reporter=list

# 2. The assertion spec — four isolated FR tests (this is what the PR/CI relies on).
CI=1 BASE_URL=http://localhost:3000 \
  ./node_modules/.bin/playwright test --project=learn-e2e \
  e2e/learn/quiz-done-state.spec.ts --reporter=list
```

**Expected — spec 1 (the walk) prints a checkpoint trace and passes:**

```
  ✔ opened /learn/quiz → "Question 1 of 30"
  ✔ pre-target: buttons read "Next question" / "Finish & see summary"; NO banner yet
  ✔ walked to "Question 30 of 30" (answering #30) — still no banner (FR-4: only after grading)
  ✔ FR-4/FR-5: milestone visible at Q30, ABOVE the feedback, names "30"
  ✔ FR-3: still on /learn/quiz — no force-eject
  ✔ FR-7/FR-2: "Keep practising" → same session over-run → "Question 31" (denominator dropped)
  ✔ FR-6: "See summary" → /learn/summary with the stored score
  S5 validation walk PASSED — all FR checkpoints green.
  1 passed
```

**Expected — spec 2 (assertions): `4 passed`.**

### Watch it run (answers "can I see the browser?")

The Playwright run drives its **own** headless browser — it does NOT render into
the Claude preview panel (that's a separate browser). To *see* the run:

- **Video:** every `learn-e2e` test records `video.webm`. After a run, open:
  ```
  frontend/test-results/validate_s5_done_state-*/video.webm
  frontend/test-results/quiz-done-state-*/video.webm
  ```
- **HTML report** (screenshots + steps + video inline): run **without** `CI=1` so
  the HTML reporter is used, then open the report:
  ```bash
  BASE_URL=http://localhost:3000 ./node_modules/.bin/playwright test \
    --project=learn-e2e e2e/learn/validate_s5_done_state.spec.ts
  ./node_modules/.bin/playwright show-report
  ```
  With `E2E_SCREENSHOTS=1`, the report shows the pre-target, boundary-milestone,
  over-run, and summary screenshots attached to the walk.
- **Headed mode** (watch the actual browser window live):
  ```bash
  BASE_URL=http://localhost:3000 ./node_modules/.bin/playwright test \
    --project=learn-e2e e2e/learn/validate_s5_done_state.spec.ts --headed
  ```

---

## §B — Manual UI walk (localhost, ~2 min if you seed a short target)

> **Heads-up on the walk length.** A dev session opens at the **30-question**
> target floor, so reaching the milestone by hand means answering 30 items. To
> keep it quick, you can pick any answer each time (correctness doesn't gate the
> done-state — only the *count* does). Or trust §A and spot-check the two things
> below that are visible immediately.

Open `http://localhost:3000/learn/quiz`.

**Step 1 — Pre-target labels are the ORIGINALS (no walking needed).**
Answer the first question (pick any choice → **Submit answer**). On the feedback
screen, confirm the two buttons read their **original** labels:
- **Next question →**
- **Finish & see summary**
✅ The S5 labels do NOT appear yet — they are **gated on reaching the target**
(reverted 2026-07-09). No milestone banner yet either (correct — target not reached).

**Step 2 — Progress bar counts up.**
Press **Next question →** and repeat. The top bar advances "Question 2 of 30",
"Question 3 of 30", … and the fill grows. (This is the S4 bar; S5 rides on it.)

**Step 3 — The milestone + the label flip at the target.**
Continue until you answer **question 30**. On the feedback screen for #30 you
should see, **above the answer feedback**:
> 🎉 You've completed your 30-question session!

…and the two buttons now **flip** to **Keep practising** / **See summary** (in
lock-step with the banner). ✅ **FR-4/FR-5** — the banner names the count and sits
above the feedback (you can still see #30's answer). ✅ **FR-3** — you are NOT
auto-navigated away; you're still on `/learn/quiz`.

**Step 4 — Keep practising past the target (over-run).**
Press **Keep practising**. The next item shows **"Question 31"** — note the bar
now **drops the "of 30"** denominator (you're past the goal, so the fixed target
stops being shown). ✅ **FR-2 / FR-7** — same session continues, tally preserved.

**Step 5 — Exit to the Summary.**
Answer once more, then on the feedback screen press **See summary**. You land on
`/learn/summary?session=…` showing your score. ✅ **FR-6** — the session closed and
routed with the stored score (the Summary does not re-tally).

**Retake:** from the Summary, the CTA links back to `/learn/quiz` (a fresh
session) and the skill/bucket links open a focused drill — the retake surface
already existed; S5 just routes you to it.

---

## §C — Selector reference (for debugging a failed step)

| What | `data-testid` | Notes |
|---|---|---|
| Milestone banner | `quiz-done-banner` | Present only when `gradedTotal >= target_count` |
| Feedback banner | `feedback-banner` | The answer feedback; banner renders ABOVE it |
| Progress bar | `quiz-progress` | "Question N of M"; drops "of M" in over-run |
| Answer choice A | `choice-A` | (also `choice-B/C/D`) |
| Submit | `quiz-submit` | Answering phase |
| Keep practising | `quiz-next` | **Label changed, testid unchanged** — same handler |
| See summary | `quiz-finish` | **Label changed, testid unchanged** — same handler |

The two action `data-testid`s are **deliberately unchanged** from S3/S4 — only the
label text changed — so every existing selector and the loop behaviour are
untouched (FR-10). That's why the S3/S4 regression specs still pass.

---

## §D — What's NOT visually testable here

- **The `complete` threshold math** (endless session, exact boundary `>=`,
  `target=1`, the answering-vs-reviewing offset) is byte-covered by the unit tests
  (`lib/translators/quiz_progress_vm.test.ts`, 12 cases) — cheaper than walking
  those edges live.
- **No i18n:** the banner copy is an inline literal (the repo has no `t()` helper
  yet); this is intentional and matches the sibling components.
- **Dashboard mastery after all-wrong** shows ~100% — that is a **separate, known,
  parked bug** (F1 in `docs/plan/preact-learn-followups.notes.md`), NOT an S5
  concern. Don't be alarmed if you answer 30 wrong and the dashboard looks off.
