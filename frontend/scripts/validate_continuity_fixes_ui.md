# Manual UI walkthrough — Epic A/B continuity fixes

**Status: VALIDATED — 2026-07-10**  
Manual Steps 1–6 complete · `pnpm test:e2e:continuity` **4 passed** · open note: FLAG-6 mastery *value* honesty (label ✅).

**Audience:** you, validating FLAG-1 / FLAG-4 / FLAG-6 / Reveal polish on localhost
after the continuity-fix implementation. Tick each row; screenshot any ❌.

**Spec:** [`docs/plan/epic-ab-continuity-fixes.spec.md`](../../docs/plan/epic-ab-continuity-fixes.spec.md)  
**Automated companion:** [`e2e/learn/validate_continuity_fixes.spec.ts`](../e2e/learn/validate_continuity_fixes.spec.ts)  
**Prior Epic A/B walk (unchanged):** [`validate_epic_ab_ui.md`](./validate_epic_ab_ui.md)

| Fix | FR | Pass looks like | Result |
|---|---|---|---|
| FLAG-4 | FR-3 | Coach **← Back** restores the left quiz item (not a fresh Q1) | ✅ |
| FLAG-1 | FR-5 | Coach history **N** updates after a second pin on the same skill | ✅ |
| FLAG-6 | FR-7 | Summary tile label is **Mastery change** (not bare Mastery) | ⚠️ label ✅; value revisit |
| Reveal polish | FR-8 | Enabled Reveal uses foreground text (`data-enabled="true"`) | ✅ |
| FLAG-5 | — | **Out of scope** (Epic C0) — expect Wrap-up without `?session=` still | 🚧 |

---

## §0 — Start localhost (latest code)

Quiz continuity is **frontend-local** (in-tab `ActiveQuizPointer` + `InMemoryEngineDb`).
Coach chat still needs the Python middleware on `:8000` for live replies; miss-count
and resume do **not** need Postgres.

```bash
# Terminal A — middleware (if not already up)
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
PORT_STRICT=1 PORT=8000 .venv/bin/python -m middleware

# Terminal B — frontend with auth bypass + your uncommitted continuity fixes
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
E2E_BYPASS_AUTH=1 pnpm dev
```

Wait until [http://localhost:3000/learn/quiz](http://localhost:3000/learn/quiz) returns 200.
Use a **desktop** viewport (≥1024px) so Feedback shows **Ask the coach**.

- [x] **0.1** `/learn/quiz` loads a question (`data-testid="quiz-context"`).
- [x] **0.2** DevTools → Network: no WorkOS redirect loop (bypass is on).

### Automated proof (optional, run first)

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
  pnpm test:e2e:continuity
```

Expected: FR-8, FLAG-4, FLAG-6 green; FLAG-1 green or skipped if the scheduler
never returns a second miss on the same skill within 12 steps.

**2026-07-10 run:** 4 passed (FR-8, FLAG-4, FLAG-1, FLAG-6).

---

## Legend

- ✅ PASS — matches continuity spec
- ❌ FAIL — contradicts FR
- 🚧 KNOWN-GAP — FLAG-5 / Epic C0
- ⚠️ SKIP — scheduler / surface made the step non-reproducible this run

---

## Step 1 — Reveal polish (FR-8)

**Do:** open [http://localhost:3000/learn/quiz](http://localhost:3000/learn/quiz). Do **not** select a choice yet. Inspect **Reveal answer**.

**Check (disabled):**
- [x] `data-enabled="false"` and the button is disabled.
- [x] Classes include `text-muted` (ghost look).

**Do:** click any choice letter.

**Check (enabled):**
- [x] `data-enabled="true"` and the button is enabled.
- [x] Classes include `data-[enabled=true]:text-fg` (or computed color is foreground, not the same muted as before).
- [x] Visually: Reveal is clearly darker / more readable than when disabled.

Covers: **FR-8**. ✅

---

## Step 2 — FLAG-4: leave an item, Ask coach, Back resumes it

**Do:**
1. On Quiz, answer Q1 → **Next question →** so you land on a later item (call it “leave-off”).
2. Note the passage / stem text (or copy `quiz-context` inner text).
3. Optionally note the progress label (“Question N of …”).
4. Answer the leave-off item → click **Ask the coach**.
5. Confirm URL is `/learn/coach` and **Current item** shows the pin.
6. Click **← Back**.

**Check:**
- [x] URL is `/learn/quiz` again.
- [x] The **same** passage/stem as the leave-off item is visible (not a brand-new Q1).
- [x] Progress position is consistent with the leave-off item (not reset to Question 1, and **not** advanced to N+1).
- [x] You are in **Feedback / review** (rationale + **Next question →** visible) — Ask-the-coach leaves from Feedback, so Back restores that review, not a fresh answering slate. Tap **Next** yourself when ready.

Covers: **FR-3**. ✅

---

## Step 3 — FLAG-1: miss count refreshes on a second same-skill pin

**Do:** continue from Step 2 (same tab — resume keeps the session).

1. If you are still on the leave-off Feedback, click **Next question →**.
2. Walk **Next** until you see another item whose skill matches the first miss
   (look for `data-skill` on the quiz chrome, or the skill id in the coach pin label `Q… · <skill>`).
3. Intentionally miss it (pick a wrong choice if you can tell; otherwise any choice — you need a miss for history).
4. Click **Ask the coach** again.

**Check:**
- [x] `data-testid="coach-history"` is visible.
- [x] The **N** in “Sees your history: N misses on …” is **higher** than after the first pin
      (e.g. `1 misses` → `2 misses`), not stuck on the old number.

**If** you never get a second item on the same skill within ~12 questions: mark ⚠️ SKIP
and rely on the Playwright FLAG-1 test / L1 effect-deps change.

Covers: **FR-5**. ✅ (also green in e2e)

---

## Step 4 — FLAG-6: Summary says “Mastery change”

**Do:** from Quiz Feedback, click **Finish & see summary** (or finish any short session).

**Check:**
- [x] URL is `/learn/summary?session=…`.
- [x] The middle stat tile (`data-testid="summary-delta"`) label reads **Mastery change**
      (uppercase in the UI: `MASTERY CHANGE`).
- [ ] Value is a signed percent (e.g. `+8%`) **or** `—` if the start snapshot was missing —
      never a fabricated absolute mastery % labeled only “Mastery”.

Covers: **FR-7**.

> **Open note (2026-07-10 manual walk):** label ✅ “Mastery change”, but the
> **value is not trusted yet** — session score **5/10** showed something like
> absolute **72%** mastery rather than an honest signed session delta (`+N%` /
> `—`). Revisit: confirm tile is delta-vs-start snapshot (FR-G1 / ADR-0011 §4),
> not current absolute mastery mislabeled. Do **not** sign off FLAG-6 value until re-checked.
> E2e asserts the **label** only (`MASTERY CHANGE +0%` observed).

---

## Step 5 — FLAG-5 known gap (do not expect a pass)

**Do:** start a quiz, Ask the coach once, click **Wrap up session →**.

**Check (document only):**
- [x] 🚧 URL is `/learn/summary` **without** `?session=` (or shows “No session to summarize.”).
      *(2026-07-10: confirmed — “no session to summarize” after Wrap up from coach.)*
- [x] This is **Epic C0**, not this sprint — do not file as a continuity regression.

> **Related finding (was out of scope; fixed 2026-07-10):** Home **Review my misses (N)**
> now links to `/learn/quiz?mode=review` and opens a session bounded to the unique miss
> pool (engine FR-A6). Re-check: badge **N** = unique *outstanding* misses (latest attempt
> per item still wrong; a later correct clears it) = progress **of N** (not lifetime miss
> history; not of 30). At the last miss, **Keep practising** is hidden — only **See summary**
> (no empty-pool error).
>
> **Also fixed 2026-07-10:** Bucket / `?focus=` drill now pins to that skill (FR-A5). After
> missing on skill A, drilling skill B serves only B — Home misses include wrongs from both.

---

## Step 6 — Finish clears resume (smoke)

**Do:** after Step 4’s Finish, navigate back to `/learn/quiz` (nav or URL).

**Check:**
- [x] A **fresh** session starts (new item / Question 1), not the finished session’s last item.
      *(2026-07-10: confirmed.)*
- [x] (Finish called `clearActiveQuiz` — FR-2.)

---

## Sign-off

- [x] Automated: `pnpm test:e2e:continuity` green (2026-07-10 — 4 passed).
- [x] Steps 1–3 ✅; Step 4 ⚠️ (label ✅, value revisit); Step 5 🚧; Step 6 ✅.
  - Step 4 / FLAG-6: **revisit** — value honesty (absolute vs signed delta) not signed off; label ✅; e2e asserts label.
  - Step 5 / FLAG-5: 🚧 confirmed (Wrap up → no session) — Epic C0.
  - Step 6: ✅ Finish clears resume.
  - Follow-ons fixed during walk: outstanding miss pool, review `?mode=review`, drill FR-A5 pin, hide Keep practising when review complete.
- [x] No ❌ screenshots required (failures were fixed in-walk).

**Reviewer:** Rajnish Khatri · **Date:** 2026-07-10 · **Continuity fixes validated** (with FLAG-6 value open note).
