# Manual validation walkthrough — PT2 exam (asset-served, server-graded)

> Human sit-through checklist for `feat/exam-official-forms` at **http://localhost:3000/learn/exam**.
> Complements the automated V-E/M/R/S reports. Focus areas: **images actually serve** (the CV4 fix
> we just landed), **keys never reach the client** (ADR-0041/0042), and the four-section flow.
> Tick each box; note anything that looks off next to it.

## 0. Pre-flight (30 sec)

- [ ] Dev server started with `EXAM_ASSET_DIR=…/docs/preact9secure/json` on **:3000** (WorkOS redirect).
- [ ] Signed in via WorkOS; `/learn/exam` renders (not a 500 / not an auth loop).
- [ ] Open **DevTools → Network** now and leave it recording — several checks below read it.

## 1. Exam home (`/learn/exam`) — FR-P2-19

- [ ] **Both forms are listed**: "Test 01 — English" *and* the new PT2 (Enhanced ACT) form.
      *(If PT2 is missing → `_generated/` didn't load or `EXAM_ASSET_DIR` is wrong.)*
- [ ] PT2 shows **four sections** — English, Math, Reading, Science — each with a status
      (`not started` initially).
- [ ] Starting a section shows official **directions + time** before a **Begin** (clock starts on Begin).

## 2. English section — text-first path (should be clean text, 0 images)

- [ ] Questions render as **text** (stems + A–D choices); underlined portions show for NO-CHANGE items.
- [ ] **No images** appear (English is `fidelity: ok`). No "content unavailable" placeholders.
- [ ] Countdown counts down from the section time; a **5-minute warning** appears once (FR-15).
- [ ] Navigate freely (next/prev/navigator); change an answer; **flag** a question → the navigator marks it.
- [ ] Submitting with blanks warns with the unanswered count (FR-18).

## 3. Math section — THE image fix (CV4-1/2) · 34 of 45 items are image-necessary

- [ ] Open a **math-notation** item (e.g. **Q2, Q3, Q17**). The **official question image renders**
      (a crisp PNG of the printed question) — **not** the garbled text `√ _ 112 + √ _ 63 …`, and
      **not** a "content unavailable" box. *This is exactly what CV4 fixed.*
      - Q17 should read √112 + √63 + √175 = ? with choices like 12√7. (Answer C — but don't grade yet.)
- [ ] The **A–D choice buttons are still clickable text** beneath the image; select one.
- [ ] Open a **plain (`ok`) Math item** (e.g. **Q1, Q5, Q11, Q12**) — these render as **text**, no image.
- [ ] **Network check:** the image request is `GET /api/engine/asset/act-practice-test-2/questions%2Fmath-qNN.png`
      → **200**, `content-type: image/png`. *(The `%2F` = the encoded slashy key from CV4-2.
      A 404 here means the fix regressed.)*

## 4. Science section — passages + figures (FR-P2-12/13)

- [ ] A **passage block** renders above the questions (intro/text), shared across its item group.
- [ ] Figure-based items (e.g. Passage I "According to **Table 2** …", Q1) show the **figure/page image**,
      not just prose — otherwise the question is unanswerable.
- [ ] The ~4 math-notation Science items render their image too.
- [ ] Force a failure once if you can (e.g. DevTools block the asset URL) → you should see a visible
      **"content unavailable"** placeholder, never a broken-image icon (FR-P2-13).

## 5. Reading section — passages, text only

- [ ] Reading **passages render as text** (the 4 passages), questions reference them; **no images**.
- [ ] Paired-passage set (if present) reads coherently.

## 6. Server-side grading + key safety (ADR-0041/0042 — the security point) — FR-P2-5/6/9

- [ ] **Before submit**, in DevTools → Network, open the response for **`getExamFormForClient`**
      (the form the client fetched). **Search it for `answer_letter`, `why_correct`, `per_choice_rationale`
      → there must be NONE.** *(Keys are server-only; this is the whole point.)*
- [ ] Submit a section → a **score appears** (computed server-side). Try tampering: it should ignore any
      client-supplied score.
- [ ] **Direct-key probe (optional):** `curl -i http://localhost:3000/api/engine/db/getExamFormKeys`
      (or hit it in the browser) → **404** (server-only method, not client-dispatchable).

## 7. Review screen — post-grade reveal (FR-P2-9/18)

- [ ] After a section is finished, the **review** shows each question with your answer, the **correct
      answer** (now revealed — post-grade only), dwell/visits, and flags.
- [ ] **Unscored (field-test) items** carry an "unscored" badge and are **excluded** from the raw/scale score.

## 8. Scoring & composite (FR-P2-17)

- [ ] Section results show raw over **scored** items + a **scale score** (PT2 has conversion tables).
- [ ] After finishing English + Math + Reading, the run shows a **composite = mean(E, M, R)**;
      **Science is reported separately** (Enhanced ACT rule).

## 9. Resume / durability (FR-P2 inherits phase-1 FR-14/1)

- [ ] Mid-section, **reload the page** → the countdown resumes from the server clock and your answers/flags
      are restored (only the last un-flushed dwell may be lost).
- [ ] Let a section's clock hit **0** (use a short section or the `?dur=` override if enabled) →
      it **auto-submits** as `expired`; reopening it shows review, not a re-answer screen.

## 10. Test-01 untouched (regression) — ADR-0041 exemption

- [ ] The old **"Test 01 — English"** still works exactly as before (client-bundled, client-graded).
      It must not have changed.

---

### Known — not a bug in what you're validating
- The **CI red on PR #189** (3 tests) is a *test-tiering* gap (real-PT2 tests can't run in CI without the
  ©ACT artifact) + two new adapters needing catalogue registration — **not** a defect in the running app.
  Fixing it is a separate ~3-edit pass.
- A **404 on a specific PNG** but not others usually means that one item's key or the on-disk PNG is
  missing — note the item number; it's a data/converter issue, not the serve path.

### If something's wrong, capture
Item number + section + screenshot + the failing Network row (URL + status). That's enough to route it
straight to a fix task.
